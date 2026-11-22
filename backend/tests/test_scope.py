"""Study area, coverage and time (redesign phase 2), on the synthetic catalog."""
import io
import json
import zipfile

import geopandas as gpd
import pytest


WEST = {"kind": "zones", "dataset": "test_zones", "column": "zone", "values": ["west"], "name": "West"}


@pytest.fixture(autouse=True)
def collections_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))


def test_study_area_options_and_resolve(client, catalog):
    opts = client.get("/api/study-area/options/test_zones").json()
    assert {"name": "zone", "values": ["east", "west"]} in opts["columns"]
    summary = client.post("/api/study-area/resolve", json=WEST).json()
    assert summary["bbox"] == pytest.approx([-74.0, 40.75, -73.98, 40.76])
    assert 1.5 < summary["area_km2"] < 2.5


def test_catalog_index_has_time_and_bbox(client, catalog):
    rows = {d["id"]: d for d in client.get("/api/catalog/index").json()["datasets"]}
    assert rows["test_points"]["time"]["start"] == "2019-03-01"
    # The bbox comes from the density grid (the points' cells cover the western half only).
    assert rows["test_points"]["bbox"] == pytest.approx([-74.0, 40.75, -73.98, 40.76])
    assert rows["test_zones"]["time"] is None


def test_datasets_without_a_profile_grid_get_one_from_their_data(client, catalog):
    import scope
    # test_zones has no profile: its grid and bbox are computed from the polygons and cached.
    rows = {d["id"]: d for d in client.get("/api/catalog/index").json()["datasets"]}
    x1, y1, x2, y2 = rows["test_zones"]["bbox"]
    assert x1 <= -74.0 and x2 >= -73.96 and y1 <= 40.75 and y2 >= 40.76
    assert (catalog / ".extent_cache.json").exists()
    cells, _, source = scope.dataset_cells(str(catalog), "test_zones")
    assert source == "data" and cells and all(c[4] >= 1 for c in cells)
    out = client.post("/api/coverage", json={"datasets": ["test_zones"],
                                              "study_area": {"kind": "bbox", "bbox": [-74.0, 40.75, -73.96, 40.76]}}).json()
    assert out["datasets"]["test_zones"]["grid_from"] == "data"
    assert out["datasets"]["test_zones"]["share_of_area"] == 1.0


def test_bbox_ignores_a_swapped_profile_envelope():
    import scope
    prof = {"spatial_coverage": [{"ranges": [{"range": {"type": "envelope", "coordinates": [[40.76, -74.0], [40.75, -73.96]]}}],
                                  "grid": {"bounds": [-74.0, 40.75, -73.96, 40.76], "cell_degrees": [0.005, 0.005],
                                           "cells": [[0, 0, 3], [7, 1, 2]]}}]}
    _, bounds = scope.coverage_cells(prof)
    assert bounds == pytest.approx([-74.0, 40.75, -73.96, 40.76])


def test_coverage_shares_of_the_study_area(client, catalog):
    whole = {"kind": "bbox", "bbox": [-74.0, 40.75, -73.96, 40.76]}
    out = client.post("/api/coverage", json={"datasets": ["test_points", "test_rates"], "study_area": whole}).json()
    assert out["datasets"]["test_rates"]["share_of_area"] == 1.0
    # Points are measured by spread: their cells cover the western half of the box.
    assert out["datasets"]["test_points"]["measure"] == "spread"
    assert out["datasets"]["test_points"]["share_of_area"] == pytest.approx(0.5, abs=0.01)
    assert out["datasets"]["test_points"]["points_inside"] == 8
    assert {f["properties"]["n"] for f in out["features"]} == {1, 2}


def test_checks_warn_about_time_and_coverage(client, catalog):
    doc = {"datasets": [{"id": "test_points"}, {"id": "test_rates"}],
           "study_area": {"kind": "bbox", "bbox": [-73.98, 40.75, -73.96, 40.76]}}
    kinds = {w["kind"]: w for w in client.post("/api/collections/check", json=doc).json()["warnings"]}
    assert "time_no_overlap" in kinds and "2010-12-31" in kinds["time_no_overlap"]["message"]
    # The points are all in the western half, the study area is the eastern half.
    assert kinds["coverage_none"]["datasets"] == ["test_points"]
    # A time window on the rates that reaches 2019 removes the period warning.
    doc["datasets"][1]["time_window"] = {"start": "2005-01-01", "end": "2020-01-01"}
    kinds = {w["kind"] for w in client.post("/api/collections/check", json=doc).json()["warnings"]}
    assert "time_no_overlap" not in kinds


def test_export_clips_to_the_study_area_and_lists_warnings(client, catalog):
    doc = client.post("/api/collections", json={"name": "West side", "study_area": WEST,
                                                "datasets": [{"id": "test_points"}, {"id": "test_rates"}]}).json()
    r = client.post(f"/api/collections/{doc['id']}/export", json={"embed": "always", "formats": ["gpkg"]})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    gdf = gpd.read_file(io.BytesIO(z.read("data/sources/test_points.gpkg")))
    assert len(gdf) == 3
    readme = z.read("README.md").decode()
    assert "## Study area" in readme and "The periods do not overlap" in readme
    package = json.loads(z.read("datapackage.json"))
    assert package["urbantrace:export"]["clipped"] is True


def test_points_spread_over_the_area_are_not_partial(client, catalog):
    import json
    # Few points, one per corner of the box: a cell share would be tiny, the spread is the whole box.
    prof = json.loads((catalog / "metadata_v2" / "test_points.json").read_text())
    prof["spatial_coverage"][0]["grid"]["cells"] = [[0, 0, 1], [7, 0, 1], [0, 1, 1], [7, 1, 1]]
    (catalog / "metadata_v2" / "test_points.json").write_text(json.dumps(prof))
    whole = {"kind": "bbox", "bbox": [-74.0, 40.75, -73.96, 40.76]}
    out = client.post("/api/coverage", json={"datasets": ["test_points"], "study_area": whole}).json()
    assert out["datasets"]["test_points"]["share_of_area"] == 1.0
    warnings = client.post("/api/collections/check", json={"datasets": [{"id": "test_points"}], "study_area": whole}).json()
    assert not [w for w in warnings["warnings"] if w["kind"].startswith("coverage")]


def test_no_data_in_the_study_area_is_its_own_warning(client, catalog):
    far = {"kind": "bbox", "bbox": [-73.90, 40.80, -73.85, 40.85]}
    warnings = client.post("/api/collections/check", json={"datasets": [{"id": "test_points"}], "study_area": far}).json()
    assert [w["kind"] for w in warnings["warnings"]] == ["coverage_none"]


def test_catalog_in_area_measures_each_dataset(client, catalog):
    west = {"kind": "bbox", "bbox": [-74.0, 40.75, -73.98, 40.76]}
    out = client.post("/api/catalog/in-area", json=west).json()["datasets"]
    assert out["test_points"]["measure"] == "spread" and out["test_points"]["points_inside"] > 0
    assert out["test_zones"]["measure"] == "cells" and out["test_zones"]["share_of_area"] == 1.0
    far = {"kind": "bbox", "bbox": [-73.90, 40.80, -73.85, 40.85]}
    out = client.post("/api/catalog/in-area", json=far).json()["datasets"]
    assert out["test_points"]["share_of_area"] == 0 and out["test_points"]["points_inside"] == 0
    assert client.post("/api/catalog/in-area", json={"kind": "bbox", "bbox": [1, 1, 0, 0]}).status_code == 400
