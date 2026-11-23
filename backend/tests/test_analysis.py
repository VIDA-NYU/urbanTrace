"""Analysis (redesign phase 5): sweeps, validation, dasymetric, priority index, report, exports."""
import io
import json
import zipfile

import pytest

import analysis
import urbanweave as uw

needs_dasymetric = pytest.mark.skipif(not hasattr(uw, "dasymetric"),
                                      reason=f"urbanweave {uw.__version__} has no dasymetric (added after 0.1.0a1)")
from test_plans import _plan, COUNT, RATE


@pytest.fixture(autouse=True)
def dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("URBANTRACE_COLLECTIONS_DIR", str(tmp_path / "collections"))
    monkeypatch.setenv("URBANTRACE_PLAN_CACHE", str(tmp_path / "plan_cache"))


VARIANTS = [{"via": {"kind": "h3", "resolution": 8}}, {"via": {"kind": "h3", "resolution": 9}},
            {"method": "nearest"}, {"method": "area_overlap"}]


def test_sweep_ranks_each_unit_under_each_variant(client, catalog):
    r = client.post("/api/analysis/sweep", json={"plan": _plan(COUNT), "step": "count_zones", "column": "total",
                                                 "variants": VARIANTS, "top_share": 0.5})
    assert r.status_code == 200, r.text
    out = r.json()
    sw = out["sweep"]
    ran = {v["label"]: v["ok"] for v in sw["variants"]}
    assert ran["as built"] and ran["via H3 r8"] and ran["via H3 r9"] and ran["nearest"]
    assert ran["area_overlap"] is False                       # points cannot be area-weighted: reported, not fatal
    assert len(out["target_ids"]) == 2 and "top_share" in out["columns"] and "rank_range" in out["columns"]
    # Extensive totals carried through an H3 grid and back keep their sum (22 points' counts)
    assert sum(out["columns"][sw["columns"]["via H3 r9"]]) == pytest.approx(22)
    assert sw["always_top"] + sw["sometimes_top"] >= 1
    assert all(f["properties"].get("top_share") is not None for f in out["geojson"]["features"])


def test_sweep_refuses_categorical_and_unknown_columns(client, catalog):
    r = client.post("/api/analysis/sweep", json={"plan": _plan(COUNT), "step": "count_zones", "column": "nope", "variants": VARIANTS})
    assert r.status_code == 400 and "no output column" in r.json()["detail"]


def test_validation_table_matches_the_definition(client, catalog):
    r = client.post("/api/analysis/validate", json={"plan": _plan(COUNT), "step": "count_zones", "column": "total",
                                                    "outcomes": {"dataset": "test_points"}, "quantiles": [0.5]})
    assert r.status_code == 200, r.text
    row = r.json()["validation"]["table"][0]
    # totals are west 10, east 12; the median is 11, so the east zone is "high" and holds 3 of 6 points
    assert row == {"quantile": 0.5, "threshold": 11.0, "coverage": 0.5, "n_high": 3, "n_total": 6, "units_high": 1,
                   "baseline": 0.5, "lift": 1.0, "note": None}


def test_validation_on_a_derived_variable(client, catalog):
    derived = [{"id": "d", "inputs": ["count_zones", "rate_zones"], "expression": "total * rate", "as": "x"}]
    r = client.post("/api/analysis/validate", json={"plan": _plan(COUNT, RATE), "derived": derived, "column": "x",
                                                    "outcomes": {"dataset": "test_points"}})
    assert r.status_code == 200, r.text
    assert r.json()["validation"]["result"] == "d"


@needs_dasymetric
def test_dasymetric_keeps_zone_totals(client, catalog):
    body = {"zones": {"dataset": "test_zones", "totals": ["pop"]}, "target": {"kind": "h3", "resolution": 9},
            "priors": [{"dataset": "test_points"}]}
    r = client.post("/api/analysis/dasymetric", json=body)
    assert r.status_code == 200, r.text
    est = [v for v in r.json()["columns"]["pop_est"] if v is not None]
    assert sum(est) == pytest.approx(400)
    assert r.json()["dasymetric"]["report"]


