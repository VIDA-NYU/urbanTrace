from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import geopandas as gpd
import json
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
from integration_engine import IntegrationPipeline, ZonedIntegrationPipeline, MultivariateIntegrationPipeline, VariableTrackConfig
from grids.h3_grid import H3GridSystem

from operators.allocation.binary import BinaryContainment, BinaryCentroidContainment, NearestAssignment
from operators.allocation.proportional import ProportionalAreaWeighted, ProportionalLengthWeighted
from operators.allocation.kernel import GaussianKernel

from operators.aggregation.aggregators import (
    SumAggregation, MeanAggregation, WeightedMeanAggregation, DensityAggregation,
    MajorityAggregation, MaxAggregation, MinAggregation, LengthWeightedAggregation
)

from operators.zoning.mapping import (
    CentroidZoning,
    AreaWeightedZoning,
    LengthWeightedZoning as LengthWeightedZoningMapping,
)
from operators.zoning.aggregators import (
    SumZoning, WeightedMeanZoning, DensityZoning,
    MajorityZoning, MaxZoning, MinZoning,
    LengthWeightedZoning as LengthWeightedZoningAggregation,
)

# --- Imports for Map Algebra Engine ---
from h3_engine import rasterize_geojson_to_h3 
from llm_agent import UrbanTraceCopilot
from tool import COPILOT_FRONTEND_TOOLS

# ==========================================
# 1. APP SETUP & CONSTANTS
# ==========================================

app = FastAPI(title="UrbanTrace Spatial API")

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

# Operator Registries for Formal Integration
ALLOCATION_REGISTRY = {
    "BinaryContainment": BinaryContainment,
    "BinaryCentroidContainment": BinaryCentroidContainment,
    "ProportionalAreaWeighted": ProportionalAreaWeighted,
    "ProportionalLengthWeighted": ProportionalLengthWeighted,
    "NearestAssignment": NearestAssignment,
    "GaussianKernel": GaussianKernel
}

AGGREGATION_REGISTRY = {
    # Mathematical operators (continuous/additive data)
    "SumAggregation": SumAggregation,
    "MeanAggregation": MeanAggregation,
    "WeightedMeanAggregation": WeightedMeanAggregation,
    "DensityAggregation": DensityAggregation,
    # Discrete selection operators (categorical/index data)
    "MajorityAggregation": MajorityAggregation,
    "MaxAggregation": MaxAggregation,
    "MinAggregation": MinAggregation,
    # Line network operators (street/transit geometries)
    "LengthWeightedAggregation": LengthWeightedAggregation
}

# Zoning Operator Registries
ZONING_MAPPING_REGISTRY = {
    "CentroidZoning": CentroidZoning,
    "AreaWeightedZoning": AreaWeightedZoning,
    "LengthWeightedZoning": LengthWeightedZoningMapping
}

ZONING_AGGREGATION_REGISTRY = {
    # Mathematical operators (for continuous/additive data)
    "SumZoning": SumZoning,
    "WeightedMeanZoning": WeightedMeanZoning,
    "DensityZoning": DensityZoning,
    # Discrete selection operators (for categorical/index data)
    "MajorityZoning": MajorityZoning,
    "MaxZoning": MaxZoning,
    "MinZoning": MinZoning,
    # Line network operators (for street/transit geometries)
    "LengthWeightedZoning": LengthWeightedZoningAggregation
}

# Geometry constraints for valid operator selection
GEOMETRY_CONSTRAINTS = {
    "Point": ["BinaryContainment", "BinaryCentroidContainment", "NearestAssignment", "GaussianKernel"],
    "MultiPoint": ["BinaryContainment", "BinaryCentroidContainment", "NearestAssignment", "GaussianKernel"],
    "LineString": ["ProportionalLengthWeighted", "GaussianKernel"],
    "MultiLineString": ["ProportionalLengthWeighted", "GaussianKernel"],
    "Polygon": ["ProportionalAreaWeighted", "BinaryCentroidContainment"],
    "MultiPolygon": ["ProportionalAreaWeighted", "BinaryCentroidContainment"]
}

# ==========================================
# 2. PYDANTIC REQUEST MODELS
# ==========================================

class IntegrationRequest(BaseModel):
    """Payload for the formal mathematical spatial integration (I = A_1 ∘ R)."""
    dataset_path: str        
    target_column: str       
    allocation_operator: str 
    aggregation_operator: str 
    resolution: int          

class OperationRequest(BaseModel):
    """Payload for fast map algebra (intersect, union, preview)."""
    operationType: str          
    datasetIds: list[str]       
    resolution: int = 9


