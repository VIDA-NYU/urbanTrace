import pandas as pd
import geopandas as gpd
from .base import ZoningMappingOperator


class CentroidZoning(ZoningMappingOperator):
    """
    Binary zoning assignment.

    - For polygonal zones: assigns each grid cell to the zone containing its centroid.
    - For point zones: assigns each point zone to the grid cell containing the point.

    Uses binary assignment: γ_{jℓ} ∈ {0, 1}.
    """
    
    def map_to_zones(self, grid_gdf: gpd.GeoDataFrame, zones_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        # Ensure zones have a zone_id column
        if 'zone_id' not in zones_gdf.columns:
            zones_gdf = zones_gdf.copy()
            zones_gdf['zone_id'] = zones_gdf.index.astype(str)

        zone_geom_types = set(zones_gdf.geometry.geom_type.unique())

        # Point targets: assign each point zone to the containing H3 cell.
        if zone_geom_types.issubset({'Point', 'MultiPoint'}):
            joined = gpd.sjoin(
                zones_gdf[['zone_id', 'geometry']],
                grid_gdf[['cell_id', 'geometry']],
                how='inner',
                predicate='within'
            )

            joined['gamma'] = 1.0
            return joined[['cell_id', 'zone_id', 'gamma']].reset_index(drop=True)
        
        # Create centroid geometries for spatial join
        centroids_gdf = grid_gdf[['cell_id', 'geometry']].copy()
        centroids_gdf['geometry'] = centroids_gdf.geometry.centroid
        
        # Spatial join: which zone contains each cell's centroid?
        joined = gpd.sjoin(
            centroids_gdf, 
            zones_gdf[['zone_id', 'geometry']], 
            how='inner', 
            predicate='within'
        )
        
        # Binary weight: cell is fully assigned to one zone
        joined['gamma'] = 1.0
        
        return joined[['cell_id', 'zone_id', 'gamma']].reset_index(drop=True)


class AreaWeightedZoning(ZoningMappingOperator):
    """
    Assigns grid cells to zones proportionally based on area overlap.
    γ_{jℓ} = Area(c_j ∩ z_ℓ) / Area(c_j)
    
    This preserves mass when redistributing cell values to zones.
    """
    
    def map_to_zones(self, grid_gdf: gpd.GeoDataFrame, zones_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        # Ensure zones have a zone_id column
        if 'zone_id' not in zones_gdf.columns:
            zones_gdf = zones_gdf.copy()
            zones_gdf['zone_id'] = zones_gdf.index.astype(str)
        
        # Pre-calculate original cell areas if not present
        if 'area' not in grid_gdf.columns:
            grid_gdf = grid_gdf.copy()
            grid_gdf['area'] = grid_gdf.to_crs("EPSG:3857").geometry.area
        
        # Compute geometric intersection between cells and zones
        intersection = gpd.overlay(
            grid_gdf[['cell_id', 'geometry', 'area']], 
            zones_gdf[['zone_id', 'geometry']], 
            how='intersection'
        )
        
        # Calculate intersection area in projected CRS for accuracy
        intersection['intersection_area'] = intersection.to_crs("EPSG:3857").geometry.area
        
        # Gamma = intersection area / original cell area
        intersection['gamma'] = intersection['intersection_area'] / intersection['area']
        
        # Filter out negligible overlaps (floating point artifacts)
        intersection = intersection[intersection['gamma'] > 1e-6]
        
        return intersection[['cell_id', 'zone_id', 'gamma']].reset_index(drop=True)


class LengthWeightedZoning(ZoningMappingOperator):
    """
    Assigns grid cells to line-based zones proportionally by line overlap length.
    γ_{jℓ} = Length(c_j ∩ z_ℓ) / Length(z_ℓ)

    Intended for zones represented as LineString/MultiLineString geometries
    (roads, bike routes, rivers, transit corridors).
    """

    def map_to_zones(self, grid_gdf: gpd.GeoDataFrame, zones_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        if 'zone_id' not in zones_gdf.columns:
            zones_gdf = zones_gdf.copy()
            zones_gdf['zone_id'] = zones_gdf.index.astype(str)

        zone_geom_types = set(zones_gdf.geometry.geom_type.unique())
        allowed_line_types = {'LineString', 'MultiLineString'}
        if not zone_geom_types.issubset(allowed_line_types):
            raise ValueError(
                "LengthWeightedZoning requires line-based zones (LineString or MultiLineString). "
                f"Found geometry types: {sorted(zone_geom_types)}"
            )

        # Intersect grid cells (polygons) with zone lines
        intersection = gpd.overlay(
            grid_gdf[['cell_id', 'geometry']],
            zones_gdf[['zone_id', 'geometry']],
            how='intersection',
            keep_geom_type=False
        )

        if intersection.empty:
            return pd.DataFrame(columns=['cell_id', 'zone_id', 'gamma'])

        # Compute projected lengths for accurate metric weighting
        zones_metric = zones_gdf[['zone_id', 'geometry']].to_crs("EPSG:3857").copy()
        zones_metric['zone_length'] = zones_metric.geometry.length

        intersection_metric = intersection.to_crs("EPSG:3857").copy()
        intersection_metric['intersection_length'] = intersection_metric.geometry.length

        weights = intersection[['cell_id', 'zone_id']].copy()
        weights['intersection_length'] = intersection_metric['intersection_length'].values
        weights = weights.merge(zones_metric[['zone_id', 'zone_length']], on='zone_id', how='left')

        # Gamma = line overlap length / total zone line length
        weights['gamma'] = weights['intersection_length'] / weights['zone_length']
        weights = weights[(weights['intersection_length'] > 1e-9) & (weights['gamma'] > 1e-9)]

        return weights[['cell_id', 'zone_id', 'gamma']].reset_index(drop=True)
