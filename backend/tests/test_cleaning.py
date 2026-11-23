"""Data checks and corrections with atlas-clean (cleaning.py), on the synthetic catalog."""
import io
import json
import zipfile

import pytest

pytest.importorskip("atlas_clean")

import catalog as cat  # noqa: E402
import cleaning  # noqa: E402
from conftest import DATES, POINTS, _fc  # noqa: E402


@pytest.fixture()
def swapped(catalog, monkeypatch, tmp_path):
    """test_swapped: the test points with latitude and longitude exchanged."""
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))
    monkeypatch.setenv("URBANTRACE_PLAN_CACHE", str(tmp_path / "plan_cache"))
    (catalog / "geojson" / "test_swapped.geojson").write_text(json.dumps(_fc([
        {"type": "Feature", "properties": {"count": c, "date": DATES[i]},
         "geometry": {"type": "Point", "coordinates": [y, x]}} for i, (x, y, c) in enumerate(POINTS)])))
    return "test_swapped"


def _plan():
    return {"version": 1,
            "sources": {"s": {"kind": "vector", "columns": {"count": {"kind": "extensive"}},
                              "urbantrace": {"dataset": "test_swapped"}}},
            "targets": {"zones": {"kind": "zones", "urbantrace": {"dataset": "test_zones"}}},
            "steps": [{"id": "st", "source": "s", "match": {"method": "contain", "target": "zones"},
                       "aggregate": [{"method": "sum", "column": "count", "as": "total", "fill_empty": 0}]}]}


def test_check_finds_the_swap_and_proposes_a_fix(client, catalog, swapped):
    out = client.post(f"/api/datasets/{swapped}/check").json()
    assert [i["detector"] for i in out["issues"]] == ["coordinates_swapped"]
    assert [f["action"] for f in out["fixes"]] == ["swap_xy"]
    assert out["recipe"] is None
    # nothing changed yet: the points are still where the file puts them
    assert cat.load(catalog, swapped).geometry.x.iloc[0] == pytest.approx(POINTS[0][1])


def test_accepted_fixes_are_replayed_on_every_load(client, catalog, swapped):
    out = client.post(f"/api/datasets/{swapped}/check").json()
    before = client.post("/api/plan/run", json={"plan": _plan()})
    assert before.status_code == 400 and "longitude" in before.json()["detail"]   # the swap spans the globe
    saved = client.post(f"/api/datasets/{swapped}/recipe", json={"accept": [out["fixes"][0]["id"]]}).json()
    assert saved["recipe"]["fixes"][0]["action"] == "swap_xy"
    assert (catalog / "recipes" / f"{swapped}.json").exists()
    gdf = cat.load(catalog, swapped)
    assert gdf.geometry.x.iloc[0] == pytest.approx(POINTS[0][0])          # corrected
    assert gdf["count"].tolist() == [c for _, _, c in POINTS]             # attributes keep their type
    assert gdf.attrs["urbantrace_cleaning"]["fixes"][0]["action"] == "swap_xy"
    after = client.post("/api/plan/run", json={"plan": _plan()}).json()
    assert sum(after["steps"]["st"]["columns"]["total"]) == 22
    assert after["inputs"]["s"]["cleaning"]["rows_changed"] == 6
    index = {d["id"]: d for d in client.get("/api/catalog/index").json()["datasets"]}
    assert index[swapped]["corrected"] and index[swapped]["bbox"][0] < -73   # coverage from corrected data
    # the export carries the recipe and says what was corrected
    doc = client.post("/api/collections", json={"name": "c", "datasets": [{"id": swapped}], "plan": _plan()}).json()
    z = zipfile.ZipFile(io.BytesIO(client.post(f"/api/collections/{doc['id']}/export",
                                               json={"embed": "always", "formats": ["parquet"]}).content))
    assert f"data/recipes/{swapped}.json" in z.namelist()
    assert "## Corrections" in z.read("README.md").decode()


def test_deleting_the_recipe_restores_the_file(client, catalog, swapped):
    out = client.post(f"/api/datasets/{swapped}/check").json()
    client.post(f"/api/datasets/{swapped}/recipe", json={"accept": [out["fixes"][0]["id"]]})
    assert client.delete(f"/api/datasets/{swapped}/recipe").json() == {"deleted": True}
    assert cat.load(catalog, swapped).geometry.x.iloc[0] == pytest.approx(POINTS[0][1])


def test_unknown_fix_and_empty_acceptance_are_400s(client, catalog, swapped):
    assert client.post(f"/api/datasets/{swapped}/recipe", json={"accept": []}).status_code == 400
    assert client.post(f"/api/datasets/{swapped}/recipe", json={"accept": ["nope"]}).status_code == 400
    assert client.post("/api/datasets/missing/check").status_code == 404