class ZonedIntegrationRequest(BaseModel):
    """
    Payload for full zoned integration pipeline: I = A_2 ∘ Z_map ∘ A_1 ∘ R
    Transforms source data through grid to reporting zones.
    """
    dataset_path: str              # Source dataset filename
    target_column: str             # Attribute column to integrate
    allocation_operator: str       # R: spatial allocation method
    grid_aggregation_operator: str # A_1: cell-level aggregation
    zoning_mapping_operator: str   # Z_map: cell-to-zone mapping
    zoning_aggregation_operator: str  # A_2: zone-level aggregation
    zones_path: str                # Reporting zones dataset filename
    resolution: int = 9            # H3 grid resolution
    output_mode: str = "zones"     # "grid" | "zones" | "both"


class VariableConfigRequest(BaseModel):
    """Configuration for a single variable in multivariate analysis."""
    dataset_path: str              # Source dataset filename
    target_column: str             # Attribute column to integrate
    output_name: Optional[str] = None  # Column name in merged output (defaults to target_column)
    allocation_operator: str       # R: spatial allocation method
    grid_aggregation_operator: str # A_1: cell-level aggregation
    zoning_mapping_operator: Optional[str] = None   # Z_map: cell-to-zone mapping
    zoning_aggregation_operator: Optional[str] = None  # A_2: zone-level aggregation


class MultivariateIntegrationRequest(BaseModel):
    """
    Payload for multivariate spatial analysis with parallel processing.
    
    Supports multiple datasets with independent mathematical rules,
    merged into unified grid and/or zone output.
    """
    variables: List[VariableConfigRequest]  # List of variable configurations
    zones_path: Optional[str] = None        # Optional reporting zones
    resolution: int = 9                     # H3 grid resolution
    output_mode: str = "grid"               # "grid" | "zones" | "both"


class CopilotTargetZoning(BaseModel):
    dataset_name: str
    geometry_type: Optional[str] = None


class CopilotSourceVariable(BaseModel):
    dataset_name: str
    column_name: str
    original_geometry: Optional[str] = None


class CopilotRecommendRequest(BaseModel):
    target_zoning: CopilotTargetZoning
    source_variables: List[CopilotSourceVariable]


class CopilotChatRequest(BaseModel):
    """Payload for UrbanTrace LLM copilot chat with live dashboard graph context."""
    message: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt: str = "You are a helpful assistant for UrbanTrace."
    thinking_budget_tokens: int | None = None
    log_stream: bool = True


def get_copilot_agent() -> UrbanTraceCopilot:
    """Lazy singleton so missing API keys do not crash app startup."""
    global _COPILOT_AGENT
    if _COPILOT_AGENT is None:
        _COPILOT_AGENT = UrbanTraceCopilot()
    return _COPILOT_AGENT


class HotspotVariableRequest(BaseModel):
    dataset_name: str
    column_name: str


class HotspotSynthesisRequest(BaseModel):
    source_variables: List[HotspotVariableRequest]
    goal: Optional[str] = None  # User-defined priority goal (e.g. "pedestrian safety risk")


# ==========================================
# 3. DATASET MANAGEMENT ENDPOINTS
# ==========================================

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
            
            datasets.append(dataset_info)
            
    return {"datasets": datasets}

