"""Analysis (docs/REDESIGN.md, phase 5): sensitivity sweeps, validation against outcomes, dasymetric
disaggregation, the priority index, and the report.

- **Sweep.** One step's output column, recomputed under alternatives: H3 resolutions or other zone
  systems as an intermediate support (source → alternative → the step's target), or other matching
  methods. Every variant lands on the step's own target, so each unit gets one value per variant, a
  rank per variant, and stability measures: the range of its ranks and the share of variants in which
  it is among the top units. Pairwise Spearman correlations say how much the variants agree overall.
- **Validation.** A result ranked against known outcomes (points such as program sites), as in the
  paper's Table 3: for each quantile, the share of outcomes inside the units above it (coverage),
  the share of units above it (baseline) and their ratio (lift).
- **Dasymetric.** Zone totals spread over finer targets in proportion to point priors
  (``urbanweave.dasymetric``), on catalog data.
- **Priority index.** The Result Map's composite: each variable min-max normalized over the units,
  inverted where its direction is inverted, weighted and summed.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, mapping

import urbanweave as uw

import catalog
import plans
import scope
from geometry import repair as _repair

_EXTENSIVE = {"count", "weighted_count", "sum"}


class AnalysisError(ValueError):
    pass


def _step(spec: dict, step_id: str) -> dict:
    for s in spec.get("steps") or []:
        if s.get("id") == step_id:
            return s
    raise AnalysisError(f"Unknown step {step_id!r}.")


def _ancestors(spec: dict, step_id: str) -> list[dict]:
    """The steps *step_id* reads (through @references), in plan order, excluding itself."""
    by_id = {s["id"]: s for s in spec.get("steps") or []}
    need, stack = set(), [step_id]
    while stack:
        src = by_id[stack.pop()].get("source")
        if isinstance(src, str) and src.startswith("@") and src[1:] in by_id and src[1:] not in need:
            need.add(src[1:])
            stack.append(src[1:])
    return [s for s in spec["steps"] if s["id"] in need]


def _reduction_for(step: dict, column: str) -> dict:
    for r in step.get("aggregate") or []:
        if uw.Reduction.from_dict(dict(r)).alias == column:
            return dict(r)
    raise AnalysisError(f"Step {step['id']!r} has no output column {column!r}.")


def _column_kind(step: dict, column: str, spec: dict) -> str:
    r = _reduction_for(step, column)
    if r["method"] in ("count", "weighted_count"):
        return "extensive"
    if r["method"] == "sum":
        src = step.get("source")
        declared = ((spec.get("sources") or {}).get(src) or {}).get("columns", {}) if isinstance(src, str) else {}
        return (declared.get(str(r.get("column"))) or {}).get("kind") or "extensive"
    return "intensive" if r["method"] != "majority" else "categorical"


# --- sweep ---------------------------------------------------------------------------------------

def _variant_plan(spec: dict, step: dict, column: str, kind: str, variant: dict, i: int) -> tuple[dict, str]:
    """A plan computing *column* under *variant*, ending on the step's own target."""
    out = json.loads(json.dumps(spec))
    out["steps"] = _ancestors(spec, step["id"])
    red = _reduction_for(step, column)
    target = step["match"]["target"]
    method = variant.get("method") or step["match"]["method"]
    via = variant.get("via")
    params = {} if variant.get("method") else {k: v for k, v in step["match"].items() if k not in ("method", "target")}
    if not via:
        final = f"__v{i}"
        out["steps"].append({"id": final, "source": step["source"], "match": {"method": method, "target": target, **params},
                             "aggregate": [red]})
        return out, final
    via_name = f"__via{i}"
    if via.get("kind") == "h3":
        out["targets"][via_name] = {"kind": "h3", "resolution": int(via["resolution"])}
    elif via.get("kind") == "zones":
        out["targets"][via_name] = {"kind": "zones", "urbantrace": {"dataset": via["dataset"]}}
    else:
        raise AnalysisError(f"Unknown alternative support {via!r}.")
    first, final = f"__v{i}a", f"__v{i}"
    out["steps"].append({"id": first, "source": step["source"], "match": {"method": method, "target": via_name, **params},
                         "aggregate": [{**red, "as": column}]})
    back = ({"method": "sum", "column": column, "as": column} if kind == "extensive"
            else {"method": "weighted_mean", "column": column, "as": column} if kind == "intensive"
            else {"method": "majority", "column": column, "as": column})
    out["steps"].append({"id": final, "source": f"@{first}", "match": {"method": "area_overlap", "target": target},
                         "aggregate": [back]})
    return out, final


