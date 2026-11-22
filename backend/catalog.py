"""The dataset catalog: where each dataset's file is, where it came from, and what its profile says.

Datasets are named by their stem (``NYC_libraries``). Each function takes the data directory, so
the API can point it elsewhere (the tests use a temporary one).

- Files: ``geoparquet/<stem>.parquet`` when it exists (faster to read, column-selectable; written by
  ``tools/convert_to_geoparquet.py``), otherwise ``geojson/<stem>.geojson``.
- Origins: ``origins.json`` (docs/REDESIGN.md, section 2.2), filled by ``tools/fill_origins.py`` and
  by uploads.
- Hashes: SHA-256 of the served file, computed when first needed and cached by path, size and
  modification time in ``.hash_cache.json``, so nothing reads the whole lake up front.
- Profiles: atlas-profiler 0.1.0 profiles in ``metadata_v2``, descriptions in
  ``descriptions_ddg.csv``.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import threading
from pathlib import Path

import geopandas as gpd

_STEM = re.compile(r"\w[\w.\-]*")
_hash_lock = threading.Lock()


def stem_of(name: str | None) -> str:
    """The dataset stem of a name, filename or path (``a/b/NYC_libraries.geojson`` → ``NYC_libraries``)."""
    if not isinstance(name, str):
        return ""
    stem = os.path.basename(name.strip())
    for suffix in (".geojson", ".parquet", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem


def valid_stem(stem: str) -> bool:
    return bool(stem) and bool(_STEM.fullmatch(stem))


def dataset_path(data_dir, stem: str) -> Path | None:
    """The file to read for a dataset: GeoParquet if present, else GeoJSON; None if neither exists."""
    data_dir = Path(data_dir)
    for path in (data_dir / "geoparquet" / f"{stem}.parquet", data_dir / "geojson" / f"{stem}.geojson"):
        if path.exists():
            return path
    return None


def load(data_dir, stem: str, columns: list[str] | None = None, clean: bool = True) -> gpd.GeoDataFrame:
    """Read a dataset, optionally only some columns (plus geometry). Raises FileNotFoundError.

    With *clean* (the default), the dataset's atlas-clean recipe, if one was saved, is replayed
    (cleaning.py); what it did is in ``gdf.attrs["urbantrace_cleaning"]``."""
    path = dataset_path(data_dir, stem)
    if path is None:
        raise FileNotFoundError(f"Dataset {stem!r} is not in the catalog")
    import cleaning
    corrected = clean and cleaning.has_recipe(data_dir, stem)
    read_columns = None if corrected else columns       # a recipe may use any column
    if path.suffix == ".parquet":
        gdf = gpd.read_parquet(path, columns=None if read_columns is None else [*read_columns, "geometry"])
    else:
        gdf = gpd.read_file(path)
    if corrected:
        gdf, report = cleaning.apply(data_dir, stem, gdf)
        gdf.attrs["urbantrace_cleaning"] = report
    if columns is not None:
        attrs = dict(gdf.attrs)
        gdf = gdf[[c for c in columns if c in gdf.columns] + [gdf.geometry.name]]
        gdf.attrs.update(attrs)
    return gdf


def list_stems(data_dir) -> list[str]:
    data_dir = Path(data_dir)
    stems = {p.stem for p in (data_dir / "geojson").glob("*.geojson")}
    stems |= {p.stem for p in (data_dir / "geoparquet").glob("*.parquet")}
    return sorted(stems)


# --- origins -------------------------------------------------------------------------------------

def origins(data_dir) -> dict:
    path = Path(data_dir) / "origins.json"
    return json.loads(path.read_text()) if path.exists() else {}


def origin(data_dir, stem: str) -> dict:
    """The dataset's origin record, or one that says the origin is unknown."""
    rec = origins(data_dir).get(stem)
    if rec is not None:
        return rec
    return {"portal": None, "portal_id": None, "source_url": None, "publisher": None, "license": None,
            "source_updated_at": None, "retrieved_at": None, "status": "unknown",
            "notes": ["no origin record for this dataset"]}


def set_origin(data_dir, stem: str, record: dict) -> None:
    path = Path(data_dir) / "origins.json"
    data = origins(data_dir)
    data[stem] = record
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dict(sorted(data.items())), indent=1) + "\n")
    os.replace(tmp, path)


# --- hashes --------------------------------------------------------------------------------------

def sha256(data_dir, path: Path) -> str:
    """SHA-256 of a file, cached by path, size and modification time."""
    path = Path(path)
    st = path.stat()
    key = str(path.resolve())
    cache_path = Path(data_dir) / ".hash_cache.json"
    with _hash_lock:
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        hit = cache.get(key)
        if hit and hit["size"] == st.st_size and hit["mtime"] == st.st_mtime:
            return hit["sha256"]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _hash_lock:
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        cache[key] = {"size": st.st_size, "mtime": st.st_mtime, "sha256": digest}
        cache_path.write_text(json.dumps(cache, indent=1))
    return digest


# --- profiles and descriptions -------------------------------------------------------------------

def profile(data_dir, stem: str) -> dict | None:
    path = Path(data_dir) / "metadata_v2" / f"{stem}.json"
    return json.loads(path.read_text()) if path.exists() else None


def description(data_dir, stem: str) -> str:
    path = Path(data_dir) / "descriptions_ddg.csv"
    if not path.exists():
        return ""
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if stem_of(row.get("dataset")) == stem:
                return (row.get("description") or "").strip()
    return ""


def profile_summary(prof: dict | None) -> dict | None:
    """The parts of a profile worth carrying in a manifest: size, geometry, coverage, columns."""
    if not prof:
        return None
    columns = []
    for col in prof.get("columns", []):
        entry = {"name": col.get("name"), "structural_type": col.get("structural_type"),
                 "semantic_types": col.get("semantic_types") or []}
        for key in ("num_distinct_values", "missing_values_ratio", "mean", "stddev"):
            if key in col:
                entry[key] = col[key]
        columns.append(entry)
    spatial = []
    for cov in prof.get("spatial_coverage", []):
        spatial.append({k: v for k, v in cov.items() if k not in ("geohashes4", "kdtree", "grid")})
    temporal = []
    for cov in prof.get("temporal_coverage", []):
        temporal.append({k: cov.get(k) for k in ("column_names", "ranges", "temporal_resolution") if k in cov})
    return {"rows": prof.get("nb_rows"), "columns_count": prof.get("nb_columns"),
            "geometry_type": prof.get("geometricType"), "crs": prof.get("crs"),
            "spatial_coverage": spatial, "temporal_coverage": temporal, "columns": columns,
            "computed_on": prof.get("computed_on")}
