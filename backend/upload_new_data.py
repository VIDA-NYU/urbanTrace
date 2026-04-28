from typing import Any, Dict
import os
import json
import geopandas as gpd
import pandas as pd
from fastapi import HTTPException, UploadFile

try:
    import datamart_profiler
except Exception:
    datamart_profiler = None


def _validate_and_extract_features(geojson_obj: Any) -> list[dict[str, Any]]:
    if not isinstance(geojson_obj, dict):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid GeoJSON object.")

    geojson_type = geojson_obj.get("type")

    if geojson_type == "FeatureCollection":
        features = geojson_obj.get("features")
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: 'features' must be an array.")
        return features

    if geojson_type == "Feature":
        return [geojson_obj]

    raise HTTPException(
        status_code=400,
        detail="Invalid GeoJSON: top-level type must be 'FeatureCollection' or 'Feature'.",
    )


def _compute_geometric_type(features: list[dict[str, Any]]) -> str:
    if not features:
        return "None"

    geometry_types: set[str] = set()

    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: each item in features must be a Feature.")

        geometry = feature.get("geometry")
        if geometry is None:
            geometry_types.add("None")
            continue

        if not isinstance(geometry, dict):
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: feature geometry must be an object or null.")

        geometry_type = geometry.get("type")
        if not isinstance(geometry_type, str) or not geometry_type.strip():
            raise HTTPException(status_code=400, detail="Invalid GeoJSON: geometry.type is required.")

        geometry_types.add(geometry_type.strip())

    if len(geometry_types) == 1:
        return next(iter(geometry_types))
    return "Mixed"


def _profile_dataset(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    # Preferred profiler
    if datamart_profiler is not None:
        try:
            return datamart_profiler.process_dataset(gdf, include_sample=True, plots=False)
        except Exception:
            pass

    # Fallback basic profiler
    profile: Dict[str, Any] = {
        "columns": [],
        "nb_rows": len(gdf),
        "nb_columns": len(gdf.columns),
        "sample": ""
    }

    for col_name, col_data in gdf.items():
        if col_name == "geometry":
            continue

        dtype_str = str(col_data.dtype)
        if "int" in dtype_str:
            structural_type = "integer"
        elif "float" in dtype_str:
            structural_type = "float"
        elif "object" in dtype_str:
            structural_type = "string"
        elif "datetime" in dtype_str:
            structural_type = "datetime"
        else:
            structural_type = "unknown"

        null_count = int(col_data.isna().sum())
        non_null_count = len(col_data) - null_count
        distinct_count = int(col_data.nunique())

        col_profile = {
            "name": col_name,
            "structural_type": structural_type,
            "column_type": dtype_str,
            "null_count": null_count,
            "null_percentage": round(null_count / len(gdf) * 100, 2) if len(gdf) > 0 else 0,
            "non_null_count": non_null_count,
            "num_distinct_values": distinct_count,
            "coverage": []
        }

        if structural_type in ["integer", "float"]:
            try:
                col_numeric = pd.to_numeric(col_data, errors="coerce")
                col_profile["mean"] = round(float(col_numeric.mean()), 4) if col_numeric.notna().any() else None
                col_profile["median"] = round(float(col_numeric.median()), 4) if col_numeric.notna().any() else None
                col_profile["stddev"] = round(float(col_numeric.std()), 4) if col_numeric.notna().any() else None
                col_profile["min"] = round(float(col_numeric.min()), 4) if col_numeric.notna().any() else None
                col_profile["max"] = round(float(col_numeric.max()), 4) if col_numeric.notna().any() else None
            except Exception:
                pass

        profile["columns"].append(col_profile)

    try:
        if len(gdf) > 0 and gdf.geometry is not None:
            bounds = gdf.total_bounds
            spatial_coverage = {
                "type": "envelope",
                "ranges": [
                    {
                        "type": "bbox",
                        "coordinates": [
                            [bounds[0], bounds[1]],
                            [bounds[2], bounds[3]]
                        ]
                    }
                ]
            }
            profile["spatial_coverage"] = [spatial_coverage]
    except Exception:
        pass

    try:
        sample_gdf = gdf.drop(columns=["geometry"], errors="ignore").head(5)
        profile["sample"] = sample_gdf.to_csv(index=False)
    except Exception:
        profile["sample"] = ""

    return profile


def _generate_enriched_metadata(geojson_obj: Dict[str, Any], gdf: gpd.GeoDataFrame, profile: Dict[str, Any]) -> Dict[str, Any]:
    geojson_metadata = {
        "geometricType": geojson_obj.get("geometricType", "Unknown"),
        "name": geojson_obj.get("name"),
        "crs": str(gdf.crs) if gdf.crs else None
    }
    enriched = {**geojson_metadata, **profile}
    return enriched


async def process_uploaded_geojson(file: UploadFile, data_dir: str) -> Dict[str, Any]:
    original_name = (file.filename or "").strip()
    if not original_name or not original_name.lower().endswith(".geojson"):
        raise HTTPException(status_code=400, detail="Only .geojson files are allowed.")

    safe_filename = os.path.basename(original_name)
    if not safe_filename or safe_filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    geojson_dir = os.path.join(data_dir, "geojson")
    metadata_dir = os.path.join(data_dir, "metadata")
    os.makedirs(geojson_dir, exist_ok=True)
    os.makedirs(metadata_dir, exist_ok=True)

    try:
        payload = await file.read()
        decoded = payload.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file as UTF-8 text.")

    try:
        geojson_obj = json.loads(decoded)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON/GeoJSON.")

    features = _validate_and_extract_features(geojson_obj)
    geometric_type = _compute_geometric_type(features)
    geojson_obj["geometricType"] = geometric_type

    output_path = os.path.join(geojson_dir, safe_filename)
    try:
        with open(output_path, "w", encoding="utf-8") as out_file:
            json.dump(geojson_obj, out_file, separators=(",", ":"), ensure_ascii=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(exc)}")

    metadata_saved = False
    try:
        gdf = gpd.read_file(output_path)
        profile = _profile_dataset(gdf)
        enriched_metadata = _generate_enriched_metadata(geojson_obj, gdf, profile)

        base_name = safe_filename.replace(".geojson", "")
        metadata_filename = f"{base_name}.json"
        metadata_path = os.path.join(metadata_dir, metadata_filename)

        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(enriched_metadata, meta_file, indent=2, ensure_ascii=False)

        metadata_saved = True
    except Exception:
        metadata_saved = False

    return {
        "message": "GeoJSON uploaded successfully.",
        "filename": safe_filename,
        "geometricType": geometric_type,
        "saved_to": output_path,
        "metadata_saved": metadata_saved,
    }