def _label(variant: dict) -> str:
    if variant.get("label"):
        return variant["label"]
    parts = []
    via = variant.get("via")
    if via and via.get("kind") == "h3":
        parts.append(f"via H3 r{via['resolution']}")
    elif via:
        parts.append(f"via {via.get('dataset')}")
    if variant.get("method"):
        parts.append(variant["method"])
    return ", ".join(parts) or "as built"


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    both = pd.concat([a, b], axis=1).dropna()
    if len(both) < 3:
        return None
    r = both.rank().corr().iloc[0, 1]
    return None if pd.isna(r) else round(float(r), 3)


def sweep(data_dir, plan_spec: dict, study_area, cache_root, *, step_id: str, column: str, variants: list[dict],
          top_share: float = 0.2) -> dict:
    """Recompute one step's column under each variant; ranks and stability per unit of its target."""
    spec = json.loads(json.dumps(plan_spec))
    step = _step(spec, step_id)
    kind = _column_kind(step, column, spec)
    if kind == "categorical":
        raise AnalysisError("A sweep ranks numeric values; this column is categorical.")
    variants = [{"label": "as built"}] + [v for v in variants or [] if v.get("via") or v.get("method")]
    values, summary, base_payload = {}, [], None
    for i, variant in enumerate(variants):
        label = _label(variant)
        try:
            if i == 0:
                vplan, final = spec, step_id
            else:
                vplan, final = _variant_plan(spec, step, column, kind, variant, i)
            out = plans.run(data_dir, vplan, study_area, cache_root, outputs=[final])
        except (plans.PlanInputError, uw.UrbanweaveError, AnalysisError) as e:
            summary.append({"label": label, "ok": False, "error": str(e)})
            continue
        payload = out["steps"][final]
        if base_payload is None:
            base_payload = payload
        values[label] = pd.Series(payload["columns"][column], index=payload["target_ids"], dtype="float64")
        summary.append({"label": label, "ok": True, "units": int(values[label].notna().sum())})
    if base_payload is None or len(values) < 2:
        raise AnalysisError("The sweep needs the step and at least one variant that run: "
                            + "; ".join(f"{s['label']}: {s.get('error')}" for s in summary if not s["ok"]))
    table = pd.DataFrame(values).reindex(base_payload["target_ids"])
    ranks = table.rank(ascending=False, method="min")
    n_valid = table.notna().sum()
    top_cut = {c: max(1, math.ceil(top_share * n_valid[c])) for c in table.columns}
    in_top = pd.DataFrame({c: ranks[c] <= top_cut[c] for c in table.columns})
    measured = ranks.notna().sum(axis=1)
    stats = pd.DataFrame({
        "rank_min": ranks.min(axis=1), "rank_max": ranks.max(axis=1),
        "rank_range": ranks.max(axis=1) - ranks.min(axis=1),
        "top_share": in_top.sum(axis=1).where(measured > 0) / measured.where(measured > 0),
    }, index=table.index)
    labels = list(table.columns)
    agreement = [{"a": labels[i], "b": labels[j], "spearman": _spearman(table[labels[i]], table[labels[j]])}
                 for i in range(len(labels)) for j in range(i + 1, len(labels))]
    col_names = {lab: f"v{k}_{column}" for k, lab in enumerate(labels)}
    frame = pd.concat([table.rename(columns=col_names), stats], axis=1).reset_index().rename(columns={"index": "target_id"})
    columns = list(col_names.values()) + ["rank_min", "rank_max", "rank_range", "top_share"]
    kinds = {c: kind for c in col_names.values()}
    kinds.update({"rank_min": "intensive", "rank_max": "intensive", "rank_range": "intensive", "top_share": "intensive"})
    payload = _payload_like(base_payload, frame, columns, kinds)
    stable = stats["top_share"]
    return {**payload, "sweep": {
        "step": step_id, "column": column, "value_kind": kind, "top_share": top_share,
        "variants": summary, "columns": {lab: col_names[lab] for lab in labels}, "agreement": agreement,
        "always_top": int((stable == 1).sum()), "sometimes_top": int(((stable > 0) & (stable < 1)).sum()),
        "units": int(len(stats)),
    }}


