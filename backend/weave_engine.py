"""UrbanTrace's multivariate integration, run on urbanweave.

This replaces ``MultivariateIntegrationPipeline`` behind ``/api/integrate_multivariate`` while
keeping the request and response shapes. Operator names map onto urbanweave through the tables in
``urbanweave.compat.urbantrace`` (``ALLOCATION``, ``GRID_AGGREGATION``, ``ZONING_MAPPING``,
``ZONING_AGGREGATION``), so the rules for each operator live in urbanweave, not here.

``compat.urbantrace.run`` integrates one variable on a grid built over that variable's own extent.
A multivariate request needs one grid over the union of all sources' extents (as the legacy
pipeline built it), so this module composes the same steps with ``uw.match`` and ``uw.aggregate``
on a shared grid.

Differences from the legacy pipeline, each with a name:

- every difference in ``urbanweave.compat.urbantrace.CHANGES`` (``boundary_once``,
  ``utm_measurement``, ``missing_not_zero``, ``h3_index_lookup``, ``overlap_basis``);
- ``own_zoning_mapping``: each variable is zoned with its own zoning mapping operator. The legacy
  pipeline applied the first zoned variable's mapping to every variable;
- ``grid_covers_sources``: the grid's extent is the sources' bounding box padded by one cell
  circumradius, so every source's cell is part of the grid. The legacy grid kept only cells whose
  centers fall inside the bounding box, which silently dropped features near its edges (urbanweave
  reports them as ``outside_support``). Cells that receive nothing are not sent, so the padding adds
  no empty cells to the response;
- ``own_cells_only``: a variable is zoned from the cells it has values in. The legacy pipeline
  zoned every variable over all cells with data from any variable, with zeros filled in, so a
  weighted mean or majority counted cells the variable never reached as zeros.

Invalid polygons (self-intersections, bad rings) in sources and zones are repaired with
``shapely.make_valid`` before matching, keeping their polygonal parts, and each repair is listed in
the reports (``repaired_geometries``). urbanweave itself excludes invalid sources and refuses
invalid zones; repairing them is data preparation, which is UrbanTrace's part. The legacy pipeline
used them unrepaired.

Kept on purpose for the wire format, until results are sent in columns (redesign phase 4): density
per m², legacy weighting basis, cells and zones without a value sent as 0, values as floats.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

import h3
import shapely
from shapely.geometry import MultiPolygon, Polygon

import urbanweave as uw
from urbanweave.compat import urbantrace as legacy
from urbanweave.registry import problems as registry_problems

import scope

CHANGES = legacy.CHANGES + ("grid_covers_sources", "own_zoning_mapping", "own_cells_only")

#: Allowed allocation operators per geometry type, generated from urbanweave's registry.
GEOMETRY_CONSTRAINTS = legacy.geometry_constraints()

_WGS84 = "EPSG:4326"
_DEFAULT_BANDWIDTH_M = 1000.0


class Track:
    """One variable of a multivariate request."""

    def __init__(self, source_gdf, target_column, output_name, allocation, grid_aggregation,
                 zoning_mapping=None, zoning_aggregation=None, time_window=None, params=None):
        if allocation not in legacy.ALLOCATION:
            raise uw.InputError(f"Unknown allocation operator: {allocation}")
        if grid_aggregation not in legacy.GRID_AGGREGATION:
            raise uw.InputError(f"Unknown grid aggregation operator: {grid_aggregation}")
        if zoning_mapping is not None and zoning_mapping not in legacy.ZONING_MAPPING:
            raise uw.InputError(f"Unknown zoning mapping operator: {zoning_mapping}")
        if zoning_aggregation is not None and zoning_aggregation not in legacy.ZONING_AGGREGATION:
            raise uw.InputError(f"Unknown zoning aggregation operator: {zoning_aggregation}")
        if target_column not in source_gdf.columns:
            raise uw.InputError(f"Column {target_column!r} is not in the dataset for {output_name!r}.")
        self.time_report = None
        if time_window and time_window.get("column"):
            try:
                source_gdf, self.time_report = scope.filter_by_time(
                    source_gdf, time_window["column"], time_window.get("start"), time_window.get("end"))
            except scope.ScopeError as e:
                raise uw.InputError(f"{e} ({output_name})")
            if len(source_gdf) == 0:
                raise uw.InputError(f"No rows of {output_name!r} fall in the time window "
                                    f"{time_window.get('start') or '…'} to {time_window.get('end') or '…'}.")
        self.source, self.repairs = _prepare(source_gdf, "source_id", f"Source dataset for {output_name!r}")
        self.area_report = None
        # Method parameters the user set (e.g. a Gaussian bandwidth), checked against the registry.
        method = legacy.ALLOCATION[allocation][0]
        accepted = uw.registry()["matching"][method].get("params", {})
        unknown = sorted(set(params or {}) - set(accepted))
        if unknown:
            raise uw.InputError(f"{allocation} ({method}) has no parameter {', '.join(unknown)}; "
                                f"it accepts {', '.join(accepted) or 'none'}.")
        self.params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        self.column = target_column
        self.name = output_name
        self.allocation = allocation
        self.grid_aggregation = grid_aggregation
        self.zoning_mapping = zoning_mapping
        self.zoning_aggregation = zoning_aggregation

    @property
    def zoned(self) -> bool:
        return bool(self.zoning_mapping and self.zoning_aggregation)


def _polygonal(geom):
    """The polygonal parts of a repaired geometry (make_valid can add stray lines or points)."""
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    parts = [p for p in shapely.get_parts(geom) if isinstance(p, (Polygon, MultiPolygon))]
    return shapely.union_all(parts) if parts else None


def _repair(gdf: gpd.GeoDataFrame, id_column: str):
    """Repair invalid polygons; return the frame and a record of what was repaired."""
    geoms = gdf.geometry
    polygonal = geoms.geom_type.isin(["Polygon", "MultiPolygon"]).to_numpy()
    invalid = polygonal & geoms.notna().to_numpy() & ~geoms.is_valid.to_numpy()
    if not invalid.any():
        return gdf, None
    out = gdf.copy()
    fixed = [_polygonal(g) for g in shapely.make_valid(geoms[invalid].to_numpy())]
    out.loc[invalid, out.geometry.name] = gpd.GeoSeries(fixed, index=out.index[invalid], crs=out.crs)
    ids = out.loc[invalid, id_column].astype(str).tolist()
    return out, {"count": int(invalid.sum()), "sample": ids[:20], "method": "shapely.make_valid, polygonal parts"}


def _prepare(gdf: gpd.GeoDataFrame, id_column: str, label: str):
    """WGS84, an ID column, and repaired polygons; returns the frame and the repair record."""
    if gdf.crs is None:
        raise uw.InputError(f"{label} has no CRS defined. Please set a valid CRS before integration.")
    out = gdf if gdf.crs.equals(_WGS84) else gdf.to_crs(_WGS84)
    if id_column not in out.columns:
        out = out.copy()
        out[id_column] = out.index.astype(str)
    return _repair(out, id_column)


def _reduction(name: str, alias: str, legacy_basis: bool):
    basis = {"basis": "allocation_fraction"} if legacy_basis else {}
    if name == "sum":
        return uw.sum("x", as_=alias)
    if name == "mean":
        return uw.mean("x", as_=alias)
    if name == "weighted_mean":
        return uw.weighted_mean("x", as_=alias, **basis)
    if name == "density":
        return uw.density("x", as_=alias)
    if name == "majority":
        return uw.majority("x", as_=alias, **basis)
    if name == "max":
        return uw.max("x", as_=alias)
    if name == "min":
        return uw.min("x", as_=alias)
    raise uw.UnsupportedError(f"No urbanweave reduction for {name!r}.")


def _wire_values(series: pd.Series) -> pd.Series:
    """Numbers as floats (JSON-safe, as the legacy pipeline sent them); other values unchanged."""
    if is_numeric_dtype(series) and not is_bool_dtype(series):
        return series.astype("float64")
    return series


def _report(frame) -> dict | None:
    report = uw.report_of(frame)
    return None if report is None else json.loads(report.to_json())


def _grid_track(track: Track, cells: gpd.GeoDataFrame):
    """Source → shared grid for one variable: (cell values, match, report)."""
    method, params, _ = legacy.ALLOCATION[track.allocation]
    params = dict(params)
    if method == "gaussian":
        params["bandwidth"] = _DEFAULT_BANDWIDTH_M
    params.update(track.params)
    if method == "contain" and "MultiPoint" in set(track.source.geometry.geom_type):
        raise uw.UnsupportedError(
            f"BinaryContainment does not accept MultiPoint sources ({track.name}): the legacy operator gave "
            "every part's cell the whole value. Use BinaryCentroidContainment or NearestAssignment.")
    m = uw.match(track.source, cells, method, **params)
    values = pd.DataFrame({"source_id": track.source["source_id"].to_numpy(),
                           "x": track.source[track.column].to_numpy()})
    reduction, _ = legacy.GRID_AGGREGATION[track.grid_aggregation]
    basis = "allocation_fraction" in m.quantities
    grid = uw.aggregate(m, values, [_reduction(reduction, track.name, basis)])
    report = _report(grid)
    if reduction == "density":
        grid[track.name] = grid[track.name] / 1e6  # per km² -> per m², UrbanTrace's wire unit
    grid = grid.rename(columns={"target_id": "cell_id"})
    grid = grid[grid[track.name].notna()][["cell_id", "geometry", track.name]].reset_index(drop=True)
    return grid, m, report


def _zone_track(track: Track, grid: gpd.GeoDataFrame, zones: gpd.GeoDataFrame, resolution: int):
    """Shared grid → zones for one variable, from the cells it has values in: (zone values, report)."""
    cell_values = gpd.GeoDataFrame(grid.rename(columns={track.name: "x"}), geometry="geometry", crs=_WGS84)
    cell_values.attrs["urbanweave_support"] = {"kind": "h3", "resolution": int(resolution), "id_column": "cell_id"}
    method, params, _ = legacy.ZONING_MAPPING[track.zoning_mapping]
    params = dict(params)
    if track.zoning_mapping == "CentroidZoning" and set(zones.geometry.geom_type) <= {"Point", "MultiPoint"}:
        method, params = "sample", {}
    m = uw.match(cell_values, zones, method, source_id="cell_id", target_id="zone_id", **params)
    reduction = legacy.ZONING_AGGREGATION[track.zoning_aggregation]
    if track.zoning_aggregation == "SumZoning" and method == "polygon_to_lines":
        # Legacy SumZoning on line zones weighs each cell by the share of the zone's length in it.
        out = pd.DataFrame({"zone_id": zones["zone_id"].to_numpy(),
                            track.name: legacy.target_normalized_sum(m, cell_values["x"])})
        return out, None
    out = uw.aggregate(m, cell_values, [_reduction(reduction, track.name, "allocation_fraction" in m.quantities)],
                       targets=zones[["zone_id", "geometry"]])
    report = _report(out)
    if reduction == "density":
        out[track.name] = out[track.name] / 1e6
    return pd.DataFrame(out[["zone_id", track.name]]), report


def _padded_extent(bounds: np.ndarray, resolution: int) -> tuple:
    """The union of the sources' bounds, padded by one cell circumradius (an H3 hexagon's circumradius
    equals its edge length; 1.5x the average edge covers the variation in cell size)."""
    minx, miny = bounds[:, 0].min(), bounds[:, 1].min()
    maxx, maxy = bounds[:, 2].max(), bounds[:, 3].max()
    pad_m = 1.5 * h3.average_hexagon_edge_length(int(resolution), unit="m")
    dlat = pad_m / 111_320.0
    dlon = pad_m / (111_320.0 * max(np.cos(np.radians(max(abs(miny), abs(maxy)))), 1e-6))
    return (minx - dlon, max(miny - dlat, -90.0), maxx + dlon, min(maxy + dlat, 90.0))


def run(tracks: list[Track], resolution: int, zones_gdf: gpd.GeoDataFrame | None = None,
        output_mode: str = "grid", study_area=None) -> dict:
    """Run a multivariate integration; the result has ``grid`` and/or ``zones`` frames, as the
    legacy pipeline returned them, and ``reports`` with urbanweave's report of every step.

    With a *study_area* (a shapely geometry in EPSG:4326), sources are clipped to it, the grid
    covers it (padded by one cell, as for a bounding box), and only zones that touch it are kept."""
    if not tracks:
        raise uw.InputError("At least one variable track is required")

    pad_m = 1.5 * h3.average_hexagon_edge_length(int(resolution), unit="m")
    if study_area is not None:
        for track in tracks:
            track.source, track.area_report = scope.clip_to_area(track.source, study_area)
            if len(track.source) == 0:
                raise uw.InputError(f"No features of {track.name!r} fall in the study area.")
        cells = uw.targets.h3_cells(scope.padded_area(study_area, pad_m), int(resolution), cover="geometry")
    else:
        bounds = np.array([t.source.total_bounds for t in tracks])
        cells = uw.targets.h3_cells(_padded_extent(bounds, resolution), int(resolution))

    grids, reports, area = {}, {}, None
    for track in tracks:
        grid, m, report = _grid_track(track, cells)
        grids[track.name] = grid
        reports[track.name] = {"allocation": report, "repaired_geometries": track.repairs,
                               "time_window": track.time_report, "study_area": track.area_report}
        if area is None:
            size, _ = m.target_sizes()  # km², in the local UTM zone
            area = pd.DataFrame({"cell_id": cells["target_id"].to_numpy(), "area": size * 1e6})

    merged = None
    for name, grid in grids.items():
        part = grid[["cell_id", name]]
        merged = part if merged is None else merged.merge(part, on="cell_id", how="outer")
    shell = cells[["target_id", "geometry"]].rename(columns={"target_id": "cell_id"}).merge(area, on="cell_id")
    unified = shell.merge(merged, on="cell_id", how="inner")
    for name in grids:
        unified[name] = _wire_values(unified[name]).fillna(0)
    unified = gpd.GeoDataFrame(unified, geometry="geometry", crs=_WGS84)

    result: dict = {"reports": reports, "changes": list(CHANGES)}
    if output_mode in ("grid", "both"):
        result["grid"] = unified

    if output_mode in ("zones", "both") and zones_gdf is not None:
        zoned = [t for t in tracks if t.zoned]
        if not zoned:
            raise uw.InputError("No tracks have zoning configuration for zone output")
        zones, zone_repairs = _prepare(zones_gdf, "zone_id", "Zones dataset")
        if study_area is not None:
            zones = zones[scope.zones_in_area(zones, study_area)]
            if len(zones) == 0:
                raise uw.InputError("No zones touch the study area.")
        result["zone_repairs"] = zone_repairs
        unified_zones = zones[["zone_id", "geometry"]].copy()
        for track in zoned:
            values, report = _zone_track(track, grids[track.name], zones, resolution)
            reports[track.name]["zoning"] = report
            unified_zones = unified_zones.merge(values, on="zone_id", how="left")
            unified_zones[track.name] = _wire_values(unified_zones[track.name]).fillna(0)
        result["zones"] = gpd.GeoDataFrame(unified_zones, geometry="geometry", crs=_WGS84)

    return result


# --- the registry, for interfaces and the copilot (redesign phase 3) -----------------------------

#: Copilot classifications → urbanweave value kinds (an ordinal index is treated as categorical).
VALUE_KIND = {"extensive": "extensive", "intensive": "intensive", "ordinal index": "categorical",
              "ordinal": "categorical", "categorical": "categorical"}


def zoning_method(zoning_mapping: str, zone_geometry: str | None) -> str:
    """The urbanweave method a legacy zoning mapping runs, given the zones' geometry type."""
    method = legacy.ZONING_MAPPING[zoning_mapping][0]
    if zoning_mapping == "CentroidZoning" and (zone_geometry or "") in ("Point", "MultiPoint"):
        return "sample"
    return method


