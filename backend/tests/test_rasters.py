"""Raster datasets (rasters.py) as plan sources: zonal statistics onto zones and H3 cells. A small
synthetic raster stands in for tree canopy."""
import json
import zipfile

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("exactextract")


@pytest.fixture()
def canopy(catalog):
    """30 m cells in UTM 18N over the test box: 20 % west of -73.98, 60 % east of it, a no-data strip."""
    from rasterio.transform import from_origin
    from rasterio.warp import transform_bounds
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", "EPSG:32618", -74.005, 40.745, -73.955, 40.765)
    w, h = int((x1 - x0) // 30) + 1, int((y1 - y0) // 30) + 1
    tr = from_origin(x0, y1, 30, 30)
    xs = x0 + 30 * (np.arange(w) + 0.5)
    from pyproj import Transformer
    lon = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True).transform(xs, np.full(w, (y0 + y1) / 2))[0]
    row = np.where(lon < -73.98, 20, 60).astype("uint8")
    a = np.tile(row, (h, 1))
    a[:2, :] = 255                                            # no data along the top
    folder = catalog / "raster"
    folder.mkdir()
    with rasterio.open(folder / "test_canopy.tif", "w", driver="GTiff", width=w, height=h, count=1, dtype="uint8",
                       crs="EPSG:32618", transform=tr, nodata=255) as dst:
        dst.write(a, 1)
    (folder / "test_canopy.json").write_text(json.dumps({
        "title": "Test canopy", "band": "canopy_pct", "units": "percent", "value_kind": "intensive", "nodata": 255,
        "display_range": [0, 100], "resolution_m": 30, "license": "Public domain", "source_url": "https://example.org/canopy",
        "bounds_wgs84": [-74.005, 40.745, -73.955, 40.765], "stats": {"valid_cells": int((a != 255).sum()), "mean": 40}}))
    return folder


def _plan(target):
    return {"version": 1, "sources": {"c": {"kind": "raster", "urbantrace": {"dataset": "test_canopy"}}},
            "targets": {"t": target},
            "steps": [{"id": "s", "source": "c", "convert": {"method": "zonal_stats", "target": "t",
                       "aggregate": [{"method": "weighted_mean", "column": "canopy_pct", "as": "canopy"}]}}]}


def test_canopy_per_zone(client, canopy):
    plan = _plan({"kind": "zones", "urbantrace": {"dataset": "test_zones"}})
    assert client.post("/api/plan/validate", json={"plan": plan}).json()["ok"]
    r = client.post("/api/plan/run", json={"plan": plan, "outputs": ["s"]})
    assert r.status_code == 200, r.text
    out = r.json()["steps"]["s"]
    by_zone = {f["properties"]["label"]: f["properties"]["canopy"] for f in out["geojson"]["features"]}
    assert by_zone["west"] == pytest.approx(20, abs=0.5) and by_zone["east"] == pytest.approx(60, abs=0.5)
    assert out["kinds"]["canopy"] == "intensive"
    assert r.json()["reports"]["s"]["conversion"] == "zonal_stats"
    assert r.json()["inputs"]["c"]["kind"] == "raster"


def test_canopy_per_h3_cell_in_a_study_area(client, canopy):
    area = {"kind": "zones", "dataset": "test_zones", "column": "zone", "values": ["east"], "name": "East"}
    r = client.post("/api/plan/run", json={"plan": _plan({"kind": "h3", "resolution": 9}), "study_area": area, "outputs": ["s"]})
    assert r.status_code == 200, r.text
    vals = [v for v in r.json()["steps"]["s"]["columns"]["canopy"] if v is not None]
    assert vals and np.median(vals) == pytest.approx(60, abs=1)


def test_listing_preview_and_index(client, canopy):
    listed = {d["id"]: d for d in client.get("/datasets").json()["datasets"]}
    assert listed["test_canopy"]["metadata"]["geometricType"] == "Raster"
    assert listed["test_canopy"]["metadata"]["columns"][0]["name"] == "canopy_pct"
    png = client.get("/api/rasters/test_canopy/preview.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    index = {d["id"]: d for d in client.get("/api/catalog/index").json()["datasets"]}
    assert index["test_canopy"]["geometry"] == "Raster"


def test_missing_raster(client, canopy):
    plan = _plan({"kind": "zones", "urbantrace": {"dataset": "test_zones"}})
    plan["sources"]["c"]["urbantrace"]["dataset"] = "nope"
    v = client.post("/api/plan/validate", json={"plan": plan}).json()
    assert not v["ok"] and "not in the catalog" in json.dumps(v["problems"])


def test_export_carries_the_geotiff(catalog, canopy, tmp_path):
    import export
    out = tmp_path / "p.zip"
    pkg = export.build(str(catalog), {"name": "c", "datasets": [{"id": "test_canopy"}]}, out, embed="always")
    res = next(r for r in pkg["resources"] if r["path"].endswith(".tif"))
    assert res["schema"]["fields"][0]["unit"] == "percent"
    assert "data/sources/test_canopy.tif" in zipfile.ZipFile(out).namelist()
