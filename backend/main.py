from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import geopandas as gpd
import pandas as pd
import json
import shapely
import numpy as np
import os
import csv
import io
import re
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Load .env automatically (supports backend/.env and repo-root/.env)
if load_dotenv:
    _backend_dir = Path(__file__).resolve().parent
    _env_candidates = [_backend_dir / ".env", _backend_dir.parent / ".env"]
    for _env_path in _env_candidates:
        if _env_path.exists():
            load_dotenv(dotenv_path=_env_path, override=False)
            break

# --- Imports for Formal Integration Engine ---
import urbanweave as uw
from urbanweave.compat import urbantrace as uw_legacy

import catalog
import collections_store
import export as exporter
import scope
import plans
import analysis
import suggest
import cleaning
import geocode
import copilot_settings
import osm
from fastapi.responses import HTMLResponse
from llm_agent import UrbanTraceCopilot
from tool import COPILOT_FRONTEND_TOOLS

# ==========================================
# 1. APP SETUP & CONSTANTS
# ==========================================

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(_app):
    _check_llm_providers()          # in the background: startup does not wait for it
    yield


app = FastAPI(title="UrbanTrace Spatial API", lifespan=_lifespan)

# Allow the React frontend to communicate with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"], # Vite's default port + fallback
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory pointing to the data folder
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_COPILOT_AGENT: UrbanTraceCopilot | None = None
_COPILOT_KEY: tuple | None = None


def _strip_dataset_suffixes(name: str | None) -> str:
    if not isinstance(name, str):
        return ""

    dataset_id = os.path.basename(name.strip())

    for suffix in (".geojson", ".json"):
        if dataset_id.endswith(suffix):
            dataset_id = dataset_id[: -len(suffix)]
            break

    return dataset_id


def _geojson_filename(name: str | None) -> str:
    dataset_id = _strip_dataset_suffixes(name)
    if not dataset_id:
        return ""
    return f"{dataset_id}.geojson"


def _normalize_dataset_stem(dataset_name: str | None) -> str:
    return _strip_dataset_suffixes(dataset_name)


def _metadata_path_for_dataset(dataset_name: str | None) -> str:
    stem = _normalize_dataset_stem(dataset_name)
    return os.path.join(DATA_DIR, "metadata", f"{stem}.json")


# ==========================================
# 2. PYDANTIC REQUEST MODELS
# ==========================================

class CopilotChatRequest(BaseModel):
    """Payload for UrbanTrace LLM copilot chat with live dashboard graph context."""
    message: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt: str = "You are a helpful assistant for UrbanTrace."
    thinking_budget_tokens: int | None = None
    log_stream: bool = True


def copilot_disabled() -> bool:
    """Rules only, no LLM calls: chosen in the interface (copilot_settings.py), else COPILOT_DISABLED=1
    in backend/.env. Endpoints with rules fall back to them."""
    return not copilot_settings.effective(DATA_DIR)["enabled"]


def get_copilot_agent() -> UrbanTraceCopilot:
    """Lazy singleton so missing API keys do not crash app startup; rebuilt when the settings change."""
    if copilot_disabled():
        raise RuntimeError("The copilot's LLM is turned off (rules only)")
    global _COPILOT_AGENT, _COPILOT_KEY
    eff = copilot_settings.effective(DATA_DIR)
    key = (eff["provider"], eff["model"], eff["local_base_url"])
    if _COPILOT_AGENT is None or _COPILOT_KEY != key:
        _COPILOT_AGENT = UrbanTraceCopilot(llm_provider=eff["provider"], llm_model=eff["model"] or None,
                                           local_base_url=eff["local_base_url"])
        _COPILOT_KEY = key
    return _COPILOT_AGENT


