"""Data-quality checks and corrections with atlas-clean (PLAN.md, release item 4).

An analyst checks a catalog dataset from its node: atlas-clean's spatial detectors run against the
dataset's existing profile, with the catalog's region as the extent the data should fall in, and
propose fixes (swap latitude and longitude, declare the right CRS, repair invalid polygons, ...).
Accepted fixes are saved as an atlas-clean recipe in ``data/recipes/<stem>.json``; from then on every
load of the dataset (``catalog.load``) replays it, and plans, previews, coverage and exports see the
corrected data, with the correction reported.

atlas-clean is optional: without it, checks are unavailable and recipes are not applied (loads
return the data as it is, and say so in the report).

atlas-clean reads attributes as text; a recipe's geometry fixes are taken from its result and the
attributes keep their types, except columns a fix changed, which are converted back where they were
numeric.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import pandas as pd

import catalog

try:  # optional: atlas-clean[geo]
    from atlas_clean import CleaningSession, DetectConfig, Recipe
    from atlas_clean.profile import Profile
    AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without atlas-clean
    AVAILABLE = False

# atlas-clean's spatial detectors, minus the one that needs reference zones
DETECTORS = ["coordinates_swapped", "crs_mislabelled", "crs_missing", "out_of_extent", "geometry_invalid",
             "geometry_empty", "geometry_mixed", "geometry_duplicate", "location_spike", "zones_overlap_or_gap",
             "missing_disguised"]


class CleaningError(ValueError):
    pass


def _require():
    if not AVAILABLE:
        raise CleaningError("Data checks need atlas-clean: pip install 'atlas-clean[geo]'.")


def recipe_path(data_dir, stem: str) -> Path:
    return Path(data_dir) / "recipes" / f"{stem}.json"


def _meta_path(data_dir, stem: str) -> Path:
    return Path(data_dir) / "recipes" / f"{stem}.meta.json"


def has_recipe(data_dir, stem: str) -> bool:
    return recipe_path(data_dir, stem).exists()


def recipe_info(data_dir, stem: str) -> dict | None:
    """What the saved recipe does: {fixes: [{action, rationale, issue}], saved, extent} or None."""
    meta = _meta_path(data_dir, stem)
    if not has_recipe(data_dir, stem):
        return None
    return json.loads(meta.read_text()) if meta.exists() else {"fixes": [], "saved": None}


def catalog_region(data_dir) -> list[float]:
    """Where the catalog's data is: the median of the datasets' bounding boxes, side by side, so a
    few misplaced datasets (swapped coordinates, the wrong CRS) do not stretch it."""
    import scope
    boxes = [r["bbox"] for r in scope.catalog_index(data_dir) if r.get("bbox")]
    sane = [b for b in boxes if -180 <= b[0] <= b[2] <= 180 and -90 <= b[1] <= b[3] <= 90]
    if not sane:
        raise CleaningError("The catalog has no datasets with a known extent.")
    x0, y0, x1, y1 = (median(b[i] for b in sane) for i in range(4))
    # The median box sits a little inside the real edge (a citywide dataset's box is just the city);
    # pad it by 10% on each side, so places near the edge are not reported as outside.
    px, py = 0.1 * (x1 - x0), 0.1 * (y1 - y0)
    return [x0 - px, y0 - py, x1 + px, y1 + py]


def _session(data_dir, stem: str, extent):
    path = catalog.dataset_path(data_dir, stem)
    if path is None:
        raise CleaningError(f"Dataset {stem!r} is not in the catalog.")
    prof = catalog.profile(data_dir, stem) or {"columns": [], "nb_rows": 0}
    return CleaningSession(str(path), profile=Profile(prof, validate=False), extent=tuple(extent),
                           config=DetectConfig(enabled=DETECTORS), name=stem, llm_cache_dir=None)


def check(data_dir, stem: str) -> dict:
    """Run the checks on a dataset: {extent, issues, fixes, recipe}. Fixes are proposals; nothing
    changes until some are accepted with :func:`save`."""
    _require()
    extent = catalog_region(data_dir)
    s = _session(data_dir, stem, extent)
    issues = s.detect()
    fixes = s.propose()
    return {
        "dataset": stem, "extent": extent,
        "issues": [{"id": i.id, "detector": i.detector, "severity": i.severity, "message": i.message,
                    "affected_rows": i.affected_rows, "columns": i.columns} for i in issues],
        "fixes": [{"id": f.id, "issue_id": f.issue_id, "action": f.action, "params": f.params,
                   "rationale": f.rationale} for f in fixes],
        "recipe": recipe_info(data_dir, stem),
    }


def save(data_dir, stem: str, accept: list[str]) -> dict:
    """Accept the fixes with these ids (from :func:`check`) and save them as the dataset's recipe."""
    _require()
    if not accept:
        raise CleaningError("Choose at least one fix to accept.")
    extent = catalog_region(data_dir)
    s = _session(data_dir, stem, extent)
    issues = {i.id: i for i in s.detect()}
    fixes = {f.id: f for f in s.propose()}
    unknown = [f for f in accept if f not in fixes]
    if unknown:
        raise CleaningError(f"Unknown fix id(s): {', '.join(unknown)}; run the check again.")
    for fid in accept:
        s.accept(fid)
    recipe = s.recipe(name=stem)
    path = recipe_path(data_dir, stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    recipe.save(path)
    meta = {"dataset": stem, "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"), "extent": extent,
            "fixes": [{"id": fid, "action": fixes[fid].action, "rationale": fixes[fid].rationale,
                       "issue": issues[fixes[fid].issue_id].message if fixes[fid].issue_id in issues else ""}
                      for fid in accept]}
    _meta_path(data_dir, stem).write_text(json.dumps(meta, indent=1))
    return meta


def delete(data_dir, stem: str) -> bool:
    found = False
    for p in (recipe_path(data_dir, stem), _meta_path(data_dir, stem)):
        if p.exists():
            p.unlink()
            found = True
    return found


def apply(data_dir, stem: str, gdf):
    """Replay the dataset's recipe on *gdf* (the whole dataset, as read). Returns the corrected frame
    and a report ({fixes, rows_changed, log}), or the frame unchanged and None without a recipe."""
    if not has_recipe(data_dir, stem):
        return gdf, None
    if not AVAILABLE:
        return gdf, {"skipped": "atlas-clean is not installed; the saved corrections were not applied"}
    recipe = Recipe.load(recipe_path(data_dir, stem))
    result = recipe.apply(gdf)
    fixed = result.to_geopandas()
    out = gdf.copy()
    out = out.set_geometry(gpd_series(fixed.geometry.values, crs=fixed.crs, index=out.index))
    for col in fixed.columns:
        if col == fixed.geometry.name:
            continue
        new = pd.Series(fixed[col].values, index=out.index)
        if col not in out.columns:
            out[col] = new                                  # e.g. a flag column added by flag_rows
            continue
        old = out[col]
        if _text(new).equals(_text(old)):
            continue                                        # unchanged: keep the typed column
        out[col] = pd.to_numeric(new, errors="coerce") if pd.api.types.is_numeric_dtype(old) else new
    report = {"fixes": [{"action": e["action"], "target": e["target"], "rows": e["rows"]} for e in result.log],
              "rows_changed": int(sum(e["rows"] for e in result.log)), "recipe": f"recipes/{stem}.json"}
    return out, report


def _text(series: pd.Series) -> pd.Series:
    """Values as atlas-clean sees them: text, with missing values empty."""
    return series.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))


def gpd_series(values, crs, index):
    import geopandas as gpd
    return gpd.GeoSeries(values, crs=crs, index=index)