def test_priority_matches_the_result_map():
    cols = {"a": [0, 5, 10, None], "b": [1, 1, 3, None]}
    p = analysis.priority(cols, [{"column": "a", "weight": 3}, {"column": "b", "weight": 1, "direction": "inverted"}])
    # a normalized: 0, .5, 1; b inverted: 1, 1, 0; weights .75/.25; the all-missing unit scores 0
    assert p == pytest.approx([0.25, 0.625, 0.75, 0.0])


def test_report_and_export_carry_analyses(client, catalog):
    doc = client.post("/api/collections", json={
        "name": "Needs", "goal": "Where are needs highest?", "datasets": [{"id": "test_points"}],
        "plan": _plan(COUNT),
        "analyses": [
            {"id": "a1", "kind": "sweep", "name": "Resolution sweep",
             "config": {"step": "count_zones", "column": "total", "variants": VARIANTS[:2], "top_share": 0.5}},
            {"id": "a2", "kind": "validation", "name": "Against sites",
             "config": {"step": "count_zones", "column": "total", "outcomes": {"dataset": "test_points"}, "quantiles": [0.5]}},
            {"id": "a3", "kind": "priority", "name": "Priority",
             "config": {"result": "count_zones", "variables": [{"column": "total", "weight": 2, "rationale": "need"},
                                                              {"column": "sites", "weight": 1, "direction": "inverted"}]}},
            {"id": "a4", "kind": "dasymetric", "name": "Population",
             "config": {"zones": {"dataset": "test_zones", "totals": ["pop"]}, "target": {"kind": "h3", "resolution": 9},
                        "priors": [{"dataset": "test_points"}]}},
            {"id": "a5", "kind": "sweep", "name": "Broken", "config": {"step": "nope", "column": "x"}},
        ]}).json()
    html = client.get(f"/api/collections/{doc['id']}/report").text
    assert "<svg" in html and "Resolution sweep" in html and "Priority index" in html and "Lift" in html
    r = client.post(f"/api/collections/{doc['id']}/export", json={"formats": ["parquet"]})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert "report.html" in names
    assert {"data/results/resolution-sweep.parquet", "data/results/against-sites.parquet",
            "data/results/priority.parquet"} <= names
    assert ("data/results/population.parquet" in names) == hasattr(uw, "dasymetric")
    readme = z.read("README.md").decode()
    assert "## Analyses" in readme and "| 0.5 | 11.0 | 0.5 | 3 | 6 | 0.5 | 1.0 |" in readme
    assert "Broken" in readme and "could not be run" in readme
    import geopandas as gpd
    pr = gpd.read_parquet(io.BytesIO(z.read("data/results/priority.parquet")))
    assert "priority" in pr.columns and pr["priority"].between(0, 1).all()


def test_unnamed_analyses_are_named_after_their_kind_and_column():
    import main
    assert main._analysis_name({"kind": "sweep", "name": "sweep 7016", "config": {"column": "libraries"}}) == "sweep_libraries"
    assert main._analysis_name({"kind": "validation", "config": {"column": "schools_per_library"}}) == "validation_schools_per_library"
    assert main._analysis_name({"kind": "sweep", "name": "Resolution sweep", "config": {"column": "x"}}) == "Resolution sweep"


def test_priority_leaves_out_undecided_directions():
    import analysis
    cols = {"a": [1, 2, 3], "b": [3, 2, 1]}
    only_a = analysis.priority(cols, [{"column": "a", "weight": 1, "direction": "normal"},
                                      {"column": "b", "weight": 1, "direction": "unknown"}])
    assert only_a == [0.0, 0.5, 1.0]
    import pytest
    with pytest.raises(analysis.AnalysisError):
        analysis.priority(cols, [{"column": "b", "weight": 1, "direction": "unknown"}])
