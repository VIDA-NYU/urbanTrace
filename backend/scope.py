"""Study area, coverage and time (docs/REDESIGN.md, phase 2).

- **Study area**: a spec stored on the collection, either a zones dataset with an optional filter
  (``{"kind": "zones", "dataset": "<stem>", "column": "boroname", "values": ["Manhattan"]}``) or a
  box (``{"kind": "bbox", "bbox": [minx, miny, maxx, maxy]}``). :func:`study_area_geometry`
  resolves it to one geometry in EPSG:4326. Integrations clip their sources to it and build the
  grid over it; exports clip to it.
- **Coverage**: where each dataset has data, from the atlas-profiler density grid in its profile
  (cells of about 300 m with counts); for datasets whose profile has none, a grid computed once from
  the data and cached (:func:`dataset_cells`); the envelope only when the data cannot be read.
- **Time**: each dataset's time range from its profile; :func:`checks` warns when the selected
  datasets' periods do not overlap or a dataset does not reach the study area.
"""
from __future__ import annotations

from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box, mapping

import catalog

_WGS84 = "EPSG:4326"


class ScopeError(ValueError):
    pass


# --- study area ----------------------------------------------------------------------------------

def study_area_geometry(data_dir, spec: dict | None):
    """The study area as one shapely geometry in EPSG:4326, or None when no area is set."""
    if not spec:
        return None
    kind = spec.get("kind")
    if kind == "bbox":
        try:
            minx, miny, maxx, maxy = (float(v) for v in spec["bbox"])
        except (KeyError, TypeError, ValueError):
            raise ScopeError("A bbox study area needs bbox = [minx, miny, maxx, maxy] in EPSG:4326.")
        if not (minx < maxx and miny < maxy):
            raise ScopeError("The study area's bbox is empty.")
        return box(minx, miny, maxx, maxy)
    if kind == "zones":
        stem = catalog.stem_of(spec.get("dataset"))
        if not catalog.valid_stem(stem):
            raise ScopeError("A zones study area needs a dataset.")
        try:
            gdf = catalog.load(data_dir, stem)
        except FileNotFoundError as e:
            raise ScopeError(str(e))
        gdf = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
        column, values = spec.get("column"), spec.get("values")
        if column:
            if column not in gdf.columns:
                raise ScopeError(f"Column {column!r} is not in {stem}.")
            if values:
                gdf = gdf[gdf[column].astype(str).isin([str(v) for v in values])]
        geoms = gdf.geometry[gdf.geometry.notna()]
        geoms = geoms.make_valid() if hasattr(geoms, "make_valid") else geoms.buffer(0)
        geoms = geoms[geoms.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"])]
        if geoms.empty:
            raise ScopeError("The study area selection is empty.")
        return shapely.union_all(geoms.to_numpy())
    raise ScopeError(f"Unknown study area kind {kind!r}.")


def study_area_options(data_dir, stem: str, max_values: int = 300) -> dict:
    """Columns of a zones dataset that can select part of it, with their values."""
    gdf = catalog.load(data_dir, stem)
    columns = []
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        s = gdf[col].dropna().astype(str)
        n = s.nunique()
        if 1 < n <= max_values:
            columns.append({"name": col, "values": sorted(s.unique().tolist())})
    return {"dataset": stem, "features": len(gdf), "columns": columns}


def study_area_summary(geom) -> dict | None:
    if geom is None:
        return None
    s = gpd.GeoSeries([geom], crs=_WGS84)
    area_km2 = float(s.to_crs(s.estimate_utm_crs()).area.iloc[0] / 1e6)
    return {"bbox": list(geom.bounds), "area_km2": round(area_km2, 2), "geometry": mapping(geom)}


# A zone belongs to the study area when this share of its area lies inside it. Testing only that it
# intersects without touching keeps neighbours whose shared boundary differs by rounding: Brooklyn,
# built from NTA zones, picked up 8 Queens and Manhattan zones overlapping it by about 0 m².
ZONE_MIN_SHARE_INSIDE = 0.01


def zones_in_area(gdf: gpd.GeoDataFrame, area, min_share: float = ZONE_MIN_SHARE_INSIDE) -> pd.Series:
    """Boolean mask of the zones with at least *min_share* of their area inside *area* (EPSG:4326)."""
    src = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
    candidates = src.intersects(area) & ~src.touches(area)
    mask = pd.Series(False, index=gdf.index)
    if not candidates.any():
        return mask
    near = src[candidates]
    try:
        local = near.estimate_utm_crs()
    except Exception:
        local = "EPSG:3857"
    zones_m = near.to_crs(local).geometry
    area_m = gpd.GeoSeries([area], crs=_WGS84).to_crs(local).iloc[0]
    zone_area = zones_m.area
    share = zones_m.intersection(area_m).area / zone_area.where(zone_area > 0)
    # Zones without area (lines, points used as targets) fall back to the intersection test.
    mask.loc[near.index] = share.fillna(1.0).to_numpy() >= min_share
    return mask


def clip_to_area(gdf: gpd.GeoDataFrame, geom) -> tuple[gpd.GeoDataFrame, dict]:
    """Keep the features that intersect the study area, clipped to it; report how many were dropped."""
    if geom is None:
        return gdf, None
    src = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
    invalid = src.geometry.notna() & ~src.geometry.is_valid
    if invalid.any():
        # Clipping needs valid geometry; repair it (the integration engine repairs it the same way).
        src = src.copy()
        src.loc[invalid, src.geometry.name] = src.loc[invalid].geometry.make_valid()
    inside = src.intersects(geom)
    kept = src[inside]
    polygonal = kept.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString"])
    if polygonal.any():
        # Clip lines and polygons so only their part inside the area is integrated.
        clipped = kept.copy()
        cut = kept.loc[polygonal].geometry.intersection(geom)
        families = kept.loc[polygonal].geom_type.str.replace("Multi", "")
        cut = [_same_family(g, fam) for g, fam in zip(cut, families)]
        clipped.loc[polygonal, clipped.geometry.name] = gpd.GeoSeries(cut, index=clipped.index[polygonal.to_numpy()], crs=_WGS84)
        clipped = clipped[clipped.geometry.notna() & ~clipped.geometry.is_empty]
        kept = clipped
    report = {"features": int(len(src)), "kept": int(len(kept)), "outside_study_area": int((~inside).sum())}
    if int(inside.sum()) > len(kept):
        report["only_touching_study_area"] = int(inside.sum()) - len(kept)
    if invalid.any():
        report["repaired_before_clipping"] = int(invalid.sum())
    return kept, report


def _same_family(geom, family: str):
    """The parts of a clipped geometry of the source's family (Polygon or LineString); None if none."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type.replace("Multi", "") == family:
        return geom
    parts = [p for p in shapely.get_parts(geom) if p.geom_type.replace("Multi", "") == family]
    return shapely.union_all(parts) if parts else None


def padded_area(geom, pad_m: float):
    """The area grown by *pad_m* metres (measured in its UTM zone), in EPSG:4326."""
    s = gpd.GeoSeries([geom], crs=_WGS84)
    utm = s.estimate_utm_crs()
    return s.to_crs(utm).buffer(pad_m).to_crs(_WGS84).iloc[0]


# --- coverage ------------------------------------------------------------------------------------

def coverage_cells(prof: dict | None) -> tuple[list[tuple[float, float, float, float, int]], list[float] | None]:
    """The profile's density-grid cells as (minx, miny, maxx, maxy, count), and the data's bbox.

    The bbox comes from the grid when there is one: some profiles store the envelope with latitude
    and longitude swapped, while their grid is right."""
    if not prof:
        return [], None
    cells, envelope = [], None
    for cov in prof.get("spatial_coverage") or []:
        grid = cov.get("grid")
        env = _envelope(cov)
        if env:
            envelope = env if envelope is None else [min(envelope[0], env[0]), min(envelope[1], env[1]),
                                                     max(envelope[2], env[2]), max(envelope[3], env[3])]
        if grid and grid.get("cells"):
            x0, y0 = grid["bounds"][0], grid["bounds"][1]
            dx, dy = grid["cell_degrees"]
            for col, row, count in grid["cells"]:      # row 0 is the southern edge
                cells.append((x0 + col * dx, y0 + row * dy, x0 + (col + 1) * dx, y0 + (row + 1) * dy, int(count)))
    return cells, (_cells_bounds(cells) if cells else envelope)


def _cells_bounds(cells) -> list[float]:
    return [min(c[0] for c in cells), min(c[1] for c in cells), max(c[2] for c in cells), max(c[3] for c in cells)]


# Datasets whose profile has no density grid (atlas-profiler gives none for most polygon and line
# datasets) get one computed from the data: features per 0.005° cell. It is computed once per file
# and cached by path, size and modification time in data/.extent_cache.json.
_DATA_GRID_STEP = 0.005
_MAX_DATA_GRID_CELLS = 250_000


def dataset_cells(data_dir, stem: str) -> tuple[list[tuple[float, float, float, float, int]], list[float] | None, str | None]:
    """Coverage cells and bbox of a catalog dataset, and where they came from ("profile" or "data")."""
    import cleaning
    # A corrected dataset's profile describes the data before correction (a swap, a wrong CRS), so
    # its coverage comes from the corrected data instead.
    import geocode
    cells, bounds = (([], None) if cleaning.has_recipe(data_dir, stem) or geocode.has_result(data_dir, stem)
                     else coverage_cells(catalog.profile(data_dir, stem)))
    if cells:
        return cells, bounds, "profile"
    try:
        cells = _data_cells(data_dir, stem)
    except Exception:                                    # unreadable data: fall back to the envelope
        cells = None
    if cells:
        return cells, _cells_bounds(cells), "data"
    return [], bounds, ("profile" if bounds else None)


def _data_cells(data_dir, stem: str):
    from pathlib import Path
    import json
    path = catalog.dataset_path(data_dir, stem)
    if path is None:
        return None
    st = path.stat()
    cache_path = Path(data_dir) / ".extent_cache.json"
    key = str(path.resolve())
    import cleaning
    import geocode
    recipe = cleaning.recipe_path(data_dir, stem)
    if recipe.exists():                                   # the corrected data: one entry per recipe version
        key += f"#recipe:{recipe.stat().st_mtime}"
    located = geocode.result_path(data_dir, stem)
    if located.exists():                                  # rows located from addresses
        key += f"#geocoded:{located.stat().st_mtime}"
    with catalog._hash_lock:
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    hit = cache.get(key)
    if hit and hit["size"] == st.st_size and hit["mtime"] == st.st_mtime:
        return [tuple(c) for c in hit["cells"]]
    gdf = catalog.load(data_dir, stem, columns=[])
    if gdf.crs is not None and not gdf.crs.equals(_WGS84):
        gdf = gdf.to_crs(_WGS84)
    geoms = gdf.geometry.to_numpy()
    geoms = geoms[~(shapely.is_missing(geoms) | shapely.is_empty(geoms))]
    cells = []
    if len(geoms):
        geoms = np.where(shapely.is_valid(geoms), geoms, shapely.make_valid(geoms))
        step = _DATA_GRID_STEP
        x1, y1, x2, y2 = shapely.total_bounds(geoms)
        i0, j0 = int(np.floor(x1 / step)), int(np.floor(y1 / step))
        ni, nj = int(np.floor(x2 / step)) - i0 + 1, int(np.floor(y2 / step)) - j0 + 1
        if ni * nj <= _MAX_DATA_GRID_CELLS:
            ii, jj = np.meshgrid(np.arange(ni) + i0, np.arange(nj) + j0, indexing="ij")
            ii, jj = ii.ravel(), jj.ravel()
            boxes = shapely.box(ii * step, jj * step, (ii + 1) * step, (jj + 1) * step)
            hits = shapely.STRtree(geoms).query(boxes, predicate="intersects")
            counts = np.bincount(hits[0], minlength=len(boxes))
            for k in np.nonzero(counts)[0]:
                cells.append((round(float(ii[k] * step), 6), round(float(jj[k] * step), 6),
                              round(float((ii[k] + 1) * step), 6), round(float((jj[k] + 1) * step), 6), int(counts[k])))
    with catalog._hash_lock:
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        cache[key] = {"size": st.st_size, "mtime": st.st_mtime, "cells": cells}
        cache_path.write_text(json.dumps(cache))
    return cells


def _envelope(cov: dict):
    for r in cov.get("ranges") or []:
        rng = r.get("range") or {}
        if rng.get("type") == "envelope":
            (x1, y1), (x2, y2) = rng["coordinates"]
            return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]
    return None


def coverage(data_dir, stems: list[str], area=None) -> dict:
    """Coverage of several datasets on one grid: a GeoJSON of cells with how many datasets reach each,
    and per dataset its bbox, cell count and share of the study area it reaches."""
    per = {}
    cell_sets = {}
    for stem in stems:
        cells, bounds, source = dataset_cells(data_dir, stem)
        per[stem] = {"bbox": bounds, "cells": len(cells), "has_grid": bool(cells), "grid_from": source if cells else None}
        cell_sets[stem] = cells
    # Put every dataset on a common lattice: snap cell centres to 0.005° (about 500 m).
    step = 0.005
    owners: dict[tuple[int, int], set] = {}
    for stem, cells in cell_sets.items():
        if not cells and per[stem]["bbox"]:
            # No density grid: the envelope stands in, marked as approximate.
            x1, y1, x2, y2 = per[stem]["bbox"]
            xs = np.arange(np.floor(x1 / step), np.ceil(x2 / step))
            ys = np.arange(np.floor(y1 / step), np.ceil(y2 / step))
            if len(xs) * len(ys) <= 40_000:
                for i in xs:
                    for j in ys:
                        owners.setdefault((int(i), int(j)), set()).add(stem)
            per[stem]["approximate"] = True
            continue
        for x1, y1, x2, y2, _ in cells:
            key = (int(np.floor((x1 + x2) / 2 / step)), int(np.floor((y1 + y2) / 2 / step)))
            owners.setdefault(key, set()).add(stem)
    features = []
    for (i, j), who in owners.items():
        geom = box(i * step, j * step, (i + 1) * step, (j + 1) * step)
        if area is not None and not geom.intersects(area):
            continue
        features.append({"type": "Feature", "geometry": mapping(geom),
                         "properties": {"n": len(who), "datasets": sorted(who)}})
    if area is not None:
        # The study area's own cells on the lattice, so a share does not depend on the other datasets.
        x1, y1, x2, y2 = area.bounds
        ii, jj = np.meshgrid(np.arange(np.floor(x1 / step), np.ceil(x2 / step)),
                             np.arange(np.floor(y1 / step), np.ceil(y2 / step)), indexing="ij")
        area_boxes = shapely.box(ii.ravel() * step, jj.ravel() * step, (ii.ravel() + 1) * step, (jj.ravel() + 1) * step)
        total = int(shapely.intersects(area_boxes, area).sum())
        for stem in stems:
            mine = sum(1 for f in features if stem in f["properties"]["datasets"])
            per[stem]["share_of_area"] = round(min(1.0, mine / total), 3) if total else 0.0
            per[stem]["measure"] = "cells"
            if _is_points(data_dir, stem) and cell_sets[stem]:
                per[stem].update(_point_spread(cell_sets[stem], area))
    return {"type": "FeatureCollection", "features": features, "datasets": per, "cell_degrees": step}


def _is_points(data_dir, stem: str) -> bool:
    return str((catalog.profile(data_dir, stem) or {}).get("geometricType") or "").endswith("Point")


def _point_spread(cells, area) -> dict:
    """For points, a share of cells says little (60 libraries spread over a borough fill a few percent
    of its cells). Instead: the points inside the area (from the density grid, so approximate at the
    edge), their share of the dataset, and how far they spread: the part of the area inside the convex
    hull of the cells that hold them."""
    boxes = shapely.box(*np.array([c[:4] for c in cells]).T)
    counts = np.array([c[4] for c in cells])
    inside = shapely.intersects(boxes, area) & ~shapely.touches(boxes, area)
    n_inside, n_total = int(counts[inside].sum()), int(counts.sum())
    spread = 0.0
    if inside.any():
        hull = shapely.convex_hull(shapely.union_all(boxes[inside]))
        spread = float(shapely.area(shapely.intersection(hull, area)) / shapely.area(area))
    return {"measure": "spread", "share_of_area": round(min(1.0, spread), 3),
            "points_inside": n_inside, "share_of_rows": round(n_inside / n_total, 3) if n_total else 0.0}


def catalog_in_area(data_dir, area) -> dict:
    """For every catalog dataset, how much of it is in the study area, for the search sidebar:
    points as spread and count inside (see _point_spread), other geometries as the share of the area's
    ~500 m cells they reach. Datasets with no grid or extent are left out (unknown)."""
    step = 0.005
    x1, y1, x2, y2 = area.bounds
    ii, jj = np.meshgrid(np.arange(np.floor(x1 / step), np.ceil(x2 / step)),
                         np.arange(np.floor(y1 / step), np.ceil(y2 / step)), indexing="ij")
    boxes = shapely.box(ii.ravel() * step, jj.ravel() * step, (ii.ravel() + 1) * step, (jj.ravel() + 1) * step)
    inside = shapely.intersects(boxes, area)
    area_keys = {(int(i), int(j)) for i, j, k in zip(ii.ravel(), jj.ravel(), inside) if k}
    out = {}
    for stem in catalog.list_stems(data_dir):
        cells, _, _ = dataset_cells(data_dir, stem)
        if not cells:
            continue
        if _is_points(data_dir, stem):
            out[stem] = _point_spread(cells, area)
        else:
            keys = {(int(np.floor((c[0] + c[2]) / 2 / step)), int(np.floor((c[1] + c[3]) / 2 / step))) for c in cells}
            share = len(keys & area_keys) / len(area_keys) if area_keys else 0.0
            out[stem] = {"measure": "cells", "share_of_area": round(min(1.0, share), 3)}
    import rasters
    for stem in rasters.list_stems(data_dir):              # a raster covers its box (no data inside is rare)
        b = rasters.sidecar(data_dir, stem).get("bounds_wgs84")
        if b:
            share = shapely.area(shapely.intersection(area, shapely.box(*b))) / (shapely.area(area) or 1)
            out[stem] = {"measure": "cells", "share_of_area": round(min(1.0, float(share)), 3)}
    return out


# --- time ----------------------------------------------------------------------------------------

def time_range(prof: dict | None) -> dict | None:
    """The dataset's time range from its profile: {"start", "end", "columns", "resolution"}."""
    if not prof:
        return None
    lo, hi, cols, res = None, None, [], None
    for cov in prof.get("temporal_coverage") or []:
        cols += cov.get("column_names") or []
        res = res or cov.get("temporal_resolution")
        for r in cov.get("ranges") or []:
            rng = r.get("range") or {}
            if "gte" in rng:
                lo = rng["gte"] if lo is None else min(lo, rng["gte"])
            if "lte" in rng:
                hi = rng["lte"] if hi is None else max(hi, rng["lte"])
    if lo is None and hi is None:
        return None
    iso = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat() if t is not None else None
    return {"start": iso(lo), "end": iso(hi), "columns": cols, "resolution": res}


def catalog_index(data_dir) -> list[dict]:
    """One row per dataset for search filters: bbox, time range, geometry type, rows, and whether
    atlas-clean corrections are saved for it, or rows located from addresses."""
    import cleaning
    import geocode
    out = []
    for stem in catalog.list_stems(data_dir):
        prof = catalog.profile(data_dir, stem)
        _, bounds, _ = dataset_cells(data_dir, stem)
        out.append({"id": stem, "bbox": bounds, "time": time_range(prof),
                    "geometry": (prof or {}).get("geometricType"), "rows": (prof or {}).get("nb_rows"),
                    "corrected": cleaning.has_recipe(data_dir, stem),
                    "located": geocode.has_result(data_dir, stem)})
    import rasters
    for stem in rasters.list_stems(data_dir):                # rasters: their box, for the study-area filter
        side = rasters.sidecar(data_dir, stem)
        out.append({"id": stem, "bbox": side.get("bounds_wgs84"), "time": None, "geometry": "Raster",
                    "rows": (side.get("stats") or {}).get("valid_cells"), "corrected": False, "located": False})
    return out


def filter_by_time(gdf: gpd.GeoDataFrame, column: str, start: str | None, end: str | None):
    """Rows whose *column* falls in [start, end] (ISO dates, end inclusive of the whole day)."""
    if column not in gdf.columns:
        raise ScopeError(f"Time column {column!r} is not in the dataset.")
    t = pd.to_datetime(gdf[column], errors="coerce", utc=True)
    keep = t.notna()
    if start:
        keep &= t >= pd.Timestamp(start, tz="UTC")
    if end:
        keep &= t < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    report = {"column": column, "start": start, "end": end, "rows": int(len(gdf)), "kept": int(keep.sum()),
              "unparsed": int(t.isna().sum())}
    return gdf[keep.to_numpy()], report


# --- checks --------------------------------------------------------------------------------------

def checks(data_dir, doc: dict) -> list[dict]:
    """Warnings about a collection: periods that do not overlap, datasets that miss the study area."""
    warnings = []
    stems = [catalog.stem_of(d.get("id")) for d in doc.get("datasets", []) if d.get("id")]
    ranges = {}
    windows = {d.get("id"): d.get("time_window") for d in doc.get("datasets", []) if d.get("time_window")}
    for stem in stems:
        tr = time_range(catalog.profile(data_dir, stem))
        w = windows.get(stem)
        if w and (w.get("start") or w.get("end")):
            tr = {"start": w.get("start") or (tr or {}).get("start"), "end": w.get("end") or (tr or {}).get("end")}
        if tr and tr.get("start") and tr.get("end"):
            ranges[stem] = tr
    if len(ranges) >= 2:
        latest_start = max(r["start"] for r in ranges.values())
        earliest_end = min(r["end"] for r in ranges.values())
        if latest_start > earliest_end:
            a = max(ranges, key=lambda s: ranges[s]["start"])
            b = min(ranges, key=lambda s: ranges[s]["end"])
            warnings.append({"kind": "time_no_overlap",
                             "message": f"The periods do not overlap: {b} ends {ranges[b]['end']}, "
                                        f"{a} starts {ranges[a]['start']}.",
                             "datasets": sorted(ranges), "ranges": ranges})
    try:
        area = study_area_geometry(data_dir, doc.get("study_area"))
    except ScopeError as e:
        warnings.append({"kind": "study_area_invalid", "message": str(e)})
        area = None
    if area is not None:
        cov = coverage(data_dir, stems, area)
        for stem, info in cov["datasets"].items():
            share = info.get("share_of_area")
            if share is None:
                continue
            if share == 0 or (info.get("measure") == "spread" and info.get("points_inside") == 0):
                warnings.append({"kind": "coverage_none", "message": f"{stem} has no data in the study area.",
                                 "datasets": [stem], "share": 0.0})
            elif share < 0.5:
                if info.get("measure") == "spread":
                    message = (f"{stem}'s {info['points_inside']} points in the study area spread over only "
                               f"{share:.0%} of it.")
                else:
                    message = (f"{stem} has data in {share:.0%} of the study area"
                               + (" (estimated from its extent)" if info.get("approximate") else "") + ".")
                warnings.append({"kind": "coverage_partial", "message": message, "datasets": [stem], "share": share})
    return warnings
