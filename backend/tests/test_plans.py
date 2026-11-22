"""Plans (redesign phase 4): validate, run in columns, derived variables, replay, export and import."""
import io
import json
import zipfile

import pytest

import main
import plans


@pytest.fixture(autouse=True)
def dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))
    monkeypatch.setenv("URBANTRACE_PLAN_CACHE", str(tmp_path / "plan_cache"))


def _plan(*steps, targets=None):
    return {"version": 1,
            "sources": {"pts": {"kind": "vector", "columns": {"count": {"kind": "extensive"}},
                                "urbantrace": {"dataset": "test_points"}},
                        "rates": {"kind": "vector", "columns": {"rate": {"kind": "intensive"}},
                                  "urbantrace": {"dataset": "test_rates"}}},
            "targets": targets or {"grid": {"kind": "h3", "resolution": 9},
                                   "zones": {"kind": "zones", "urbantrace": {"dataset": "test_zones"}}},
            "steps": list(steps)}


COUNT = {"id": "count_zones", "source": "pts", "match": {"method": "contain", "target": "zones"},
         "aggregate": [{"method": "count", "as": "sites", "fill_empty": 0},
                       {"method": "sum", "column": "count", "as": "total"}]}
RATE = {"id": "rate_zones", "source": "rates", "match": {"method": "area_overlap", "target": "zones"},
        "aggregate": [{"method": "weighted_mean", "column": "rate", "as": "rate"}]}
GRID = {"id": "grid", "source": "pts", "match": {"method": "contain", "target": "grid"},
        "aggregate": [{"method": "sum", "column": "count", "as": "total"}]}


def test_run_returns_columns_and_zone_geometry(client, catalog):
    r = client.post("/api/plan/run", json={"plan": _plan(COUNT), "outputs": ["count_zones"]})
    assert r.status_code == 200, r.text
    out = r.json()["steps"]["count_zones"]
    assert sorted(out["columns"]) == ["sites", "total"]
    assert sum(out["columns"]["sites"]) == 6 and sum(out["columns"]["total"]) == 22
    assert out["kinds"] == {"sites": "extensive", "total": "extensive"}
    assert len(out["geojson"]["features"]) == 2
    props = out["geojson"]["features"][0]["properties"]
    assert {"zone_id", "sites", "total"} <= set(props)
    assert r.json()["reports"]["count_zones"]["match"]["method"] == "contain"


def test_h3_grid_keeps_edge_points_and_missing_stays_missing(client, catalog):
    out = client.post("/api/plan/run", json={"plan": _plan(GRID)}).json()["steps"]["grid"]
    values = out["columns"]["total"]
    assert sum(v for v in values if v is not None) == 22
    assert None in values                         # cells with no points are missing, not zero


def test_where_filters_a_reduction(client, catalog):
    step = {**COUNT, "aggregate": [{"method": "count", "as": "big", "fill_empty": 0,
                                    "where": {"column": "count", "op": ">=", "value": 4}}]}
    out = client.post("/api/plan/run", json={"plan": _plan(step)}).json()["steps"]["count_zones"]
    assert sum(out["columns"]["big"]) == 3       # counts 5, 7, 4


def test_derived_variable_on_a_shared_target(client, catalog):
    body = {"plan": _plan(COUNT, RATE), "outputs": ["count_zones"],
            "derived": [{"id": "per_rate", "inputs": ["count_zones", "rate_zones"],
                         "expression": "total / (rate * 100)", "as": "total_per_pct", "kind": "intensive"}]}
    out = client.post("/api/plan/run", json=body).json()["steps"]["per_rate"]
    assert set(out["columns"]) == {"sites", "total", "rate", "total_per_pct"}
    assert out["kinds"]["total_per_pct"] == "intensive"
    for t, rate, d in zip(out["columns"]["total"], out["columns"]["rate"], out["columns"]["total_per_pct"]):
        assert d == pytest.approx(t / (rate * 100))


