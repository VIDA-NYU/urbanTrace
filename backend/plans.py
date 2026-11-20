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

Unlike the compatibility path (weave_engine.py), plans use urbanweave's own conventions: density
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
from weave_engine import _repair

_WGS84 = "EPSG:4326"
_OUTPUT_KIND = {"count": "extensive", "weighted_count": "extensive", "sum": None, "density": "intensive",
                "mean": "intensive", "weighted_mean": "intensive", "median": "intensive",
                "weighted_median": "intensive", "majority": "categorical", "shares": "intensive"}


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
    keep = ["source_id", *sorted(c for c in columns_needed if c in gdf.columns), gdf.geometry.name]
    gdf = gdf[list(dict.fromkeys(keep))].reset_index(drop=True)
    if len(gdf) == 0:
        raise PlanInputError(f"source {name!r}: no rows left after the time window and study area.")
    return gdf, report


def _zones_file(data_dir, name: str, spec: dict, area, cache: Path):
    ut = spec.get("urbantrace") or {}
    stem = catalog.stem_of(ut.get("dataset"))
    if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
        raise PlanInputError(f"target {name!r}: dataset {ut.get('dataset')!r} is not in the catalog.")
    gdf = catalog.load(data_dir, stem)
    gdf = gdf.to_crs(_WGS84) if gdf.crs is not None and not gdf.crs.equals(_WGS84) else gdf
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf["target_id"] = gdf.index.astype(str)
    gdf, repaired = _repair(gdf, "target_id")
    if area is not None:
        gdf = gdf[gdf.intersects(area) & ~gdf.touches(area)]   # zones that only share an edge are out
        if len(gdf) == 0:
            raise PlanInputError(f"target {name!r}: no zones of {stem} touch the study area.")
    # A label for display: the first text column with unique values (e.g. a neighborhood name).
    label = next((c for c in gdf.columns if c not in ("target_id", gdf.geometry.name)
                  and gdf[c].dtype == object and gdf[c].nunique() == len(gdf)), None)
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
        for r in step.get("aggregate") or []:
            if r.get("column") is not None:
                need[src].add(str(r["column"]))
            conds = r.get("where")
            for c in (conds if isinstance(conds, list) else [conds] if conds else []):
                if isinstance(c, dict) and c.get("column"):
                    need[src].add(str(c["column"]))
    return need


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
    zones_frames = {}
    for name, tspec in (spec.get("targets") or {}).items():
        kind = tspec.get("kind")
        if kind == "zones" and (tspec.get("urbantrace") or {}).get("dataset"):
            path, frame, tinfo = _zones_file(data_dir, name, tspec, area, cache)
            tspec["path"] = str(path)
            zones_frames[name] = frame
            info["targets"][name] = {"kind": "zones", **tinfo}
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
                    uses = step.get("source") == name and any(
                        str(r.get("column")) == col or any(isinstance(c, dict) and c.get("column") == col
                                                           for c in (r.get("where") if isinstance(r.get("where"), list) else [r.get("where")]))
                        for r in step.get("aggregate") or [])
                    if uses:
                        add(step.get("id", "_plan"), f"{stem} has no column {col}.")
    for name, tspec in (spec.get("targets") or {}).items():
        stem = catalog.stem_of(((tspec or {}).get("urbantrace") or {}).get("dataset"))
        if (tspec or {}).get("kind") == "zones" and stem and catalog.dataset_path(data_dir, stem) is None:
            add(_owner(f"target '{name}'", spec), f"Zones dataset {stem} is not in the catalog.")
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


def _kinds_of(step: dict, declared: dict) -> dict:
    out = {}
    for r in step.get("aggregate") or []:
        alias = Reduction.from_dict(dict(r)).alias
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
    if target_info.get("kind") == "zones" and zones_frame is not None:
        z = zones_frame.set_index("target_id")
        geo = gpd.GeoDataFrame(z.loc[[i for i in ids if i in z.index]], geometry=z.geometry.name, crs=_WGS84).reset_index()
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

    def target_of(step_id):
        step = steps[step_id]
        tgt = (step.get("match") or {}).get("target")
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
        kinds = _kinds_of(steps[sid], declared.get(src, {}) if isinstance(src, str) else {})
        columns = [c for c in frame.columns if c not in ("target_id", "geometry") and c in kinds]
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
            k = _kinds_of(steps[i], declared.get(src, {}) if isinstance(src, str) else {})
            cols = [c for c in frame.columns if c in k]
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
