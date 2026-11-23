"""Plans (docs/REDESIGN.md, phase 4): the canvas as an urbanweave plan.

The canvas sends a plan in urbanweave's schema (version 1) with UrbanTrace's own details under
``"urbantrace"`` keys, which urbanweave ignores:

    {"version": 1,
     "sources": {"s1": {"kind": "vector", "columns": {"count": {"kind": "extensive"}},
                        "urbantrace": {"dataset": "NYC_libraries", "time_window": {...}}}},
     "targets": {"t1": {"kind": "h3", "resolution": 9},
                 "t2": {"kind": "zones", "urbantrace": {"dataset": "NTA_Neighborhood_Tabulation_Areas"}}},
     "steps": [{"id": "step1", "source": "s1", "match": {"method": "contain", "target": "t1"},
                "aggregate": [{"method": "count", "as": "libraries", "fill_empty": 0}]}]}

Before urbanweave runs it, this module binds each source from the catalog (time window applied,
invalid polygons repaired, clipped to the study area), writes each zones target as a repaired
GeoPackage in the plan cache and points the target at it, and gives H3 targets an extent: the study
area or the sources' bounds, padded by one cell so features near the edge are kept.

Results come back in columns: target IDs and one array per output column, with value kinds; zones
also come with their geometry for the map. Derived variables (a Calculate node) are evaluated on
the joined outputs of steps that share a target.

Plans use urbanweave's own conventions: density
per km², means weighted by overlap, missing stays missing.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

import urbanweave as uw
from urbanweave.plan import Plan
from urbanweave.reducers import Reduction

import catalog
import scope
from shapely.geometry import box
from geometry import repair as _repair

_WGS84 = "EPSG:4326"
_OUTPUT_KIND = {"count": "extensive", "weighted_count": "extensive", "sum": None, "density": "intensive",
                "mean": "intensive", "weighted_mean": "intensive", "median": "intensive",
                "weighted_median": "intensive", "majority": "categorical", "shares": "intensive",
                "ratio_of_sums": "intensive"}


class PlanInputError(ValueError):
    """A problem with the plan as UrbanTrace received it (unknown dataset, bad expression...)."""


# --- value kinds ---------------------------------------------------------------------------------

_INTENSIVE_WORDS = re.compile(r"(rate|ratio|pct|percent|share|avg|average|mean|median|density|index|per_|_per|"
                              r"score|prop|proportion|income|rent|price|temperature|temp|age)", re.I)
_CATEGORICAL_TYPES = {"http://schema.org/Enumeration", "http://schema.org/Text", "http://schema.org/Boolean",
                      "http://schema.org/identifier", "http://schema.org/AdministrativeArea"}


def suggest_value_kinds(data_dir, stem: str) -> dict:
    """A value kind for each column, from its profile and name, with the reason."""
    prof = catalog.profile(data_dir, stem) or {}
    out = {}
    for col in prof.get("columns", []):
        name = col.get("name") or ""
        stype = col.get("structural_type") or ""
        semantic = set(col.get("semantic_types") or [])
        numeric = stype in ("http://schema.org/Integer", "http://schema.org/Float")
        if not numeric or semantic & {"http://schema.org/identifier", "http://schema.org/latitude",
                                      "http://schema.org/longitude"}:
            kind, why = ("categorical", "not numeric" if not numeric else "an identifier or coordinate")
            if not numeric and not (semantic & _CATEGORICAL_TYPES):
                kind, why = None, "not a numeric or categorical column"
        elif _INTENSIVE_WORDS.search(name):
            kind, why = "intensive", "its name suggests a rate, average or density"
        elif stype == "http://schema.org/Float":
            kind, why = "intensive", "decimal values; check: a total stored as decimals is extensive"
        else:
            kind, why = "extensive", "whole numbers, likely counts or totals"
        if kind:
            out[name] = {"kind": kind, "reason": why}
    return out


# --- preparing a plan ----------------------------------------------------------------------------

def _cache_dir(cache_root) -> Path:
    p = Path(cache_root)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _bind_source(data_dir, name: str, spec: dict, area, columns_needed: set[str]):
    ut = spec.get("urbantrace") or {}
    stem = catalog.stem_of(ut.get("dataset"))
    if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
        raise PlanInputError(f"source {name!r}: dataset {ut.get('dataset')!r} is not in the catalog.")
    gdf = catalog.load(data_dir, stem)
    missing = sorted(c for c in columns_needed if c not in gdf.columns)
    if missing:
        raise PlanInputError(f"source {name!r}: {stem} has no column {', '.join(missing)}.")
    report = {"dataset": stem, "rows": int(len(gdf))}
    if gdf.attrs.get("urbantrace_cleaning"):
        report["cleaning"] = gdf.attrs["urbantrace_cleaning"]     # corrections replayed (cleaning.py)
    if gdf.attrs.get("urbantrace_geocoded"):
        report["geocoded"] = gdf.attrs["urbantrace_geocoded"]     # rows located from addresses (geocode.py)
    tw = ut.get("time_window") or {}
    if tw.get("column") and (tw.get("start") or tw.get("end")):
        try:
            gdf, report["time_window"] = scope.filter_by_time(gdf, tw["column"], tw.get("start"), tw.get("end"))
        except scope.ScopeError as e:
            raise PlanInputError(f"source {name!r}: {e}")
    gdf = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
    if "source_id" not in gdf.columns:
        gdf = gdf.assign(source_id=gdf.index.astype(str))
    gdf, repaired = _repair(gdf, "source_id")
    if repaired:
        report["repaired_geometries"] = repaired
    if area is not None:
        gdf, report["study_area"] = scope.clip_to_area(gdf, area)
    else:
        gdf, outside = _within_region(data_dir, gdf)
        if outside:
            report["outside_region"] = outside
    keep = ["source_id", *sorted(c for c in columns_needed if c in gdf.columns), gdf.geometry.name]
    gdf = gdf[list(dict.fromkeys(keep))].reset_index(drop=True)
    if len(gdf) == 0:
        raise PlanInputError(f"source {name!r}: no rows left after the time window and study area.")
    return gdf, report


def label_column(gdf) -> str | None:
    """A column that names each zone for display (e.g. NTA's ``ntaname``): text, unique, preferring
    a column called *name*; never a portal row id (Socrata's ``:id``) or a code-like column."""
    from pandas.api.types import is_object_dtype, is_string_dtype
    candidates = []
    for c in gdf.columns:
        if c in ("target_id", gdf.geometry.name) or str(c).startswith(":"):
            continue
        col = gdf[c]
        if not (is_string_dtype(col) or is_object_dtype(col)) or col.nunique(dropna=True) != len(gdf):
            continue
        values = col.dropna().astype(str)
        if values.str.fullmatch(r"[-+]?[0-9.eE]+").all():      # numbers stored as text (shape_area)
            continue
        name_like = "name" in str(c).lower()
        has_space = values.str.contains(" ").mean()           # names have spaces more often than codes
        candidates.append((not name_like, -has_space, -values.str.len().mean(), list(gdf.columns).index(c), c))
    if candidates:
        return min(candidates)[-1]
    # No text name: a unique whole-number code (community district 301, ZIP 11211), not a row id.
    from pandas.api.types import is_integer_dtype
    for c in gdf.columns:
        low = str(c).lower()
        if c in ("target_id", gdf.geometry.name) or low.startswith((":", "objectid", "fid", "shape")):
            continue
        col = gdf[c]
        as_int = col if is_integer_dtype(col) else pd.to_numeric(col, errors="coerce") if (is_string_dtype(col) or is_object_dtype(col)) else None
        if as_int is None or as_int.isna().any() or (as_int % 1 != 0).any() or as_int.nunique() != len(gdf):
            continue
        return c
    return None


def key_values(series: pd.Series) -> pd.Series:
    """Keys as text for joins: whole numbers without a decimal part (BBL 1000010001.0 ->
    "1000010001"), surrounding spaces removed, missing stays missing."""
    def one(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        text = str(v).strip()
        if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
            text = text[:-2]
        return text or None
    return series.map(one).astype(object)


def _within_region(data_dir, gdf):
    """Without a study area, the catalog's region bounds a step: features entirely outside it (a
    missing location coded as 0,0, a point geocoded to another state) are left out and reported,
    so a few strays do not stretch the extent around the globe. When nothing is inside, the data is
    left as it is: the coordinates are then probably in another CRS, and urbanweave says so."""
    import cleaning
    try:
        region = cleaning.catalog_region(data_dir)
    except Exception:
        return gdf, None
    inside = gdf.intersects(box(*region))
    n_out = int((~inside).sum())
    if n_out == 0 or not inside.any():
        return gdf, None
    sample = gdf.loc[~inside, "source_id"].astype(str).head(10).tolist() if "source_id" in gdf else []
    return gdf[inside.to_numpy()], {"region": [round(v, 4) for v in region], "rows": int(len(gdf)),
                                    "kept": int(inside.sum()), "outside": n_out, "sample": sample}


def _zones_file(data_dir, name: str, spec: dict, area, cache: Path):
    ut = spec.get("urbantrace") or {}
    stem = catalog.stem_of(ut.get("dataset"))
    if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
        raise PlanInputError(f"target {name!r}: dataset {ut.get('dataset')!r} is not in the catalog.")
    gdf = catalog.load(data_dir, stem)
    gdf = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    id_column = ut.get("id_column")
    if id_column:                                   # zones identified by a code, for joins on a key
        if id_column not in gdf.columns:
            raise PlanInputError(f"target {name!r}: {stem} has no column {id_column!r}.")
        keys = key_values(gdf[id_column])
        if keys.isna().any() or keys.duplicated().any():
            raise PlanInputError(f"target {name!r}: {id_column!r} does not identify each zone of {stem} "
                                 f"({int(keys.isna().sum())} missing, {int(keys.duplicated().sum())} repeated).")
        gdf["target_id"] = keys.to_numpy()
    else:
        gdf["target_id"] = gdf.index.astype(str)
    gdf, repaired = _repair(gdf, "target_id")
    if area is not None:
        gdf = gdf[scope.zones_in_area(gdf, area)]   # zones with (almost) nothing inside are out
        if len(gdf) == 0:
            raise PlanInputError(f"target {name!r}: no zones of {stem} touch the study area.")
    label = label_column(gdf)
    keep = ["target_id", *( [label] if label else []), gdf.geometry.name]
    gdf = gdf[keep].reset_index(drop=True)
    digest = hashlib.sha256(gdf.to_json().encode()).hexdigest()[:16]
    path = cache / "zones" / f"{stem}-{digest}.gpkg"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(path, driver="GPKG", layer="zones")
    return path, gdf, {"dataset": stem, "zones": int(len(gdf)), "repaired_geometries": repaired, "label": label}


def _columns_needed(spec: dict) -> dict[str, set[str]]:
    """The columns each source needs: reduction columns and where-columns of steps reading it."""
    need: dict[str, set[str]] = {n: set((d or {}).get("columns", {}) or {}) for n, d in (spec.get("sources") or {}).items()}
    for step in spec.get("steps") or []:
        src = step.get("source")
        if not isinstance(src, str) or src.startswith("@") or src not in need:
            continue
        body = step.get("reduce") or {}
        if body.get("by"):
            need[src].add(str(body["by"]))
        for r in body.get("aggregate") or []:               # a join on a key: sum or ratio_of_sums
            for k in ("column", "numerator", "denominator"):
                if r.get(k) is not None:
                    need[src].add(str(r[k]))
        for r in step.get("aggregate") or []:
            if r.get("column") is not None:
                need[src].add(str(r["column"]))
            conds = r.get("where")
            for c in (conds if isinstance(conds, list) else [conds] if conds else []):
                if isinstance(c, dict) and c.get("column"):
                    need[src].add(str(c["column"]))
    return need


OSM_KINDS = ("osm_streets", "osm_intersections")
_OSM_FRAMES: dict = {}


def _osm_target(data_dir, name: str, tspec: dict, area):
    """A Streets node's target: the study area's street network (osm.py), downloaded once and handed
    to urbanweave as a GraphML file. Returns the segments (or intersections) for the result map."""
    import osm
    kind = tspec["kind"]
    network = ((tspec.get("urbantrace") or {}).get("network_type")) or "drive"
    if area is None:
        raise PlanInputError(f"target {name!r}: street networks are downloaded for the study area; choose one first.")
    try:
        path = osm.graph_path(data_dir, area, network)
        if not path.exists():
            osm.download(data_dir, area, network)          # usually done beforehand from the Streets node
    except osm.OsmError as e:
        raise PlanInputError(f"target {name!r}: {e}")
    tspec["graphml"] = str(path)
    key = (str(path), path.stat().st_mtime, kind)
    if key not in _OSM_FRAMES:
        from urbanweave import streets as S
        frame = S.osm_streets(graphml=path) if kind == "osm_streets" else S.osm_intersections(graphml=path)
        keep = [c for c in ("target_id", "name", "highway", "length_m", "degree") if c in frame.columns]
        frame = frame[keep + [frame.geometry.name]].to_crs(_WGS84)
        frame["target_id"] = frame["target_id"].astype(str)
        if len(_OSM_FRAMES) > 4:
            _OSM_FRAMES.clear()
        _OSM_FRAMES[key] = frame
    frame = _OSM_FRAMES[key]
    meta = osm.info(data_dir, area, network)
    return frame, {"kind": kind, "network_type": network, "count": int(len(frame)),
                   "downloaded_at": meta.get("downloaded_at"), "attribution": osm.ATTRIBUTION}


def prepare(data_dir, plan_spec: dict, study_area_spec, cache_root):
    """Bind sources and resolve targets; return (uw.Plan, sources, info)."""
    if not isinstance(plan_spec, dict):
        raise PlanInputError("The plan must be a JSON object.")
    spec = json.loads(json.dumps(plan_spec))
    spec.setdefault("version", 1)
    try:
        area = scope.study_area_geometry(data_dir, study_area_spec)
    except scope.ScopeError as e:
        raise PlanInputError(str(e))
    cache = _cache_dir(cache_root)
    need = _columns_needed(spec)
    sources, info = {}, {"sources": {}, "targets": {}, "study_area": study_area_spec}
    for name, sspec in (spec.get("sources") or {}).items():
        sources[name], info["sources"][name] = _bind_source(data_dir, name, sspec, area, need.get(name, set()))
    # Joins on a key: keys compared as text, so 11211, "11211" and 11211.0 meet (zones' IDs, likewise)
    for step in spec.get("steps") or []:
        by, src = (step.get("reduce") or {}).get("by"), step.get("source")
        if by and isinstance(src, str) and src in sources and by in sources[src].columns:
            sources[src] = sources[src].assign(**{by: key_values(sources[src][by])})
    zones_frames = {}
    for name, tspec in (spec.get("targets") or {}).items():
        kind = tspec.get("kind")
        if kind == "zones" and (tspec.get("urbantrace") or {}).get("dataset"):
            path, frame, tinfo = _zones_file(data_dir, name, tspec, area, cache)
            tspec["path"] = str(path)
            zones_frames[name] = frame
            info["targets"][name] = {"kind": "zones", **tinfo}
        elif kind in OSM_KINDS:
            frame, tinfo = _osm_target(data_dir, name, tspec, area)
            zones_frames[name] = frame
            info["targets"][name] = tinfo
        elif kind == "h3":
            res = int(tspec.get("resolution", 9))
            pad_m = 1.5 * h3.average_hexagon_edge_length(res, unit="m")
            if area is not None:
                ext = scope.padded_area(area, pad_m).bounds
            elif sources:
                b = np.array([g.total_bounds for g in sources.values()])
                lat = max(abs(b[:, 1].min()), abs(b[:, 3].max()))
                dlat, dlon = pad_m / 111_320.0, pad_m / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
                ext = (b[:, 0].min() - dlon, b[:, 1].min() - dlat, b[:, 2].max() + dlon, b[:, 3].max() + dlat)
            else:
                raise PlanInputError(f"target {name!r}: an H3 grid needs a study area or a source to size it.")
            tspec["extent"] = [float(v) for v in ext]
            tspec["resolution"] = res
            info["targets"][name] = {"kind": "h3", "resolution": res}
    info["zones_frames"] = zones_frames
    return Plan(spec), sources, info


# --- validation ----------------------------------------------------------------------------------

_STEP_REF = re.compile(r"^step ([^:]+):\s*(.*)$")


def _profile_columns(data_dir, stem: str) -> set[str] | None:
    """Column names from the dataset's profile (v2, else v1), without reading the data."""
    prof = catalog.profile(data_dir, stem)
    if prof and prof.get("columns"):
        return {c.get("name") for c in prof["columns"]}
    v1 = Path(data_dir) / "metadata" / f"{stem}.json"
    if v1.exists():
        cols = json.loads(v1.read_text()).get("columns") or []
        return {c.get("name") for c in cols} or None
    return None


def validate(data_dir, plan_spec: dict, study_area_spec, cache_root) -> dict:
    """Problems with the plan, by step ID (``"_plan"`` for the rest), before anything runs. Cheap: it
    checks datasets and columns against the catalog's profiles and runs urbanweave's preflight,
    without reading any data."""
    by_step: dict[str, list[str]] = {}
    if not isinstance(plan_spec, dict):
        return {"ok": False, "problems": {"_plan": ["The plan must be a JSON object."]}}
    spec = json.loads(json.dumps(plan_spec))
    spec.setdefault("version", 1)

    def add(owner, msg):
        by_step.setdefault(owner, []).append(msg)

    need = _columns_needed(spec)
    for name, sspec in (spec.get("sources") or {}).items():
        stem = catalog.stem_of(((sspec or {}).get("urbantrace") or {}).get("dataset"))
        if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
            add(_owner(f"source '{name}'", spec), f"Dataset {stem or '?'} is not in the catalog.")
            continue
        known = _profile_columns(data_dir, stem)
        if known is not None:
            for col in sorted(need.get(name, set()) - known):
                for step in spec.get("steps") or []:
                    body = step.get("reduce") or {}
                    uses = step.get("source") == name and (any(
                        str(r.get("column")) == col or any(isinstance(c, dict) and c.get("column") == col
                                                           for c in (r.get("where") if isinstance(r.get("where"), list) else [r.get("where")]))
                        for r in step.get("aggregate") or []) or str(body.get("by")) == col or any(
                        col in (str(r.get(k)) for k in ("column", "numerator", "denominator")) for r in body.get("aggregate") or []))
                    if uses:
                        add(step.get("id", "_plan"), f"{stem} has no column {col}.")
    for name, tspec in (spec.get("targets") or {}).items():
        ut = (tspec or {}).get("urbantrace") or {}
        stem = catalog.stem_of(ut.get("dataset"))
        if (tspec or {}).get("kind") in OSM_KINDS and study_area_spec is None:
            add(_owner(f"target '{name}'", spec), "Street networks are downloaded for the study area; choose one first.")
        if (tspec or {}).get("kind") in OSM_KINDS and not tspec.get("graphml"):
            tspec["graphml"] = "pending.graphml"                   # resolved when the plan runs (prepare)
        if (tspec or {}).get("kind") == "zones" and stem and catalog.dataset_path(data_dir, stem) is None:
            add(_owner(f"target '{name}'", spec), f"Zones dataset {stem} is not in the catalog.")
        elif ut.get("id_column") and stem:
            known = _profile_columns(data_dir, stem)
            if known is not None and ut["id_column"] not in known:
                add(_owner(f"target '{name}'", spec), f"{stem} has no column {ut['id_column']}.")
    try:
        problems = Plan(spec)._problems(source_names=list(spec.get("sources") or {}))
    except uw.UrbanweaveError as e:
        problems = [str(e)]
    for msg in problems:
        m = _STEP_REF.match(msg)
        add(m.group(1) if m else "_plan", m.group(2) if m else msg)
    return {"ok": not by_step, "problems": by_step}


def _owner(msg: str, spec: dict) -> str:
    """The step a source/target error belongs to, so the interface can mark it."""
    m = re.match(r"^(source|target) '([^']+)'", msg)
    if m:
        kind, name = m.groups()
        for step in spec.get("steps") or []:
            body = step.get("match") or {}
            if (kind == "source" and step.get("source") == name) or (kind == "target" and body.get("target") == name):
                return step.get("id", "_plan")
    return "_plan"


# --- running -------------------------------------------------------------------------------------

def _plain_values(series: pd.Series) -> list:
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        arr = series.astype("float64").to_numpy()
        return [None if not np.isfinite(v) else (int(v) if float(v).is_integer() and abs(v) < 2**53 else float(v)) for v in arr]
    return [None if (v is None or (isinstance(v, float) and math.isnan(v))) else str(v) for v in series]


def _step_columns(frame, kinds: dict) -> tuple[list[str], dict]:
    """The output columns of a step's result and their value kinds. A ``shares`` reduction named
    ``share`` writes one column per category (``share_a``, ``share_b``, ...), fractions, so intensive."""
    shares = [a for a, k in kinds.items() if k == "shares"]
    cols, out = [], {a: k for a, k in kinds.items() if k != "shares"}
    for c in frame.columns:
        if c in ("target_id", "geometry"):
            continue
        if c in out:
            cols.append(c)
        elif any(c.startswith(f"{a}_") for a in shares):
            cols.append(c)
            out[c] = "intensive"
    return cols, out


def _kinds_of(step: dict, declared: dict) -> dict:
    out = {}
    for r in (step.get("aggregate") or (step.get("reduce") or {}).get("aggregate") or []):
        alias = Reduction.from_dict(dict(r)).alias
        if r.get("method") == "shares":
            out[alias] = "shares"                       # expanded per category by _step_columns
            continue
        kind = _OUTPUT_KIND.get(r.get("method"))
        if kind is None:
            kind = (declared.get(str(r.get("column"))) or {}).get("kind")
        out[alias] = kind
    return out


_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant, ast.Add, ast.Sub,
                  ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod, ast.FloorDiv)


def evaluate_expression(expression: str, frame: pd.DataFrame) -> pd.Series:
    """Arithmetic on columns (names, numbers, + - * / ** % //, parentheses); nothing else is allowed.
    A division by zero gives a missing value."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise PlanInputError(f"The expression is not valid: {e.msg}.")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise PlanInputError(f"The expression may only use column names, numbers and + - * / ** % ( ); "
                                 f"{type(node).__name__} is not allowed.")
        if isinstance(node, ast.Name) and node.id not in frame.columns:
            raise PlanInputError(f"The expression uses {node.id!r}, which is not an output of its inputs "
                                 f"({', '.join(map(str, frame.columns))}).")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise PlanInputError("Only numbers may appear as constants.")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            return pd.to_numeric(frame[n.id], errors="coerce").astype("float64")
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        a, b = ev(n.left), ev(n.right)
        with np.errstate(divide="ignore", invalid="ignore"):
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
            if isinstance(n.op, ast.Pow):
                return a ** b
            if isinstance(n.op, ast.Mod):
                return a % b
            return a // b

    out = ev(tree)
    if not isinstance(out, pd.Series):
        out = pd.Series(out, index=frame.index)
    return out.replace([np.inf, -np.inf], np.nan)


def _columns_payload(frame: pd.DataFrame, columns: list[str], kinds: dict, target_info: dict, zones_frame=None,
                     label=None) -> dict:
    ids = frame["target_id"].astype(str).tolist()
    payload = {"target": target_info, "target_ids": ids,
               "columns": {c: _plain_values(frame[c]) for c in columns},
               "kinds": {c: kinds.get(c) for c in columns}}
    if target_info.get("kind") in ("zones", *OSM_KINDS) and zones_frame is not None:
        z = zones_frame.set_index("target_id")
        geo = gpd.GeoDataFrame(z.loc[[i for i in ids if i in z.index]], geometry=z.geometry.name, crs=_WGS84).reset_index()
        if target_info.get("kind") in OSM_KINDS:                 # thousands of segments: about a metre is enough
            import shapely
            geo = geo.set_geometry(shapely.set_precision(geo.geometry.to_numpy(), 1e-5, mode="pointwise"))
            label = "name" if "name" in geo.columns else None
        props = pd.DataFrame({"zone_id": ids, **{c: payload["columns"][c] for c in columns}}).set_index("zone_id")
        if label and label in geo.columns:
            props["label"] = geo.set_index("target_id")[label].reindex(props.index).tolist()
        geo = geo[["target_id", geo.geometry.name]].rename(columns={"target_id": "zone_id"}).join(props, on="zone_id")
        payload["geojson"] = json.loads(geo.to_json(na="null"))
    return payload


def run(data_dir, plan_spec: dict, study_area_spec, cache_root, *, outputs=None, derived=None,
        record: bool = False, manifest_path=None) -> dict:
    """Run the plan; return the requested steps' results in columns, every step's report, and (with
    *record*) the manifest, written under the plan cache."""
    plan, sources, info = prepare(data_dir, plan_spec, study_area_spec, cache_root)
    cache = _cache_dir(cache_root) / "artifacts" if record else None
    try:
        result = plan.run(sources, cache=cache, manifest_path=manifest_path)
    except uw.UrbanweaveError as e:
        raise PlanInputError(str(e))
    steps = {s["id"]: s for s in plan.spec["steps"]}
    declared = {n: (d or {}).get("columns", {}) for n, d in (plan.spec.get("sources") or {}).items()}
    zones_frames = info.pop("zones_frames")
    labels = {n: t.get("label") for n, t in info["targets"].items() if t.get("kind") == "zones"}
    labels.update({n: "name" for n, t in info["targets"].items() if t.get("kind") == "osm_streets"})

    def target_of(step_id):
        step = steps[step_id]
        tgt = (step.get("match") or step.get("reduce") or {}).get("target")
        return tgt, info["targets"].get(tgt, {"kind": "other"})

    out = {"steps": {}, "reports": {sid: result.reports.get(sid) for sid in steps},
           "inputs": info["sources"], "targets": info["targets"], "engine": "urbanweave-plan",
           "plan": plan.spec, "manifest_path": str(result.manifest_path) if result.manifest_path else None}
    wanted = outputs or [plan.spec["steps"][-1]["id"]]
    for sid in wanted:
        if sid not in steps:
            raise PlanInputError(f"Unknown output step {sid!r}.")
        frame = result.outputs[sid]
        src = steps[sid].get("source")
        columns, kinds = _step_columns(frame, _kinds_of(steps[sid], declared.get(src, {}) if isinstance(src, str) else {}))
        tname, tinfo = target_of(sid)
        out["steps"][sid] = _columns_payload(frame, columns, kinds, tinfo, zones_frames.get(tname), labels.get(tname))
    for d in derived or []:
        inputs = d.get("inputs") or []
        if not inputs or any(i not in steps for i in inputs):
            raise PlanInputError(f"derived {d.get('id')!r}: its inputs must be steps of the plan.")
        targets = {target_of(i)[0] for i in inputs}
        if len(targets) != 1:
            raise PlanInputError(f"derived {d.get('id')!r}: its inputs must share one target, not {', '.join(map(str, targets))}.")
        joined, kinds = None, {}
        for i in inputs:
            frame = result.outputs[i]
            src = steps[i].get("source")
            cols, k = _step_columns(frame, _kinds_of(steps[i], declared.get(src, {}) if isinstance(src, str) else {}))
            clash = set(cols) & set(kinds)
            if clash:
                raise PlanInputError(f"derived {d.get('id')!r}: output names repeat across inputs: {', '.join(sorted(clash))}.")
            kinds.update(k)
            part = pd.DataFrame(frame[["target_id", *cols]])
            joined = part if joined is None else joined.merge(part, on="target_id", how="outer")
        columns = list(kinds)
        if d.get("expression"):
            alias = d.get("as") or "derived"
            if alias in joined.columns:
                raise PlanInputError(f"derived {d.get('id')!r}: {alias!r} is already an output name.")
            joined[alias] = evaluate_expression(d["expression"], joined)
            kinds[alias] = d.get("kind") or "intensive"
            columns.append(alias)
        tname, tinfo = target_of(inputs[0])
        out["steps"][d.get("id") or "derived"] = {
            **_columns_payload(joined, columns, kinds, tinfo, zones_frames.get(tname), labels.get(tname)),
            "derived": {"inputs": inputs, "expression": d.get("expression"), "as": d.get("as"), "kind": d.get("kind")},
        }
    out["reports"] = json.loads(json.dumps(out["reports"], default=str))
    return out