@pytest.mark.parametrize("expression,message", [
    ("__import__('os')", "not allowed"), ("total.real", "not allowed"), ("nope * 2", "not an output"),
])
def test_unsafe_or_unknown_expressions_are_refused(client, catalog, expression, message):
    body = {"plan": _plan(COUNT), "derived": [{"id": "d", "inputs": ["count_zones"], "expression": expression, "as": "x"}]}
    r = client.post("/api/plan/run", json=body)
    assert r.status_code == 400 and message in r.json()["detail"]


def test_derived_inputs_must_share_a_target(client, catalog):
    body = {"plan": _plan(COUNT, GRID), "derived": [{"id": "d", "inputs": ["count_zones", "grid"], "expression": "total", "as": "x"}]}
    r = client.post("/api/plan/run", json=body)
    assert r.status_code == 400 and "share one target" in r.json()["detail"]


def test_validate_names_the_step(client, catalog):
    bad = {**RATE, "aggregate": [{"method": "sum", "column": "rate", "as": "rate_sum"}]}   # summing an intensive value
    v = client.post("/api/plan/validate", json={"plan": _plan(COUNT, bad)}).json()
    assert not v["ok"] and "rate_zones" in v["problems"] and "count_zones" not in v["problems"]
    missing = {**COUNT, "source": "pts", "aggregate": [{"method": "sum", "column": "nope", "as": "x"}]}
    v = client.post("/api/plan/validate", json={"plan": _plan(missing)}).json()
    assert not v["ok"] and any("no column nope" in m for m in v["problems"]["count_zones"])


def test_study_area_limits_a_plan(client, catalog):
    area = {"kind": "zones", "dataset": "test_zones", "column": "zone", "values": ["west"]}
    out = client.post("/api/plan/run", json={"plan": _plan(COUNT), "study_area": area}).json()
    assert len(out["steps"]["count_zones"]["target_ids"]) == 1
    assert sum(out["steps"]["count_zones"]["columns"]["total"]) == 10
    assert out["inputs"]["pts"]["study_area"]["kept"] == 3


def test_recorded_runs_replay(client, catalog):
    doc = client.post("/api/collections", json={"name": "Plan"}).json()
    out = client.post("/api/plan/run", json={"plan": _plan(COUNT), "record": True, "collection_id": doc["id"]}).json()
    assert out["manifest_path"]
    assert client.get(f"/api/collections/{doc['id']}").json()["runs"][0]["manifest_path"] == out["manifest_path"]
    rep = client.post("/api/plan/replay", json={"manifest_path": out["manifest_path"]}).json()
    assert rep["ok"], rep
    assert client.post("/api/plan/replay", json={"manifest_path": "/etc/passwd"}).status_code == 404


def test_value_kind_suggestions(catalog):
    import json as _j
    prof = catalog / "metadata_v2" / "test_points.json"
    p = _j.loads(prof.read_text())
    p["columns"] = [{"name": "count", "structural_type": "http://schema.org/Integer"},
                    {"name": "poverty_rate", "structural_type": "http://schema.org/Float"},
                    {"name": "borough", "structural_type": "http://schema.org/Text",
                     "semantic_types": ["http://schema.org/Enumeration"]}]
    prof.write_text(_j.dumps(p))
    kinds = plans.suggest_value_kinds(catalog, "test_points")
    assert {k: v["kind"] for k, v in kinds.items()} == {"count": "extensive", "poverty_rate": "intensive",
                                                         "borough": "categorical"}


def test_export_carries_the_plan_and_imports_back(client, catalog):
    doc = client.post("/api/collections", json={
        "name": "Plan export", "datasets": [{"id": "test_points"}, {"id": "test_rates"}],
        "plan": _plan(COUNT, RATE),
        "derived": [{"id": "d", "inputs": ["count_zones", "rate_zones"], "expression": "total * rate", "as": "x"}]}).json()
    r = client.post(f"/api/collections/{doc['id']}/export", json={"embed": "always", "formats": ["parquet"]})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert {"plan.json", "manifest.json", "collection.json"} <= names
    # Results are named after what they hold: the step (several outputs) and the derived variable
    assert {"data/results/count_zones.parquet", "data/results/x.parquet"} <= names
    plan_json = json.loads(z.read("plan.json"))
    zone_path = plan_json["targets"]["zones"]["path"]
    assert zone_path.startswith("data/targets/") and zone_path in names
    manifest = json.loads(z.read("manifest.json"))
    assert [s["id"] for s in manifest["steps"]] == ["count_zones", "rate_zones"] and "base_dir" not in manifest
    readme = z.read("README.md").decode()
    assert "## Rerunning the plan" in readme and "`x` = `total * rate`" in readme

    imported = client.post("/api/collections/import",
                           files={"file": ("export.zip", r.content, "application/zip")}).json()
    assert imported["collection"]["plan"]["steps"][0]["id"] == "count_zones"
    assert imported["missing_datasets"] == [] and imported["collection"]["id"] != doc["id"]


