"""UrbanTrace's version is recorded where it helps later: saved collections, exports, the API."""
import version


def test_version_is_recorded(client, catalog, tmp_path):
    doc = client.post("/api/collections", json={"name": "v"}).json()
    assert doc["saved_with"] == f"UrbanTrace {version.VERSION}"
    import export
    pkg = export.build(str(catalog), {"name": "v", "datasets": [{"id": "test_points"}]}, tmp_path / "p.zip", embed="always")
    assert pkg["urbantrace:software"]["urbantrace"] == version.VERSION and pkg["urbantrace:software"]["urbanweave"]
    assert client.get("/openapi.json").json()["info"]["version"] == version.VERSION
