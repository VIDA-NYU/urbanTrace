"""Fetch a whole NYC Open Data dataset (every row, paged through the Socrata API) into the catalog as
GeoParquet, and profile it again with atlas-profiler.

The catalog's GeoJSON copies were made with a row cap (500,000); ``catalog.dataset_path`` prefers a
GeoParquet copy when there is one, so the full dataset replaces the capped one for every use
without touching the GeoJSON. The profile (``data/metadata_v2/<stem>.json``) is recomputed from the
full data by atlas-profiler, run in its own environment; the fields UrbanTrace adds to profiles are
kept. ``origins.json`` records when it was retrieved and how many rows it has.

    cd backend && ./venv/bin/python ../tools/fetch_open_data.py forestry_tree_points
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

PAGE = 50_000
PROFILER_PYTHON = Path.home() / "src" / "atlas-profiler" / ".venv" / "bin" / "python"
PROFILE_SCRIPT = """
import json, sys
import pandas as pd
from atlas_profiler import process_dataset
df = pd.read_parquet(sys.argv[1])
meta = process_dataset(df)
json.dump(meta, open(sys.argv[2], "w"), default=str)
"""


def fetch(portal_id: str, domain: str = "data.cityofnewyork.us"):
    """Every row of a Socrata dataset as a GeoDataFrame (WGS84)."""
    import geopandas as gpd
    import httpx
    frames, offset = [], 0
    with httpx.Client(timeout=300, headers={"User-Agent": "UrbanTrace catalog"}) as client:
        while True:
            t = time.perf_counter()
            r = client.get(f"https://{domain}/resource/{portal_id}.geojson",
                           params={"$limit": PAGE, "$offset": offset, "$order": ":id"})
            r.raise_for_status()
            feats = r.json().get("features") or []
            if not feats:
                break
            for f in feats:                                   # an attribute named "geometry" (a text copy of
                props = f.get("properties") or {}             # the location) would clash with the geometry
                if "geometry" in props:
                    props["geometry_text"] = props.pop("geometry")
            frames.append(gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326"))
            offset += len(feats)
            print(f"  {offset:,} rows ({time.perf_counter() - t:.0f} s)", flush=True)
            if len(feats) < PAGE:
                break
    import pandas as pd
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def profile(gdf, old: dict, profiler_python: Path) -> dict:
    """atlas-profiler's profile of the data (with latitude and longitude columns, as the catalog's
    profiles were made), keeping the fields UrbanTrace added to the old profile."""
    import pandas as pd
    df = pd.DataFrame(gdf.drop(columns=gdf.geometry.name))
    pts = gdf.geometry
    df["geometry_latitude"] = pts.y.where(pts.geom_type == "Point")
    df["geometry_longitude"] = pts.x.where(pts.geom_type == "Point")
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "data.parquet", Path(tmp) / "profile.json"
        df.to_parquet(src)
        script = Path(tmp) / "profile.py"
        script.write_text(PROFILE_SCRIPT)
        subprocess.run([str(profiler_python), str(script), str(src), str(out)], check=True)
        new = json.loads(out.read_text())
    for k, v in old.items():                               # UrbanTrace's own fields (geometricType, ...)
        new.setdefault(k, v)
    new["geometricType"] = old.get("geometricType") or str(gdf.geom_type.mode().iloc[0])
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem", help="catalog dataset (its origins.json entry gives the portal ID)")
    ap.add_argument("--data", default=str(BACKEND.parent / "data"))
    ap.add_argument("--profiler-python", default=str(PROFILER_PYTHON))
    ap.add_argument("--no-profile", action="store_true")
    a = ap.parse_args()
    data = Path(a.data)
    origins_path = data / "origins.json"
    origins = json.loads(origins_path.read_text())
    origin = origins.get(a.stem) or {}
    if origin.get("portal") != "NYC Open Data" or not origin.get("portal_id"):
        raise SystemExit(f"{a.stem}: no NYC Open Data portal ID in origins.json")
    t0 = time.perf_counter()
    gdf = fetch(origin["portal_id"])
    out = data / "geoparquet" / f"{a.stem}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(out)
    print(f"{out}: {len(gdf):,} rows, {out.stat().st_size / 1e6:.0f} MB, {time.perf_counter() - t0:.0f} s")
    if not a.no_profile:
        prof_path = data / "metadata_v2" / f"{a.stem}.json"
        old = json.loads(prof_path.read_text()) if prof_path.exists() else {}
        t1 = time.perf_counter()
        prof_path.write_text(json.dumps(profile(gdf, old, Path(a.profiler_python)), default=str))
        print(f"{prof_path}: profiled in {time.perf_counter() - t1:.0f} s")
    origin.update(retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), rows=len(gdf),
                  retrieved_with="tools/fetch_open_data.py (all rows)")
    origins[a.stem] = origin
    origins_path.write_text(json.dumps(origins, indent=1) + "\n")       # the file's own formatting


if __name__ == "__main__":
    main()