@app.get("/dataset/{filename}")
async def get_geojson(filename: str, simplify: bool = False):
    print(f"Requesting dataset: {filename} (simplify={simplify})")
    """Serves raw or simplified GeoJSON data to the frontend."""
    geojson_dir = os.path.join(DATA_DIR, "geojson")
    resolved_filename = _geojson_filename(filename)
    path = os.path.join(geojson_dir, resolved_filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    
    gdf = gpd.read_file(path)
    
    if gdf.crs and gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    if simplify:
        # Simplify geometry to reduce payload size for UI previews
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
        
    return gdf.__geo_interface__


# ==========================================
# 7. MULTIVARIATE INTEGRATION ENDPOINT (Parallel Tracks + Dual-Merge)
# ==========================================

@app.post("/api/integrate_multivariate")
async def integrate_multivariate(request: MultivariateIntegrationRequest):
    """
    Executes multivariate spatial analysis with parallel processing.
    
    Each variable is processed through its own mathematical pipeline,
    then merged into a unified grid and/or zone output.
    
    Architecture:
    - Step 1: Parallel Source → Grid (each variable uses its own R + A_1)
    - Step 1.5: Merge on cell_id → Unified Grid
    - Step 2: Parallel Grid → Zone (each variable uses its own Z_map + A_2)
    - Step 3: Merge on zone_id → Unified Zones
    """
    try:
        if not request.variables:
            raise HTTPException(status_code=400, detail="At least one variable is required")
        
        # Build track configurations
        tracks = []
        
        for var in request.variables:
            # Validate operators
            if var.allocation_operator not in ALLOCATION_REGISTRY:
                raise HTTPException(status_code=400, detail=f"Unknown allocation operator: {var.allocation_operator}")
            if var.grid_aggregation_operator not in AGGREGATION_REGISTRY:
                raise HTTPException(status_code=400, detail=f"Unknown grid aggregation operator: {var.grid_aggregation_operator}")
            
            # Load source dataset
            source_path = os.path.join(
                DATA_DIR,
                "geojson",
                _geojson_filename(var.dataset_path),
            )
            try:
                source_gdf = gpd.read_file(source_path)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Could not load {var.dataset_path}: {str(e)}")
            
            # Validate allocation operator against geometry
            geom_types = source_gdf.geometry.geom_type.unique()
            for geom_type in geom_types:
                if geom_type in GEOMETRY_CONSTRAINTS:
                    allowed = GEOMETRY_CONSTRAINTS[geom_type]
                    if var.allocation_operator not in allowed:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Operator '{var.allocation_operator}' not valid for {geom_type} in {var.dataset_path}"
                        )
            
            # Build operators
            allocator = ALLOCATION_REGISTRY[var.allocation_operator]()
            grid_aggregator = AGGREGATION_REGISTRY[var.grid_aggregation_operator]()
            
            # Optional zoning operators
            zoning_mapper = None
            zoning_aggregator = None
            
            if var.zoning_mapping_operator and var.zoning_aggregation_operator:
                if var.zoning_mapping_operator not in ZONING_MAPPING_REGISTRY:
                    raise HTTPException(status_code=400, detail=f"Unknown zoning mapping operator: {var.zoning_mapping_operator}")
                if var.zoning_aggregation_operator not in ZONING_AGGREGATION_REGISTRY:
                    raise HTTPException(status_code=400, detail=f"Unknown zoning aggregation operator: {var.zoning_aggregation_operator}")
                
                zoning_mapper = ZONING_MAPPING_REGISTRY[var.zoning_mapping_operator]()
                zoning_aggregator = ZONING_AGGREGATION_REGISTRY[var.zoning_aggregation_operator]()
            
            # Create track config (default output_name to target_column)
            track = VariableTrackConfig(
                source_gdf=source_gdf,
                target_column=var.target_column,
                output_name=var.output_name or var.target_column,
                allocator=allocator,
                grid_aggregator=grid_aggregator,
                zoning_mapper=zoning_mapper,
                zoning_aggregator=zoning_aggregator
            )
            tracks.append(track)
        
        # Load zones if provided
        zones_gdf = None
        if request.zones_path:
            zones_path = os.path.join(
                DATA_DIR,
                "geojson",
                _geojson_filename(request.zones_path),
            )
            try:
                zones_gdf = gpd.read_file(zones_path)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Could not load zones: {str(e)}")
        
        # Execute multivariate pipeline
        grid = H3GridSystem()
        pipeline = MultivariateIntegrationPipeline(grid_system=grid)
        
        result = pipeline.run(
            tracks=tracks,
            resolution=request.resolution,
            zones_gdf=zones_gdf,
            output_mode=request.output_mode
        )
        
        # Build response
        response = {
            "status": "success",
            "operation": "multivariate_integration",
            "resolution": request.resolution,
            "variables": [v.output_name or v.target_column for v in request.variables]
        }
        
        # Convert grid output
        if 'grid' in result:
            grid_gdf = result['grid']
            df_no_geom = grid_gdf.drop(columns=['geometry'])
            final_hex_data = {}
            
            # Get variable names for this request
            var_names = [(v.output_name or v.target_column) for v in request.variables]
            
            for _, row in df_no_geom.iterrows():
                row_dict = row.to_dict()
                cell_id = row_dict.pop('cell_id', None)
                if not cell_id:
                    continue
                
                # Get all variable values
                var_values = {name: row_dict.get(name, 0) for name in var_names}
                
                # Use sum of variable values for visualization intensity
                total_value = sum(var_values.values())
                
                final_hex_data[cell_id] = {
                    "count": total_value,
                    "variables": var_values,
                    "sample_props": row_dict
                }
            
            response["data"] = final_hex_data
            response["hex_count"] = len(final_hex_data)
        
        # Convert zones output
        if 'zones' in result:
            zones_gdf = result['zones']
            response["geojson"] = json.loads(zones_gdf.to_json())
            response["zone_count"] = len(zones_gdf)
        
        return response
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multivariate integration failed: {str(e)}")