def _payload_like(base: dict, frame: pd.DataFrame, columns: list[str], kinds: dict) -> dict:
    """A results-in-columns payload on the same target as *base*, with *frame*'s columns."""
    frame = frame.set_index("target_id").reindex(base["target_ids"]).reset_index().rename(columns={"index": "target_id"})
    payload = {"target": base["target"], "target_ids": base["target_ids"],
               "columns": {c: plans._plain_values(frame[c]) for c in columns}, "kinds": {c: kinds.get(c) for c in columns}}
    if base.get("geojson"):
        by_id = {str(t): i for i, t in enumerate(base["target_ids"])}
        feats = []
        for f in base["geojson"]["features"]:
            zid = str(f["properties"].get("zone_id"))
            i = by_id.get(zid)
            props = {"zone_id": zid, **({"label": f["properties"]["label"]} if "label" in f["properties"] else {})}
            if i is not None:
                props.update({c: payload["columns"][c][i] for c in columns})
            feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
        payload["geojson"] = {"type": "FeatureCollection", "features": feats}
    return payload


# --- validation against outcomes ----------------------------------------------------------------

def validate_outcomes(data_dir, plan_spec: dict, study_area, cache_root, *, step_id: str | None, column: str,
                      outcomes: dict, quantiles=(0.5, 0.6, 0.7), derived: list[dict] | None = None) -> dict:
    """Coverage and lift of the units ranked highest by *column* against outcome points."""
    spec = json.loads(json.dumps(plan_spec))
    derived = derived or []
    target_step = step_id
    if derived:
        target_step = derived[0]["inputs"][0]
    step = _step(spec, target_step)
    stem = catalog.stem_of(outcomes.get("dataset"))
    if not catalog.valid_stem(stem):
        raise AnalysisError("Choose an outcomes dataset.")
    spec["sources"]["__outcomes"] = {"kind": "vector", "columns": {},
                                     "urbantrace": {"dataset": stem, **({"time_window": outcomes["time_window"]} if outcomes.get("time_window") else {})}}
    prof = catalog.profile(data_dir, stem) or {}
    method = "contain" if (prof.get("geometricType") or "Point") in ("Point",) else "centroid"
    spec["steps"].append({"id": "__outcomes", "source": "__outcomes",
                          "match": {"method": method, "target": step["match"]["target"]},
                          "aggregate": [{"method": "count", "as": "outcomes", "fill_empty": 0}]})
    try:
        out = plans.run(data_dir, spec, study_area, cache_root,
                        outputs=([step_id] if not derived else []) + ["__outcomes"], derived=derived)
    except (plans.PlanInputError, uw.UrbanweaveError) as e:
        raise AnalysisError(str(e))
    key = derived[0]["id"] if derived else step_id
    result = out["steps"][key]
    if column not in result["columns"]:
        raise AnalysisError(f"{key} has no output column {column!r}.")
    counts = out["steps"]["__outcomes"]
    value = pd.Series(result["columns"][column], index=result["target_ids"], dtype="float64")
    hits = pd.Series(counts["columns"]["outcomes"], index=counts["target_ids"], dtype="float64").reindex(value.index).fillna(0)
    rep = (out["reports"].get("__outcomes") or {}).get("match", {}).get("sources", {})
    total_outcomes = float(hits.sum())
    valid = value.notna()
    rows = []
    for q in sorted(float(x) for x in quantiles):
        thresh = float(value[valid].quantile(q)) if valid.any() else float("nan")
        high = valid & (value >= thresh)
        n_high = float(hits[high].sum())
        coverage = n_high / total_outcomes if total_outcomes else None
        baseline = float(high.sum() / valid.sum()) if valid.any() else None
        rows.append({"quantile": q, "threshold": round(thresh, 6), "coverage": None if coverage is None else round(coverage, 4),
                     "n_high": int(n_high), "n_total": int(total_outcomes), "units_high": int(high.sum()),
                     "baseline": None if baseline is None else round(baseline, 4),
                     "lift": None if not coverage or not baseline else round(coverage / baseline, 3),
                     # With tied values the units above a quantile can be many more than 1 - q of them
                     "note": (f"ties: {baseline:.0%} of units are at or above the threshold, not {1 - q:.0%}"
                              if baseline is not None and abs(baseline - (1 - q)) > 0.05 else None)})
    frame = pd.DataFrame({"target_id": value.index, column: value.values, "outcomes": hits.values})
    frame["high_at_first_quantile"] = (valid & (value >= rows[0]["threshold"])).astype(float).values if rows else 0.0
    payload = _payload_like(result, frame, [column, "outcomes", "high_at_first_quantile"],
                            {column: result["kinds"].get(column), "outcomes": "extensive", "high_at_first_quantile": "categorical"})
    return {**payload, "validation": {
        "result": key, "column": column, "outcomes": stem, "table": rows,
        "outcome_points": {"total": rep.get("total"), "matched": rep.get("matched"),
                           "unmatched": {k: v.get("count") for k, v in (rep.get("unmatched") or {}).items()}},
    }}


