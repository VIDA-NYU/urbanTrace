"""Raster datasets in the catalog (PLAN.md, phase 6): tree canopy first.

A raster is a GeoTIFF in ``data/raster/<stem>.tif`` with a sidecar ``<stem>.json`` saying what its
values are (title, units, value kind, no-data value, band name, source, license, year). Rasters are
listed with the vector datasets but kept apart from them (``catalog.list_stems`` is vector only):
they enter plans as raster sources, summarized onto zones or H3 cells by urbanweave's
``zonal_stats`` (exact cell coverage with exactextract on a projected grid), e.g. the mean percent
tree canopy of each neighborhood, each cell weighted by the share of it inside the neighborhood.
"""
from __future__ import annotations

import json
from pathlib import Path


class RasterError(ValueError):
    pass


def folder(data_dir) -> Path:
    return Path(data_dir) / "raster"


def list_stems(data_dir) -> list[str]:
    f = folder(data_dir)
    return sorted(p.stem for p in f.glob("*.tif") if (f / f"{p.stem}.json").exists()) if f.exists() else []


def path(data_dir, stem: str) -> Path | None:
    p = folder(data_dir) / f"{stem}.tif"
    return p if p.exists() else None


def is_raster(data_dir, stem: str) -> bool:
    return path(data_dir, stem) is not None


def sidecar(data_dir, stem: str) -> dict:
    p = folder(data_dir) / f"{stem}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def profile(data_dir, stem: str) -> dict:
    """The listing's metadata for a raster, in the shape the sidebar and nodes read for vector
    datasets: name, geometricType "Raster", one column per band, bounds, and the sidecar."""
    s = sidecar(data_dir, stem)
    band = s.get("band") or "band_1"
    return {
        "name": s.get("title") or stem.replace("_", " "), "description": s.get("description"),
        "geometricType": "Raster", "nb_rows": (s.get("stats") or {}).get("valid_cells"),
        "columns": [{"name": band, "structural_type": "http://schema.org/Float", "units": s.get("units"),
                     "value_kind": s.get("value_kind"), **{k: v for k, v in (s.get("stats") or {}).items() if k in ("mean", "min", "max")}}],
        "raster": {k: s.get(k) for k in ("units", "value_kind", "resolution_m", "crs", "bounds_wgs84", "year", "nodata",
                                           "source_url", "publisher", "license", "retrieved_at")},
        "spatial_coverage": [{"type": "latlong", "ranges": [{"range": {"type": "envelope", "coordinates": [
            [s["bounds_wgs84"][0], s["bounds_wgs84"][3]], [s["bounds_wgs84"][2], s["bounds_wgs84"][1]]]}}]}] if s.get("bounds_wgs84") else [],
    }


def read(data_dir, stem: str, window_wgs84=None):
    """The raster as urbanweave reads it, with the sidecar's value kind, units and band name. With
    *window_wgs84* (a lon/lat box), only that part is read, padded by a few cells."""
    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.warp import transform_bounds
    import urbanweave as uw
    p = path(data_dir, stem)
    if p is None:
        raise RasterError(f"Raster {stem!r} is not in the catalog.")
    s = sidecar(data_dir, stem)
    with rasterio.open(p) as src:
        window = None
        if window_wgs84 is not None:
            b = transform_bounds("EPSG:4326", src.crs, *window_wgs84)
            pad = 3 * max(abs(src.res[0]), abs(src.res[1]))
            window = from_bounds(b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad, src.transform).round_offsets().round_lengths()
            window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(1, window=window, masked=True)
        transform = src.window_transform(window) if window is not None else src.transform
        nodata = s.get("nodata", src.nodata)
        if nodata is not None:
            arr = np.ma.masked_equal(arr, nodata) if not np.ma.is_masked(arr) else np.ma.masked_where(arr.data == nodata, arr)
        return uw.read_raster(arr.astype("float32"), transform=transform, crs=src.crs,
                              value_kind=s.get("value_kind"), units=s.get("units"), names=[s.get("band") or "band_1"])


def preview_png(data_dir, stem: str, max_px: int = 512) -> bytes:
    """A small picture of the raster (transparent where there is no data), for the dataset node."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    p = path(data_dir, stem)
    if p is None:
        raise RasterError(f"Raster {stem!r} is not in the catalog.")
    s = sidecar(data_dir, stem)
    with rasterio.open(p) as src:
        scale = max(src.width, src.height) / max_px
        h, w = max(1, int(src.height / scale)), max(1, int(src.width / scale))
        a = src.read(1, out_shape=(h, w), resampling=Resampling.average if scale > 1 else Resampling.nearest).astype(float)
        nodata = s.get("nodata", src.nodata)
    valid = np.isfinite(a) & (a != nodata if nodata is not None else True)
    lo, hi = (s.get("display_range") or [np.nanmin(a[valid]) if valid.any() else 0, np.nanmax(a[valid]) if valid.any() else 1])
    t = np.clip((a - lo) / ((hi - lo) or 1), 0, 1)
    # light to dark green
    c0, c1 = np.array([247, 252, 245]), np.array([0, 90, 50])
    rgb = (c0 + (c1 - c0) * t[..., None]).astype("uint8")
    alpha = np.where(valid & (a > lo), 215, 0).astype("uint8")
    from rasterio.io import MemoryFile
    with MemoryFile() as mem:
        with mem.open(driver="PNG", width=w, height=h, count=4, dtype="uint8") as png:
            for i in range(3):
                png.write(rgb[..., i], i + 1)
            png.write(alpha, 4)
        return mem.read()
