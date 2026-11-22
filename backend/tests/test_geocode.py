"""Locating rows from their addresses (geocode.py). NYC GeoSearch is replaced by a fake: nothing
here goes over the network."""
import json
import time

import pytest

import catalog as cat
import geocode

# GeoSearch's answers in the fake, by query. Like the real service, it answers a made-up address
# with some other building rather than nothing.
ANSWERS = {
    "350 5th Ave, Manhattan": {"lon": -73.9857, "lat": 40.7545, "label": "350 5 AVENUE", "housenumber": "350",
                               "street": "5 AVENUE", "borough": "Manhattan", "postalcode": "10118"},
    "1 Nowhere Ln, Queens": {"lon": -73.91, "lat": 40.72, "label": "1 49 LANE", "housenumber": "1",
                             "street": "49 LANE", "borough": "Queens", "postalcode": "11378"},
    "20 W 34 St, Brooklyn": {"lon": -73.9860, "lat": 40.7486, "label": "20 WEST 34 STREET", "housenumber": "20",
                             "street": "WEST 34 STREET", "borough": "Manhattan", "postalcode": "10001"},
}


@pytest.fixture()
def addresses(catalog, monkeypatch):
    """test_sites: five rows, two with a location; the others have addresses only."""
    rows = [
        ({"address": "350 5th Ave", "boro": "MN", "n": 1}, None),
        ({"address": "1 Nowhere Ln", "boro": "QN", "n": 2}, None),
        ({"address": "20 W 34 St", "boro": "BK", "n": 3}, None),          # GeoSearch says Manhattan
        ({"address": "MARGINAL STREET", "boro": "MN", "n": 4}, None),     # no house number
        ({"address": "350 5th Ave", "boro": "MN", "n": 5}, [-73.99, 40.755]),
        ({"address": "1 Main St", "boro": "MN", "n": 6}, [-73.97, 40.752]),
    ]
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p, "geometry": {"type": "Point", "coordinates": g} if g else None}
        for p, g in rows]}
    (catalog / "geojson" / "test_sites.geojson").write_text(json.dumps(fc))
    (catalog / "metadata_v2" / "test_sites.json").write_text(json.dumps({
        "nb_rows": 6, "geometricType": "Point",
        "columns": [{"name": "address"}, {"name": "boro"}, {"name": "n"}]}))
    calls = []

    def fake(query):
        calls.append(query)
        return ANSWERS.get(query)
    monkeypatch.setattr(geocode, "_search", fake)
    return calls


def test_suggested_columns():
    assert geocode.suggest_columns(["house_no", "street_name", "borough", "zip_code"]) == \
        {"house": "house_no", "street": "street_name", "borough": "borough", "zip": "zip_code"}
    assert geocode.suggest_columns(["staddr", "boro", "zip"]) == {"address": "staddr", "borough": "boro", "zip": "zip"}


def test_answers_are_checked_against_the_address_sent():
    addr = {"house": "350", "street": "5th Ave", "borough": "Manhattan", "zip": ""}
    assert geocode.verdict(addr, ANSWERS["350 5th Ave, Manhattan"])[0] == "matched"     # 5TH AVE = 5 AVENUE
    assert geocode.verdict({**addr, "house": "1", "street": "Nowhere Ln", "borough": "Queens"},
                           ANSWERS["1 Nowhere Ln, Queens"])[0] == "different"
    assert geocode.verdict(addr, None)[0] == "not_found"
    rear = {"house": "255", "street": "REAR BENEDICT ROAD", "borough": "Staten Island", "zip": ""}
    assert geocode.verdict(rear, {"housenumber": "255 REAR", "street": "BENEDICT ROAD", "borough": "Staten Island"})[0] == "matched"
    assert geocode.norm_street("E 5th St") == geocode.norm_street("EAST 5 STREET")
    assert geocode.norm_street("B'WAY") == "BROADWAY"
    assert geocode.norm_street("E42nd Street") == "EAST 42 STREET"


