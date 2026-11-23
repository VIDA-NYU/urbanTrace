// d3-geo reads polygons on the sphere and expects exterior rings clockwise, the opposite of the
// GeoJSON standard (RFC 7946) that shapely and most files follow. A ring in the other direction is
// read as the whole globe minus the polygon, so fitSize zooms out to the world and the fill covers
// everything. rewindForD3 flips any polygon whose spherical area is more than a hemisphere.
import { geoArea } from 'd3-geo';

const flip = (rings) => rings.map((ring) => [...ring].reverse());
const fixPolygon = (rings) => (geoArea({ type: 'Polygon', coordinates: rings }) > 2 * Math.PI ? flip(rings) : rings);

export function rewindGeometry(geometry) {
  if (!geometry) return geometry;
  if (geometry.type === 'Polygon') return { ...geometry, coordinates: fixPolygon(geometry.coordinates) };
  if (geometry.type === 'MultiPolygon') return { ...geometry, coordinates: geometry.coordinates.map(fixPolygon) };
  if (geometry.type === 'GeometryCollection') return { ...geometry, geometries: geometry.geometries.map(rewindGeometry) };
  return geometry;
}

export function rewindForD3(geojson) {
  if (!geojson) return geojson;
  if (geojson.type === 'FeatureCollection') return { ...geojson, features: geojson.features.map(rewindForD3) };
  if (geojson.type === 'Feature') return { ...geojson, geometry: rewindGeometry(geojson.geometry) };
  return rewindGeometry(geojson);
}
