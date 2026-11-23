"""Geometry repair shared by plans and analyses.

urbanweave refuses invalid polygons; UrbanTrace repairs them first (shapely.make_valid, keeping the
polygonal parts) and reports what it repaired, so a dataset with a few self-intersecting zones is
still usable and the report says so.
"""
from __future__ import annotations

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon, Polygon


def _polygonal(geom):
    """The polygonal parts of a repaired geometry (make_valid can add stray lines or points)."""
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    parts = [p for p in shapely.get_parts(geom) if isinstance(p, (Polygon, MultiPolygon))]
    return shapely.union_all(parts) if parts else None


def repair(gdf: gpd.GeoDataFrame, id_column: str):
    """Repair invalid polygons; return the frame and a record of what was repaired (None if nothing)."""
    geoms = gdf.geometry
    polygonal = geoms.geom_type.isin(["Polygon", "MultiPolygon"]).to_numpy()
    invalid = polygonal & geoms.notna().to_numpy() & ~geoms.is_valid.to_numpy()
    if not invalid.any():
        return gdf, None
    out = gdf.copy()
    fixed = [_polygonal(g) for g in shapely.make_valid(geoms[invalid].to_numpy())]
    out.loc[invalid, out.geometry.name] = gpd.GeoSeries(fixed, index=out.index[invalid], crs=out.crs)
    ids = out.loc[invalid, id_column].astype(str).tolist()
    return out, {"count": int(invalid.sum()), "sample": ids[:20], "method": "shapely.make_valid, polygonal parts"}