# --- dasymetric ----------------------------------------------------------------------------------

def dasymetric(data_dir, study_area_spec, cache_root, *, zones: dict, target: dict, priors: list[dict],
               normalize: str | None = "share", fallback: str = "area") -> dict:
    """Spread zone totals over a target in proportion to point priors."""
    try:
        area = scope.study_area_geometry(data_dir, study_area_spec)
    except scope.ScopeError as e:
        raise AnalysisError(str(e))

    def load(stem, label):
        stem = catalog.stem_of(stem)
        if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
            raise AnalysisError(f"{label}: dataset {stem!r} is not in the catalog.")
        g = catalog.load(data_dir, stem)
        g = g.to_crs(4326) if g.crs is not None and not g.crs.equals("EPSG:4326") else g
        g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
        return stem, g

    zstem, zg = load(zones.get("dataset"), "zones")
    totals = [c for c in zones.get("totals") or [] if c]
    if not totals or any(c not in zg.columns for c in totals):
        raise AnalysisError(f"Choose total columns of {zstem}.")
    zg["zone_id"] = zg.index.astype(str)
    zg, _ = _repair(zg, "zone_id")
    if area is not None:
        zg = zg[scope.zones_in_area(zg, area)]
    for c in totals:
        zg[c] = pd.to_numeric(zg[c], errors="coerce")
    if target.get("kind") == "h3":
        res = int(target.get("resolution", 9))
        pad = 1.5 * h3.average_hexagon_edge_length(res, unit="m")
        extent = scope.padded_area(area, pad) if area is not None else scope.padded_area(zg.geometry.union_all(), pad)
        tg = uw.targets.h3_cells(extent, res, cover="geometry")
        tinfo = {"kind": "h3", "resolution": res}
        tid = None
    else:
        tstem, tg = load(target.get("dataset"), "target")
        tg["target_id"] = tg.index.astype(str)
        tg, _ = _repair(tg, "target_id")
        if area is not None:
            tg = tg[scope.zones_in_area(tg, area)]
        tinfo = {"kind": "zones", "dataset": tstem}
        tid = "target_id"
    layers, weights = {}, {}
    for k, p in enumerate(priors or []):
        pstem, pg = load(p.get("dataset"), "prior")
        if area is not None:
            pg, _ = scope.clip_to_area(pg, area)
        name = f"{pstem}_{k}"
        col = p.get("column") or None
        if col and col not in pg.columns:
            raise AnalysisError(f"prior {pstem} has no column {col!r}.")
        if col:
            pg[col] = pd.to_numeric(pg[col], errors="coerce").fillna(0).clip(lower=0)
        layers[name] = (pg, col) if col else pg
        weights[name] = float(p.get("weight") or 1)
    if not layers:
        raise AnalysisError("Add at least one prior dataset.")
    spread = getattr(uw, "dasymetric", None)
    if spread is None:
        raise AnalysisError(f"Dasymetric disaggregation needs a newer urbanweave than {uw.__version__} "
                            "(it was added after 0.1.0a1).")
    try:
        out = spread(zg[["zone_id", *totals, "geometry"]], tg, layers, total=totals if len(totals) > 1 else totals[0],
                            zone_id="zone_id", target_id=tid, weights=weights, normalize=normalize, fallback=fallback,
                            as_=[f"{c}_est" for c in totals] if len(totals) > 1 else f"{totals[0]}_est")
    except uw.UrbanweaveError as e:
        raise AnalysisError(str(e))
    report = json.loads(json.dumps(uw.report_of(out) or {}, default=str))
    out = out.rename(columns={tid: "target_id"}) if tid and tid != "target_id" else out
    cols = [f"{c}_est" for c in totals]
    ids = out["target_id"].astype(str).tolist()
    payload = {"target": tinfo, "target_ids": ids, "columns": {c: plans._plain_values(out[c]) for c in cols},
               "kinds": {c: "extensive" for c in cols}}
    if tinfo["kind"] == "zones":
        geo = gpd.GeoDataFrame(out[["target_id", *cols, "geometry"]], geometry="geometry", crs=4326).rename(columns={"target_id": "zone_id"})
        payload["geojson"] = json.loads(geo.to_json(na="null"))
    return {**payload, "dasymetric": {"zones": zstem, "totals": totals, "priors": [p.get("dataset") for p in priors],
                                      "normalize": normalize, "fallback": fallback, "report": report}}


