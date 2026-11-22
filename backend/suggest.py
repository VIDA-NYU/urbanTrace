"""The copilot's suggestion for a plan step (docs/REDESIGN.md, phase 4; PLAN.md, release item 3).

Given a step's source dataset, its target (zones or an H3 grid) and the collection's goal, suggest a
matching method and reductions in urbanweave's vocabulary, with a rationale an analyst can check.

The LLM is offered only what urbanweave's registry accepts for these geometries: the matching methods
that fit, and the reductions with the value kinds they suit. Its answer is checked again against the
registry (``urbanweave.registry.problems``); anything that does not fit is replaced and the reason
recorded in ``notes``. Without an LLM (none configured, or it fails), a rule-based suggestion is made
from the geometries and the columns' suggested value kinds.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import urbanweave as uw
from urbanweave.registry import problems as registry_problems

import catalog
import plans

KINDS = ("extensive", "intensive", "categorical")

# Rule-based choices, in order of preference, when the LLM gives none or one that does not fit.
_METHOD_PREFERENCE = {
    "Point": ["contain", "nearest", "centroid"],
    "LineString": ["length_weighted", "centroid", "largest_overlap"],
    "Polygon": ["area_overlap", "centroid", "largest_overlap", "representative_point"],
}
_REDUCTION_FOR_KIND = {
    "extensive": ["sum", "count"],
    "intensive": ["weighted_mean", "mean", "median"],
    "categorical": ["majority", "shares"],
}


class SuggestError(ValueError):
    pass


def _family(geometry: str | None) -> str:
    g = (geometry or "Polygon").replace("Multi", "")
    return g if g in _METHOD_PREFERENCE else "Polygon"


def _snake(text: str, fallback: str = "value") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_").lower()
    return (s[:40] or fallback)


def context(data_dir, source: dict, target: dict, goal: str | None = None, focus: list[str] | None = None) -> dict:
    """Everything a suggestion needs: geometries, candidate methods and reductions, the columns."""
    stem = catalog.stem_of(source.get("dataset"))
    if not catalog.valid_stem(stem) or catalog.dataset_path(data_dir, stem) is None:
        raise SuggestError(f"Source dataset {source.get('dataset')!r} is not in the catalog.")
    prof = catalog.profile(data_dir, stem) or {}
    src_geom = prof.get("geometricType") or "Point"

    if target.get("kind") == "h3":
        tgt_geom, tgt_support = "Polygon", "h3"
        target_desc = {"kind": "h3", "resolution": target.get("resolution")}
    else:
        tstem = catalog.stem_of(target.get("dataset"))
        if not catalog.valid_stem(tstem) or catalog.dataset_path(data_dir, tstem) is None:
            raise SuggestError(f"Target dataset {target.get('dataset')!r} is not in the catalog.")
        tgt_geom, tgt_support = (catalog.profile(data_dir, tstem) or {}).get("geometricType") or "Polygon", "vector"
        target_desc = {"kind": "zones", "dataset": tstem, "geometry": tgt_geom,
                       "description": (catalog.description(data_dir, tstem) or "")[:300]}

    reg = uw.registry()
    methods = {name: info for name, info in reg["matching"].items()
               if not registry_problems(src_geom, tgt_geom, name, source_support="vector", target_support=tgt_support)}
    reductions = {name: info for name, info in reg["aggregation"].items() if info.get("serializable", True) and name != "custom"}

    kinds = plans.suggest_value_kinds(data_dir, stem)
    stats = {c.get("name"): c for c in prof.get("columns", [])}
    columns = []
    for name, k in kinds.items():
        c = stats.get(name, {})
        columns.append({"name": name, "kind": k["kind"], "why": k["reason"],
                        **{key: c.get(key) for key in ("num_distinct_values", "mean", "stddev") if c.get(key) is not None}})
    # The analyst's columns first, then the rest, capped for the prompt
    focus = [f for f in (focus or []) if f in kinds]
    columns.sort(key=lambda c: (c["name"] not in focus,))
    return {
        "stem": stem, "source_geometry": src_geom, "target_geometry": tgt_geom, "target_support": tgt_support,
        "methods": methods, "reductions": reductions, "kinds": {n: k["kind"] for n, k in kinds.items()},
        "focus": focus,
        "payload": {
            "goal": goal or "",
            "source": {"dataset": stem, "geometry": src_geom, "rows": prof.get("nb_rows"),
                       "description": (catalog.description(data_dir, stem) or "")[:600], "columns": columns[:40]},
            "target": target_desc,
            "available_methods": {n: {"summary": i.get("summary"), "assignment": i.get("assignment")} for n, i in methods.items()},
            "available_reductions": {n: {"summary": i.get("summary"), "value_kinds": i.get("value_kinds"),
                                         "needs_column": i.get("needs_column")} for n, i in reductions.items()},
            "analyst_columns": focus,
        },
    }


def _fits(ctx: dict, method: str, aggregation: str, kind: str | None) -> list[str]:
    return registry_problems(ctx["source_geometry"], ctx["target_geometry"], method, kind, aggregation,
                             source_support="vector", target_support=ctx["target_support"])


def heuristic(ctx: dict) -> dict:
    """A rule-based suggestion: the usual method for the geometries, a count, and a reduction per
    column the analyst pointed at, chosen by its value kind."""
    method = next((m for m in _METHOD_PREFERENCE[_family(ctx["source_geometry"])] if m in ctx["methods"]),
                  next(iter(ctx["methods"]), None))
    if method is None:
        raise SuggestError(f"No matching method fits {ctx['source_geometry']} onto {ctx['target_geometry']}.")
    # The count is named after what is counted: NYC_libraries -> libraries
    counted = re.sub(r"^(nyc_|\d+_)+", "", _snake(ctx["stem"], "count"))[:30] or "count"
    reds = [{"method": "count", "column": None, "as": counted, "kind": "extensive"}]
    for col in ctx["focus"]:
        kind = ctx["kinds"].get(col)
        agg = next((a for a in _REDUCTION_FOR_KIND.get(kind, []) if a in ctx["reductions"] and not _fits(ctx, method, a, kind)), None)
        if agg:
            reds.append({"method": agg, "column": col, "as": _snake(f"{agg}_{col}" if agg != "sum" else col), "kind": kind})
    focus = ", ".join(ctx["focus"])
    reasoning = (f"{method} is urbanweave's usual method for {ctx['source_geometry']} sources onto "
                 f"{'an H3 grid' if ctx['target_support'] == 'h3' else ctx['target_geometry'] + ' zones'}. "
                 "A count gives how many features fall in each unit"
                 + (f"; {focus} {'is' if len(ctx['focus']) == 1 else 'are'} aggregated by value kind." if focus else "."))
    return {"method": method, "reductions": reds, "reasoning": reasoning, "engine": "heuristic"}


def check(ctx: dict, answer: dict) -> tuple[dict, list[str]]:
    """The answer with whatever does not fit urbanweave's registry replaced, and why."""
    notes: list[str] = []
    method = str(answer.get("method") or "")
    if method not in ctx["methods"]:
        fallback = heuristic(ctx)["method"]
        notes.append(f"{method or 'No method'} does not fit {ctx['source_geometry']} onto {ctx['target_geometry']}; "
                     f"{fallback} is used instead.")
        method = fallback
    reds, used = [], set()
    raw = answer.get("reductions")
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        agg, col = str(r.get("method") or ""), r.get("column") or None
        info = ctx["reductions"].get(agg)
        if info is None:
            notes.append(f"{agg or 'An empty reduction'} is not an urbanweave reduction; left out.")
            continue
        if info.get("needs_column") and col not in ctx["kinds"]:
            notes.append(f"{agg} needs a column of the source; {col!r} is not one, so it was left out.")
            continue
        if not info.get("needs_column"):
            col = None
        kind = ctx["kinds"].get(col) if col else (r.get("kind") if r.get("kind") in KINDS else "extensive")
        reasons = _fits(ctx, method, agg, kind)
        if reasons:
            replacement = next((a for a in _REDUCTION_FOR_KIND.get(kind, []) if a in ctx["reductions"]
                                and not _fits(ctx, method, a, kind)), None)
            if not replacement:
                notes.append(f"{agg} of {col} was left out: {' '.join(reasons)}")
                continue
            notes.append(f"{agg} of {col} does not suit a {kind} column ({' '.join(reasons)}); {replacement} is used instead.")
            agg = replacement
        name = _snake(str(r.get("as") or ""), _snake(f"{agg}_{col}" if col else agg))
        while name in used:
            name += "_2"
        used.add(name)
        reds.append({"method": agg, "column": col, "as": name, "kind": kind})
    if not reds:
        notes.append("No usable reduction was suggested; a count is used.")
        reds = heuristic(ctx)["reductions"][:1]
    return {"method": method, "reductions": reds, "reasoning": str(answer.get("reasoning") or "").strip()}, notes


def suggest(data_dir, source: dict, target: dict, goal: str | None = None, focus: list[str] | None = None,
            ask: Callable[[dict], dict | None] | None = None) -> dict:
    """The suggestion for a step: ``{method, params, reductions, reasoning, engine, notes}``.
    *ask* sends the payload to the LLM and returns its answer, or None."""
    ctx = context(data_dir, source, target, goal, focus)
    answer, engine = None, "heuristic"
    if ask is not None:
        try:
            answer = ask(ctx["payload"])
        except Exception:
            answer = None
        if answer:
            engine = "llm"
    if not answer:
        answer = heuristic(ctx)
    checked, notes = check(ctx, answer)
    if not checked["reasoning"]:
        checked["reasoning"] = heuristic(ctx)["reasoning"]
    return {**checked, "params": {}, "engine": engine, "notes": notes}