def zoning_problems(zoning_mapping: str | None, zoning_aggregation: str | None, zone_geometry: str | None,
                    classification: str | None = None) -> list[str]:
    """Why a zoning mapping / aggregation does not fit H3 cells → these zones (empty when it fits),
    checked against urbanweave's registry."""
    reasons = []
    geom = zone_geometry or "Polygon"
    method = None
    if zoning_mapping is not None:
        if zoning_mapping not in legacy.ZONING_MAPPING:
            return [f"Unknown zoning mapping {zoning_mapping!r}."]
        method = zoning_method(zoning_mapping, geom)
        reasons += registry_problems("Polygon", geom, method, source_support="h3", target_support="vector")
    if zoning_aggregation is not None:
        if zoning_aggregation not in legacy.ZONING_AGGREGATION:
            return reasons + [f"Unknown zoning aggregation {zoning_aggregation!r}."]
        reduction = legacy.ZONING_AGGREGATION[zoning_aggregation]
        kind = VALUE_KIND.get((classification or "").strip().lower())
        spec = uw.registry()["aggregation"][reduction]
        if kind and kind not in spec["value_kinds"]:
            reasons.append(f"{zoning_aggregation} ({reduction}) does not suit {kind} values.")
        if method is not None:
            provided = uw.registry()["matching"][method]["match_quantities"]
            for q in spec.get("requires", []):
                if q != "density_denominator" and q not in provided:
                    reasons.append(f"{zoning_aggregation} needs {q}, which {zoning_mapping} ({method}) does not provide.")
    return reasons


