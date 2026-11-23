"""API tests for the catalog and operator endpoints, on the synthetic catalog in conftest.py."""


def test_datasets_lists_the_catalog(client, catalog):
    names = {d["id"] for d in client.get("/datasets").json()["datasets"]}
    assert names == {"test_points", "test_rates", "test_zones"}


def test_operators_come_from_the_registry(client):
    body = client.get("/api/operators").json()
    assert body["registry"]["package"] == "urbanweave"
    assert "contain" in body["registry"]["matching"] and "count" in body["registry"]["aggregation"]
