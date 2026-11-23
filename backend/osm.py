"""OpenStreetMap street networks as plan targets (PLAN.md, phase 6).

A Streets node makes the study area's street segments, or its intersections, the target of a step:
crashes per km of street, the nearest street segment of each school, trees within 50 m of each
intersection. The network is downloaded live from OpenStreetMap (OSMnx, Overpass API) for the study
area's polygon, once per area and network type, and kept as a GraphML file in ``data/osm/``; plans
hand urbanweave that file (an ``osm_streets`` / ``osm_intersections`` target with ``graphml``), so
runs are fast, fingerprinted in the manifest and replayable. Downloading again is a separate action.

OpenStreetMap data is © OpenStreetMap contributors, available under the ODbL; reports and exports
that use it say so.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

NETWORK_TYPES = ("drive", "walk", "bike", "all")
ATTRIBUTION = "Street network © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright), via OSMnx"
MAX_KM2 = float(os.getenv("URBANTRACE_OSM_MAX_KM2") or 1000)   # NYC is ~780 km²


class OsmError(ValueError):
    pass


def available() -> bool:
    try:
        import osmnx  # noqa: F401
        return True
    except ImportError:
        return False


def _key(area, network_type: str) -> str:
    import shapely
    geom = shapely.set_precision(area, 1e-6)                # the same study area gives the same file
    return hashlib.sha256(shapely.to_wkb(geom) + network_type.encode()).hexdigest()[:16]


def graph_path(data_dir, area, network_type: str) -> Path:
    return Path(data_dir) / "osm" / f"{network_type}_{_key(area, network_type)}.graphml"


def _meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def area_km2(area) -> float:
    import geopandas as gpd
    s = gpd.GeoSeries([area], crs="EPSG:4326")
    return float(s.to_crs(s.estimate_utm_crs()).area.iloc[0] / 1e6)


def info(data_dir, area, network_type: str) -> dict:
    """Whether the network for this area is downloaded: {network_type, downloaded, nodes, edges,
    downloaded_at, km2, file}."""
    _check_type(network_type)
    path = graph_path(data_dir, area, network_type)
    out = {"network_type": network_type, "downloaded": path.exists(), "km2": round(area_km2(area), 1),
           "file": f"osm/{path.name}", "attribution": ATTRIBUTION, "available": available()}
    if path.exists() and _meta_path(path).exists():
        out.update(json.loads(_meta_path(path).read_text()))
    return out


def _check_type(network_type: str):
    if network_type not in NETWORK_TYPES:
        raise OsmError(f"Unknown network type {network_type!r}; choose one of {', '.join(NETWORK_TYPES)}.")


def download(data_dir, area, network_type: str) -> dict:
    """Download the street network inside *area* (WGS84 polygon) and keep it as GraphML."""
    _check_type(network_type)
    if not available():
        raise OsmError("Street networks need OSMnx: pip install 'urbanweave[osm]'.")
    km2 = area_km2(area)
    if km2 > MAX_KM2:
        raise OsmError(f"The study area is {km2:,.0f} km²; street networks are downloaded for at most {MAX_KM2:,.0f} km² "
                       "(URBANTRACE_OSM_MAX_KM2). Choose a smaller study area.")
    import osmnx as ox
    # OSMnx caches Overpass responses; keep them with the networks, not in the working folder
    ox.settings.cache_folder = str(Path(data_dir) / "osm" / "http_cache")
    path = graph_path(data_dir, area, network_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    try:
        G = ox.graph_from_polygon(area, network_type=network_type, simplify=True, truncate_by_edge=True)
    except Exception as e:  # Overpass errors, empty areas
        raise OsmError(f"OpenStreetMap download failed: {type(e).__name__}: {str(e)[:300]}")
    tmp = path.with_suffix(".tmp.graphml")
    ox.save_graphml(G, tmp)
    tmp.replace(path)
    meta = {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "seconds": round(time.perf_counter() - t0, 1),
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "osmnx": ox.__version__,
            "network_type": network_type}
    _meta_path(path).write_text(json.dumps(meta))
    return info(data_dir, area, network_type)


# --- background downloads: a borough takes a minute or two --------------------------------------

_JOBS: dict[str, dict] = {}
_lock = threading.Lock()


def start(data_dir, area, network_type: str) -> dict:
    _check_type(network_type)
    k = graph_path(data_dir, area, network_type).name
    with _lock:
        job = _JOBS.get(k)
        if job and job["state"] == "running":
            return job
        job = _JOBS[k] = {"state": "running", "network_type": network_type, "started": time.time(), "error": None}

    def work():
        try:
            job["result"] = download(data_dir, area, network_type)
            job["state"] = "done"
        except Exception as e:
            job.update(state="failed", error=str(e))
    threading.Thread(target=work, daemon=True).start()
    return job


def status(data_dir, area, network_type: str) -> dict | None:
    return _JOBS.get(graph_path(data_dir, area, network_type).name)
