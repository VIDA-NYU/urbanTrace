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
    (geo / "test_points.geojson").write_text(json.dumps(_fc([
        {"type": "Feature", "properties": {"count": c, "name": f"p{i}"},
         "geometry": {"type": "Point", "coordinates": [x, y]}} for i, (x, y, c) in enumerate(POINTS)])))
    (geo / "test_rates.geojson").write_text(json.dumps(_fc([
        _polygon(COVER, rate=0.2), _polygon(BOWTIE, rate=0.6)])))
    (geo / "test_zones.geojson").write_text(json.dumps(_fc([
        _polygon(WEST, zone="west"), _polygon(EAST, zone="east")])))
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