def describe_operators() -> dict:
    """Each legacy operator name with the urbanweave method or reduction it runs and the registry's
    description of it: for operator pickers and the copilot."""
    reg = uw.registry()
    out = {"allocation": {}, "grid_aggregation": {}, "zoning_mapping": {}, "zoning_aggregation": {}}
    for name, (method, params, note) in legacy.ALLOCATION.items():
        spec = reg["matching"][method]
        out["allocation"][name] = {"method": method, "fixed_params": params, "note": note,
                                   "summary": spec.get("summary"), "assignment": spec.get("assignment"),
                                   "params": spec.get("params", {})}
    for name, (reduction, _) in legacy.GRID_AGGREGATION.items():
        spec = reg["aggregation"][reduction]
        out["grid_aggregation"][name] = {"reduction": reduction, "summary": spec.get("summary"),
                                         "value_kinds": spec.get("value_kinds")}
    for name, (method, params, note) in legacy.ZONING_MAPPING.items():
        spec = reg["matching"][method]
        out["zoning_mapping"][name] = {"method": method, "note": note, "summary": spec.get("summary"),
                                       "assignment": spec.get("assignment")}
    for name, reduction in legacy.ZONING_AGGREGATION.items():
        spec = reg["aggregation"][reduction]
        out["zoning_aggregation"][name] = {"reduction": reduction, "summary": spec.get("summary"),
                                           "value_kinds": spec.get("value_kinds")}
    return out
