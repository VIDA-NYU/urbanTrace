"""Run every catalog dataset through every stage of UrbanTrace and record what happens.

For each dataset, in its own process (so one huge or broken file cannot stop the run), with a time
limit per dataset:

1. load: read it through ``catalog.load`` (rows, geometry types, CRS, invalid geometries)
2. coverage: its coverage cells and bounding box (``scope.dataset_cells``); flags a box outside the
   catalog's region
3. checks: atlas-clean's spatial checks (``cleaning.check``), if atlas-clean is installed
4. step to zones: a plan step onto the NTA neighborhoods (whole city): the usual method for its
   geometry, a count, and a sum or mean of one numeric column when there is one
5. step to H3: the same onto an H3 grid at resolution 8 over the dataset's extent
6. preview: the simplified GeoJSON the map preview receives, and its size
7. export: a one-dataset package (GeoParquet, embedded)

Results go to ``--out`` as JSON lines (one per dataset) and a Markdown summary beside them.

    cd backend && ./venv/bin/python ../tools/corpus_check.py --out ../benchmark/results/corpus_check
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

ZONES = "NTA_Neighborhood_Tabulation_Areas"
METHOD = {"Point": "contain", "LineString": "length_weighted", "Polygon": "area_overlap"}


def _stage(record: dict, name: str, fn):
    t = time.perf_counter()
    try:
        record[name] = {"ok": True, **(fn() or {})}
    except Exception as e:  # recorded, not raised: the point is to see every failure
        record[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:600],
                        "where": traceback.extract_tb(e.__traceback__)[-1].filename.split("/")[-1]}
    record[name]["seconds"] = round(time.perf_counter() - t, 2)


def one(stem: str, data_dir: str, cache: str) -> dict:
    import shapely

    import catalog
    import cleaning
    import export
    import plans
    import scope

    rec: dict = {"dataset": stem}
    state: dict = {}

    def load():
        gdf = catalog.load(data_dir, stem)
        state["gdf"] = gdf
        geoms = gdf.geometry.to_numpy()
        types = gdf.geometry.geom_type.value_counts(dropna=False).to_dict()
        fam = next((METHOD[k] and k for k in METHOD if any(str(t).endswith(k) for t in types if t)), None)
        state["family"] = fam
        return {"rows": int(len(gdf)), "types": {str(k): int(v) for k, v in types.items()},
                "crs": str(gdf.crs) if gdf.crs else None,
                "invalid": int((~shapely.is_valid(geoms[~shapely.is_missing(geoms)])).sum()),
                "missing_geometry": int(shapely.is_missing(geoms).sum() + shapely.is_empty(geoms[~shapely.is_missing(geoms)]).sum()),
                "columns": int(len(gdf.columns) - 1)}

    def coverage():
        cells, bounds, source = scope.dataset_cells(data_dir, stem)
        region = state.setdefault("region", cleaning.catalog_region(data_dir))
        inside = bool(bounds) and not (bounds[2] < region[0] or bounds[0] > region[2] or bounds[3] < region[1] or bounds[1] > region[3])
        return {"cells": len(cells), "source": source, "bbox": [round(v, 4) for v in bounds] if bounds else None,
                "meets_region": inside}

    def checks():
        if not cleaning.AVAILABLE:
            return {"skipped": "atlas-clean not installed"}
        out = cleaning.check(data_dir, stem)
        return {"issues": [f"{i['severity']}:{i['detector']}({i['affected_rows']})" for i in out["issues"]],
                "fixes": sorted({f["action"] for f in out["fixes"]})}

    def plan_for(target: dict, kinds: dict) -> dict:
        fam = state.get("family") or "Polygon"
        numeric = next((c for c, k in kinds.items() if k["kind"] == "extensive"), None) or \
            next((c for c, k in kinds.items() if k["kind"] == "intensive"), None)
        aggregate = [{"method": "count", "as": "n", "fill_empty": 0}]
        columns = {}
        if numeric:
            kind = kinds[numeric]["kind"]
            aggregate.append({"method": "sum" if kind == "extensive" else ("weighted_mean" if fam != "Point" else "mean"),
                              "column": numeric, "as": "v"})
            columns[numeric] = {"kind": kind}
        state["numeric"] = numeric
        return {"version": 1, "sources": {"s": {"kind": "vector", "columns": columns, "urbantrace": {"dataset": stem}}},
                "targets": {"t": target},
                "steps": [{"id": "st", "source": "s", "match": {"method": METHOD[fam], "target": "t"}, "aggregate": aggregate}]}

    def step(target):
        def run():
            kinds = plans.suggest_value_kinds(data_dir, stem)
            out = plans.run(data_dir, plan_for(target, kinds), None, cache, outputs=["st"])
            rep = out["reports"]["st"]["match"]
            cols = out["steps"]["st"]["columns"]
            return {"method": rep["method"], "units": len(out["steps"]["st"]["target_ids"]),
                    "matched": f"{rep['sources']['matched']}/{rep['sources']['total']}",
                    "excluded": {k: v.get("count") for k, v in (rep["sources"].get("excluded") or {}).items()},
                    "unmatched": {k: v.get("count") for k, v in (rep["sources"].get("unmatched") or {}).items()},
                    "total_n": float(sum(x or 0 for x in cols["n"])), "column": state.get("numeric")}
        return run

    def preview():
        gdf = state["gdf"]
        g = gdf.to_crs("EPSG:4326") if gdf.crs is not None and str(gdf.crs) != "EPSG:4326" else gdf.copy()
        g["geometry"] = g["geometry"].simplify(tolerance=0.001, preserve_topology=True)
        size = len(json.dumps(g.__geo_interface__, default=str))
        return {"mb": round(size / 1e6, 1)}

    def package():
        with tempfile.TemporaryDirectory() as tmp:
            export.build(data_dir, {"name": stem, "datasets": [{"id": stem}]}, Path(tmp) / "p.zip", embed="always",
                         formats=["parquet"])
            return {"mb": round((Path(tmp) / "p.zip").stat().st_size / 1e6, 1)}

    _stage(rec, "load", load)
    if not rec["load"]["ok"]:
        return rec
    _stage(rec, "coverage", coverage)
    _stage(rec, "checks", checks)
    if state.get("family"):
        _stage(rec, "step_zones", step({"kind": "zones", "urbantrace": {"dataset": ZONES}}))
        _stage(rec, "step_h3", step({"kind": "h3", "resolution": 8}))
    _stage(rec, "preview", preview)
    _stage(rec, "export", package)
    return rec


def summarize(records: list[dict], out_md: Path):
    stages = ["load", "coverage", "checks", "step_zones", "step_h3", "preview", "export"]
    lines = ["# Whole-catalog run", "", f"{len(records)} datasets, run {time.strftime('%Y-%m-%d')} by `tools/corpus_check.py`.", ""]
    lines += ["| Stage | OK | Failed | Slowest (s) |", "|---|---|---|---|"]
    for st in stages:
        rs = [r[st] for r in records if st in r]
        ok = sum(1 for x in rs if x.get("ok"))
        slow = max((x.get("seconds", 0) for x in rs), default=0)
        lines.append(f"| {st} | {ok} | {len(rs) - ok} | {slow} |")
    timeouts = [r["dataset"] for r in records if r.get("timeout")]
    if timeouts:
        lines += ["", "**Timed out:** " + ", ".join(f"`{t}`" for t in timeouts)]
    lines += ["", "## Failures", ""]
    for r in records:
        for st in stages:
            x = r.get(st)
            if x and not x.get("ok"):
                lines.append(f"- `{r['dataset']}` · {st}: {x['error']}")
    lines += ["", "## Outside the catalog's region", ""]
    lines += [f"- `{r['dataset']}`: bbox {r['coverage'].get('bbox')}" for r in records
              if r.get("coverage", {}).get("ok") and not r["coverage"].get("meets_region")]
    lines += ["", "## Checks with errors", ""]
    lines += [f"- `{r['dataset']}`: {', '.join(i for i in r['checks']['issues'] if i.startswith('error'))}" for r in records
              if r.get("checks", {}).get("ok") and any(i.startswith("error") for i in r["checks"].get("issues", []))]
    lines += ["", "## Slowest datasets (total seconds)", ""]
    tot = sorted(((sum(r[s].get("seconds", 0) for s in stages if s in r), r["dataset"]) for r in records), reverse=True)[:10]
    lines += [f"- `{d}`: {round(t, 1)} s" for t, d in tot]
    out_md.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "benchmark/results/corpus_check"))
    ap.add_argument("--data", default=str(BACKEND.parent / "data"))
    ap.add_argument("--one", help=argparse.SUPPRESS)
    ap.add_argument("--only", nargs="*", help="these datasets only")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per dataset")
    args = ap.parse_args()
    cache = os.environ.get("URBANTRACE_PLAN_CACHE") or str(Path(tempfile.gettempdir()) / "urbantrace_corpus_cache")
    if args.one:
        print(json.dumps(one(args.one, args.data, cache), default=str))
        return
    import catalog
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stems = args.only or catalog.list_stems(args.data)
    jsonl = out / "results.jsonl"
    done = {}
    if jsonl.exists():                                     # resume
        for line in jsonl.read_text().splitlines():
            r = json.loads(line)
            done[r["dataset"]] = r
    with jsonl.open("a") as f:
        for i, stem in enumerate(stems, 1):
            if stem in done:
                continue
            t = time.perf_counter()
            try:
                p = subprocess.run([sys.executable, __file__, "--one", stem, "--data", args.data], cwd=BACKEND,
                                   capture_output=True, text=True, timeout=args.timeout)
                last = (p.stdout.strip().splitlines() or ["{}"])[-1]
                rec = json.loads(last) if last.startswith("{") else {"dataset": stem, "crash": p.stderr[-800:]}
            except subprocess.TimeoutExpired:
                rec = {"dataset": stem, "timeout": args.timeout}
            rec["seconds"] = round(time.perf_counter() - t, 1)
            done[stem] = rec
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
            print(f"[{i}/{len(stems)}] {stem}: {rec['seconds']} s"
                  + ("" if all(v.get("ok", True) for v in rec.values() if isinstance(v, dict)) else " (failures)"), flush=True)
    summarize([done[s] for s in stems if s in done], out / "summary.md")


if __name__ == "__main__":
    main()
