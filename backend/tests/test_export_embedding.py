"""When a source is embedded in an export: a recorded license, and a size limit judged after
clipping to the study area (a large citywide file can be embedded for one neighborhood)."""
import json
import zipfile

import export
import scope


def _license(catalog, stem):
    (catalog / "origins.json").write_text(json.dumps({stem: {"source_url": "https://example.org/x", "license": "CC0"}}))


def test_size_is_judged_after_clipping(catalog, tmp_path, monkeypatch):
    # 3,000 points over both zones, a tenth of them in the west
    import numpy as np
    rng = np.random.default_rng(0)
    xs = np.r_[rng.uniform(-74.0, -73.98, 300), rng.uniform(-73.98, -73.96, 2700)]
    ys = rng.uniform(40.75, 40.76, 3000)
    (catalog / "geojson" / "test_many.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"v": i}, "geometry": {"type": "Point", "coordinates": [float(x), float(y)]}}
        for i, (x, y) in enumerate(zip(xs, ys))]}))
    _license(catalog, "test_many")
    whole = (catalog / "geojson" / "test_many.geojson").stat().st_size
    monkeypatch.setattr(export, "EMBED_LIMIT_BYTES", whole // 3)      # the whole file is over the limit
    coll = {"name": "c", "datasets": [{"id": "test_many"}]}
    # Without a study area: referenced
    pkg = export.build(str(catalog), coll, tmp_path / "a.zip")
    assert not any(r["path"].startswith("data/sources/") for r in pkg["resources"])
    # Clipped to the western zone it is small: embedded
    area = scope.study_area_geometry(str(catalog), {"kind": "zones", "dataset": "test_zones", "column": "zone", "values": ["west"]})
    pkg = export.build(str(catalog), coll, tmp_path / "b.zip", area=area)
    assert any(r["path"] == "data/sources/test_many.parquet" for r in pkg["resources"])
    assert "data/sources/test_many.parquet" in zipfile.ZipFile(tmp_path / "b.zip").namelist()


def test_too_large_even_after_clipping_is_referenced(catalog, tmp_path, monkeypatch):
    _license(catalog, "test_points")
    monkeypatch.setattr(export, "EMBED_LIMIT_BYTES", 10)
    area = scope.study_area_geometry(str(catalog), {"kind": "bbox", "bbox": [-74.0, 40.75, -73.96, 40.76]})
    pkg = export.build(str(catalog), {"name": "c", "datasets": [{"id": "test_points"}]}, tmp_path / "c.zip", area=area)
    assert not any(r["path"].startswith("data/sources/") for r in pkg["resources"])
    assert "data/sources/test_points.parquet" not in zipfile.ZipFile(tmp_path / "c.zip").namelist()
    assert any("after clipping" in r["reason"] for r in pkg["urbantrace:references"])