def test_address_parsing():
    spec = {"address": "a"}
    assert geocode.address_of({"a": "68 Jay Street; Suite 201"}, spec)["street"] == "Jay Street"
    assert geocode.address_of({"a": "1 AVENUE"}, spec)["house"] == ""            # First Avenue, no number
    assert geocode.address_of({"a": "116 AVENUE"}, spec)["house"] == ""
    a = geocode.address_of({"a": "49 1/2 First Ave", "z": 10003.0}, {**spec, "zip": "z"})
    assert (a["house"], a["street"], a["zip"]) == ("49 1/2", "First Ave", "10003")


def test_preview_sends_nothing(client, addresses):
    r = client.post("/api/datasets/test_sites/geocode/preview", json={"spec": {}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["suggested"] == {"address": "address", "borough": "boro"}
    assert body["missing"] == 4 and body["addresses"] == 3 and body["without_house_number"] == 1
    assert addresses == []


def test_locating_rows_and_using_them(client, addresses):
    out = geocode.run(_dir(), "test_sites", {"address": "address", "borough": "boro"})
    assert out["located"] == 1                                       # only 350 5th Ave checks out
    assert out["rows_by_status"] == {"matched": 1, "different": 2, "not_found": 0, "outside_region": 0,
                                     "without_house_number": 1}
    assert sorted(addresses) == sorted(["350 5th Ave, Manhattan", "1 Nowhere Ln, Queens", "20 W 34 St, Brooklyn"])
    gdf = cat.load(_dir(), "test_sites")
    assert gdf.geometry.iloc[0].x == pytest.approx(-73.9857)          # filled
    assert gdf.geometry.iloc[1] is None                              # not used: a different address
    assert gdf.attrs["urbantrace_geocoded"]["rows_located"] == 1
    # A second run asks nothing again (answers are cached)
    addresses.clear()
    geocode.run(_dir(), "test_sites", {"address": "address", "borough": "boro"})
    assert addresses == []


def test_plans_report_located_rows(client, addresses):
    geocode.run(_dir(), "test_sites", {"address": "address", "borough": "boro"})
    plan = {"version": 1, "sources": {"s": {"kind": "vector", "columns": {}, "urbantrace": {"dataset": "test_sites"}}},
            "targets": {"g": {"kind": "h3", "resolution": 8}},
            "steps": [{"id": "st", "source": "s", "match": {"method": "contain", "target": "g"},
                       "aggregate": [{"method": "count", "as": "n"}]}]}
    r = client.post("/api/plan/run", json={"plan": plan, "outputs": ["st"]})
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["s"]["geocoded"]["rows_located"] == 1
    assert sum(v or 0 for v in r.json()["steps"]["st"]["columns"]["n"]) == 3    # 2 located before + 1 now


def test_job_endpoint_and_delete(client, addresses):
    r = client.post("/api/datasets/test_sites/geocode", json={"spec": {"address": "address", "borough": "boro"}})
    assert r.status_code == 200, r.text
    for _ in range(50):
        job = client.get("/api/datasets/test_sites/geocode").json()["job"]
        if job["state"] != "running":
            break
        time.sleep(0.05)
    assert job["state"] == "done", job
    assert client.get("/api/datasets/test_sites/geocode").json()["saved"]["located"] == 1
    assert client.delete("/api/datasets/test_sites/geocode").json()["deleted"]
    assert cat.load(_dir(), "test_sites").geometry.iloc[0] is None


def test_turned_off(client, addresses, monkeypatch):
    monkeypatch.setenv("URBANTRACE_GEOCODER", "off")
    r = client.post("/api/datasets/test_sites/geocode", json={"spec": {"address": "address"}})
    assert r.status_code == 403
    assert addresses == []


def test_a_changed_dataset_is_not_filled(client, addresses):
    geocode.run(_dir(), "test_sites", {"address": "address", "borough": "boro"})
    path = _dir() + "/geojson/test_sites.geojson"
    fc = json.loads(open(path).read())
    fc["features"].append(fc["features"][-1])
    open(path, "w").write(json.dumps(fc))
    gdf = cat.load(_dir(), "test_sites")
    assert gdf.geometry.iloc[0] is None
    assert "skipped" in gdf.attrs["urbantrace_geocoded"]


def _dir():
    import main
    return main.DATA_DIR