class CopilotSettingsBody(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    local_base_url: Optional[str] = None


def _copilot_status() -> Dict[str, Any]:
    provs = copilot_settings.providers(DATA_DIR)
    return {"settings": copilot_settings.effective(DATA_DIR), "providers": provs,
            "available": [p["id"] for p in provs if p.get("ready")]}


def _check_llm_providers():
    """Which LLM providers work, checked once in the background at startup: keys found in the
    environment (the shell's or backend/.env) are verified with their provider by a free request,
    and a local server is asked for its models. The interface offers to turn the copilot on."""
    if not copilot_settings.checks_enabled():
        return
    import threading

    def run():
        try:
            copilot_settings.check_all(DATA_DIR)
            print(copilot_settings.summary(DATA_DIR), flush=True)
        except Exception as exc:  # never stops the backend
            print(f"Copilot provider check failed: {exc}", flush=True)
    threading.Thread(target=run, daemon=True).start()


@app.post("/api/copilot/check")
async def recheck_copilot():
    """Check the providers again (after adding a key or starting a local server)."""
    await asyncio.to_thread(copilot_settings.check_all, DATA_DIR)
    return await asyncio.to_thread(_copilot_status)


@app.get("/api/copilot/settings")
async def get_copilot_settings():
    """Whether the copilot uses an LLM, which one, and which providers this server can use."""
    return await asyncio.to_thread(_copilot_status)


@app.post("/api/copilot/settings")
async def set_copilot_settings(body: CopilotSettingsBody):
    """Turn the LLM on or off and choose it. Keys are not taken here: they stay in backend/.env."""
    try:
        copilot_settings.save(DATA_DIR, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await asyncio.to_thread(_copilot_status)


@app.delete("/api/copilot/settings")
async def reset_copilot_settings():
    """Back to the environment's settings (backend/.env)."""
    copilot_settings.reset(DATA_DIR)
    return await asyncio.to_thread(_copilot_status)


@app.post("/api/copilot/test")
async def test_copilot():
    """Send one short request to the configured LLM: does it answer, and how fast."""
    import time as _time
    if copilot_disabled():
        raise HTTPException(status_code=400, detail="The LLM is turned off.")
    t0 = _time.perf_counter()
    try:
        agent = await asyncio.to_thread(get_copilot_agent)
        resp = await asyncio.to_thread(agent._create_completion,
                                       {"model": agent.model, "stream": False,
                                        "messages": [{"role": "user", "content": "Reply with the single word OK."}]}, 0)
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {str(e)[:300]}")
    return {"ok": True, "reply": text[:80], "seconds": round(_time.perf_counter() - t0, 1),
            "provider": agent.provider, "model": agent.model}


class HotspotVariableRequest(BaseModel):
    dataset_name: str
    column_name: str                       # the variable on the map (a plan step's output name)
    source_column: Optional[str] = None    # the dataset column it was computed from, if any
    aggregation: Optional[str] = None      # how (count, sum, weighted_mean, ...)


class HotspotSynthesisRequest(BaseModel):
    source_variables: List[HotspotVariableRequest]
    goal: Optional[str] = None  # User-defined priority goal (e.g. "pedestrian safety risk")


# ==========================================
# 3. DATASET MANAGEMENT ENDPOINTS
# ==========================================

from upload_new_data import process_uploaded_geojson

@app.get("/datasets")
async def list_datasets():
    """Lists available datasets and their metadata for the frontend Node Library."""
    geojson_dir = os.path.join(DATA_DIR, "geojson")
    
    datasets = []
    
    if not os.path.exists(geojson_dir):
        return {"datasets": []}

    for f in os.listdir(geojson_dir):
        if f.endswith(".geojson"):
            base_name = f.replace(".geojson", "")
            meta_path = _metadata_path_for_dataset(base_name)
            
            dataset_info = {
                "id": base_name,
                "name": base_name.replace("_", " "),
                "filename": f,
                "metadata": None
            }

            if os.path.exists(meta_path):
                with open(meta_path, 'r') as meta_file:
                    dataset_info["metadata"] = json.load(meta_file)
                # The row count from the current profile (metadata_v2), which a refetch updates
                # (tools/fetch_open_data.py); the original profiles keep the copy they were made from
                current = catalog.profile(DATA_DIR, base_name)
                if current and current.get("nb_rows") is not None:
                    dataset_info["metadata"]["nb_rows"] = current["nb_rows"]
            
            datasets.append(dataset_info)

    # Raster datasets (rasters.py): listed alongside, with geometricType "Raster"
    import rasters
    for stem in rasters.list_stems(DATA_DIR):
        datasets.append({"id": stem, "name": stem.replace("_", " "), "filename": f"{stem}.tif",
                         "metadata": rasters.profile(DATA_DIR, stem)})
    return {"datasets": datasets}


@app.get("/api/rasters/{stem}/preview.png")
async def raster_preview(stem: str):
    """A small picture of a raster dataset for its node (transparent where there is no data)."""
    import rasters
    from fastapi.responses import Response
    if not catalog.valid_stem(stem) or not rasters.is_raster(DATA_DIR, stem):
        raise HTTPException(status_code=404, detail="Raster not found")
    png = await asyncio.to_thread(rasters.preview_png, DATA_DIR, stem)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/rasters/{stem}")
async def raster_info(stem: str):
    import rasters
    if not catalog.valid_stem(stem) or not rasters.is_raster(DATA_DIR, stem):
        raise HTTPException(status_code=404, detail="Raster not found")
    return rasters.profile(DATA_DIR, stem)


@app.post("/datasets/upload")
async def upload_geojson(
    file: UploadFile = File(...),
    source_url: Optional[str] = Form(None),
    license: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
):
    """
    Upload a .geojson file with full metadata generation pipeline:
    1. Save GeoJSON to /data/geojson
    2. Compute geometricType
    3. Profile dataset (columns, statistics, spatial coverage)
    4. Generate enriched metadata
    5. Save metadata to /data/metadata
    """
    # Delegate processing to upload_new_data module (profiles + saves metadata)
    result = await process_uploaded_geojson(file, DATA_DIR)
    stem = catalog.stem_of(result.get("filename") or file.filename)
    if catalog.valid_stem(stem):
        from datetime import datetime, timezone
        catalog.set_origin(DATA_DIR, stem, {
            "portal": None, "portal_id": None, "source_url": (source_url or "").strip() or None,
            "publisher": (publisher or "").strip() or None, "license": (license or "").strip() or None,
            "source_updated_at": None, "retrieved_at": None,
            "catalog_added_at": datetime.now(timezone.utc).date().isoformat(),
            "derived_from": None, "status": "uploaded",
            "notes": [] if source_url else ["uploaded without a source URL; origin unknown"],
        })
        result["origin"] = catalog.origin(DATA_DIR, stem)
    return result

# Profiles made by atlas-profiler 0.1.0 (data/metadata_v2), their HTML reports (data/reports_v2)
# and the dataset descriptions, for the dataset info box. The rest of the app still reads
# data/metadata.
PROFILE_V2_DIR = os.path.join(DATA_DIR, "metadata_v2")
REPORTS_V2_DIR = os.path.join(DATA_DIR, "reports_v2")
DESCRIPTIONS_CSV = os.path.join(DATA_DIR, "descriptions_ddg.csv")
# Bulky spatial summaries the info box does not draw
_PROFILE_HEAVY_KEYS = ("geohashes4", "kdtree", "grid")


def _dataset_description(stem: str) -> str:
    if not os.path.exists(DESCRIPTIONS_CSV):
        return ""
    with open(DESCRIPTIONS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if _normalize_dataset_stem(row.get("dataset")) == stem:
                return (row.get("description") or "").strip()
    return ""


@app.get("/datasets/{dataset_id}/details")
async def get_dataset_details(dataset_id: str):
    """Description and newest profile of one dataset, for the dataset info box."""
    stem = _normalize_dataset_stem(dataset_id)
    if not re.fullmatch(r"\w[\w.\-]*", stem):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    profile = None
    path = os.path.join(PROFILE_V2_DIR, f"{stem}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            profile = json.load(f)
        profile.pop("_profiling_times", None)
        for entry in profile.get("spatial_coverage", []):
            for key in _PROFILE_HEAVY_KEYS:
                entry.pop(key, None)
    return {
        "id": stem,
        "description": _dataset_description(stem),
        "profile": profile,
        "report_url": f"/reports/{stem}" if os.path.exists(os.path.join(REPORTS_V2_DIR, f"{stem}.html")) else None,
    }


@app.get("/reports/{dataset_id}")
async def get_dataset_report(dataset_id: str):
    """The dataset's HTML profile report (atlas-profiler)."""
    stem = _normalize_dataset_stem(dataset_id)
    path = os.path.join(REPORTS_V2_DIR, f"{stem}.html")
    if not re.fullmatch(r"\w[\w.\-]*", stem) or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path, media_type="text/html")


PREVIEW_MAX_FEATURES = 50_000


@app.get("/dataset/{filename}")
async def get_geojson(filename: str, simplify: bool = False, columns: Optional[str] = None,
                      max_features: Optional[int] = None):
    """A dataset as GeoJSON (WGS84), with its saved corrections (cleaning.py).

    With *simplify* (map previews) it is light: geometries simplified and rounded to about a metre,
    only the *columns* asked for (comma-separated; none by default), and at most *max_features*
    features (an even sample, 50,000 by default); ``urbantrace.rows`` and ``urbantrace.sampled``
    say how many there are and how many were sent. Without it, the whole dataset."""
    stem = catalog.stem_of(filename)
    if not catalog.valid_stem(stem) or catalog.dataset_path(DATA_DIR, stem) is None:
        raise HTTPException(status_code=404, detail="File not found")
    wanted = [c for c in (columns or "").split(",") if c] if simplify else None
    gdf = await asyncio.to_thread(catalog.load, DATA_DIR, stem, wanted)
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    if not simplify:
        return gdf.__geo_interface__
    rows = int(len(gdf))
    cap = max_features or PREVIEW_MAX_FEATURES
    if rows > cap:                                        # an even sample keeps the picture of where data is
        gdf = gdf.iloc[np.linspace(0, rows - 1, cap).astype(int)]
    geoms = gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)
    # Round coordinates (about 1 m) to shrink the response; point by point, so invalid polygons
    # (MODZCTA has some) are rounded rather than refused
    gdf = gdf.set_geometry(shapely.set_precision(geoms.to_numpy(), 1e-5, mode="pointwise"))
    out = json.loads(gdf.to_json(drop_id=True))
    out["urbantrace"] = {"rows": rows, "sampled": int(len(gdf)), "columns": [c for c in gdf.columns if c != gdf.geometry.name]}
    return out


@app.get("/api/operators")
async def get_available_operators():
    """
    Returns all available operators and geometry constraints for the frontend.
    Under urbanweave they are generated from its registry, which is included.
    """
    return uw_legacy.operators_payload()


def _extract_sample_values(sample_csv: Optional[str], target_column: str, max_rows: int = 20) -> List[Any]:
    if not sample_csv:
        return []

    try:
        reader = csv.DictReader(io.StringIO(sample_csv))
        values: List[Any] = []
        for row in reader:
            if len(values) >= max_rows:
                break
            raw = row.get(target_column)
            if raw is None or raw == "":
                continue

            token = str(raw).strip()
            if re.fullmatch(r"-?\d+", token):
                values.append(int(token))
            elif re.fullmatch(r"-?\d*\.\d+", token):
                values.append(float(token))
            else:
                values.append(token)
        return values
    except Exception:
        return []


def _infer_hotspot_direction(dataset_name: str, column_name: str, sample_data: List[Any]) -> str:
    label = f"{dataset_name} {column_name}".lower()

    # Facilities and services: more of them means less need
    inverted_keywords = [
        "income", "wealth", "salary", "resource", "access", "coverage",
        "library", "libraries", "park", "clinic", "hospital", "station", "center", "centre",
        "program", "slot", "seat", "facility", "facilities", "hotspot", "wi-fi", "wifi", "tree", "garden",
        "bike lane", "bike lanes", "infrastructure", "service", "capacity",
        "safety score", "score", "rating", "index (good)", "quality"
    ]
    normal_keywords = [
        "injury", "injuries", "crash", "collision", "fatal", "poverty",
        "unemployment", "pollution", "hvi", "vulnerability", "risk", "danger",
        "complaint", "exposure", "burden"
    ]

    if any(k in label for k in normal_keywords):
        return "normal"
    if any(k in label for k in inverted_keywords):
        return "inverted"

    # Light statistical fallback: if values are mostly very high percentages/scores, assume beneficial metric.
    nums = [v for v in sample_data if isinstance(v, (int, float))]
    if nums:
        avg = sum(nums) / len(nums)
        if avg >= 85 and any(k in label for k in ["score", "rate", "index"]):
            return "inverted"

    # No rule applies: say so rather than guess. The analyst sets the direction on the map.
    return "unknown"


def _hotspot_reasoning(direction: str, dataset_name: str, column_name: str) -> str:
    if direction == "unknown":
        return (f"No rule says whether more {column_name} ({dataset_name}) means more or less need, and no LLM is "
                f"configured to judge it from the goal. Choose a direction; until then it is left out of the score.")
    if direction == "inverted":
        return f"Lower values in {column_name} ({dataset_name}) indicate higher unmet need, so scale is inverted for hotspot priority."
    return f"Higher values in {column_name} ({dataset_name}) directly indicate higher risk/need, so scale is used as-is."


def _build_heuristic_hotspot_audits(
    source_payload: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    audits: List[Dict[str, Any]] = []
    for var in source_payload:
        # A ratio or a formula mixes two things (schools per library): its words do not tell the direction
        mixed = str(var.get("computed_as", "")).startswith("expression") or re.search(r"(^|_)per(_|$)", var["column_name"].lower())
        direction = "unknown" if mixed else _infer_hotspot_direction(
            var["dataset_name"],
            var["column_name"],
            var["sample_data"],
        )
        audits.append({
            "dataset_name": var["dataset_name"],
            "column_name": var["column_name"],
            "direction": direction,
            "reasoning": _hotspot_reasoning(direction, var["dataset_name"], var["column_name"]),
            "weight": 1.0,
            "engine": "heuristic",
        })
    return audits


@app.post("/api/v1/copilot/synthesize-hotspot")
async def synthesize_hotspot(request: HotspotSynthesisRequest):
    """
    Produces semantic variable audit for hotspot synthesis.
    Returns per-variable direction (normal/inverted), weight, and reasoning.
    """
    if not request.source_variables:
        raise HTTPException(status_code=400, detail="source_variables cannot be empty")

    source_payload: List[Dict[str, Any]] = []

    for item in request.source_variables:
        if item.aggregation == "expression":            # a Calculate node's column: its formula is the description
            source_payload.append({"dataset_name": _normalize_dataset_stem(item.dataset_name), "column_name": item.column_name,
                                   "computed_as": f"expression: {item.source_column or ''}".strip(),
                                   "column_metadata": {}, "sample_data": []})
            continue
        metadata_path = _metadata_path_for_dataset(item.dataset_name)
        if not os.path.exists(metadata_path):
            raise HTTPException(status_code=404, detail=f"Metadata not found for dataset: {item.dataset_name}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # A plan step's output is named by the analyst (libraries, fill_rate): describe it by the
        # column it came from, and by how it was computed (a count has no source column).
        source = item.source_column or item.column_name
        column_meta = next((c for c in metadata.get("columns", []) if c.get("name") == source), None)
        if not column_meta and not item.aggregation:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{source}' not found in metadata for dataset '{item.dataset_name}'"
            )
        column_meta = column_meta or {}

        sample_values = _extract_sample_values(metadata.get("sample"), source, max_rows=20) if item.source_column or column_meta else []
        source_payload.append({
            "dataset_name": _normalize_dataset_stem(item.dataset_name),
            "column_name": item.column_name,
            **({"computed_as": f"{item.aggregation} of {item.source_column}" if item.source_column
                else f"{item.aggregation} of {_normalize_dataset_stem(item.dataset_name)} features per unit"}
               if item.aggregation else {}),
            "column_metadata": {
                "structural_type": column_meta.get("structural_type"),
                "num_distinct_values": column_meta.get("num_distinct_values"),
                "mean": column_meta.get("mean"),
                "stddev": column_meta.get("stddev"),
                "coverage": column_meta.get("coverage", [])
            },
            "sample_data": sample_values
        })

    llm_payload: Dict[str, Any] = {
        "task": "Synthesize hotspot priority polarity and weights.",
        "source_variables": source_payload,
        "score_range": [0.0, 1.0]
    }
    if request.goal and request.goal.strip():
        llm_payload["goal"] = request.goal.strip()

    requested_pairs = {
        (_normalize_dataset_stem(v.dataset_name), v.column_name)
        for v in request.source_variables
    }

    audits: Optional[List[Dict[str, Any]]] = None
    try:
        copilot = get_copilot_agent()
    except Exception as exc:
        print(f"Hotspot synthesis copilot unavailable: {exc}")
    else:
        audits = await asyncio.to_thread(
            copilot.synthesize_hotspot_semantics,
            llm_payload,
        )
    if not audits:
        audits = _build_heuristic_hotspot_audits(source_payload)

    normalized_audits: List[Dict[str, Any]] = []
    for audit in audits:
        ds = _normalize_dataset_stem(str(audit.get("dataset_name", "")))
        col = str(audit.get("column_name", ""))
        if (ds, col) not in requested_pairs:
            continue

        direction_raw = str(audit.get("direction", "normal")).lower()
        direction = direction_raw if direction_raw in ("inverted", "unknown") else "normal"
        weight = audit.get("weight", 0.0)
        try:
            weight = float(weight)
        except Exception:
            weight = 0.0
        if weight < 0:
            weight = 0.0

        normalized_audits.append({
            "dataset_name": ds,
            "column_name": col,
            "direction": direction,
            "reasoning": str(audit.get("reasoning", "")) or _hotspot_reasoning(direction, ds, col),
            "weight": weight,
            "engine": audit.get("engine", "llm")
        })

    if not normalized_audits:
        normalized_audits = _build_heuristic_hotspot_audits(source_payload)

    # Normalize weights to sum to 1
    total_w = sum(max(0.0, float(a.get("weight", 0.0))) for a in normalized_audits)
    if total_w <= 0:
        n = len(normalized_audits)
        for a in normalized_audits:
            a["weight"] = round(1.0 / n, 4) if n else 0.0
    else:
        for a in normalized_audits:
            a["weight"] = round(max(0.0, float(a.get("weight", 0.0))) / total_w, 4)

    # Explicit one-line debug signal for quick engine-path checks per request
    engine_used = "llm" if any(str(a.get("engine", "")).lower() == "llm" for a in normalized_audits) else "heuristic"
    print(f"HOTSPOT_ENGINE={engine_used}")

    return {
        "analysisType": "hotspot_priority",
        "scoreRange": [0.0, 1.0],
        "engine": engine_used,                 # "heuristic": directions from keyword rules, to be checked
        "variables": normalized_audits,
        "summary": ("Priority score is a weighted blend of normalized variables; 1.0 means the most of what the goal "
                    "looks for" + (f" ({request.goal.strip()})." if request.goal and request.goal.strip() else " (highest need when no goal is given)."))
    }


class StepSuggestionRequest(BaseModel):
    source: Dict[str, Any]
    target: Dict[str, Any]
    goal: Optional[str] = None
    columns: Optional[List[str]] = None


@app.post("/api/copilot/suggest-step")
async def suggest_step(body: StepSuggestionRequest):
    """A matching method and reductions for a plan step, with a rationale, checked against urbanweave's
    registry (suggest.py). Uses the LLM when one is configured, else rules."""
    try:
        agent = get_copilot_agent()
        ask = agent.suggest_step
    except Exception:
        ask = None
    try:
        return await asyncio.to_thread(suggest.suggest, DATA_DIR, body.source, body.target, body.goal, body.columns, ask)
    except suggest.SuggestError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# COLLECTIONS AND EXPORT (docs/REDESIGN.md, section 2)
# ==========================================

def _collections() -> collections_store.Store:
    root = os.getenv("URBANTRACE_COLLECTIONS_DIR") or os.path.join(DATA_DIR, "collections")
    return collections_store.Store(root)


class CollectionBody(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    notes: Optional[str] = None
    datasets: Optional[List[Dict[str, Any]]] = None
    integrations: Optional[List[Dict[str, Any]]] = None
    analyses: Optional[List[Dict[str, Any]]] = None
    study_area: Optional[Dict[str, Any]] = None
    canvas: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    derived: Optional[List[Dict[str, Any]]] = None
    runs: Optional[List[Dict[str, Any]]] = None


class ExportOptions(BaseModel):
    embed: str = "auto"                      # "auto" | "always" | "never"
    formats: List[str] = Field(default_factory=lambda: ["parquet", "gpkg"])
    include_results: bool = True
    clip: bool = True                        # clip sources to the collection's study area


def _get_collection(cid: str) -> Dict[str, Any]:
    try:
        return _collections().get(cid)
    except collections_store.NotFound:
        raise HTTPException(status_code=404, detail=f"Collection {cid} not found")


@app.get("/api/collections")
async def list_collections():
    return {"collections": _collections().list()}


@app.post("/api/collections")
async def create_collection(body: CollectionBody):
    return _collections().create(body.model_dump(exclude_none=True))


@app.get("/api/collections/{cid}")
async def get_collection(cid: str):
    return _get_collection(cid)


@app.put("/api/collections/{cid}")
async def update_collection(cid: str, body: CollectionBody):
    _get_collection(cid)
    return _collections().update(cid, body.model_dump(exclude_unset=True))


@app.delete("/api/collections/{cid}")
async def delete_collection(cid: str):
    _get_collection(cid)
    _collections().delete(cid)
    return {"status": "deleted", "id": cid}


def _zip_response(path: str, filename: str) -> FileResponse:
    return FileResponse(path, media_type="application/zip", filename=filename,
                        background=BackgroundTask(lambda: os.path.exists(path) and os.remove(path)))


def _temp_zip() -> str:
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    return path


def _export_extras(doc: Dict[str, Any], options: ExportOptions) -> Dict[str, Any]:
    """The parts of an export beyond the datasets: study area, checks (phase 2)."""
    try:
        area = scope.study_area_geometry(DATA_DIR, doc.get("study_area"))
    except scope.ScopeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    extras = {"area": area if options.clip else None, "warnings": scope.checks(DATA_DIR, doc)}
    files = {"collection.json": json.dumps({k: v for k, v in doc.items() if k != "runs"}, indent=1, default=str).encode()}
    if options.include_results and doc.get("plan") and doc["plan"].get("steps"):
        plan_results, plan_files, plan_readme = _export_plan(doc, options)
        extras["results"] = (extras.get("results") or []) + plan_results
        files.update(plan_files)
        extras["readme_sections"] = plan_readme
    analyses = _run_collection_analyses(doc) if options.include_results and doc.get("plan") else []
    for a in analyses:
        if a.get("payload"):
            extras.setdefault("results", []).append(_analysis_result(a))
        else:
            extras.setdefault("results", []).append({"name": a["name"], "frames": {}, "caveats": [f"{a['name']}: {a['error']}"]})
    extras.setdefault("readme_sections", [])
    extras["readme_sections"] = list(extras["readme_sections"]) + _analysis_readme(analyses)
    files["report.html"] = _collection_report(doc, analyses).encode()
    # Corrections replayed on the datasets (atlas-clean recipes), so the package says what changed
    corrections = []
    for d in doc.get("datasets", []):
        stem = catalog.stem_of(d.get("id"))
        info = cleaning.recipe_info(DATA_DIR, stem) if catalog.valid_stem(stem) else None
        if info is None:
            continue
        files[f"data/recipes/{stem}.json"] = cleaning.recipe_path(DATA_DIR, stem).read_bytes()
        fixes = "; ".join(f"{f['action']}: {f['rationale']}" for f in info.get("fixes", [])) or "see the recipe"
        corrections.append(f"- `{stem}`: {fixes} (`data/recipes/{stem}.json`, an atlas-clean recipe)")
    # Rows located from their addresses (geocode.py): the service, the checks, how many
    located = []
    for d in doc.get("datasets", []):
        stem = catalog.stem_of(d.get("id"))
        g = geocode.info(DATA_DIR, stem) if catalog.valid_stem(stem) else None
        if g is None:
            continue
        files[f"data/geocoded/{stem}.json"] = geocode.result_path(DATA_DIR, stem).read_bytes()
        rs = g.get("rows_by_status", {})
        located.append(f"- `{stem}`: {g.get('located', 0):,} of {g.get('missing', 0):,} rows without a location located with "
                       f"{g.get('service')} on {str(g.get('saved', ''))[:10]} (columns {', '.join(f'{k}: `{v}`' for k, v in (g.get('spec') or {}).items())}); "
                       f"not located: {rs.get('different', 0):,} answered with a different address, {rs.get('not_found', 0):,} not found, "
                       f"{rs.get('without_house_number', 0):,} without a house number (`data/geocoded/{stem}.json`)")
    # Raster datasets: their citation and license terms (e.g. CC BY-NC-SA asks for attribution,
    # non-commercial use and results shared alike)
    import rasters
    raster_lines = []
    for d in doc.get("datasets", []):
        stem = catalog.stem_of(d.get("id"))
        if catalog.valid_stem(stem) and rasters.is_raster(DATA_DIR, stem):
            side = rasters.sidecar(DATA_DIR, stem)
            raster_lines.append(f"- `{stem}`: {side.get('citation') or side.get('source_url') or ''} License: {side.get('license') or 'not recorded'}."
                                + (f" {side['license_note']}" if side.get("license_note") else ""))
    if raster_lines:
        extras["readme_sections"] = list(extras["readme_sections"]) + [
            "## Raster sources and their licenses", "",
            "Results computed from these rasters carry their terms.", "", *raster_lines, ""]
    # Street networks from OpenStreetMap: the license asks for attribution
    if any((tg or {}).get("kind") in plans.OSM_KINDS for tg in ((doc.get("plan") or {}).get("targets") or {}).values()):
        extras["readme_sections"] = list(extras["readme_sections"]) + [
            "## Street networks", "",
            f"Street segments and intersections were downloaded for the study area from OpenStreetMap. {osm.ATTRIBUTION}.", ""]
    if located:
        extras["readme_sections"] = list(extras["readme_sections"]) + [
            "## Rows located from addresses", "",
            "Some rows had an address but no location. Their addresses were sent to a geocoder, and an answer was used "
            "only when its house number, street and borough were the ones sent.", "", *located, ""]
    if corrections:
        extras["readme_sections"] = list(extras["readme_sections"]) + [
            "## Corrections", "",
            "These datasets were checked with [atlas-clean](https://github.com/VIDA-NYU/atlas-clean) and "
            "corrected before use; the sources in this package and the results are the corrected data.", "",
            *corrections, ""]
    extras["extra_files"] = files
    return extras


def _plan_cache() -> str:
    return os.getenv("URBANTRACE_PLAN_CACHE") or os.path.join(DATA_DIR, "plan_cache")


def _step_rationales(doc: Dict[str, Any]) -> Dict[str, str]:
    """The copilot's rationale kept on each Step node of the canvas, by step id."""
    out = {}
    for n in ((doc.get("canvas") or {}).get("nodes") or []):
        data = n.get("data") or {}
        reasoning = (data.get("suggestion") or {}).get("reasoning")
        if n.get("type") == "stepNode" and reasoning:
            sid = re.sub(r"[^A-Za-z0-9_]+", "_", data.get("stepId") or n.get("id") or "").strip("_")[:40]
            out[sid] = reasoning
    return out


def _export_plan(doc: Dict[str, Any], options: "ExportOptions"):
    """Run the collection's plan with a manifest; return its results, plan.json/manifest.json, and
    README lines on rerunning it in a notebook."""
    import tempfile
    spec = doc["plan"]
    step_ids = [s["id"] for s in spec.get("steps", [])]
    with tempfile.TemporaryDirectory() as tmp:
        manifest_file = Path(tmp) / "manifest.json"
        try:
            out = plans.run(DATA_DIR, spec, doc.get("study_area"), tmp, outputs=step_ids,
                            derived=doc.get("derived") or [], record=True, manifest_path=manifest_file)
        except (plans.PlanInputError, uw.UrbanweaveError) as e:
            return [{"name": "Plan", "frames": {}, "caveats": [f"The plan could not be run: {e}"]}], {}, []
        manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else None
        files = {}
        # The plan as a notebook would run it: zones targets read from the package, sources bound by name.
        portable = json.loads(json.dumps(out["plan"]))
        for name, t in (portable.get("targets") or {}).items():
            if t.get("kind") == "zones" and t.get("path"):
                local = Path(t["path"])
                stem = catalog.stem_of((t.get("urbantrace") or {}).get("dataset"))
                origin = catalog.origin(DATA_DIR, stem)
                src_path = catalog.dataset_path(DATA_DIR, stem)
                embed, why = exporter._embed_decision(options.embed, origin, src_path.stat().st_size if src_path else 0)
                t["path"] = f"data/targets/{local.name}"
                if embed and local.exists():
                    files[t["path"]] = local.read_bytes()
                else:
                    t.setdefault("urbantrace", {})["not_included"] = why
        files["plan.json"] = json.dumps(portable, indent=1).encode()
        if manifest:
            manifest.pop("base_dir", None)
            files["manifest.json"] = json.dumps(manifest, indent=1, default=str).encode()
    results = []
    for sid, payload in out["steps"].items():
        ids = payload["target_ids"]
        frame = pd.DataFrame({"target_id": ids, **payload["columns"]})
        if payload.get("geojson"):
            geo = gpd.GeoDataFrame.from_features(payload["geojson"]["features"], crs="EPSG:4326")
            frame = geo
        elif payload["target"].get("kind") == "h3":
            import h3 as _h3
            from shapely.geometry import Polygon as _Poly
            frame = gpd.GeoDataFrame(frame, geometry=[_Poly([(lng, lat) for lat, lng in _h3.cell_to_boundary(c)]) for c in ids],
                                     crs="EPSG:4326")
        reports = {sid: out["reports"].get(sid)} if sid in out["reports"] else None
        derived = payload.get("derived") or {}
        cols = list(payload["columns"])
        # Named after what it holds: a derived variable's name, a step's single output, else the step id.
        rname = derived.get("as") or (cols[0] if len(cols) == 1 else sid)
        rationale = _step_rationales(doc).get(sid)
        results.append({"name": rname, "frames": {"output": frame}, "value_kinds": payload.get("kinds"),
                        "request": {"plan_step": sid, **({"derived": payload["derived"]} if payload.get("derived") else {})},
                        "reports": reports, "description": f"Output of plan step `{sid}`" +
                        (f": {payload['derived']['expression']}" if payload.get("derived", {}).get("expression") else "") + ".",
                        "summary_lines": _plan_report_lines(sid, out["reports"].get(sid))
                        + ([f"Why this method: {rationale}"] if rationale else [])})
    bindings = ", ".join(f'"{n}": gpd.read_parquet("data/sources/{catalog.stem_of((d.get("urbantrace") or {}).get("dataset"))}.parquet")'
                         for n, d in (spec.get("sources") or {}).items())
    readme = ["## Rerunning the plan", "",
              "`plan.json` is an [urbanweave](https://github.com/VIDA-NYU/urbanweave) plan and `manifest.json` "
              "records the run that produced `data/results/` (inputs by fingerprint, engine versions, each step's report).",
              "Sources are bound by name when the plan runs. Each source's dataset, time window and study area are "
              "recorded under `urbantrace` in `plan.json`; apply them to the files in `data/sources/` (or to the "
              "published datasets), then:", "", "```python", "import geopandas as gpd", "import urbanweave as uw",
              'plan = uw.Plan.from_json("plan.json")', f"run = plan.run({{{bindings}}})", "```", ""]
    if doc.get("derived"):
        readme += ["Derived variables are computed from the joined step outputs after the plan runs:", ""]
        readme += [f"- `{d.get('as')}` = `{d.get('expression')}` on {', '.join(d.get('inputs') or [])}" for d in doc["derived"] if d.get("expression")]
        readme.append("")
    return results, files, readme


def _plan_report_lines(step_id: str, report: Optional[Dict[str, Any]]) -> List[str]:
    if (report or {}).get("conversion") == "reduce":       # a join on a key
        unknown = (report.get("unknown_keys") or {}).get("count", 0)
        return [f"`{step_id}`: rows joined on `{report.get('by')}` into {report.get('groups')} key(s)"
                + (f"; {unknown} key(s) match no zone" if unknown else "") + "."]
    match = (report or {}).get("match") or {}
    src = match.get("sources") or {}
    if not src:
        return []
    line = f"`{step_id}`: {src.get('matched')} of {src.get('total')} features matched by {match.get('method')}"
    unmatched = ", ".join(f"{v.get('count')} {k.replace('_', ' ')}" for k, v in (src.get("unmatched") or {}).items())
    if unmatched:
        line += f"; unmatched: {unmatched}"
    crs = (match.get("measurement") or {}).get("crs_name")
    return [line + (f"; measured in {crs}" if crs else "") + "."]


@app.post("/api/collections/{cid}/export")
def export_collection(cid: str, options: ExportOptions = ExportOptions()):
    """The collection as a zip: datapackage.json, data files and a README (redesign section 2.3)."""
    doc = _get_collection(cid)
    path = _temp_zip()
    try:
        extras = _export_extras(doc, options)
        exporter.build(DATA_DIR, doc, Path(path), embed=options.embed, formats=tuple(options.formats), **extras)
    except ValueError as e:
        os.remove(path)
        raise HTTPException(status_code=400, detail=str(e))
    name = exporter._slug(doc.get("name"))
    return _zip_response(path, f"{name}.zip")


class ResultExportBody(BaseModel):
    name: str = "result"
    geojson: Dict[str, Any]
    provenance: Optional[Dict[str, Any]] = None
    formats: List[str] = Field(default_factory=lambda: ["parquet", "gpkg", "geojson"])


@app.post("/api/results/export")
def export_result(body: ResultExportBody):
    """One result map as a zip: the data in the requested formats, its provenance and a README."""
    features = body.geojson.get("features") or []
    if not features:
        raise HTTPException(status_code=400, detail="The result has no features to export")
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
    collection = {"name": body.name, "goal": "", "datasets": []}
    result = {"name": body.name, "frames": {"result": gdf},
              "description": "A result exported from a Result Map node.",
              "request": (body.provenance or {}).get("request"), "reports": (body.provenance or {}).get("reports")}
    extra = {"provenance.json": json.dumps(body.provenance or {}, indent=1, default=str).encode()}
    path = _temp_zip()
    try:
        exporter.build(DATA_DIR, collection, Path(path), formats=tuple(body.formats), results=[result],
                       extra_files=extra)
    except ValueError as e:
        os.remove(path)
        raise HTTPException(status_code=400, detail=str(e))
    return _zip_response(path, f"{exporter._slug(body.name, 'result')}.zip")


@app.get("/datasets/{dataset_id}/origin")
async def get_dataset_origin(dataset_id: str):
    stem = catalog.stem_of(dataset_id)
    if not catalog.valid_stem(stem):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    return catalog.origin(DATA_DIR, stem)


# ==========================================
# STUDY AREA, COVERAGE AND TIME (docs/REDESIGN.md, phase 2)
# ==========================================

@app.get("/api/catalog/index")
async def get_catalog_index():
    """One row per dataset (bbox, time range, geometry, rows) for search filters."""
    return {"datasets": scope.catalog_index(DATA_DIR)}


# --- data checks and corrections with atlas-clean (cleaning.py) ---------------------------------

class RecipeBody(BaseModel):
    accept: List[str]


def _dataset_stem(dataset_id: str) -> str:
    stem = catalog.stem_of(dataset_id)
    if not catalog.valid_stem(stem) or catalog.dataset_path(DATA_DIR, stem) is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return stem


def _corrections_changed():
    """Coverage and study-area shares depend on corrected data."""
    _IN_AREA_CACHE.clear()


@app.post("/api/datasets/{dataset_id}/check")
async def check_dataset(dataset_id: str):
    """atlas-clean's spatial checks on a dataset, with proposed fixes (nothing changes yet)."""
    stem = _dataset_stem(dataset_id)
    try:
        return await asyncio.to_thread(cleaning.check, DATA_DIR, stem)
    except cleaning.CleaningError as e:
        raise HTTPException(status_code=400 if cleaning.AVAILABLE else 501, detail=str(e))


@app.get("/api/datasets/{dataset_id}/recipe")
async def get_recipe(dataset_id: str):
    return {"recipe": cleaning.recipe_info(DATA_DIR, _dataset_stem(dataset_id))}


@app.post("/api/datasets/{dataset_id}/recipe")
async def save_recipe(dataset_id: str, body: RecipeBody):
    """Accept fixes from a check; they are replayed on every later load of the dataset."""
    stem = _dataset_stem(dataset_id)
    try:
        meta = await asyncio.to_thread(cleaning.save, DATA_DIR, stem, body.accept)
    except cleaning.CleaningError as e:
        raise HTTPException(status_code=400 if cleaning.AVAILABLE else 501, detail=str(e))
    _corrections_changed()
    return {"recipe": meta}


@app.delete("/api/datasets/{dataset_id}/recipe")
async def delete_recipe(dataset_id: str):
    found = cleaning.delete(DATA_DIR, _dataset_stem(dataset_id))
    _corrections_changed()
    return {"deleted": found}


class GeocodeBody(BaseModel):
    spec: Dict[str, Optional[str]] = Field(default_factory=dict)


def _geocode_spec(spec: Dict[str, Optional[str]]) -> Dict[str, str]:
    return {k: v for k, v in (spec or {}).items() if k in ("address", "house", "street", "borough", "zip") and v}


@app.post("/api/datasets/{dataset_id}/geocode/preview")
async def geocode_preview(dataset_id: str, body: GeocodeBody):
    """What locating rows from their addresses would do: rows without a location, the address
    columns, how many addresses would be sent and where. Sends nothing."""
    stem = _dataset_stem(dataset_id)
    try:
        return await asyncio.to_thread(geocode.preview, DATA_DIR, stem, _geocode_spec(body.spec) or None)
    except geocode.GeocodeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/datasets/{dataset_id}/geocode")
async def geocode_start(dataset_id: str, body: GeocodeBody):
    """Send the addresses of the rows without a location to NYC GeoSearch and save the locations
    that check out (geocode.py). Runs in the background; poll GET for progress."""
    stem = _dataset_stem(dataset_id)
    if not geocode.enabled():
        raise HTTPException(status_code=403, detail="Geocoding is turned off on this server (URBANTRACE_GEOCODER=off).")
    spec = _geocode_spec(body.spec)
    if not (spec.get("address") or (spec.get("house") and spec.get("street"))):
        raise HTTPException(status_code=400, detail="Choose the address column, or the house number and street columns.")
    return {"job": geocode.start(DATA_DIR, stem, spec, on_done=_corrections_changed)}


@app.get("/api/datasets/{dataset_id}/geocode")
async def geocode_get(dataset_id: str):
    stem = _dataset_stem(dataset_id)
    return {"job": geocode.status(stem), "saved": geocode.info(DATA_DIR, stem), "enabled": geocode.enabled()}


@app.delete("/api/datasets/{dataset_id}/geocode")
async def geocode_delete(dataset_id: str):
    found = geocode.delete(DATA_DIR, _dataset_stem(dataset_id))
    _corrections_changed()
    return {"deleted": found}


class OsmNetworkBody(BaseModel):
    study_area: Optional[Dict[str, Any]] = None
    network_type: str = "drive"


def _osm_area(body: OsmNetworkBody):
    if not body.study_area:
        raise HTTPException(status_code=400, detail="Street networks are downloaded for the study area; choose one first.")
    try:
        area = scope.study_area_geometry(DATA_DIR, body.study_area)
    except scope.ScopeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if area is None:
        raise HTTPException(status_code=400, detail="Street networks are downloaded for the study area; choose one first.")
    return area


@app.post("/api/osm/network")
async def osm_network(body: OsmNetworkBody):
    """Whether the study area's street network is downloaded, and any download under way."""
    area = await asyncio.to_thread(_osm_area, body)
    try:
        out = await asyncio.to_thread(osm.info, DATA_DIR, area, body.network_type)
    except osm.OsmError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**out, "job": osm.status(DATA_DIR, area, body.network_type), "max_km2": osm.MAX_KM2}


@app.post("/api/osm/network/download")
async def osm_network_download(body: OsmNetworkBody):
    """Download the study area's street network from OpenStreetMap (in the background)."""
    area = await asyncio.to_thread(_osm_area, body)
    if not osm.available():
        raise HTTPException(status_code=501, detail="Street networks need OSMnx: pip install 'urbanweave[osm]'.")
    km2 = await asyncio.to_thread(osm.area_km2, area)
    if km2 > osm.MAX_KM2:
        raise HTTPException(status_code=400, detail=f"The study area is {km2:,.0f} km²; street networks are downloaded for at most {osm.MAX_KM2:,.0f} km².")
    try:
        return {"job": osm.start(DATA_DIR, area, body.network_type)}
    except osm.OsmError as e:
        raise HTTPException(status_code=400, detail=str(e))


_IN_AREA_CACHE: Dict[str, Any] = {}


@app.post("/api/catalog/in-area")
async def get_catalog_in_area(body: Dict[str, Any]):
    """How much of each catalog dataset is in the study area (*body* is the study area spec), for
    sorting and filtering the sidebar. Cached per spec: profiles do not change while the server runs."""
    key = json.dumps(body, sort_keys=True)
    if key not in _IN_AREA_CACHE:
        try:
            area = scope.study_area_geometry(DATA_DIR, body)
        except scope.ScopeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if area is None:
            raise HTTPException(status_code=400, detail="No study area.")
        _IN_AREA_CACHE[key] = await asyncio.to_thread(scope.catalog_in_area, DATA_DIR, area)
    return {"datasets": _IN_AREA_CACHE[key]}


@app.get("/api/study-area/options/{dataset_id}")
async def get_study_area_options(dataset_id: str):
    stem = catalog.stem_of(dataset_id)
    if not catalog.valid_stem(stem) or catalog.dataset_path(DATA_DIR, stem) is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return scope.study_area_options(DATA_DIR, stem)


@app.post("/api/study-area/resolve")
async def resolve_study_area(spec: Dict[str, Any]):
    """The study area's geometry, bbox and area, for display."""
    try:
        return scope.study_area_summary(scope.study_area_geometry(DATA_DIR, spec))
    except scope.ScopeError as e:
        raise HTTPException(status_code=400, detail=str(e))


class CoverageRequest(BaseModel):
    datasets: List[str]
    study_area: Optional[Dict[str, Any]] = None


@app.post("/api/coverage")
async def get_coverage(body: CoverageRequest):
    """Where the datasets have data, on a common ~500 m lattice, and how much of the study area each reaches."""
    try:
        area = scope.study_area_geometry(DATA_DIR, body.study_area)
    except scope.ScopeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    stems = [catalog.stem_of(d) for d in body.datasets if catalog.valid_stem(catalog.stem_of(d))]
    out = scope.coverage(DATA_DIR, stems, area)
    out["study_area"] = scope.study_area_summary(area)
    return out


@app.post("/api/collections/check")
async def check_collection(body: CollectionBody):
    """Warnings for a collection as it stands (saved or not): periods, coverage of the study area."""
    return {"warnings": scope.checks(DATA_DIR, body.model_dump(exclude_none=True))}


# ==========================================
# PLANS (docs/REDESIGN.md, phase 4)
# ==========================================

class PlanRequest(BaseModel):
    plan: Dict[str, Any]
    study_area: Optional[Dict[str, Any]] = None
    outputs: Optional[List[str]] = None
    derived: Optional[List[Dict[str, Any]]] = None
    record: bool = False                     # write a manifest under the plan cache, for replay
    collection_id: Optional[str] = None      # with record, the run is listed on this collection


@app.post("/api/plan/validate")
def validate_plan(body: PlanRequest):
    """Problems with a plan before it runs, by step ID."""
    return plans.validate(DATA_DIR, body.plan, body.study_area, _plan_cache())


@app.post("/api/plan/run")
def run_plan(body: PlanRequest):
    """Run a plan: results in columns for the requested steps (and derived variables), every report."""
    try:
        out = plans.run(DATA_DIR, body.plan, body.study_area, _plan_cache(), outputs=body.outputs,
                        derived=body.derived, record=body.record)
    except plans.PlanInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except uw.UrbanweaveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if body.record and body.collection_id and out.get("manifest_path"):
        try:
            doc = _collections().get(body.collection_id)
            runs = (doc.get("runs") or [])[-19:] + [{"manifest_path": out["manifest_path"],
                                                     "created": pd.Timestamp.now(tz="UTC").isoformat()}]
            _collections().update(body.collection_id, {"runs": runs})
        except collections_store.NotFound:
            pass
    return out


class ReplayRequest(BaseModel):
    manifest_path: str


@app.post("/api/plan/replay")
def replay_plan(body: ReplayRequest):
    """Rerun a recorded plan run from its pinned inputs; name any input that changed."""
    from urbanweave.plan import replay
    cache = Path(_plan_cache()).resolve()
    path = Path(body.manifest_path).resolve()
    if cache not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found in the plan cache")
    try:
        run = replay(json.loads(path.read_text()), cache=cache / "artifacts")
    except uw.UrbanweaveError as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "message": "Replayed from the pinned inputs; every fingerprint matched.",
            "steps": list(run.outputs)}


@app.get("/api/datasets/{dataset_id}/value-kinds")
async def get_value_kinds(dataset_id: str):
    """A suggested value kind for each column (extensive, intensive, categorical), with the reason."""
    stem = catalog.stem_of(dataset_id)
    if not catalog.valid_stem(stem):
        raise HTTPException(status_code=400, detail="Invalid dataset id")
    return {"dataset": stem, "columns": plans.suggest_value_kinds(DATA_DIR, stem)}


@app.post("/api/collections/import")
async def import_collection(file: UploadFile = File(...)):
    """A collection from an exported package (its collection.json); lists datasets not in the catalog."""
    import zipfile
    data = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            doc = json.loads(z.read("collection.json"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Not an UrbanTrace export (no collection.json)")
    fields = {k: v for k, v in doc.items() if k not in ("id", "schema", "created_at", "updated_at", "runs")}
    fields["name"] = (fields.get("name") or "Imported collection")
    created = _collections().create(fields)
    missing = [d.get("id") for d in doc.get("datasets", [])
               if catalog.dataset_path(DATA_DIR, catalog.stem_of(d.get("id"))) is None]
    return {"collection": created, "missing_datasets": missing}


# ==========================================
# ANALYSIS (docs/REDESIGN.md, phase 5)
# ==========================================

class SweepRequest(BaseModel):
    plan: Dict[str, Any]
    study_area: Optional[Dict[str, Any]] = None
    step: str
    column: str
    variants: List[Dict[str, Any]] = Field(default_factory=list)
    top_share: float = 0.2


class ValidateRequest(BaseModel):
    plan: Dict[str, Any]
    study_area: Optional[Dict[str, Any]] = None
    step: Optional[str] = None
    derived: Optional[List[Dict[str, Any]]] = None
    column: str
    outcomes: Dict[str, Any]
    quantiles: List[float] = Field(default_factory=lambda: [0.5, 0.6, 0.7])


class DasymetricRequest(BaseModel):
    study_area: Optional[Dict[str, Any]] = None
    zones: Dict[str, Any]
    target: Dict[str, Any]
    priors: List[Dict[str, Any]]
    normalize: Optional[str] = "share"
    fallback: str = "area"


def _analysis_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (analysis.AnalysisError, plans.PlanInputError, uw.UrbanweaveError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analysis/sweep")
def run_sweep(body: SweepRequest):
    """One step's column under alternative supports or methods: ranks and their stability per unit."""
    return _analysis_call(analysis.sweep, DATA_DIR, body.plan, body.study_area, _plan_cache(), step_id=body.step,
                          column=body.column, variants=body.variants, top_share=body.top_share)


@app.post("/api/analysis/validate")
def run_validation(body: ValidateRequest):
    """Coverage and lift of the highest-ranked units against outcome points (the paper's Table 3)."""
    return _analysis_call(analysis.validate_outcomes, DATA_DIR, body.plan, body.study_area, _plan_cache(),
                          step_id=body.step, column=body.column, outcomes=body.outcomes, quantiles=body.quantiles,
                          derived=body.derived)


@app.post("/api/analysis/dasymetric")
def run_dasymetric(body: DasymetricRequest):
    """Zone totals spread over finer targets in proportion to point priors."""
    return _analysis_call(analysis.dasymetric, DATA_DIR, body.study_area, _plan_cache(), zones=body.zones,
                          target=body.target, priors=body.priors, normalize=body.normalize, fallback=body.fallback)


def _run_collection_analyses(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Each analysis recorded on the collection, run again: {id, kind, name, payload | error, ...}."""
    out = []
    spec, area = doc.get("plan") or {}, doc.get("study_area")
    derived_all = doc.get("derived") or []
    for a in doc.get("analyses") or []:
        kind, cfg = a.get("kind"), dict(a.get("config") or {})
        name = _analysis_name(a)
        entry = {"id": a.get("id"), "kind": kind, "name": name, "config": cfg}
        try:
            if kind == "sweep":
                entry["payload"] = analysis.sweep(DATA_DIR, spec, area, _plan_cache(), step_id=cfg["step"],
                                                  column=cfg["column"], variants=cfg.get("variants") or [],
                                                  top_share=float(cfg.get("top_share", 0.2)))
            elif kind == "validation":
                derived = [d for d in derived_all if d.get("id") == cfg.get("derived")] if cfg.get("derived") else None
                entry["payload"] = analysis.validate_outcomes(DATA_DIR, spec, area, _plan_cache(), step_id=cfg.get("step"),
                                                              column=cfg["column"], outcomes=cfg["outcomes"],
                                                              quantiles=cfg.get("quantiles") or [0.5, 0.6, 0.7], derived=derived)
            elif kind == "dasymetric":
                entry["payload"] = analysis.dasymetric(DATA_DIR, area, _plan_cache(), zones=cfg["zones"], target=cfg["target"],
                                                       priors=cfg.get("priors") or [], normalize=cfg.get("normalize", "share"),
                                                       fallback=cfg.get("fallback", "area"))
            elif kind == "priority":
                key = cfg.get("result")
                derived = [d for d in derived_all if d.get("id") == key]
                run = plans.run(DATA_DIR, spec, area, _plan_cache(), outputs=[] if derived else [key], derived=derived)
                payload = run["steps"][key]
                payload["columns"]["priority"] = analysis.priority(payload["columns"], cfg.get("variables") or [])
                payload["kinds"]["priority"] = "intensive"
                if payload.get("geojson"):
                    for f, v in zip(payload["geojson"]["features"], payload["columns"]["priority"]):
                        f["properties"]["priority"] = v
                entry["payload"] = payload
            else:
                entry["error"] = f"unknown analysis kind {kind!r}"
        except (analysis.AnalysisError, plans.PlanInputError, uw.UrbanweaveError, KeyError) as e:
            entry["error"] = f"could not be run: {e}"
        out.append(entry)
    return out


def _payload_frame(payload: Dict[str, Any]) -> gpd.GeoDataFrame:
    geoms = analysis.payload_geometries(payload)
    frame = pd.DataFrame({"target_id": payload["target_ids"], **payload["columns"]})
    return gpd.GeoDataFrame(frame, geometry=geoms, crs="EPSG:4326")


def _analysis_name(a: Dict[str, Any]) -> str:
    """What an analysis is called in exports and reports: its kind and the column it is about
    (sweep_libraries, validation_schools_per_library), unless the user named it."""
    kind, cfg, name = a.get("kind") or "analysis", a.get("config") or {}, (a.get("name") or "").strip()
    generated = not name or re.fullmatch(rf"{re.escape(kind)} [0-9A-Za-z_]{{1,8}}", name)
    if not generated:
        return name
    about = cfg.get("column") or cfg.get("step") or a.get("id") or ""
    return f"{kind}_{about}".strip("_")


def _analysis_result(a: Dict[str, Any]) -> Dict[str, Any]:
    p = a["payload"]
    record = {k: p[k] for k in ("sweep", "validation", "dasymetric") if k in p}
    lines = []
    if "sweep" in p:
        sw = p["sweep"]
        lines.append(f"{sw['always_top']} of {sw['units']} units are in the top {round(sw['top_share'] * 100)}% under every variant; "
                     f"{sw['sometimes_top']} only under some.")
    if "validation" in p:
        for row in p["validation"]["table"]:
            lines.append(f"Top {round((1 - row['quantile']) * 100)}% of units hold {row['coverage']:.1%} of the outcomes "
                         f"(lift {row['lift']})." if row["coverage"] is not None and row["lift"] is not None else "")
    return {"name": a["name"], "frames": {"analysis": _payload_frame(p)}, "value_kinds": p.get("kinds"),
            "request": {"analysis": a["kind"], "config": a["config"], **record}, "description": f"{a['kind'].capitalize()} analysis.",
            "summary_lines": [l for l in lines if l]}


def _analysis_readme(analyses: List[Dict[str, Any]]) -> List[str]:
    if not analyses:
        return []
    lines = ["## Analyses", ""]
    for a in analyses:
        lines.append(f"### {a['name']} ({a['kind']})")
        lines.append("")
        p = a.get("payload")
        if not p:
            lines += [f"Not included: {a.get('error')}", ""]
            continue
        if "validation" in p:
            lines += ["| Quantile | Threshold | Coverage | Outcomes in top units | Outcomes | Baseline | Lift |", "|---|---|---|---|---|---|---|"]
            lines += [f"| {r['quantile']} | {r['threshold']} | {r['coverage']} | {r['n_high']} | {r['n_total']} | {r['baseline']} | {r['lift']} |"
                      for r in p["validation"]["table"]]
        if "sweep" in p:
            sw = p["sweep"]
            lines.append("Variants: " + "; ".join(f"{v['label']}" + ("" if v["ok"] else f" (failed: {v['error']})") for v in sw["variants"]) + ".")
            agree = [x["spearman"] for x in sw["agreement"] if x["spearman"] is not None]
            if agree:
                lines.append(f"Spearman correlation between variants: {min(agree):.2f} to {max(agree):.2f}.")
        if a["kind"] == "priority":
            undecided = [v.get("column") for v in a["config"].get("variables") or [] if v.get("direction") == "unknown"]
            vars_ = [v for v in a["config"].get("variables") or [] if v.get("direction") != "unknown"]
            if undecided:
                lines.append("Left out (no direction chosen): " + ", ".join(f"`{c}`" for c in undecided) + ".")
            lines.append("Priority = " + " + ".join(f"{v.get('weight')}×{'(1−' if v.get('direction') == 'inverted' else ''}"
                                                     f"norm({v.get('column')}){')' if v.get('direction') == 'inverted' else ''}" for v in vars_)
                         + " (weights rescaled to sum to 1; each variable min-max normalized over the units).")
            lines += [f"- {v.get('column')}: {v.get('rationale')}" for v in vars_ if v.get("rationale")]
        lines.append("")
    return lines


def _collection_report(doc: Dict[str, Any], analyses: Optional[List[Dict[str, Any]]] = None) -> str:
    """The printable report: plan results with maps and reports, analyses, caveats."""
    sections = []
    spec = doc.get("plan")
    if spec and spec.get("steps"):
        try:
            run = plans.run(DATA_DIR, spec, doc.get("study_area"), _plan_cache(),
                            outputs=[s["id"] for s in spec["steps"]], derived=doc.get("derived") or [])
            for sid, payload in run["steps"].items():
                cols = list(payload["columns"])
                if not cols:
                    continue
                title = (payload.get("derived") or {}).get("as") or sid   # a derived variable by its name
                sections.append({"title": f"Result: {title}", "svg": analysis.svg_map(payload, cols[-1], title=cols[-1]),
                                 "lines": _plan_report_lines(sid, run["reports"].get(sid)) +
                                          ([f"Derived: {payload['derived']['as']} = {payload['derived']['expression']}"]
                                           if payload.get("derived", {}).get("expression") else [])})
        except (plans.PlanInputError, uw.UrbanweaveError) as e:
            sections.append({"title": "Plan", "text": f"The plan could not be run: {e}"})
    analyses = analyses if analyses is not None else (_run_collection_analyses(doc) if spec else [])
    for a in analyses:
        p = a.get("payload")
        if not p:
            sections.append({"title": a["name"], "text": a.get("error")})
            continue
        sec = {"title": f"{a['name']} ({a['kind']})"}
        if "sweep" in p:
            sec["svg"] = analysis.svg_map(p, "top_share", title="Share of variants in which the unit ranks in the top")
            sec["lines"] = [f"{p['sweep']['always_top']} of {p['sweep']['units']} units are in the top under every variant."]
            sec["table"] = [["Variant", "Ran", "Units"]] + [[v["label"], "yes" if v["ok"] else v["error"], v.get("units")] for v in p["sweep"]["variants"]]
        elif "validation" in p:
            sec["svg"] = analysis.svg_map(p, p["validation"]["column"], title=p["validation"]["column"])
            sec["table"] = [["Quantile", "Threshold", "Coverage", "In top", "Outcomes", "Baseline", "Lift"]] + [
                [r["quantile"], r["threshold"], r["coverage"], r["n_high"], r["n_total"], r["baseline"], r["lift"]] for r in p["validation"]["table"]]
        elif "dasymetric" in p:
            col = next(iter(p["columns"]))
            sec["svg"] = analysis.svg_map(p, col, title=col)
        elif a["kind"] == "priority":
            sec["svg"] = analysis.svg_map(p, "priority", title="Priority index")
            sec["lines"] = [f"{v.get('column')}: weight {v.get('weight')}, {v.get('direction') or 'normal'}. {v.get('rationale') or ''}"
                            for v in a["config"].get("variables") or []]
        sections.append(sec)
    datasets = [{**d, "origin": catalog.origin(DATA_DIR, catalog.stem_of(d.get("id")))} for d in doc.get("datasets") or []]
    return analysis.report_html(doc, sections, scope.checks(DATA_DIR, doc), datasets)


@app.get("/api/collections/{cid}/report", response_class=HTMLResponse)
def collection_report(cid: str):
    """The collection as a printable HTML report."""
    return HTMLResponse(_collection_report(_get_collection(cid)))

# ==========================================
# 5. LLM COPILOT ENDPOINTS
# ==========================================

@app.post("/api/copilot/chat")
async def copilot_chat(request: CopilotChatRequest):
    """
    Chat endpoint for dashboard-aware copilot.
    Frontend should send current ReactFlow `nodes` and `edges`.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="`message` cannot be empty")

    if copilot_disabled():
        raise HTTPException(status_code=503, detail="The copilot's LLM is turned off; turn it on in the copilot settings.")

    try:
        copilot = get_copilot_agent()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize copilot: {str(e)}")

    try:
        copilot_result = copilot.run_copilot_turn(
            user_message=request.message,
            system_prompt=request.system_prompt,
            thinking_budget_tokens=request.thinking_budget_tokens,
            dashboard_nodes=request.nodes,
            dashboard_edges=request.edges,
            tools=COPILOT_FRONTEND_TOOLS,
            max_tool_rounds=3,
        )
        response_text = copilot_result.get("message", "")
        initial_response_text = copilot_result.get("assistant_initial_response", "")
        tool_calls = copilot_result.get("tool_calls", [])
        tool_responses = copilot_result.get("tool_responses", [])
        suggestions = copilot_result.get("suggestions", [])
        rounds_executed = copilot_result.get("rounds_executed", 0)
        tool_round_limit_reached = copilot_result.get("tool_round_limit_reached", False)

        if request.log_stream:
            print("\n=== COPILOT RESPONSE START ===", flush=True)
            print(f"rounds_executed={rounds_executed}", flush=True)
            print(f"tool_round_limit_reached={tool_round_limit_reached}", flush=True)
            print(f"assistant_initial_response={initial_response_text}", flush=True)
            if tool_calls:
                print(f"tool_call_count={len(tool_calls)}", flush=True)
                for idx, tool_call in enumerate(tool_calls, start=1):
                    print(
                        f"tool_call_{idx}={json.dumps(tool_call, ensure_ascii=True)}",
                        flush=True,
                    )
            else:
                print("tool_call_count=0", flush=True)
            print(f"tool_calls={json.dumps(tool_calls, ensure_ascii=True)}", flush=True)
            print(f"tool_responses={json.dumps(tool_responses, ensure_ascii=True)}", flush=True)
            print(f"suggestions={json.dumps(suggestions, ensure_ascii=True)}", flush=True)
            print(f"assistant_final_response={response_text}", flush=True)
            print("=== COPILOT RESPONSE END ===", flush=True)

        return {
            "status": "success",
            "message": response_text,
            "tool_calls": tool_calls,
            "tool_responses": tool_responses,
            "suggestions": suggestions,
            "rounds_executed": rounds_executed,
            "tool_round_limit_reached": tool_round_limit_reached,
            "node_count": len(request.nodes),
            "edge_count": len(request.edges),
            "log_stream": request.log_stream,  # now used as debug-print flag
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot chat failed: {str(e)}")