# --- priority index ------------------------------------------------------------------------------

def priority(columns: dict, variables: list[dict]) -> list:
    """The Result Map's priority index over units: min-max normalized variables, inverted where the
    direction is 'inverted', weighted (weights rescaled to sum to 1) and summed; 0 where no variable
    has a nonzero value. A variable whose direction is 'unknown' (nobody decided it) is left out."""
    variables = [v for v in variables if str(v.get("direction", "")).lower() != "unknown"]
    names = [v["column"] for v in variables if v.get("column") in columns]
    if not names:
        raise AnalysisError("None of the priority variables is an output of this result with a direction set.")
    frame = pd.DataFrame({n: pd.to_numeric(pd.Series(columns[n]), errors="coerce") for n in names})
    total_w = sum(float(v.get("weight") or 0) for v in variables if v.get("column") in names) or 1.0
    score = pd.Series(0.0, index=frame.index)
    for v in variables:
        n = v.get("column")
        if n not in names:
            continue
        s = frame[n]
        lo, hi = (s.min(), s.max()) if s.notna().any() else (0.0, 1.0)
        norm = ((s - lo) / (hi - lo)) if hi > lo else pd.Series(0.0, index=s.index)
        if str(v.get("direction", "")).lower() == "inverted":
            norm = 1 - norm
        score += (float(v.get("weight") or 0) / total_w) * norm.where(s.notna(), 0.0)
    signal = frame.apply(lambda r: any(pd.notna(x) and x != 0 for x in r), axis=1)
    return [round(float(x), 6) for x in score.where(signal, 0.0)]


# --- report --------------------------------------------------------------------------------------

_PALETTE = ["#edf8fb", "#b2e2e2", "#66c2a4", "#2ca25f", "#006d2c"]


def payload_geometries(payload: dict) -> list:
    """The geometry of each target in a payload (zones from its GeoJSON, H3 cells from their ids)."""
    if payload.get("geojson"):
        from shapely.geometry import shape
        by_id = {str(f["properties"].get("zone_id")): shape(f["geometry"]) for f in payload["geojson"]["features"] if f.get("geometry")}
        return [by_id.get(str(t)) for t in payload["target_ids"]]
    if payload.get("target", {}).get("kind") == "h3":
        return [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in payload["target_ids"]]
    return [None] * len(payload["target_ids"])


