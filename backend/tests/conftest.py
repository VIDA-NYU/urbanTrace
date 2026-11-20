"""Shared fixtures: a tiny catalog of synthetic datasets in Manhattan, so the API tests need no LFS data."""
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("COPILOT_DISABLED", "1")

REPO_DATA = BACKEND.parent / "data" / "geojson"

# Two adjacent zones, about 1.7 km x 1.1 km each, in Midtown.
WEST = [(-74.00, 40.75), (-73.98, 40.75), (-73.98, 40.76), (-74.00, 40.76), (-74.00, 40.75)]
EAST = [(-73.98, 40.75), (-73.96, 40.75), (-73.96, 40.76), (-73.98, 40.76), (-73.98, 40.75)]
COVER = [(-74.00, 40.75), (-73.96, 40.75), (-73.96, 40.76), (-74.00, 40.76), (-74.00, 40.75)]
BOWTIE = [(-73.995, 40.751), (-73.985, 40.759), (-73.985, 40.751), (-73.995, 40.759), (-73.995, 40.751)]

POINTS = [(-73.995, 40.752, 3), (-73.991, 40.755, 5), (-73.987, 40.758, 2),
          (-73.975, 40.753, 7), (-73.968, 40.757, 1), (-73.962, 40.754, 4)]
DATES = ["2019-03-01", "2020-06-15", "2021-01-10", "2020-02-02", "2019-11-30", "2021-08-08"]


def _profile(rows, start, end, grid_cells=None, bounds=(-74.0, 40.75, -73.96, 40.76)):
    """A minimal atlas-profiler 0.1.0 profile: rows, a time range and a density grid."""
    from datetime import datetime, timezone
    ts = lambda d: datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()
    cov = {"type": "latlong", "ranges": [{"range": {"type": "envelope",
                                                    "coordinates": [[bounds[0], bounds[3]], [bounds[2], bounds[1]]]}}]}
    if grid_cells is not None:
        cov["grid"] = {"bounds": list(bounds), "columns": 8, "rows": 2, "cell_degrees": [0.005, 0.005],
                       "cells": grid_cells}
    return {"nb_rows": rows, "geometricType": "Point", "columns": [],
            "spatial_coverage": [cov],
            "temporal_coverage": [{"column_names": ["date"], "temporal_resolution": "day",
                                   "ranges": [{"range": {"gte": ts(start), "lte": ts(end)}}]}]}


def _fc(features):
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": features}


def _polygon(ring, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}


@pytest.fixture()
def catalog(tmp_path, monkeypatch):
    """A DATA_DIR with points, a polygon source (one polygon invalid), and two zones."""
    geo = tmp_path / "geojson"
    geo.mkdir()
    (tmp_path / "metadata").mkdir()
    # The original (v1) profile the copilot's operator recommendation reads
    (tmp_path / "metadata" / "test_points.json").write_text(json.dumps({
        "geometricType": "Point", "sample": "count,name\n3,p0\n5,p1\n2,p2\n",
        "columns": [{"name": "count", "structural_type": "http://schema.org/Integer", "mean": 3.67,
                     "num_distinct_values": 6}]}))
    (geo / "test_points.geojson").write_text(json.dumps(_fc([
        {"type": "Feature", "properties": {"count": c, "name": f"p{i}", "date": DATES[i]},
         "geometry": {"type": "Point", "coordinates": [x, y]}} for i, (x, y, c) in enumerate(POINTS)])))
    (geo / "test_rates.geojson").write_text(json.dumps(_fc([
        _polygon(COVER, rate=0.2), _polygon(BOWTIE, rate=0.6)])))
    (geo / "test_zones.geojson").write_text(json.dumps(_fc([
        _polygon(WEST, zone="west", pop=100), _polygon(EAST, zone="east", pop=300)])))
    prof = tmp_path / "metadata_v2"
    prof.mkdir()
    # Points cover the western half of the box only; rates cover all of it but years earlier.
    (prof / "test_points.json").write_text(json.dumps(_profile(6, "2019-03-01", "2021-08-08",
                                                                [[c, r, 1] for c in range(4) for r in range(2)])))
    (prof / "test_rates.json").write_text(json.dumps(_profile(2, "2005-01-01", "2010-12-31",
                                                               [[c, r, 1] for c in range(8) for r in range(2)])))
    import main
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    import main
    return TestClient(main.app)


def lfs_file_present(path: Path) -> bool:
    """True when *path* holds real data, not a Git LFS pointer."""
    if not path.exists():
        return False
    with open(path, "rb") as f:
        return not f.read(64).startswith(b"version https://git-lfs")
