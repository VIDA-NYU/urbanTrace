// Coverage map, drawn with Autark (WebGPU) over the light-gray basemap: cells shaded by how many of
// the canvas's datasets have data there, and the study area's outline.
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  BASEMAP_SOURCE, fitMercBounds, hitTest, metresPerPixel, projectCollection, screenToMerc, useAutarkMap, pointerInElement,
} from './autark/autarkMap';
import { MapError } from './VectorPreviewMap';
import { COVER_COLORS, coverageColor } from '../../lib/scope';

const CELLS = 'coverage-cells';
const OUTLINE = 'coverage-area';
const BASEMAP = 'coverage-basemap';
const OUTLINE_PX = 2;
const OUTLINE_COLOR = { r: 220, g: 38, b: 38, alpha: 1 };


// The study area's boundary as lines, so it can be drawn as an outline over the cells.
const outlineOf = (geometry) => {
  if (!geometry) return null;
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates]
    : geometry.type === 'MultiPolygon' ? geometry.coordinates : [];
  const lines = polygons.flat();
  return lines.length ? { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'MultiLineString', coordinates: lines } }] } : null;
};

export default function CoverageMap({ cells, studyArea, max, palette = COVER_COLORS, height = 420 }) {
  const canvasRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const loadedRef = useRef(false);

  const projectedCells = useMemo(() => (cells?.features?.length ? projectCollection(cells) : null), [cells]);
  const projectedArea = useMemo(() => {
    const outline = outlineOf(studyArea?.geometry);
    return outline ? projectCollection(outline) : null;
  }, [studyArea]);
  const frame = projectedArea?.mercBounds || projectedCells?.mercBounds || null;

  // Autark sizes lines in map metres; keep the outline a constant width on screen.
  const sizeOutline = (map) => {
    if (loadedRef.current && projectedArea) map.updateRenderInfo(OUTLINE, { polylinesWidth: OUTLINE_PX * metresPerPixel(map) });
  };
  const sizeOutlineRef = useRef(sizeOutline);
  useLayoutEffect(() => { sizeOutlineRef.current = sizeOutline; });

  const userMovedRef = useRef(false);
  const frameRef = useRef(frame);
  useLayoutEffect(() => { frameRef.current = frame; });
  const handleCameraChange = useCallback((map) => { setTooltip(null); sizeOutlineRef.current(map); }, []);
  const handleResize = useCallback((map) => {
    if (userMovedRef.current || !loadedRef.current || !frameRef.current) return;
    fitMercBounds(map, frameRef.current, 16);
    sizeOutlineRef.current(map);
  }, []);
  const { mapRef, ready, error } = useAutarkMap(canvasRef, { onCameraChange: handleCameraChange, onResize: handleResize });

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || (!projectedCells && !projectedArea)) return undefined;
    if (projectedCells) {
      // n, the number of datasets with data in the cell, coloured with the legend's palette.
      const top = Math.max(1, max);
      const colors = top === 1 ? [palette[0], coverageColor(palette, 1, 1)]
        : Array.from({ length: top }, (_, i) => coverageColor(palette, i + 1, top));
      map.loadCollection(CELLS, { collection: projectedCells.collection, type: 'polygons' });
      map.updateThematic(CELLS, { collection: projectedCells.collection, property: 'properties.n' });
      map.updateColorMap(CELLS, { colorMap: { type: 'sequential', colors, domainSpec: { type: 'user', params: top === 1 ? [0, 1] : [1, top] } } });
      map.updateRenderInfo(CELLS, { isColorMap: true, opacity: 0.75, strokeColor: { r: 255, g: 255, b: 255, alpha: 0.4 } });
    }
    if (projectedArea) {
      map.loadCollection(OUTLINE, { collection: projectedArea.collection, type: 'polylines' });
      map.updateRenderInfo(OUTLINE, { color: OUTLINE_COLOR, isColorMap: false });
    }
    map.loadTiles(BASEMAP, { source: BASEMAP_SOURCE, crs: 'EPSG:3857' });
    loadedRef.current = true;
    fitMercBounds(map, frame, 16);
    sizeOutlineRef.current(map);
    return () => {
      loadedRef.current = false;
      if (mapRef.current !== map) return;
      [CELLS, OUTLINE, BASEMAP].forEach((id) => map.removeLayer(id));
    };
  }, [ready, mapRef, projectedCells, projectedArea, frame, max, palette]);

  // Hover: which datasets have data in the cell (Autark picks only on double-click).
  const handlePointerMove = (event) => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || !projectedCells || event.buttons) {
      if (tooltip) setTooltip(null);
      return;
    }
    const [px, py] = pointerInElement(event);
    const [x, y] = screenToMerc(map, px, py);
    const index = hitTest(projectedCells, x, y, 0);
    if (index < 0) {
      setTooltip(null);
      return;
    }
    const props = cells.features[projectedCells.sourceIndex[index]].properties;
    setTooltip({ x: px, y: py, text: `${props.n} of ${max}: ${props.datasets.join(', ')}` });
  };

  return (
    <div
      className="ut-autark-map"
      style={{ width: '100%', height, position: 'relative', background: '#f1f5f9', borderRadius: 6, overflow: 'hidden' }}
      onPointerDown={() => { userMovedRef.current = true; }}
      onWheel={() => { userMovedRef.current = true; }}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => setTooltip(null)}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      {error && <MapError message={error} />}
      {tooltip && (
        <div style={{
          position: 'absolute', left: tooltip.x + 10, top: tooltip.y + 10, pointerEvents: 'none', zIndex: 5, maxWidth: 320,
          background: '#1e293b', color: '#f8fafc', fontSize: 11, padding: '3px 6px', borderRadius: 4,
        }}>
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
