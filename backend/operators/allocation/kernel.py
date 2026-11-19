import numpy as np
import pandas as pd
import geopandas as gpd

from .base import AllocationOperator

# A Gaussian weight below 1% of its peak is dropped: exp(-d^2 / 2 sigma^2) < 0.01 beyond this many sigmas
_CUTOFF_SIGMAS = float(np.sqrt(2 * np.log(100)))  # about 3.03


class GaussianKernel(AllocationOperator):
    """Spread each source over nearby cells with a Gaussian of its distance to the cell centroids.

    ``bandwidth`` is the standard deviation in meters. Distances are measured in a local metric
    projection (the UTM zone of the data), not in degrees. Cells farther than about 3 bandwidths get
    no weight. Each source's weights are normalized to sum to 1, so a Sum aggregation preserves the
    total; a source with no cell within reach goes whole to its nearest cell.
    """

    def __init__(self, bandwidth=1000):
        if not bandwidth or bandwidth <= 0:
            raise ValueError("bandwidth must be a positive number of meters")
        self.bandwidth = float(bandwidth)

    @property
    def supported_geometries(self): return ['Point', 'MultiPoint', 'LineString', 'MultiLineString']

    def calculate_weights(self, source_gdf, grid_gdf):
        empty = pd.DataFrame({'source_id': pd.Series(dtype=object), 'cell_id': pd.Series(dtype=object),
                              'weight': pd.Series(dtype=float)})
        if source_gdf.empty or grid_gdf.empty:
            return empty

        metric = grid_gdf.estimate_utm_crs()
        sources = source_gdf[['source_id', 'geometry']].to_crs(metric).reset_index(drop=True)
        cells = grid_gdf[['cell_id', 'geometry']].to_crs(metric).reset_index(drop=True)
        centroids = cells.geometry.centroid

        # Candidate (source, cell) pairs within the cutoff, from the spatial index
        cutoff = _CUTOFF_SIGMAS * self.bandwidth
        src_idx, cell_idx = centroids.sindex.query(sources.geometry, predicate='dwithin', distance=cutoff)
        distances = sources.geometry.values[src_idx].distance(centroids.values[cell_idx])
        decay = np.exp(-(distances ** 2) / (2 * self.bandwidth ** 2))
        keep = decay >= 0.01
        pairs = pd.DataFrame({'src': src_idx[keep], 'cell': cell_idx[keep], 'weight': decay[keep]})

        # Sources with no cell within reach go whole to their nearest cell
        missing = np.setdiff1d(np.arange(len(sources)), pairs['src'].unique())
        if len(missing):
            near_src, near_cell = centroids.sindex.nearest(sources.geometry.values[missing], return_all=False)
            pairs = pd.concat([pairs, pd.DataFrame({'src': missing[near_src], 'cell': near_cell, 'weight': 1.0})],
                              ignore_index=True)

        pairs['weight'] = pairs['weight'] / pairs.groupby('src')['weight'].transform('sum')
        return pd.DataFrame({
            'source_id': sources['source_id'].values[pairs['src']],
            'cell_id': cells['cell_id'].values[pairs['cell']],
            'weight': pairs['weight'].values,
        })
