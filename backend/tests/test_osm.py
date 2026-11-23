"""Street networks as plan targets (osm.py). A small synthetic graph stands in for the download:
nothing here goes over the network."""
import json

import pytest

osmnx = pytest.importorskip("osmnx")

import osm
import scope

AREA = {"kind": "bbox", "bbox": [-74.0, 40.75, -73.96, 40.76]}


def _grid_graph():
    """Two east-west streets and three north-south ones: 6 nodes, of which the 2 middle ones are intersections."""
    import networkx as nx
    G = nx.MultiDiGraph(crs="EPSG:4326")
    xs, ys = [-73.995, -73.98, -73.965], [40.752, 40.758]
    nid = {}
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            nid[(i, j)] = 100 + 10 * i + j
            G.add_node(nid[(i, j)], x=x, y=y, street_count=3)
    way = 1
    for i in range(2):
        for j in range(2):
            for a, b in ((nid[(i, j)], nid[(i, j + 1)]), (nid[(i, j + 1)], nid[(i, j)])):
                G.add_edge(a, b, key=0, osmid=way, name=f"Street {i}", highway="residential", oneway=False, length=1270.0)
            way += 1
    for j in range(3):
        for a, b in ((nid[(0, j)], nid[(1, j)]), (nid[(1, j)], nid[(0, j)])):
            G.add_edge(a, b, key=0, osmid=way, name=f"Avenue {j}", highway="secondary", oneway=False, length=667.0)
        way += 1
    return G


@pytest.fixture()
def streets(catalog):
    area = scope.study_area_geometry(str(catalog), AREA)
    path = osm.graph_path(str(catalog), area, "drive")
    path.parent.mkdir(parents=True, exist_ok=True)
    osmnx.save_graphml(_grid_graph(), path)
    return path


def _plan(kind="osm_streets", method="nearest_segment"):
    return {"version": 1,
            "sources": {"pts": {"kind": "vector", "columns": {"count": {"kind": "extensive"}}, "urbantrace": {"dataset": "test_points"}}},
            "targets": {"st": {"kind": kind, "urbantrace": {"network_type": "drive"}}},
            "steps": [{"id": "s", "source": "pts", "match": {"method": method, "target": "st"},
                       "aggregate": [{"method": "count", "as": "n", "fill_empty": 0},
                                     {"method": "density", "column": "count", "as": "per_km"}]}]}


def test_points_onto_street_segments(client, streets):
    v = client.post("/api/plan/validate", json={"plan": _plan(), "study_area": AREA}).json()
    assert v["ok"], v
    r = client.post("/api/plan/run", json={"plan": _plan(), "study_area": AREA, "outputs": ["s"]})
    assert r.status_code == 200, r.text
    out = r.json()["steps"]["s"]
    assert len(out["target_ids"]) == 7                                  # 4 street pieces + 3 avenues
    assert sum(out["columns"]["n"]) == 6                                # every point to its nearest segment
    feats = out["geojson"]["features"]
    assert {f["geometry"]["type"] for f in feats} == {"LineString"}
    assert all("per_km" in f["properties"] and "label" in f["properties"] for f in feats)
    assert r.json()["targets"]["st"]["attribution"].startswith("Street network © OpenStreetMap")


def test_points_onto_intersections(client, streets):
    r = client.post("/api/plan/run", json={"plan": _plan("osm_intersections", "nearest_node"), "study_area": AREA, "outputs": ["s"]})
    assert r.status_code == 200, r.text
    out = r.json()["steps"]["s"]
    assert len(out["target_ids"]) == 2 and sum(out["columns"]["n"]) == 6   # corners meet two streets: not intersections
    assert out["geojson"]["features"][0]["geometry"]["type"] == "Point"


def test_street_targets_need_a_study_area(client, streets):
    v = client.post("/api/plan/validate", json={"plan": _plan()}).json()
    assert not v["ok"] and "study area" in json.dumps(v["problems"])
    assert client.post("/api/plan/run", json={"plan": _plan(), "outputs": ["s"]}).status_code == 400


def test_network_status(client, streets):
    r = client.post("/api/osm/network", json={"study_area": AREA, "network_type": "drive"})
    assert r.status_code == 200, r.text
    assert r.json()["downloaded"] is True and r.json()["km2"] > 0
    assert client.post("/api/osm/network", json={"study_area": AREA, "network_type": "walk"}).json()["downloaded"] is False
    assert client.post("/api/osm/network", json={"study_area": AREA, "network_type": "boat"}).status_code == 400
    assert client.post("/api/osm/network", json={"network_type": "drive"}).status_code == 400