@app.get("/api/operators")
async def get_available_operators():
    """
    Returns all available operators and geometry constraints for the frontend.
    Enables dynamic operator selection UI.
    """
    return {
        "allocation": list(ALLOCATION_REGISTRY.keys()),
        "grid_aggregation": list(AGGREGATION_REGISTRY.keys()),
        "zoning_mapping": list(ZONING_MAPPING_REGISTRY.keys()),
        "zoning_aggregation": list(ZONING_AGGREGATION_REGISTRY.keys()),
        "geometry_constraints": GEOMETRY_CONSTRAINTS
    }


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


def _classify_variable(dataset_name: str, column_name: str, column_meta: Dict[str, Any], sample_data: List[Any]) -> str:
    label = f"{dataset_name} {column_name}".lower()
    distinct = column_meta.get("num_distinct_values")
    structural = str(column_meta.get("structural_type", "")).lower()

    numeric_samples = [v for v in sample_data if isinstance(v, (int, float))]
    has_decimal = any(isinstance(v, float) and not float(v).is_integer() for v in numeric_samples)

    if any(k in label for k in ["index", "rank", "score", "class", "category", "vulnerability"]):
        return "Ordinal Index"
    if distinct is not None and isinstance(distinct, (int, float)) and distinct <= 10 and "integer" in structural:
        return "Ordinal Index"
    if has_decimal or any(k in label for k in ["rate", "ratio", "density", "avg", "average", "mean", "median", "%", "percent"]):
        return "Intensive"
    if any(k in label for k in ["count", "total", "population", "incidents", "arrests", "collisions", "units", "volume"]):
        return "Extensive"
    return "Extensive"


def _pick_mapping_operator(target_geometry: str, available_mapping_ops: List[str]) -> str:
    g = (target_geometry or "").lower()
    if g in ["point", "multipoint"]:
        for candidate in ["CentroidZoning"]:
            if candidate in available_mapping_ops:
                return candidate
        return available_mapping_ops[0]

    if g in ["linestring", "multilinestring"]:
        for candidate in ["LengthWeightedZoning", "CentroidZoning"]:
            if candidate in available_mapping_ops:
                return candidate
        return available_mapping_ops[0]

    for candidate in ["AreaWeightedZoning", "CentroidZoning"]:
        if candidate in available_mapping_ops:
            return candidate
    return available_mapping_ops[0]


def _pick_aggregation_operator(classification: str, available_agg_ops: List[str]) -> str:
    if classification == "Ordinal Index":
        for candidate in ["MajorityZoning", "MaxZoning", "MinZoning"]:
            if candidate in available_agg_ops:
                return candidate
    elif classification == "Intensive":
        for candidate in ["WeightedMeanZoning", "DensityZoning", "MeanZoning"]:
            if candidate in available_agg_ops:
                return candidate
    else:
        for candidate in ["SumZoning", "WeightedMeanZoning"]:
            if candidate in available_agg_ops:
                return candidate

    return available_agg_ops[0]


