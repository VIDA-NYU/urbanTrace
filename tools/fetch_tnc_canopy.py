"""Tree canopy for NYC from the 6-inch 2021 land cover (The Nature Conservancy), as a percentage per
30 ft cell, added to the catalog as a raster (backend/rasters.py).

The land cover (Zenodo 10.5281/zenodo.14053441, CC BY-NC-SA 4.0) classifies every 6-inch pixel of the
city from 2021 LiDAR and aerial imagery; class 1 is tree canopy (crowns over 8 ft). At 10^11 pixels
it is too large to summarize zone by zone, and its overviews sample classes rather than average
them, so this tool derives the share of canopy in each 30 ft (9.1 m) cell: 60 x 60 source pixels,
canopy pixels over land pixels (no-data, class 0, and water, class 4, left out; a cell
that is all water has no value). Street trees survive at that size,
unlike in 30 m national products, which miss most of them in dense neighborhoods.

The source file (1.74 GB) is downloaded once to ``data/raster/source/`` (not committed; resumed if
interrupted); the result, ``data/raster/tnc_tree_canopy_2021.tif``, keeps the source's grid (NY State
Plane Long Island, feet).

    cd backend && ./venv/bin/python ../tools/fetch_tnc_canopy.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

URL = "https://zenodo.org/api/records/14053441/files/landcover_nyc_2021_6in.tif/content"
SOURCE_NAME = "landcover_nyc_2021_6in.tif"
SIZE = 1_742_000_000                         # about; checked against the server's Content-Length
FACTOR = 60                                  # 60 x 6 in = 30 ft
TILE = 64                                    # output cells per tile side
CANOPY = 1
WATER = 4                                    # canopy is a share of land: water is left out like no-data


def download(dest: Path):
    """Download the land cover once, resuming a partial file."""
    import httpx
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    with httpx.Client(timeout=None, follow_redirects=True) as client:
        total = int(client.head(URL).headers.get("content-length") or 0)
        if dest.exists() and (not total or dest.stat().st_size == total):
            return
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        t0, last = time.perf_counter(), 0
        with client.stream("GET", URL, headers=headers) as r:
            r.raise_for_status()
            with part.open("ab" if have and r.status_code == 206 else "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    have += len(chunk)
                    if time.perf_counter() - last > 15:
                        last = time.perf_counter()
                        print(f"  {have / 1e9:.2f} of {total / 1e9:.2f} GB ({have / 1e6 / (last - t0):.0f} MB/s)", flush=True)
    part.replace(dest)


def aggregate(src_path: Path, out_path: Path) -> dict:
    """Percent canopy per 30 ft cell (uint8, 255 = no data)."""
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    with rasterio.open(src_path) as src:
        W, H = src.width // FACTOR, src.height // FACTOR       # whole output cells only (a sliver at the edge is dropped)
        tr = src.transform * src.transform.scale(FACTOR, FACTOR)
        profile = {"driver": "GTiff", "width": W, "height": H, "count": 1, "dtype": "uint8", "crs": src.crs,
                   "transform": tr, "nodata": 255, "compress": "deflate", "tiled": True, "blockxsize": 256, "blockysize": 256}
        out = np.full((H, W), 255, dtype="uint8")
        t0, done, ntiles = time.perf_counter(), 0, ((H + TILE - 1) // TILE) * ((W + TILE - 1) // TILE)
        for oy in range(0, H, TILE):
            for ox in range(0, W, TILE):
                h, w = min(TILE, H - oy), min(TILE, W - ox)
                a = src.read(1, window=Window(ox * FACTOR, oy * FACTOR, w * FACTOR, h * FACTOR))
                a = a.reshape(h, FACTOR, w, FACTOR)
                valid = ((a != 0) & (a != WATER)).sum(axis=(1, 3))
                canopy = (a == CANOPY).sum(axis=(1, 3))
                pct = np.where(valid > 0, np.rint(100.0 * canopy / np.maximum(valid, 1)), 255).astype("uint8")
                out[oy:oy + h, ox:ox + w] = pct
                done += 1
                if done % 500 == 0:
                    print(f"  {done}/{ntiles} tiles ({time.perf_counter() - t0:.0f} s)", flush=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(out, 1)
        bounds, crs = dst.bounds, dst.crs
    v = out[out != 255]
    return {"bounds": bounds, "crs": crs, "valid_cells": int(v.size), "mean": round(float(v.mean()), 2), "max": int(v.max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(BACKEND.parent / "data"))
    a = ap.parse_args()
    from rasterio.warp import transform_bounds
    folder = Path(a.data) / "raster"
    src = folder / "source" / SOURCE_NAME
    t0 = time.perf_counter()
    download(src)
    print(f"source: {src} ({src.stat().st_size / 1e9:.2f} GB, {time.perf_counter() - t0:.0f} s)")
    stem = "tnc_tree_canopy_2021"
    t1 = time.perf_counter()
    info = aggregate(src, folder / f"{stem}.tif")
    print(f"{folder / (stem + '.tif')}: {(folder / (stem + '.tif')).stat().st_size / 1e6:.0f} MB, {time.perf_counter() - t1:.0f} s, mean {info['mean']} %")
    side = {
        "title": "Tree canopy 2021 (6-inch land cover, 30 ft cells)",
        "description": ("Percent of each 30 ft (9.1 m) cell covered by tree canopy (crowns over 8 ft) in 2021, derived from The Nature "
                        "Conservancy's 6-inch land cover of New York City (LiDAR and aerial imagery): the share of the cell's 3,600 "
                        "six-inch pixels classed as tree canopy, over its land pixels (water left out). Street trees, parks and yards alike."),
        "band": "tree_canopy_pct", "units": "percent", "value_kind": "intensive", "nodata": 255, "year": 2021,
        "display_range": [0, 100], "resolution_m": round(30 * 0.3048, 2), "crs": info["crs"].to_string(),
        "bounds_wgs84": [round(v, 5) for v in transform_bounds(info["crs"], "EPSG:4326", *info["bounds"])],
        "publisher": "The Nature Conservancy", "license": "CC BY-NC-SA 4.0",
        "license_note": "Non-commercial use; results derived from it are shared under the same license, with attribution.",
        "source_url": "https://doi.org/10.5281/zenodo.14053441",
        "citation": "The Nature Conservancy (2024). New York City Land Cover, Tree Canopy Change, and Estimated Tree Location Data, 2021. Zenodo. https://doi.org/10.5281/zenodo.14053441",
        "derived_from": {"file": SOURCE_NAME, "class": "1 (tree canopy)", "method": f"share of the land pixels among {FACTOR}x{FACTOR} six-inch pixels (water and no-data left out)"},
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": {"valid_cells": info["valid_cells"], "mean": info["mean"], "min": 0, "max": info["max"]},
    }
    (folder / f"{stem}.json").write_text(json.dumps(side, indent=1))


if __name__ == "__main__":
    main()