def svg_map(payload: dict, column: str, width: int = 520, height: int = 360, title: str = "") -> str:
    """A static choropleth of one column (quintile classes), for the report."""
    geoms = payload_geometries(payload)
    vals = pd.Series(payload["columns"].get(column, []), dtype="float64")
    pairs = [(g, v) for g, v in zip(geoms, vals) if g is not None and not g.is_empty]
    if not pairs:
        return "<p><em>No geometry to draw.</em></p>"
    minx, miny, maxx, maxy = gpd.GeoSeries([g for g, _ in pairs]).total_bounds
    k = math.cos(math.radians((miny + maxy) / 2))
    sx = (maxx - minx) * k or 1e-9
    sy = (maxy - miny) or 1e-9
    scale = min((width - 20) / sx, (height - 40) / sy)
    ox, oy = 10 + ((width - 20) - sx * scale) / 2, 30 + ((height - 40) - sy * scale) / 2
    finite = vals.dropna()
    edges = list(np.unique(finite.quantile([0.2, 0.4, 0.6, 0.8]).to_numpy())) if len(finite) else []

    def color(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "#f1f5f9"
        return _PALETTE[min(len(_PALETTE) - 1, int(np.searchsorted(edges, v, side="right")))]

    def path(geom):
        parts = []
        polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
        for p in polys:
            if p.geom_type != "Polygon":
                continue
            for ring in [p.exterior, *p.interiors]:
                pts = " ".join(f"{ox + (x - minx) * k * scale:.0f},{oy + (maxy - y) * scale:.0f}" for x, y in ring.coords)
                parts.append(f"M{pts}Z")
        return " ".join(parts)

    tol = 0.7 / scale  # about one pixel: detail finer than the drawing is dropped
    body = "".join(f'<path d="{path(g.simplify(tol, preserve_topology=True))}" fill="{color(v)}" stroke="#94a3b8" '
                   f'stroke-width="0.3" fill-rule="evenodd"/>' for g, v in pairs)
    legend = " ".join(f'<tspan fill="{c}">■</tspan>' for c in _PALETTE)
    lo, hi = (f"{finite.min():.3g}", f"{finite.max():.3g}") if len(finite) else ("", "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{html.escape(title or column)}"><text x="10" y="16" font-size="12" font-weight="600">'
            f'{html.escape(title or column)}</text><text x="{width - 10}" y="16" font-size="11" text-anchor="end">'
            f'{lo} {legend} {hi}</text>{body}</svg>')


def report_html(collection: dict, sections: list[dict], warnings: list[dict], datasets: list[dict]) -> str:
    """A printable HTML report: goal, datasets and origins, study area, each result with its map and
    report, analyses, and caveats. *sections* are ``{"title", "text", "svg", "table", "lines"}``."""
    esc = html.escape
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>{esc(collection.get('name') or 'Collection')}</title>",
           "<style>body{font:14px/1.5 system-ui,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#0f172a}"
           "h1{font-size:24px}h2{font-size:18px;margin-top:28px;border-bottom:1px solid #e2e8f0}table{border-collapse:collapse;"
           "font-size:12px;margin:8px 0}td,th{border:1px solid #e2e8f0;padding:3px 6px;text-align:left}.muted{color:#64748b}"
           "@media print{h2{break-after:avoid}svg{break-inside:avoid}}</style></head><body>",
           f"<h1>{esc(collection.get('name') or 'Collection')}</h1>",
           f"<p class='muted'>UrbanTrace report, {now}.</p>"]
    if collection.get("goal"):
        out.append(f"<p><strong>Goal:</strong> {esc(collection['goal'])}</p>")
    if collection.get("notes"):
        out.append(f"<p>{esc(collection['notes'])}</p>")
    sa = collection.get("study_area")
    if sa:
        out.append(f"<p><strong>Study area:</strong> {esc(sa.get('name') or sa.get('kind'))}</p>")
    out.append("<h2>Datasets</h2><table><tr><th>Dataset</th><th>Columns used</th><th>Source</th><th>Why</th></tr>")
    for d in datasets:
        o = d.get("origin") or {}
        src = f"<a href='{esc(o['source_url'])}'>{esc(o.get('publisher') or 'source')}</a>" if o.get("source_url") else "unknown"
        out.append(f"<tr><td>{esc(d['id'])}</td><td>{esc(', '.join(d.get('columns') or []) or 'all')}</td><td>{src}</td>"
                   f"<td>{esc(d.get('rationale') or '')}</td></tr>")
    out.append("</table>")
    for sec in sections:
        out.append(f"<h2>{esc(sec['title'])}</h2>")
        if sec.get("text"):
            out.append(f"<p>{esc(sec['text'])}</p>")
        if sec.get("svg"):
            out.append(sec["svg"])
        for line in sec.get("lines") or []:
            out.append(f"<p class='muted'>{esc(line.replace('`', ''))}</p>")  # lines are shared with the Markdown README
        if sec.get("table"):
            head, *rows = sec["table"]
            out.append("<table><tr>" + "".join(f"<th>{esc(str(h))}</th>" for h in head) + "</tr>")
            out += ["<tr>" + "".join(f"<td>{esc('' if c is None else str(c))}</td>" for c in r) + "</tr>" for r in rows]
            out.append("</table>")
    if warnings:
        out.append("<h2>Caveats</h2><ul>" + "".join(f"<li>{esc(w['message'])}</li>" for w in warnings) + "</ul>")
    out.append("</body></html>")
    return "\n".join(out)
