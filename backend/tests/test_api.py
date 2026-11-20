"""API tests for the catalog and integration endpoints, on the synthetic catalog in conftest.py."""
import pytest

import main
from conftest import POINTS


def _variable(dataset, column, allocation, aggregation, zmap=None, zagg=None):
    return {"dataset_path": f"{dataset}.geojson", "target_column": column, "output_name": f"{dataset}__{column}",
            "allocation_operator": allocation, "grid_aggregation_operator": aggregation,
            "zoning_mapping_operator": zmap, "zoning_aggregation_operator": zagg}


def _integrate(client, variables, **kw):
    body = {"variables": variables, "resolution": 9, "output_mode": "grid", **kw}
    return client.post("/api/integrate_multivariate", json=body)


@pytest.fixture(params=["urbanweave", "legacy"])
def engine(request, monkeypatch):
    """Both engines, for behaviour they share (validation, errors)."""
    monkeypatch.setattr(main, "ENGINE", request.param)
    return request.param


@pytest.fixture()
def urbanweave_engine(monkeypatch):
    monkeypatch.setattr(main, "ENGINE", "urbanweave")
    return "urbanweave"


def test_datasets_lists_the_catalog(client, catalog):
    names = {d["id"] for d in client.get("/datasets").json()["datasets"]}
    assert names == {"test_points", "test_rates", "test_zones"}


def test_operators_come_from_the_registry(client, monkeypatch):
    monkeypatch.setattr(main, "ENGINE", "urbanweave")
    body = client.get("/api/operators").json()
    assert body["registry"]["package"] == "urbanweave"
    assert "BinaryContainment" in body["geometry_constraints"]["Point"]
    assert "ProportionalAreaWeighted" not in body["geometry_constraints"]["Point"]


def test_point_counts_are_conserved_on_the_grid(client, catalog, urbanweave_engine):
    # Includes the point at the corner of the extent, whose cell center lies outside the sources'
    # bounding box (grid_covers_sources); the legacy grid dropped it.
    r = _integrate(client, [_variable("test_points", "count", "BinaryContainment", "SumAggregation")])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "urbanweave"
    total = sum(cell["variables"]["test_points__count"] for cell in body["data"].values())
    assert total == pytest.approx(sum(c for _, _, c in POINTS))
    assert body["reports"]["test_points__count"]["allocation"]["match"]["sources"]["unmatched"] == {}


def test_zones_receive_sums_and_weighted_means(client, catalog, urbanweave_engine):
    variables = [
        _variable("test_points", "count", "BinaryContainment", "SumAggregation", "CentroidZoning", "SumZoning"),
        _variable("test_rates", "rate", "ProportionalAreaWeighted", "WeightedMeanAggregation",
                  "AreaWeightedZoning", "WeightedMeanZoning"),
    ]
    r = _integrate(client, variables, zones_path="test_zones.geojson", output_mode="both")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["zone_count"] == 2
    zones = {f["properties"]["zone_id"]: f["properties"] for f in body["geojson"]["features"]}
    # Centroid zoning gives each cell to at most one zone, so the zones hold at most the total.
    assert 0 < sum(z["test_points__count"] for z in zones.values()) <= 22
    # Each variable is zoned from its own cells with its own mapping (own_cells_only,
    # own_zoning_mapping), so the rate stays within the range of its sources' values.
    for z in zones.values():
        assert 0.2 <= z["test_rates__rate"] <= 0.6


def test_invalid_operator_for_geometry_is_a_400(client, catalog, engine):
    r = _integrate(client, [_variable("test_points", "count", "ProportionalAreaWeighted", "SumAggregation")])
    assert r.status_code == 400
    assert "not valid for Point" in r.json()["detail"]


def test_missing_dataset_is_a_404(client, catalog, engine):
    r = _integrate(client, [_variable("no_such_dataset", "count", "BinaryContainment", "SumAggregation")])
    assert r.status_code == 404


def test_reports_and_repairs_are_returned(client, catalog, urbanweave_engine):
    r = _integrate(client, [_variable("test_rates", "rate", "ProportionalAreaWeighted", "WeightedMeanAggregation")])
    assert r.status_code == 200, r.text
    report = r.json()["reports"]["test_rates__rate"]
    assert report["repaired_geometries"]["count"] == 1   # the bowtie
    assert report["allocation"]["match"]["sources"]["matched"] == 2
    assert "own_zoning_mapping" in r.json()["changes"]


def test_engines_agree_on_the_synthetic_catalog(client, catalog, monkeypatch):
    variables = [
        _variable("test_points", "count", "BinaryContainment", "SumAggregation", "AreaWeightedZoning", "SumZoning"),
        _variable("test_rates", "rate", "ProportionalAreaWeighted", "WeightedMeanAggregation",
                  "AreaWeightedZoning", "WeightedMeanZoning"),
    ]
    out = {}
    for engine in ("legacy", "urbanweave"):
        monkeypatch.setattr(main, "ENGINE", engine)
        r = _integrate(client, variables, zones_path="test_zones.geojson", output_mode="both")
        assert r.status_code == 200, r.text
        out[engine] = r.json()
    old, new = out["legacy"]["data"], out["urbanweave"]["data"]
    # urbanweave keeps every legacy cell, plus the edge cells the legacy grid dropped.
    assert set(old) <= set(new)
    for cell in old:
        assert new[cell]["variables"]["test_points__count"] == old[cell]["variables"]["test_points__count"]
    recovered = sum(new[c]["variables"]["test_points__count"] for c in set(new) - set(old))
    assert sum(v["variables"]["test_points__count"] for v in old.values()) + recovered == pytest.approx(22)
    # Rates in the cells both engines have agree up to UTM vs Web Mercator weights.
    for cell in old:
        if old[cell]["variables"]["test_rates__rate"]:
            assert new[cell]["variables"]["test_rates__rate"] == pytest.approx(
                old[cell]["variables"]["test_rates__rate"], rel=1e-3)
