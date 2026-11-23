"""Convert catalog datasets from GeoJSON to GeoParquet (docs/REDESIGN.md, section 4.4).

Writes data/geoparquet/<stem>.parquet next to data/geojson/<stem>.geojson. The backend reads the
GeoParquet copy when it exists (backend/catalog.py) and keeps serving GeoJSON for map previews.
Existing, newer copies are skipped.

    python tools/convert_to_geoparquet.py NYC_libraries NYC_poverty_rate   # some datasets
    python tools/convert_to_geoparquet.py --all                            # the whole catalog (~8.8 GB of GeoJSON)
"""
import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]


def convert(src: Path, dst: Path) -> str:
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return "up to date"
    with open(src, "rb") as f:
        if f.read(64).startswith(b"version https://git-lfs"):
            return "skipped: Git LFS pointer (run git lfs pull)"
    t = time.time()
    gdf = gpd.read_file(src)
    if gdf.crs is not None and not gdf.crs.equals("EPSG:4326"):
        gdf = gdf.to_crs(4326)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".parquet.tmp")
    gdf.to_parquet(tmp, index=False, compression="zstd")
    tmp.replace(dst)
    return f"{len(gdf)} rows, {src.stat().st_size / 1e6:.1f} MB -> {dst.stat().st_size / 1e6:.1f} MB in {time.time() - t:.1f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stems", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    args = ap.parse_args()
    data = Path(args.data_dir)
    stems = sorted(p.stem for p in (data / "geojson").glob("*.geojson")) if args.all else args.stems
    if not stems:
        ap.error("name datasets or pass --all")
    for stem in stems:
        src = data / "geojson" / f"{stem}.geojson"
        if not src.exists():
            print(f"{stem}: not found", file=sys.stderr)
            continue
        print(f"{stem}: {convert(src, data / 'geoparquet' / f'{stem}.parquet')}", file=sys.stderr)


if __name__ == "__main__":
    main()
