"""What a plan does to its inputs before urbanweave runs: study area, time window, repairs, method
parameters, errors. Ported from the tests of the classic integration endpoint, retired with its node."""
import sys
from pathlib import Path

import pytest

import catalog as cat
import main

WEST = {"kind": "zones", "dataset": "test_zones", "column": "zone", "values": ["west"], "name": "West"}


@pytest.fixture(autouse=True)
def dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))
    monkeypatch.setenv("URBANTRACE_PLAN_CACHE", str(tmp_path / "plan_cache"))


def _plan(source="test_points", method="contain", params=None, time_window=None, column="count", reduction="sum",
          kind="extensive"):
    ut = {"dataset": source, **({"time_window": time_window} if time_window else {})}
    return {"version": 1,
            "sources": {"src": {"kind": "vector", "columns": {column: {"kind": kind}}, "urbantrace": ut}},
            "targets": {"grid": {"kind": "h3", "resolution": 9}},
            "steps": [{"id": "s", "source": "src", "match": {"method": method, "target": "grid", **(params or {})},
                       "aggregate": [{"method": reduction, "column": column, "as": "c"}]}]}


def _run(client, plan, study_area=None):
    return client.post("/api/plan/run", json={"plan": plan, "study_area": study_area})


def _total(body):
    return sum(v for v in body["steps"]["s"]["columns"]["c"] if v is not None)


def test_study_area_clips_sources(client, catalog):
    r = _run(client, _plan(), WEST)
    assert r.status_code == 200, r.text
    assert 0 < _total(r.json()) < 22                      # only the western points
    assert r.json()["inputs"]["src"]["study_area"]["outside_study_area"] > 0


def test_bbox_study_area(client, catalog):
    r = _run(client, _plan(), {"kind": "bbox", "bbox": [-74.0, 40.75, -73.98, 40.76]})
    assert r.status_code == 200, r.text
    assert 0 < _total(r.json()) < 22


def test_bad_study_area_is_a_400(client, catalog):
    assert _run(client, _plan(), {"kind": "bbox", "bbox": [1, 1, 0, 0]}).status_code == 400


def test_time_window_filters_rows(client, catalog):
    r = _run(client, _plan(time_window={"column": "date", "start": "2020-01-01", "end": "2020-12-31"}))
    assert r.status_code == 200, r.text
    tw = r.json()["inputs"]["src"]["time_window"]
    assert tw["kept"] == 2 and tw["rows"] == 6            # 2020-06-15 and 2020-02-02
    assert _total(r.json()) == 5 + 7


def test_time_window_with_no_rows_is_a_400(client, catalog):
    r = _run(client, _plan(time_window={"column": "date", "start": "1990-01-01", "end": "1990-12-31"}))
    assert r.status_code == 400 and "no rows left" in r.json()["detail"]


def test_invalid_polygons_are_repaired_and_reported(client, catalog):
    r = _run(client, _plan("test_rates", "area_overlap", column="rate", reduction="weighted_mean", kind="intensive"))
    assert r.status_code == 200, r.text
    assert r.json()["inputs"]["src"]["repaired_geometries"]["count"] == 1   # the bowtie


def test_method_parameters_reach_the_method(client, catalog):
    wide = _run(client, _plan(method="gaussian", params={"bandwidth": 800})).json()
    narrow = _run(client, _plan(method="gaussian", params={"bandwidth": 50})).json()
    cells = lambda body: sum(v is not None for v in body["steps"]["s"]["columns"]["c"])
    assert cells(narrow) < cells(wide)                    # a narrower kernel reaches fewer cells
    assert wide["reports"]["s"]["match"]["params"]["bandwidth"] == 800


def test_unknown_method_parameter_is_a_400(client, catalog):
    assert _run(client, _plan(method="gaussian", params={"radius": 3})).status_code == 400


def test_a_method_that_does_not_fit_the_geometry_is_a_400(client, catalog):
    r = _run(client, _plan(method="area_overlap"))        # area overlap of points
    assert r.status_code == 400


def test_missing_dataset_is_a_400(client, catalog):
    r = _run(client, _plan("nope"))
    assert r.status_code == 400 and "not in the catalog" in r.json()["detail"]


def test_geoparquet_copy_is_preferred(client, catalog):
    sys.path.insert(0, str(Path(main.__file__).resolve().parents[1] / "tools"))
    from convert_to_geoparquet import convert
    convert(catalog / "geojson" / "test_points.geojson", catalog / "geoparquet" / "test_points.parquet")
    assert cat.dataset_path(catalog, "test_points").suffix == ".parquet"
    r = _run(client, _plan())
    assert r.status_code == 200, r.text
    assert _total(r.json()) == 22


def test_without_a_study_area_strays_outside_the_catalog_region_are_left_out(client, catalog):
    # A missing location coded as 0,0: without the region it would stretch the extent around the globe
    import json as _json
    fc = _json.loads((catalog / "geojson" / "test_points.geojson").read_text())
    fc["features"].append({"type": "Feature", "properties": {"count": 100, "name": "stray", "date": "2020-01-01"},
                           "geometry": {"type": "Point", "coordinates": [0.0, 0.0]}})
    (catalog / "geojson" / "test_strays.geojson").write_text(_json.dumps(fc))
    r = _run(client, _plan("test_strays"))
    assert r.status_code == 200, r.text
    assert _total(r.json()) == 22                                   # the stray's 100 is not counted
    out = r.json()["inputs"]["src"]["outside_region"]
    assert out["outside"] == 1 and out["kept"] == 6


def test_preview_of_invalid_polygons(client, catalog):
    # The map preview rounds coordinates; an invalid polygon (the bowtie) must not make it fail
    r = client.get("/dataset/test_rates.geojson?simplify=true")
    assert r.status_code == 200, r.text
    assert r.json()["urbantrace"]["sampled"] == len(r.json()["features"])


def test_hotspot_synthesis_takes_plan_outputs(client, catalog):
    # A step's outputs are named by the analyst (a count has no source column) and a Calculate
    # column has a formula: both are described to the synthesis instead of refused
    r = client.post("/api/v1/copilot/synthesize-hotspot", json={"source_variables": [
        {"dataset_name": "test_points", "column_name": "n_points", "aggregation": "count"},
        {"dataset_name": "test_points", "column_name": "total", "source_column": "count", "aggregation": "sum"},
        {"dataset_name": "derived", "column_name": "ratio", "source_column": "total / n_points", "aggregation": "expression"}]})
    assert r.status_code == 200, r.text
    assert {v["column_name"] for v in r.json()["variables"]} == {"n_points", "total", "ratio"}
    bad = client.post("/api/v1/copilot/synthesize-hotspot", json={"source_variables": [
        {"dataset_name": "test_points", "column_name": "nope"}]})
    assert bad.status_code == 400
