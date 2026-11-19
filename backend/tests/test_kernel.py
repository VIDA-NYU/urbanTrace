"""GaussianKernel allocation: distances in meters, reach of about 3 bandwidths, totals preserved."""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grids.h3_grid import H3GridSystem  # noqa: E402
from operators.aggregation.aggregators import SumAggregation  # noqa: E402
from operators.allocation.kernel import GaussianKernel  # noqa: E402

BOUNDS = (-74.05, 40.60, -73.75, 40.88)  # NYC


@pytest.fixture(scope="module")
def grid():
    return H3GridSystem().generate_grid(BOUNDS, 8)   # cells about 0.7 km^2


def _sources(geometries):
    return gpd.GeoDataFrame({"source_id": [str(i) for i in range(len(geometries))]},
                            geometry=geometries, crs="EPSG:4326")


def test_weights_sum_to_one_per_source(grid):
    src = _sources([Point(-73.98, 40.75), Point(-73.90, 40.70), LineString([(-73.95, 40.65), (-73.93, 40.67)])])
    w = GaussianKernel(bandwidth=1000).calculate_weights(src, grid)
    assert np.allclose(w.groupby("source_id")["weight"].sum().values, 1.0)


def test_reach_follows_the_bandwidth_in_meters(grid):
    src = _sources([Point(-73.98, 40.75)])
    metric = grid.estimate_utm_crs()
    centroids = grid.to_crs(metric).geometry.centroid
    here = src.to_crs(metric).geometry.iloc[0]
    for bandwidth in (500, 1000, 2000):
        w = GaussianKernel(bandwidth=bandwidth).calculate_weights(src, grid)
        reached = centroids[grid["cell_id"].isin(w["cell_id"])]
        assert reached.distance(here).max() <= 3.1 * bandwidth
        assert 1 < len(w) < len(grid)          # spread, but not over the whole city
    # A wider kernel reaches more cells
    small = len(GaussianKernel(bandwidth=500).calculate_weights(src, grid))
    large = len(GaussianKernel(bandwidth=2000).calculate_weights(src, grid))
    assert small < large


def test_sum_aggregation_preserves_the_total(grid):
    src = _sources([Point(-73.98, 40.75), Point(-73.95, 40.72)])
    w = GaussianKernel(bandwidth=800).calculate_weights(src, grid)
    w["source_value"] = w["source_id"].map({"0": 3.0, "1": 5.0})
    assert SumAggregation().aggregate(w, grid)["allocated_val"].sum() == pytest.approx(8.0)


def test_nearer_cells_get_more_weight(grid):
    src = _sources([Point(-73.98, 40.75)])
    w = GaussianKernel(bandwidth=1000).calculate_weights(src, grid).merge(grid[["cell_id", "geometry"]], on="cell_id")
    metric = grid.estimate_utm_crs()
    d = gpd.GeoSeries(w["geometry"], crs=grid.crs).to_crs(metric).centroid.distance(src.to_crs(metric).geometry.iloc[0])
    order = np.argsort(d.values)
    assert np.all(np.diff(w["weight"].values[order]) <= 1e-12)


def test_source_far_from_every_cell_goes_to_the_nearest_cell(grid):
    src = _sources([Point(-73.40, 40.75)])   # about 30 km east of the grid
    w = GaussianKernel(bandwidth=500).calculate_weights(src, grid)
    assert len(w) == 1 and w["weight"].iloc[0] == pytest.approx(1.0)


def test_invalid_bandwidth():
    with pytest.raises(ValueError):
        GaussianKernel(bandwidth=0)
