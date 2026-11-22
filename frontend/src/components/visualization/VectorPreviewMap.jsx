// Dataset preview map, drawn with Autark (WebGPU) over a light-gray basemap.
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  BASEMAP_SOURCE, SCHEMES, SOURCE_CRS, applyViewState, cameraToViewState, colorMapFor, fitMercBounds,
  layerTypeFor, metresPerPixel, prepareCollection, useAutarkMap,
} from './autark/autarkMap';
import { API_BASE } from '../../config/api';

const DATA_LAYER = 'data';
const VALUE_KEY = '__ut_value';
const DEFAULT_COLOR = { r: 59, g: 130, b: 246, alpha: 1 };
const NUMERIC_SCHEME = SCHEMES.YlOrRd; // light yellow to dark red, as before
const POINT_RADIUS_PX = 1.5; // radius in CSS pixels (Autark pointSize is a radius)
const LINE_WIDTH_PX = 1.5;

const VectorPreviewMap = ({
  filename,
  height = 120, // CSS pixels
  selectedColumn,
  // GLOBAL VIEWPORT SYNC: Props for linked camera
  isMapSyncEnabled = false,
  globalViewState,
  onGlobalViewStateChange,
}) => {
  const canvasRef = useRef(null);
  // The response is kept with the filename it belongs to, so `loading` is derived rather than set in an effect.
  const [loaded, setLoaded] = useState({ filename: null, data: null });
  const data = loaded.filename === filename ? loaded.data : null;
  const loading = loaded.filename !== filename;

  const loadedRef = useRef(false);
  const applyingViewRef = useRef(false);
  const lastEmittedRef = useRef(null);
  const emitFrameRef = useRef(0);
  const syncRef = useRef({ isMapSyncEnabled, onGlobalViewStateChange });
  useLayoutEffect(() => {
    syncRef.current = { isMapSyncEnabled, onGlobalViewStateChange };
  });
  const globalViewStateRef = useRef(globalViewState);
  useLayoutEffect(() => {
    globalViewStateRef.current = globalViewState;
  });

  // Autark sizes points and lines in map metres; rescale them on every camera change so they keep
  // a constant on-screen size, like Deck.GL's pixel units. This does not re-upload geometry.
  const layerTypeRef = useRef(null);
  const sizeMarks = (map) => {
    if (!loadedRef.current) return;
    const mpp = metresPerPixel(map);
    if (layerTypeRef.current === 'points') map.updateRenderInfo(DATA_LAYER, { pointSize: POINT_RADIUS_PX * mpp });
    if (layerTypeRef.current === 'polylines') map.updateRenderInfo(DATA_LAYER, { polylinesWidth: LINE_WIDTH_PX * mpp });
  };
  const sizeMarksRef = useRef(sizeMarks);
  useLayoutEffect(() => {
    sizeMarksRef.current = sizeMarks;
  });

  const handleCameraChange = useCallback((map) => {
    sizeMarksRef.current(map);
    const { isMapSyncEnabled: sync, onGlobalViewStateChange: emit } = syncRef.current;
    if (applyingViewRef.current || !sync || !emit || !loadedRef.current || emitFrameRef.current) return;
    // One view-state update per animation frame, so dragging does not re-render the canvas per event.
    emitFrameRef.current = requestAnimationFrame(() => {
      emitFrameRef.current = 0;
      if (!loadedRef.current) return;
      const viewState = cameraToViewState(map);
      lastEmittedRef.current = viewState;
      syncRef.current.onGlobalViewStateChange?.(viewState);
    });
  }, []);

  // Until the user pans or zooms, keep the data framed when the node is laid out or resized.
  const userMovedRef = useRef(false);
  const projectedRef = useRef(null);
  const handleResize = useCallback((map) => {
    const bounds = projectedRef.current?.frameBounds;
    if (userMovedRef.current || syncRef.current.isMapSyncEnabled || !loadedRef.current || !bounds) return;
    applyingViewRef.current = true;
    fitMercBounds(map, bounds, 10);
    applyingViewRef.current = false;
    sizeMarksRef.current(map);
  }, []);

  const { mapRef, ready, error } = useAutarkMap(canvasRef, { onCameraChange: handleCameraChange, onResize: handleResize });

  useEffect(() => () => cancelAnimationFrame(emitFrameRef.current), []);

  // 1. Fetch data
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API_BASE}/dataset/${filename}?simplify=true`)
      .then(res => !cancelled && setLoaded({ filename, data: res.data }))
      .catch(err => {
        console.error('Preview load error', err);
        if (!cancelled) setLoaded({ filename, data: null });
      });
    return () => {
      cancelled = true;
    };
  }, [filename]);

  const projected = useMemo(() => (data ? prepareCollection(data) : null), [data]);
  useLayoutEffect(() => {
    projectedRef.current = projected;
  });

  // Values of the selected column, and whether they are numeric
  const thematic = useMemo(() => {
    if (!projected || !selectedColumn) return null;
    const values = projected.collection.features.map(f => f.properties[selectedColumn]);
    const present = values.filter(v => v !== null && v !== undefined);
    const isNumeric = present.length > 0 && typeof present[0] === 'number';
    return isNumeric ? values : null;
  }, [projected, selectedColumn]);

  // 2. Load the layer and the basemap, then frame the data
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !projected?.mercBounds) return undefined;

    const type = layerTypeFor(projected.collection);
    map.loadCollection(DATA_LAYER, { collection: projected.collection, sourceCrs: SOURCE_CRS, type });
    layerTypeRef.current = type;
    map.updateRenderInfo(DATA_LAYER, { opacity: 0.8, strokeColor: { r: 255, g: 255, b: 255, alpha: 0.5 } });
    map.loadTiles('basemap', { source: BASEMAP_SOURCE, crs: 'EPSG:3857' });
    loadedRef.current = true;

    applyingViewRef.current = true;
    if (syncRef.current.isMapSyncEnabled && lastEmittedRef.current === null && globalViewStateRef.current) {
      applyViewState(map, globalViewStateRef.current);
    } else {
      fitMercBounds(map, projected.frameBounds, 10);
    }
    applyingViewRef.current = false;
    sizeMarksRef.current(map);

    return () => {
      loadedRef.current = false;
      if (mapRef.current !== map) return;
      map.removeLayer(DATA_LAYER);
      map.removeLayer('basemap');
    };
  }, [ready, projected, mapRef]);

  // 3. Colour by the selected column
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !projected?.mercBounds) return;
    if (thematic) {
      projected.collection.features.forEach((f, i) => {
        const v = thematic[i];
        f.properties[VALUE_KEY] = typeof v === 'number' && Number.isFinite(v) ? v : null;
      });
      map.updateThematic(DATA_LAYER, { collection: projected.collection, property: `properties.${VALUE_KEY}` });
      map.updateColorMap(DATA_LAYER, { colorMap: colorMapFor(NUMERIC_SCHEME) });
      map.updateRenderInfo(DATA_LAYER, { isColorMap: true });
    } else {
      map.updateRenderInfo(DATA_LAYER, { isColorMap: false, color: DEFAULT_COLOR });
    }
  }, [ready, projected, thematic, mapRef]);

  // Tooltip with the selected column's value, for the feature Autark picks under the pointer
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !projected?.mercBounds) return undefined;
    if (!selectedColumn) { map.setTooltip(DATA_LAYER, null); return undefined; }
    map.setTooltip(DATA_LAYER, (id) => {
      const value = data.features[projected.sourceIndex[id]]?.properties?.[selectedColumn];
      return value === undefined ? null : `${selectedColumn}: ${value}`;
    });
    return () => { if (mapRef.current === map) map.setTooltip(DATA_LAYER, null); };
  }, [ready, projected, data, selectedColumn, mapRef]);

  // GLOBAL VIEWPORT SYNC: follow the shared camera unless this map produced it
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !loadedRef.current || !isMapSyncEnabled || !globalViewState) return;
    if (globalViewState === lastEmittedRef.current) return;
    applyingViewRef.current = true;
    applyViewState(map, globalViewState);
    applyingViewRef.current = false;
  }, [ready, isMapSyncEnabled, globalViewState, mapRef]);

  // The canvas stays mounted while loading: the map is created once, on mount.
  return (
    <div
      className="nodrag nowheel ut-autark-map"
      style={{ width: '100%', height: `${height}px`, position: 'relative', background: '#f1f5f9' }}
      onPointerDown={() => { userMovedRef.current = true; }}
      onWheel={() => { userMovedRef.current = true; }}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      {loading && <div style={{ position: 'absolute', inset: 0, background: '#f8fafc' }} />}
      {error && <MapError message={error} />}
    </div>
  );
};

export const MapError = ({ message }) => (
  <div style={{
    position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
    padding: '8px', fontSize: '10px', color: '#64748b', background: '#f8fafc',
  }}>
    {message}
  </div>
);

export default VectorPreviewMap;
