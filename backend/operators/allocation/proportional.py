import pandas as pd
import geopandas as gpd
from .base import AllocationOperator


METRIC_CRS = "EPSG:3857"

class ProportionalAreaWeighted(AllocationOperator):
    @property
    def supported_geometries(self): return ['Polygon', 'MultiPolygon']
    
    def calculate_weights(self, source_gdf, grid_gdf):
        source_gdf = source_gdf.copy()

        # Pre-calculate original area in a projected CRS to preserve mass correctly.
        source_metric = source_gdf.to_crs(METRIC_CRS)
        source_gdf['orig_area'] = source_metric.geometry.area.values

        # Intersect polygons with the grid in the common WGS84 support.
        intersection = gpd.overlay(source_gdf, grid_gdf, how='intersection')

        # Calculate intersection area in projected CRS for accurate weights.
        intersection_metric = intersection.to_crs(METRIC_CRS)
        intersection['weight'] = intersection_metric.geometry.area.values / intersection['orig_area']
        
        return intersection[['source_id', 'cell_id', 'weight']]

class ProportionalLengthWeighted(AllocationOperator):
    @property
    def supported_geometries(self): return ['LineString', 'MultiLineString']
    
    def calculate_weights(self, source_gdf, grid_gdf):
        source_gdf = source_gdf.copy()

        # Pre-calculate original length in a projected CRS.
        source_metric = source_gdf.to_crs(METRIC_CRS)
        source_gdf['orig_length'] = source_metric.geometry.length.values

        # Intersect lines with the common WGS84 grid.
        intersection = gpd.overlay(source_gdf, grid_gdf, how='intersection')

        if intersection.empty:
            return intersection[['source_id', 'cell_id']].assign(weight=pd.Series(dtype=float))

        # Calculate segment lengths in projected CRS for accurate weights.
        intersection_metric = intersection.to_crs(METRIC_CRS)
        intersection['weight'] = intersection_metric.geometry.length.values / intersection['orig_length']
        
        return intersection[['source_id', 'cell_id', 'weight']]