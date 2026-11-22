"""The copilot's suggestion for a plan step, on the synthetic catalog, with a stand-in LLM."""
import json

import pytest

import suggest


@pytest.fixture(autouse=True)
def profiled_columns(catalog):
    """test_points' profile with its columns, so value kinds can be suggested."""
    prof = catalog / "metadata_v2" / "test_points.json"
    p = json.loads(prof.read_text())
    p["columns"] = [{"name": "count", "structural_type": "http://schema.org/Integer"},
                    {"name": "name", "structural_type": "http://schema.org/Text",
                     "semantic_types": ["http://schema.org/Enumeration"]}]
    prof.write_text(json.dumps(p))


def test_rules_suggest_the_usual_method_and_a_count(catalog):
    out = suggest.suggest(str(catalog), {"dataset": "test_points"}, {"kind": "zones", "dataset": "test_zones"}, "goal")
    assert out["engine"] == "heuristic" and out["method"] == "contain"
    assert out["reductions"][0] == {"method": "count", "column": None, "as": "test_points", "kind": "extensive"}
    assert out["notes"] == [] and "contain" in out["reasoning"]


def test_rules_aggregate_the_analysts_columns_by_value_kind(catalog):
    out = suggest.suggest(str(catalog), {"dataset": "test_points"}, {"kind": "h3", "resolution": 9}, None, ["count"])
    assert {"method": "sum", "column": "count", "as": "count", "kind": "extensive"} in out["reductions"]


def test_an_llm_answer_that_does_not_fit_is_repaired_and_explained(catalog):
    seen = {}

    def ask(payload):
        seen.update(payload)
        return {"method": "area_overlap",                                      # not for points
                "reductions": [{"method": "mean", "column": "count", "as": "Avg count!"},   # mean of an extensive column
                               {"method": "sum", "column": "nope", "as": "x"},              # no such column
                               {"method": "teleport", "column": None, "as": "y"}],          # no such reduction
                "reasoning": "Because."}

    out = suggest.suggest(str(catalog), {"dataset": "test_points"}, {"kind": "zones", "dataset": "test_zones"}, "g", None, ask)
    # The LLM saw only the methods that fit points onto polygons
    assert "contain" in seen["available_methods"] and "area_overlap" not in seen["available_methods"]
    assert out["engine"] == "llm" and out["method"] == "contain" and out["reasoning"] == "Because."
    assert [r["method"] for r in out["reductions"]] == ["sum"] and out["reductions"][0]["as"] == "avg_count"
    text = " ".join(out["notes"])
    assert "area_overlap does not fit" in text and "'nope' is not one" in text and "teleport is not" in text


def test_an_llm_failure_falls_back_to_rules(catalog):
    def ask(payload):
        raise RuntimeError("no key")

    out = suggest.suggest(str(catalog), {"dataset": "test_points"}, {"kind": "zones", "dataset": "test_zones"}, None, None, ask)
    assert out["engine"] == "heuristic" and out["method"] == "contain"


def test_the_endpoint(client, catalog):
    r = client.post("/api/copilot/suggest-step", json={"source": {"dataset": "test_points"},
                                                        "target": {"kind": "zones", "dataset": "test_zones"}})
    assert r.status_code == 200 and r.json()["method"] == "contain"
    r = client.post("/api/copilot/suggest-step", json={"source": {"dataset": "missing"}, "target": {"kind": "h3"}})
    assert r.status_code == 400
