"""Fetch NLCD Tree Canopy Cover (USFS/USGS, 30 m, percent canopy per cell) for the catalog's region
from MRLC's Web Coverage Service, and add it to the catalog as a raster (backend/rasters.py).

The cut-out keeps MRLC's native grid (CONUS Albers, EPSG:5070, metres), which exact zonal statistics
need. Codes 254 and 255 (no data, outside the mapped area) become no-data (255).

    cd backend && ./venv/bin/python ../tools/fetch_nlcd_canopy.py --year 2021
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

WCS = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"
YEARS = range(2011, 2022)


def fetch(data_dir: Path, year: int) -> Path:
    import httpx
    import numpy as np
    import rasterio
    from rasterio.warp import transform_bounds

    import cleaning
    region = cleaning.catalog_region(str(data_dir))                     # lon/lat box of the catalog's data
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", "EPSG:5070", *region)
    params = [("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
              ("coverageId", f"mrlc_download__nlcd_tcc_conus_{year}_v2021-4"),
              ("subset", f"X({x0:.0f},{x1:.0f})"), ("subset", f"Y({y0:.0f},{y1:.0f})"), ("format", "image/geotiff")]
    r = httpx.get(WCS, params=params, timeout=180)
    if r.status_code != 200 or "tiff" not in r.headers.get("content-type", ""):
        raise SystemExit(f"MRLC answered {r.status_code}: {r.text[:300]}")
    stem = f"nlcd_tree_canopy_{year}"
    out_dir = data_dir / "raster"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stem}.tif"
    with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
        tmp.write(r.content)
        tmp.flush()
        with rasterio.open(tmp.name) as src:
            a = src.read(1)
            meta = src.profile
            crs = src.crs
        a = np.where(a > 100, 255, a).astype("uint8")
        meta.update(driver="GTiff", dtype="uint8", nodata=255, compress="deflate", tiled=True, blockxsize=256, blockysize=256,
                    photometric="minisblack")
        meta.pop("colormap", None)
        with rasterio.open(out, "w", **meta) as dst:
            dst.write(a, 1)
            bounds = dst.bounds
    valid = a[a != 255]
    side = {
        "title": f"Tree canopy cover {year} (NLCD, 30 m)",
        "description": (f"Percent of each 30 m cell covered by tree canopy in {year}, from the USFS/USGS National Land Cover "
                        "Database Tree Canopy Cover product (v2021-4), cut to the catalog's region. Covers all trees seen from "
                        "above (streets, parks, yards), unlike the street-tree inventory."),
        "band": "tree_canopy_pct", "units": "percent", "value_kind": "intensive", "nodata": 255, "year": year,
        "display_range": [0, 100], "resolution_m": 30, "crs": crs.to_string(),
        "bounds_wgs84": [round(v, 5) for v in transform_bounds(crs, "EPSG:4326", *bounds)],
        "publisher": "USDA Forest Service / USGS (MRLC)", "license": "Public domain (U.S. Government work)",
        "source_url": "https://www.mrlc.gov/data/type/tree-canopy",
        "citation": "Dewitz, J., 2024, National Land Cover Database (NLCD) Tree Canopy Cover Products: U.S. Geological Survey data release, https://doi.org/10.5066/P9JZ7AO3",
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "request": dict(params),
        "stats": {"valid_cells": int(valid.size), "mean": round(float(valid.mean()), 2) if valid.size else None,
                  "min": int(valid.min()) if valid.size else None, "max": int(valid.max()) if valid.size else None},
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(side, indent=1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2021, choices=list(YEARS))
    ap.add_argument("--data", default=str(BACKEND.parent / "data"))
    a = ap.parse_args()
    out = fetch(Path(a.data), a.year)
    print(out, f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
