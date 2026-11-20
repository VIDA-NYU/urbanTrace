"""Collections, origins and export (redesign phase 1), on the synthetic catalog."""
import io
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest

import catalog as cat
import main


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))


def _collection(client, **fields):
    body = {"name": "After-school needs", "goal": "Where are after-school programs most needed?",
            "datasets": [{"id": "test_points", "columns": ["count"], "value_kinds": {"count": "extensive"},
                          "added_by": "copilot", "rationale": "Program sites."},
                         {"id": "test_rates", "columns": ["rate"], "value_kinds": {"rate": "intensive"},
                          "added_by": "user", "rationale": None}], **fields}
    r = client.post("/api/collections", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _unzip(response):
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content))


def test_collection_lifecycle(client, catalog, store):
    doc = _collection(client)
    assert doc["schema"] == "urbantrace.collection/1" and doc["id"].startswith("c_")
    listed = client.get("/api/collections").json()["collections"]
    assert [c["id"] for c in listed] == [doc["id"]] and listed[0]["datasets"] == 2
    updated = client.put(f"/api/collections/{doc['id']}", json={"notes": "first pass"}).json()
    assert updated["notes"] == "first pass" and updated["goal"] == doc["goal"]     # untouched fields kept
    assert client.delete(f"/api/collections/{doc['id']}").status_code == 200
    assert client.get(f"/api/collections/{doc['id']}").status_code == 404
    assert client.get("/api/collections/not-an-id").status_code == 404


def test_export_without_licenses_embeds_nothing_by_default(client, catalog, store):
    doc = _collection(client)
    z = _unzip(client.post(f"/api/collections/{doc['id']}/export", json={}))
    package = json.loads(z.read("datapackage.json"))
    assert package["resources"] == []
    # No origin is recorded for the fixtures, so they cannot be referenced either.
    assert {n["name"] for n in package["urbantrace:not_included"]} == {"test_points", "test_rates"}
    readme = z.read("README.md").decode()
    assert "Where are after-school programs most needed?" in readme and "Program sites." in readme
    assert "Origin unknown for" in readme


def test_export_embeds_licensed_datasets_and_references_the_rest(client, catalog, store):
    cat.set_origin(catalog, "test_points", {"source_url": "https://example.org/points", "license": "CC0-1.0",
                                                "publisher": "Example"})
    cat.set_origin(catalog, "test_rates", {"source_url": "https://example.org/rates", "license": None})
    doc = _collection(client)
    z = _unzip(client.post(f"/api/collections/{doc['id']}/export", json={"formats": ["parquet", "gpkg"]}))
    package = json.loads(z.read("datapackage.json"))
    paths = {r["path"] for r in package["resources"]}
    assert paths == {"data/sources/test_points.parquet", "data/sources/test_points.gpkg"}
    assert [r["name"] for r in package["urbantrace:references"]] == ["test_rates"]
    res = next(r for r in package["resources"] if r["path"].endswith(".parquet"))
    assert res["hash"].startswith("sha256:") and res["urbantrace:origin"]["license"] == "CC0-1.0"
    assert {"name": "count", "type": "integer", "urbantrace:value_kind": "extensive"} in res["schema"]["fields"]
    gdf = gpd.read_parquet(io.BytesIO(z.read("data/sources/test_points.parquet")))
    assert list(gdf.columns) == ["count", "geometry"] and len(gdf) == 6        # only the columns used


def test_export_always_embeds_everything(client, catalog, store):
    doc = _collection(client)
    z = _unzip(client.post(f"/api/collections/{doc['id']}/export", json={"embed": "always", "formats": ["gpkg"]}))
    names = set(z.namelist())
    assert {"data/sources/test_points.gpkg", "data/sources/test_rates.gpkg", "datapackage.json", "README.md"} <= names


def test_export_rejects_unknown_embed_mode(client, catalog, store):
    doc = _collection(client)
    r = client.post(f"/api/collections/{doc['id']}/export", json={"embed": "sometimes"})
    assert r.status_code == 400


def test_result_export_carries_provenance(client, catalog):
    geojson = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"zone_id": "0", "value": 1.5},
         "geometry": {"type": "Polygon", "coordinates": [[[-74, 40.75], [-73.98, 40.75], [-73.98, 40.76], [-74, 40.75]]]}}]}
    r = client.post("/api/results/export", json={"name": "Zone result", "geojson": geojson,
                                                 "provenance": {"request": {"resolution": 8}}})
    z = _unzip(r)
    assert "provenance.json" in z.namelist() and "data/results/zone-result_result.gpkg" in z.namelist()
    assert json.loads(z.read("provenance.json"))["request"]["resolution"] == 8


def test_geoparquet_copy_is_preferred(client, catalog, monkeypatch):
    sys.path.insert(0, str(Path(main.__file__).resolve().parents[1] / "tools"))
    from convert_to_geoparquet import convert
    convert(catalog / "geojson" / "test_points.geojson", catalog / "geoparquet" / "test_points.parquet")
    assert cat.dataset_path(catalog, "test_points").suffix == ".parquet"
    assert list(cat.load(catalog, "test_points", ["count"]).columns) == ["count", "geometry"]
    monkeypatch.setattr(main, "ENGINE", "urbanweave")
    body = {"variables": [{"dataset_path": "test_points.geojson", "target_column": "count", "output_name": "c",
                           "allocation_operator": "BinaryContainment", "grid_aggregation_operator": "SumAggregation"}],
            "resolution": 9}
    r = client.post("/api/integrate_multivariate", json=body)
    assert r.status_code == 200, r.text
    assert sum(c["variables"]["c"] for c in r.json()["data"].values()) == 22


def test_unknown_origin_is_explicit(catalog):
    rec = cat.origin(catalog, "test_points")
    assert rec["status"] == "unknown" and rec["source_url"] is None
