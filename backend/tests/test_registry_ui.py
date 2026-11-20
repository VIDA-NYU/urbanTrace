"""Registry-driven operators, parameters, checked copilot recommendations and results in exports
(redesign phase 3), on the synthetic catalog."""
import io
import json
import zipfile

import pytest

import main
import weave_engine


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ENGINE", "urbanweave")
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))


def test_operators_describe_each_legacy_name(client):
    body = client.get("/api/operators").json()
    gauss = body["legacy"]["allocation"]["GaussianKernel"]
    assert gauss["method"] == "gaussian" and gauss["params"]["bandwidth"]["unit"] == "m"
    assert body["legacy"]["zoning_aggregation"]["WeightedMeanZoning"]["value_kinds"] == ["intensive"]


def _gauss(**params):
    return {"variables": [{"dataset_path": "test_points.geojson", "target_column": "count", "output_name": "c",
                           "allocation_operator": "GaussianKernel", "grid_aggregation_operator": "SumAggregation",
                           "allocation_params": params}], "resolution": 9}


def test_allocation_params_reach_the_method(client, catalog):
    wide = client.post("/api/integrate_multivariate", json=_gauss(bandwidth=800)).json()
    narrow = client.post("/api/integrate_multivariate", json=_gauss(bandwidth=50)).json()
    assert len(narrow["data"]) < len(wide["data"])                # a narrower kernel reaches fewer cells
    match = wide["reports"]["c"]["allocation"]["match"]
    assert match["params"]["bandwidth"] == 800


def test_unknown_allocation_param_is_a_400(client, catalog):
    r = client.post("/api/integrate_multivariate", json=_gauss(radius=3))
    assert r.status_code == 400 and "no parameter radius" in r.json()["detail"]


def test_zoning_problems_follow_the_registry():
    assert weave_engine.zoning_problems("AreaWeightedZoning", "SumZoning", "Polygon", "Extensive") == []
    reasons = weave_engine.zoning_problems("AreaWeightedZoning", "SumZoning", "LineString", "Intensive")
    assert any("LineString" in r for r in reasons) and any("intensive" in r for r in reasons)


def _recommend(client, zone_geometry):
    return client.post("/api/v1/copilot/recommend-operators", json={
        "target_zoning": {"dataset_name": "test_zones", "geometry_type": zone_geometry},
        "source_variables": [{"dataset_name": "test_points", "column_name": "count", "original_geometry": "Point"}]})


def test_recommendations_fit_the_zone_geometry(client, catalog):
    for geometry in ("Polygon", "LineString", "Point"):
        r = _recommend(client, geometry)
        assert r.status_code == 200, r.text
        rec = r.json()[0]
        assert weave_engine.zoning_problems(rec["zoningMapping"], rec["zoningAggregation"], geometry,
                                            rec["classification"]) == []


def test_a_recommendation_the_registry_rejects_is_replaced(client, catalog, monkeypatch):
    bad = [{"dataset_name": "test_points", "column_name": "count", "classification": "Intensive",
            "zoningMapping": "AreaWeightedZoning", "zoningAggregation": "SumZoning", "reasoning": "bad", "engine": "test"}]
    monkeypatch.setattr(main, "_heuristic_recommendations", lambda payload: bad)
    rec = _recommend(client, "Polygon").json()[0]
    assert rec["registry_check"]["replaced"]["zoningAggregation"] == "SumZoning"
    assert rec["zoningAggregation"] != "SumZoning" and rec["registry_check"]["fixed"] is True


def test_export_reruns_integrations_into_results(client, catalog):
    request = {"variables": [{"dataset_path": "test_points.geojson", "target_column": "count", "output_name": "crashes",
                              "allocation_operator": "BinaryContainment", "grid_aggregation_operator": "SumAggregation",
                              "zoning_mapping_operator": "AreaWeightedZoning", "zoning_aggregation_operator": "SumZoning"}],
               "resolution": 9, "zones_path": "test_zones.geojson", "output_mode": "both"}
    doc = client.post("/api/collections", json={
        "name": "Crashes", "datasets": [{"id": "test_points", "columns": ["count"], "value_kinds": {"count": "extensive"}}],
        "integrations": [{"id": "r1", "name": "Crashes by zone", "request": request},
                         {"id": "r2", "name": "Broken", "request": {"variables": [{"dataset_path": "missing.geojson"}]}}],
    }).json()
    r = client.post(f"/api/collections/{doc['id']}/export", json={"formats": ["parquet"]})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert {"data/results/crashes-by-zone_grid.parquet", "data/results/crashes-by-zone_zones.parquet"} <= set(z.namelist())
    package = json.loads(z.read("datapackage.json"))
    res = next(r for r in package["resources"] if r["path"].endswith("_zones.parquet"))
    assert res["urbantrace:result"]["request"]["zones_path"] == "test_zones.geojson"
    readme = z.read("README.md").decode()
    assert "## Integrations" in readme and "6 of 6 features matched by contain" in readme
    assert "Broken could not be rerun" in readme