def _heuristic_recommendations(llm_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    target_geometry = llm_payload.get("zoning_target", {}).get("geometry_type") or "Polygon"
    mapping_ops = llm_payload.get("available_mapping_operators", [])
    agg_ops = llm_payload.get("available_aggregation_operators", [])

    results: List[Dict[str, Any]] = []
    for var in llm_payload.get("source_variables", []):
        dataset_name = var.get("dataset_name")
        column_meta = var.get("column_metadata", {})
        column_name = column_meta.get("name")
        sample_data = var.get("sample_data", [])
        classification = _classify_variable(dataset_name, column_name, column_meta, sample_data)
        zoning_mapping = _pick_mapping_operator(target_geometry, mapping_ops)
        zoning_aggregation = _pick_aggregation_operator(classification, agg_ops)

        reasoning = (
            f"Classified as {classification} using column name, distinct values, and sample distribution. "
            f"Selected {zoning_mapping} for target geometry {target_geometry} and {zoning_aggregation} for mathematically safe zoning aggregation."
        )

        results.append({
            "dataset_name": dataset_name,
            "column_name": column_name,
            "classification": classification,
            "zoningMapping": zoning_mapping,
            "zoningAggregation": zoning_aggregation,
            "reasoning": reasoning,
            "engine": "heuristic"
        })

    return results


def _infer_hotspot_direction(dataset_name: str, column_name: str, sample_data: List[Any]) -> str:
    label = f"{dataset_name} {column_name}".lower()

    inverted_keywords = [
        "income", "wealth", "salary", "resource", "access", "coverage",
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

    return "normal"


def _hotspot_reasoning(direction: str, dataset_name: str, column_name: str) -> str:
    if direction == "inverted":
        return f"Lower values in {column_name} ({dataset_name}) indicate higher unmet need, so scale is inverted for hotspot priority."
    return f"Higher values in {column_name} ({dataset_name}) directly indicate higher risk/need, so scale is used as-is."


def _build_heuristic_hotspot_audits(
    source_payload: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    audits: List[Dict[str, Any]] = []
    for var in source_payload:
        direction = _infer_hotspot_direction(
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
        metadata_path = _metadata_path_for_dataset(item.dataset_name)
        if not os.path.exists(metadata_path):
            raise HTTPException(status_code=404, detail=f"Metadata not found for dataset: {item.dataset_name}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        column_meta = next((c for c in metadata.get("columns", []) if c.get("name") == item.column_name), None)
        if not column_meta:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{item.column_name}' not found in metadata for dataset '{item.dataset_name}'"
            )

        sample_values = _extract_sample_values(metadata.get("sample"), item.column_name, max_rows=20)
        source_payload.append({
            "dataset_name": _normalize_dataset_stem(item.dataset_name),
            "column_name": item.column_name,
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
        direction = "inverted" if direction_raw == "inverted" else "normal"
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
        "variables": normalized_audits,
        "summary": "Priority score is synthesized as a weighted normalized blend where 1.0 always means highest need."
    }


@app.post("/api/v1/copilot/recommend-operators")
async def recommend_operators(request: CopilotRecommendRequest):
    """
    Recommends zoning operators (zoningMapping + zoningAggregation) per source variable.
    Grid operators remain frontend deterministic based on geometry.
    """
    if not request.source_variables:
        raise HTTPException(status_code=400, detail="source_variables cannot be empty")

    available_mapping_operators = list(ZONING_MAPPING_REGISTRY.keys())
    available_aggregation_operators = list(ZONING_AGGREGATION_REGISTRY.keys())

    source_payload: List[Dict[str, Any]] = []
    for source_var in request.source_variables:
        metadata_path = _metadata_path_for_dataset(source_var.dataset_name)
        if not os.path.exists(metadata_path):
            raise HTTPException(status_code=404, detail=f"Metadata not found for dataset: {source_var.dataset_name}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        column_meta = next(
            (c for c in metadata.get("columns", []) if c.get("name") == source_var.column_name),
            None
        )
        if not column_meta:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{source_var.column_name}' not found in metadata for dataset '{source_var.dataset_name}'"
            )

        sample_values = _extract_sample_values(metadata.get("sample"), source_var.column_name, max_rows=20)
        source_payload.append({
            "dataset_name": _normalize_dataset_stem(source_var.dataset_name),
            "original_geometry": source_var.original_geometry or metadata.get("geometricType"),
            "column_metadata": {
                "name": column_meta.get("name"),
                "structural_type": column_meta.get("structural_type"),
                "num_distinct_values": column_meta.get("num_distinct_values"),
                "mean": column_meta.get("mean"),
                "stddev": column_meta.get("stddev"),
                "coverage": column_meta.get("coverage", [])
            },
            "sample_data": sample_values
        })

    llm_payload = {
        "task": "Determine zoning spatial mapping and aggregation operators based on statistical metadata.",
        "zoning_target": {
            "dataset_name": _normalize_dataset_stem(request.target_zoning.dataset_name),
            "geometry_type": request.target_zoning.geometry_type or "Polygon"
        },
        "available_mapping_operators": available_mapping_operators,
        "available_aggregation_operators": available_aggregation_operators,
        "source_variables": source_payload
    }

    used_engine = "llm"
    llm_result: Optional[List[Dict[str, Any]]] = None
    try:
        copilot = get_copilot_agent()
    except Exception as exc:
        print(f"Operator recommendation copilot unavailable: {exc}")
    else:
        llm_result = await asyncio.to_thread(
            copilot.recommend_zoning_operators,
            llm_payload,
        )
    if not llm_result:
        llm_result = _heuristic_recommendations(llm_payload)
        used_engine = "heuristic"

    # Enforce available operators and request alignment
    requested_pairs = {
        (_normalize_dataset_stem(s.dataset_name), s.column_name): s
        for s in request.source_variables
    }
    normalized_response: List[Dict[str, Any]] = []

    for rec in llm_result:
        dataset_name = _normalize_dataset_stem(str(rec.get("dataset_name", "")))
        column_name = str(rec.get("column_name", ""))
        if (dataset_name, column_name) not in requested_pairs:
            continue

        classification = str(rec.get("classification", "Extensive"))
        zoning_mapping = str(rec.get("zoningMapping", ""))
        zoning_aggregation = str(rec.get("zoningAggregation", ""))
        reasoning = str(rec.get("reasoning", ""))

        if zoning_mapping not in available_mapping_operators:
            zoning_mapping = _pick_mapping_operator(
                llm_payload["zoning_target"]["geometry_type"],
                available_mapping_operators
            )
        if zoning_aggregation not in available_aggregation_operators:
            zoning_aggregation = _pick_aggregation_operator(classification, available_aggregation_operators)

        normalized_response.append({
            "dataset_name": dataset_name,
            "column_name": column_name,
            "classification": classification,
            "zoningMapping": zoning_mapping,
            "zoningAggregation": zoning_aggregation,
            "reasoning": reasoning or "Recommended using metadata statistics and geometry-aware zoning constraints.",
            "engine": rec.get("engine", used_engine)
        })

    if not normalized_response:
        normalized_response = _heuristic_recommendations(llm_payload)

    return normalized_response




# ==========================================
# 4. MAP ALGEBRA ENDPOINT (Fast Rasterization)
# Deprecated but still available because OperationNode relies on it for quick previews and set operations across datasets. Does not use formal Operators but direct H3 rasterization and Python set logic for speed.
# ==========================================

@app.post("/run-operation")
async def run_operation(request: OperationRequest):
    """Performs quick H3 map algebra (preview, intersect, union) across multiple datasets."""
    if not request.datasetIds:
        raise HTTPException(status_code=400, detail="No datasets provided")

    all_hex_maps = []

    try:
        for dataset_id in request.datasetIds:
            canonical_id = _strip_dataset_suffixes(dataset_id)
            filepath = os.path.join(DATA_DIR, "geojson", _geojson_filename(dataset_id))
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail=f"Dataset not found at {filepath}")
            
            print(f"Rasterizing {canonical_id}...")
            hex_data = rasterize_geojson_to_h3(filepath, request.resolution)
            all_hex_maps.append({"id": canonical_id, "data": hex_data})

        final_hex_data = {}

        if request.operationType == "preview" or len(all_hex_maps) == 1:
            final_hex_data = all_hex_maps[0]["data"]

        elif request.operationType == "intersect":
            sets_of_keys = [set(hm["data"].keys()) for hm in all_hex_maps]
            intersected_keys = set.intersection(*sets_of_keys)

            for key in intersected_keys:
                total_count = sum(hm["data"][key]["count"] for hm in all_hex_maps)
                final_hex_data[key] = {
                    "count": total_count,
                    "sources": [hm["id"] for hm in all_hex_maps],
                    "sample_props": all_hex_maps[0]["data"][key].get("sample_props", {})
                }

        elif request.operationType in ["merge", "union"]:
            sets_of_keys = [set(hm["data"].keys()) for hm in all_hex_maps]
            union_keys = set.union(*sets_of_keys)

            for key in union_keys:
                count = 0
                sources = []
                props = {}
                
                for hm in all_hex_maps:
                    if key in hm["data"]:
                        count += hm["data"][key]["count"]
                        sources.append(hm["id"])
                        if not props: 
                            props = hm["data"][key].get("sample_props", {})

                final_hex_data[key] = {
                    "count": count,
                    "sources": sources,
                    "sample_props": props
                }
        else:
             raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operationType}")

        return {
            "status": "success",
            "operation": request.operationType,
            "resolution": request.resolution,
            "hex_count": len(final_hex_data),
            "data": final_hex_data
        }

    except Exception as e:
        print(f"Error during operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ==========================================
# 5. FORMAL INTEGRATION ENDPOINT (I = A_1 ∘ R)
# ==========================================

# @app.post("/api/integrate_test")
# async def integrate_datasets(request: IntegrationRequest):
#     """
#     DEBUG VERSION:
#     Converts IntegrationRequest into OperationRequest
#     and calls the /run-operation logic to test frontend compatibility.
#     """

#     try:
#         # Extract dataset id from dataset_path
#         # Example: "NYC_pedestrian_counts.geojson" -> "NYC_pedestrian_counts"
#         dataset_id = _strip_dataset_suffixes(Path(request.dataset_path).stem)
#
#         # Build equivalent request for /run-operation
#         operation_request = OperationRequest(
#             operationType="preview",
#             datasetIds=[dataset_id],
#             resolution=request.resolution
#         )

#         # Directly reuse the same logic
#         return await run_operation(operation_request)

#     except Exception as e:
#         print(f"Error in /api/integrate debug: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
    
# @app.post("/api/integrate")
# async def integrate_datasets(request: IntegrationRequest):
#     """Executes the formal spatial integration pipeline using explicit Operators."""
#     try:
#         if request.allocation_operator not in ALLOCATION_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown allocation operator: {request.allocation_operator}")
#         if request.aggregation_operator not in AGGREGATION_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown aggregation operator: {request.aggregation_operator}")

#         AllocatorClass = ALLOCATION_REGISTRY[request.allocation_operator]
#         AggregatorClass = AGGREGATION_REGISTRY[request.aggregation_operator]
        
#         allocator = AllocatorClass()
#         aggregator = AggregatorClass()
#         grid = H3GridSystem()

#         # Build path to the requested dataset
#         dataset_full_path = os.path.join(
#             DATA_DIR,
#             "geojson",
#             _geojson_filename(request.dataset_path),
#         )
        
#         try:
#             source_gdf = gpd.read_file(dataset_full_path)
#         except Exception as e:
#             raise HTTPException(status_code=404, detail=f"Could not load dataset at {dataset_full_path}: {str(e)}")

#         pipeline = IntegrationPipeline(grid, allocator, aggregator)
        
#         result_gdf = pipeline.run(
#             source_gdf=source_gdf,
#             target_column=request.target_column,
#             resolution=request.resolution
#         )

#         # --- NEW CODE STARTS HERE ---
#         # --- NEW CODE: Add 'the_geom' so H3PreviewDeckGL knows where to center the camera ---
#         result_gdf['the_geom'] = result_gdf.geometry.centroid.apply(lambda p: f"POINT ({p.x} {p.y})")
        
#         # 1. Drop the heavy geometry column to speed things up
#         df_no_geom = result_gdf.drop(columns=['geometry'])
        
#         final_hex_data = {}
        
#         # 2. Iterate through the rows and build the exact dictionary the frontend expects
#         for _, row in df_no_geom.iterrows():
#             row_dict = row.to_dict()
            
#             # Extract the cell_id to use as the dictionary key
#             cell_id = row_dict.pop('cell_id', None)
#             if not cell_id:
#                 continue
                
#             # Find the primary calculated value (e.g., 'allocated_val') to act as 'count' for DeckGL
#             primary_value = 1
#             for key, val in row_dict.items():
#                 if key != 'area' and isinstance(val, (int, float)):
#                     primary_value = val
#                     break
            
#             # Format exactly like /run-operation
#             final_hex_data[cell_id] = {
#                 "count": primary_value,
#                 "sample_props": row_dict
#             }

#         return {
#             "status": "success",
#             "operation": "integration",
#             "resolution": request.resolution,
#             "hex_count": len(final_hex_data),
#             "data": final_hex_data
#         }

#     except ValueError as ve:
#         raise HTTPException(status_code=400, detail=str(ve))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Integration failed: {str(e)}")

#     #     return json.loads(result_gdf.to_json())

#     # except ValueError as ve:
#     #     raise HTTPException(status_code=400, detail=str(ve))
#     # except Exception as e:
#     #     raise HTTPException(status_code=500, detail=f"Integration failed: {str(e)}")


# ==========================================
# 6. ZONED INTEGRATION ENDPOINT (I = A_2 ∘ Z_map ∘ A_1 ∘ R)
# ==========================================

# @app.post("/api/integrate_zoned")
# async def integrate_to_zones(request: ZonedIntegrationRequest):
#     """
#     Executes the full zoned integration pipeline.
#     Transforms source data through a common H3 grid to reporting zones.
    
#     Pipeline: D^(k) → R → x_j (grid) → Z → y_ℓ (zones)
#     """
#     try:
#         # Validate operator selections
#         if request.allocation_operator not in ALLOCATION_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown allocation operator: {request.allocation_operator}")
#         if request.grid_aggregation_operator not in AGGREGATION_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown grid aggregation operator: {request.grid_aggregation_operator}")
#         if request.zoning_mapping_operator not in ZONING_MAPPING_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown zoning mapping operator: {request.zoning_mapping_operator}")
#         if request.zoning_aggregation_operator not in ZONING_AGGREGATION_REGISTRY:
#             raise HTTPException(status_code=400, detail=f"Unknown zoning aggregation operator: {request.zoning_aggregation_operator}")

#         # Instantiate operators via dependency injection
#         allocator = ALLOCATION_REGISTRY[request.allocation_operator]()
#         grid_aggregator = AGGREGATION_REGISTRY[request.grid_aggregation_operator]()
#         zoning_mapper = ZONING_MAPPING_REGISTRY[request.zoning_mapping_operator]()
#         zoning_aggregator = ZONING_AGGREGATION_REGISTRY[request.zoning_aggregation_operator]()
#         grid = H3GridSystem()

#         # Load source dataset
#         source_path = os.path.join(
#             DATA_DIR,
#             "geojson",
#             _geojson_filename(request.dataset_path),
#         )
#         try:
#             source_gdf = gpd.read_file(source_path)
#         except Exception as e:
#             raise HTTPException(status_code=404, detail=f"Could not load source dataset: {str(e)}")

#         # Load zones dataset  
#         zones_path = os.path.join(
#             DATA_DIR,
#             "geojson",
#             _geojson_filename(request.zones_path),
#         )
#         try:
#             zones_gdf = gpd.read_file(zones_path)
#         except Exception as e:
#             raise HTTPException(status_code=404, detail=f"Could not load zones dataset: {str(e)}")

#         # Validate allocation operator against geometry type
#         geom_types = source_gdf.geometry.geom_type.unique()
#         for geom_type in geom_types:
#             if geom_type in GEOMETRY_CONSTRAINTS:
#                 allowed = GEOMETRY_CONSTRAINTS[geom_type]
#                 if request.allocation_operator not in allowed:
#                     raise HTTPException(
#                         status_code=400, 
#                         detail=f"Operator '{request.allocation_operator}' not valid for {geom_type}. Allowed: {allowed}"
#                     )

#         # Build and execute the zoned integration pipeline
#         pipeline = ZonedIntegrationPipeline(
#             grid_system=grid,
#             allocator=allocator,
#             grid_aggregator=grid_aggregator,
#             zoning_mapper=zoning_mapper,
#             zoning_aggregator=zoning_aggregator
#         )
        
#         # Determine output mode
#         output_mode = getattr(request, 'output_mode', 'zones')
        
#         response = {
#             "status": "success",
#             "operation": "zoned_integration",
#             "resolution": request.resolution,
#         }
        
#         # Generate grid data if needed (for "grid" or "both" modes)
#         if output_mode in ["grid", "both"]:
#             # Use run_grid_with_zone_values to paint zone-aggregated values back to cells
#             # This ensures cells within a zone all show the same aggregated value
#             grid_result_gdf = pipeline.run_grid_with_zone_values(
#                 source_gdf=source_gdf,
#                 target_column=request.target_column,
#                 resolution=request.resolution,
#                 zones_gdf=zones_gdf
#             )
            
#             # Convert grid GeoDataFrame to H3 hex dictionary format
#             df_no_geom = grid_result_gdf.drop(columns=['geometry'])
#             final_hex_data = {}
            
#             for _, row in df_no_geom.iterrows():
#                 row_dict = row.to_dict()
#                 cell_id = row_dict.pop('cell_id', None)
#                 if not cell_id:
#                     continue
                    
#                 # Use the zone_aggregated_value as the primary value
#                 primary_value = row_dict.get('zone_aggregated_value', 1)
                
#                 final_hex_data[cell_id] = {
#                     "count": primary_value,
#                     "sample_props": row_dict
#                 }
            
#             response["data"] = final_hex_data
#             response["hex_count"] = len(final_hex_data)
        
#         # Generate zone data if needed (for "zones" or "both" modes)
#         if output_mode in ["zones", "both"]:
#             zone_result_gdf = pipeline.run(
#                 source_gdf=source_gdf,
#                 target_column=request.target_column,
#                 resolution=request.resolution,
#                 zones_gdf=zones_gdf
#             )
#             response["geojson"] = json.loads(zone_result_gdf.to_json())
#             response["zone_count"] = len(zone_result_gdf)
        
#         return response

#     except ValueError as ve:
#         raise HTTPException(status_code=400, detail=str(ve))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Zoned integration failed: {str(e)}")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zoned integration failed: {str(e)}")


@app.get("/api/operators")
async def get_available_operators():
    """
    Returns all available operators and geometry constraints for the frontend.
    Enables dynamic operator selection UI.
    """
    return {
        "allocation": list(ALLOCATION_REGISTRY.keys()),
        "grid_aggregation": list(AGGREGATION_REGISTRY.keys()),
        "zoning_mapping": list(ZONING_MAPPING_REGISTRY.keys()),
        "zoning_aggregation": list(ZONING_AGGREGATION_REGISTRY.keys()),
        "geometry_constraints": GEOMETRY_CONSTRAINTS
    }


# ==========================================
# 7. LLM COPILOT ENDPOINTS
# ==========================================

@app.post("/api/copilot/chat")
async def copilot_chat(request: CopilotChatRequest):
    """
    Chat endpoint for dashboard-aware copilot.
    Frontend should send current ReactFlow `nodes` and `edges`.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="`message` cannot be empty")

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