def test_a_plan_built_by_the_canvas_runs(client, catalog):
    """tests/data/canvas_plan.json was produced by frontend/src/lib/plans.js (buildPlan, buildDerived)
    from a canvas with a time window, a where filter, a chained step and a Calculate node."""
    from pathlib import Path
    canvas = json.loads((Path(__file__).parent / "data" / "canvas_plan.json").read_text())
    v = client.post("/api/plan/validate", json={"plan": canvas["plan"]}).json()
    assert v["ok"], v
    r = client.post("/api/plan/run", json={"plan": canvas["plan"], "outputs": ["pts_zones", "chained"],
                                           "derived": canvas["derived"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["inputs"]["test_points"]["time_window"]["kept"] == 2           # the two rows dated 2020
    assert sum(out["steps"]["pts_zones"]["columns"]["sites"]) == 2
    assert sum(v for v in out["steps"]["pts_zones"]["columns"]["total"] if v) == 12   # both >= 4
    assert sum(v for v in out["steps"]["chained"]["columns"]["g"] if v) == pytest.approx(12)
    per_rate = out["steps"]["n_calc"]["columns"]["per_rate"]
    assert any(v is not None for v in per_rate)


def test_label_column_prefers_a_name_over_row_ids_and_codes():
    import geopandas as gpd
    from shapely.geometry import box
    import plans
    gdf = gpd.GeoDataFrame({
        ":id": ["row-a", "row-b"], "code": ["BK01", "BK02"], "shape_area": ["1.5", "2.5"],
        "ntaname": ["Greenpoint", "Park Slope"]}, geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=4326)
    assert plans.label_column(gdf) == "ntaname"
    # Without text names, a unique whole-number code
    coded = gpd.GeoDataFrame({"OBJECTID": [1, 2], "BoroCD": [301, 302]}, geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=4326)
    assert plans.label_column(coded) == "BoroCD"


def test_zones_overlapping_the_area_by_a_sliver_are_left_out():
    import geopandas as gpd
    from shapely.geometry import box
    import scope
    area = box(-74.0, 40.70, -73.95, 40.75)
    zones = gpd.GeoDataFrame({"name": ["inside", "half", "sliver", "outside"]}, geometry=[
        box(-73.99, 40.71, -73.97, 40.73),             # inside
        box(-73.96, 40.71, -73.94, 40.73),             # half inside
        box(-73.9500001, 40.71, -73.93, 40.73),        # shares the edge, overlapping by a hair
        box(-73.90, 40.71, -73.88, 40.73)], crs=4326)  # elsewhere
    assert zones[scope.zones_in_area(zones, area)]["name"].tolist() == ["inside", "half"]


def test_median_and_shares_reductions(client, catalog):
    step = {"id": "red", "source": "pts", "match": {"method": "contain", "target": "zones"},
            "aggregate": [{"method": "median", "column": "count", "as": "med"},
                          {"method": "shares", "column": "name", "as": "share"}]}
    plan = _plan(step)
    plan["sources"]["pts"]["columns"] = {"count": {"kind": "intensive"}, "name": {"kind": "categorical"}}  # median takes intensive values
    r = client.post("/api/plan/run", json={"plan": plan, "outputs": ["red"]})
    assert r.status_code == 200, r.text
    cols = r.json()["steps"]["red"]["columns"]
    assert "med" in cols and any(c.startswith("share") for c in cols if c != "med"), cols
