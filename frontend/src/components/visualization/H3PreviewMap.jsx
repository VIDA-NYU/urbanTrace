// H3 hexagon and reporting-zone preview map, drawn with Autark (WebGPU) over a light-gray basemap.
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { cellToBoundary, cellToLatLng, getResolution, latLngToCell } from 'h3-js';
import {
  BASEMAP_SOURCE, SCHEMES, applyViewState, cameraToViewState, colorMapFor, fitMercBounds, hitTest,
  lonLatToMerc, mercToLonLat, mercToScreen, projectCollection, schemeForColor, schemeForPalette,
  screenToMerc, useAutarkMap, pointerInElement,
} from './autark/autarkMap';
import { MapError } from './VectorPreviewMap';

const HEX_LAYER = 'h3-hexagon-layer';
const ZONE_LAYER = 'zone-layer';
const VALUE_KEY = '__ut_value';
const EXCLUDE_PROPS = ['zone_id', 'label', 'geometry', 'OBJECTID', 'Shape_Area', 'Shape_Leng', VALUE_KEY, '__display_column'];
// Counts read as counts: whole numbers without decimals, others with two.
const fmt = (v) => (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2));
const FIRE_PALETTE = { low: [253, 224, 71], high: [153, 27, 27] };

const getZoneFeatureId = (feature) => {
  const props = feature?.properties || {};
  return String(props.zone_id ?? props.ZONE_ID ?? props.OBJECTID ?? props.objectid ?? props.id ?? props.NAME ?? props.name ?? '');
};

const zoneTotal = (props) => {
  // A result that names the column to show (plan results do) is colored by it, never by a sum
  if (props.__display_column) {
    const v = props[props.__display_column];
    return typeof v === 'number' && !isNaN(v) ? v : 0;
  }
  if (props.zone_value) return props.zone_value;
  return Object.entries(props).reduce(
    (sum, [key, val]) => (!EXCLUDE_PROPS.includes(key) && typeof val === 'number' && !isNaN(val) ? sum + val : sum),
    0,
  );
};

const getDirectionSymbol = (delta) => {
  const abs = Math.abs(Number(delta) || 0);
  if (abs < 0.1) return '•';
  return delta > 0 ? '⬆' : '⬇';
};

const getDirectionColor = (delta) => {
  const abs = Math.abs(Number(delta) || 0);
  if (abs < 0.1) return 'rgb(107, 114, 128)';
  return delta > 0 ? 'rgb(22, 163, 74)' : 'rgb(220, 38, 38)';
};

const getDirectionSize = (delta) => {
  const abs = Math.abs(Number(delta) || 0);
  if (abs >= 0.5) return 28;
  if (abs >= 0.25) return 20;
  if (abs >= 0.1) return 14;
  return 8;
};

const getPolygonCentroid = (geometry) => {
  const coords = geometry?.coordinates;
  if (!coords) return null;
  let points = [];
  if (geometry.type === 'Polygon') points = coords.flat(1);
  else if (geometry.type === 'MultiPolygon') points = coords.flat(2);
  const valid = points.filter(p => Array.isArray(p) && typeof p[0] === 'number' && typeof p[1] === 'number');
  if (!valid.length) return null;
  const sum = valid.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0]);
  return [sum[0] / valid.length, sum[1] / valid.length];
};

const defaultTooltip = (object, layerId) => {
  if (layerId === HEX_LAYER) {
    const variablesHtml = object.variables && Object.keys(object.variables).length > 0
      ? Object.entries(object.variables)
        .map(([name, val]) => `<div><strong>${name}:</strong> ${typeof val === 'number' ? fmt(val) : val}</div>`)
        .join('')
      : `<div><strong>Value:</strong> ${object.count}</div>`;
    return {
      html: `
        <div style="font-family: sans-serif;">
          <div style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
            Hex ID: ${object.hex.slice(0, 8)}...
          </div>
          ${variablesHtml}
          ${object.sources?.length ? `<div style="margin-top: 4px;"><strong>Sources:</strong> ${object.sources.join(', ')}</div>` : ''}
        </div>`,
      style: { backgroundColor: '#1e293b', color: '#f8fafc', border: '1px solid #334155' },
    };
  }
  const props = object.properties || {};
  let variablesHtml;
  if (props.zone_value !== undefined) {
    variablesHtml = `<div><strong>Value:</strong> ${props.zone_value?.toFixed(2) || 'N/A'}</div>`;
  } else {
    const entries = Object.entries(props).filter(([key, val]) => !EXCLUDE_PROPS.includes(key) && typeof val === 'number' && !isNaN(val));
    variablesHtml = entries.length
      ? entries.map(([name, val]) => `<div${name === props.__display_column ? ' style="font-weight:700"' : ''}><strong>${name}:</strong> ${fmt(val)}</div>`).join('')
      : '<div>No values</div>';
  }
  return {
    html: `
      <div style="font-family: sans-serif;">
        <div style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
          ${props.label ?? `Zone ${props.zone_id ?? 'unknown'}`}
        </div>
        ${variablesHtml}
      </div>`,
    style: { backgroundColor: '#064e3b', color: '#f8fafc', border: '1px solid #10b981' },
  };
};

const H3PreviewMap = ({
  hexData,
  geojsonData,
  color = [236, 72, 153],
  useHotspotPalette = false,
  hotspotPalette = null, // { low: [r,g,b], high: [r,g,b] }, mapped to the nearest colour scheme
  highlightedHexId = null,
  highlightedZoneId = null,
  onHexHover,
  onZoneHover,
  hideLegend = false,
  customTooltip = null,
  showDirectionSymbols = false,
  showHex = true,
  showZones = false,
  // GLOBAL VIEWPORT SYNC: Props for linked camera
  isMapSyncEnabled = false,
  globalViewState,
  onGlobalViewStateChange,
}) => {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const [hasSize, setHasSize] = useState(false);
  const [tooltip, setTooltip] = useState(null);

  // Wait until React Flow gives the container real dimensions before starting WebGPU.
  useEffect(() => {
    if (!containerRef.current) return undefined;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setHasSize(true);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const loadedRef = useRef(false);
  const fittedRef = useRef(false);
  const applyingViewRef = useRef(false);
  const lastEmittedRef = useRef(null);
  const emitFrameRef = useRef(0);
  const drawSymbolsRef = useRef(() => {});
  const hoverRef = useRef({ hex: null, zone: null });
  const syncRef = useRef({ isMapSyncEnabled, onGlobalViewStateChange, globalViewState });
  useLayoutEffect(() => {
    syncRef.current = { isMapSyncEnabled, onGlobalViewStateChange, globalViewState };
  });

  const handleCameraChange = useCallback((map) => {
    setTooltip(null);
    drawSymbolsRef.current();
    const { isMapSyncEnabled: sync, onGlobalViewStateChange: emit } = syncRef.current;
    if (applyingViewRef.current || !sync || !emit || !loadedRef.current || emitFrameRef.current) return;
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
  const boundsRef = useRef(null);
  const handleResize = useCallback((map) => {
    if (userMovedRef.current || syncRef.current.isMapSyncEnabled || !loadedRef.current || !boundsRef.current) return;
    applyingViewRef.current = true;
    fitMercBounds(map, boundsRef.current, 10);
    applyingViewRef.current = false;
  }, []);

  const { mapRef, ready, error } = useAutarkMap(canvasRef, { enabled: hasSize, onCameraChange: handleCameraChange, onResize: handleResize });

  useEffect(() => () => cancelAnimationFrame(emitFrameRef.current), []);

  // ---- Data ---------------------------------------------------------------------------------

  const { hexes, maxCount } = useMemo(() => {
    if (!hexData) return { hexes: [], maxCount: 1 };
    let max = 1;
    const parsed = Object.entries(hexData).map(([hexId, info]) => {
      if (info.count > max) max = info.count;
      return { hex: hexId, count: info.count, variables: info.variables || {}, sources: info.sources || [], props: info.sample_props || {} };
    });
    return { hexes: parsed, maxCount: max };
  }, [hexData]);

  const hexProjected = useMemo(() => {
    if (!showHex || !hexes.length) return null;
    const projected = projectCollection({
      type: 'FeatureCollection',
      features: hexes.map(d => ({
        type: 'Feature',
        properties: { [VALUE_KEY]: d.count },
        geometry: { type: 'Polygon', coordinates: [cellToBoundary(d.hex, true)] },
      })),
    });
    const indexByHex = new Map(projected.sourceIndex.map((src, i) => [hexes[src].hex, i]));
    return { ...projected, indexByHex, resolution: getResolution(hexes[0].hex) };
  }, [hexes, showHex]);

  const zoneProjected = useMemo(() => {
    if (!showZones || !geojsonData?.features?.length) return null;
    const projected = projectCollection(geojsonData);
    projected.collection.features.forEach(f => {
      const props = f.properties;
      props[VALUE_KEY] = useHotspotPalette
        ? Math.max(0, Math.min(1, typeof props.hotspot_score === 'number' ? props.hotspot_score : 0))
        : zoneTotal(props);
    });
    const indexById = new Map(projected.collection.features.map((f, i) => [getZoneFeatureId(f), i]));
    return { ...projected, indexById };
  }, [geojsonData, showZones, useHotspotPalette]);

  const hexScheme = useHotspotPalette ? schemeForPalette(hotspotPalette ?? FIRE_PALETTE) : schemeForColor(color);
  const zoneScheme = useHotspotPalette ? schemeForPalette(hotspotPalette ?? FIRE_PALETTE) : SCHEMES.BuGn;

  // ---- Layers -------------------------------------------------------------------------------

  // Frame the data the first time it arrives (or follow the shared camera when sync is on).
  const frameView = useCallback((map) => {
    if (fittedRef.current) return;
    const bounds = [hexProjected?.frameBounds, zoneProjected?.frameBounds].filter(Boolean);
    if (!bounds.length) return;
    fittedRef.current = true;
    applyingViewRef.current = true;
    const { isMapSyncEnabled: sync, globalViewState: shared } = syncRef.current;
    boundsRef.current = [
      Math.min(...bounds.map(b => b[0])), Math.min(...bounds.map(b => b[1])),
      Math.max(...bounds.map(b => b[2])), Math.max(...bounds.map(b => b[3])),
    ];
    if (sync && shared) {
      applyViewState(map, shared);
    } else {
      fitMercBounds(map, boundsRef.current, 10);
    }
    applyingViewRef.current = false;
  }, [hexProjected, zoneProjected]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !hexProjected) return undefined;
    map.loadCollection(HEX_LAYER, { collection: hexProjected.collection, type: 'polygons', property: `properties.${VALUE_KEY}` });
    map.updateRenderInfo(HEX_LAYER, { opacity: 0.8, isColorMap: true, strokeColor: { r: 255, g: 255, b: 255, alpha: 0.3 } });
    loadedRef.current = true;
    return () => {
      if (mapRef.current === map) map.removeLayer(HEX_LAYER);
    };
  }, [ready, hexProjected, mapRef]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !zoneProjected) return undefined;
    map.loadCollection(ZONE_LAYER, { collection: zoneProjected.collection, type: 'polygons', property: `properties.${VALUE_KEY}` });
    map.updateRenderInfo(ZONE_LAYER, { opacity: 0.75, isColorMap: true, strokeColor: { r: 15, g: 118, b: 110, alpha: 0.8 } });
    loadedRef.current = true;
    return () => {
      if (mapRef.current === map) map.removeLayer(ZONE_LAYER);
    };
  }, [ready, zoneProjected, mapRef]);

  // Basemap, once there is a data layer to set the map origin.
  const hasData = Boolean(hexProjected || zoneProjected);
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !hasData) return undefined;
    map.loadTiles('basemap', { source: BASEMAP_SOURCE, crs: 'EPSG:3857' });
    frameView(map);
    return () => {
      if (mapRef.current === map) map.removeLayer('basemap');
    };
  }, [ready, hasData, mapRef, frameView]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (hexProjected) map.updateColorMap(HEX_LAYER, { colorMap: colorMapFor(hexScheme) });
    if (zoneProjected) map.updateColorMap(ZONE_LAYER, { colorMap: colorMapFor(zoneScheme) });
  }, [ready, mapRef, hexProjected, zoneProjected, hexScheme, zoneScheme]);

  // Highlights driven by the parent (linked hover across nodes).
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !hexProjected) return;
    const index = highlightedHexId ? hexProjected.indexByHex.get(highlightedHexId) : undefined;
    if (index === undefined) map.clearHighlightedIds(HEX_LAYER);
    else map.setHighlightedIds(HEX_LAYER, [index]);
  }, [ready, mapRef, hexProjected, highlightedHexId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !zoneProjected) return;
    const index = highlightedZoneId ? zoneProjected.indexById.get(String(highlightedZoneId)) : undefined;
    if (index === undefined) map.clearHighlightedIds(ZONE_LAYER);
    else map.setHighlightedIds(ZONE_LAYER, [index]);
  }, [ready, mapRef, zoneProjected, highlightedZoneId]);

  // GLOBAL VIEWPORT SYNC: follow the shared camera unless this map produced it
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !loadedRef.current || !isMapSyncEnabled || !globalViewState) return;
    if (globalViewState === lastEmittedRef.current) return;
    applyingViewRef.current = true;
    applyViewState(map, globalViewState);
    applyingViewRef.current = false;
  }, [ready, isMapSyncEnabled, globalViewState, mapRef]);

  // ---- Direction symbols (Autark has no text layer, so they are drawn on a 2D overlay) ------

  const symbols = useMemo(() => {
    if (!showDirectionSymbols) return [];
    const result = [];
    if (showHex) {
      hexes.forEach(d => {
        const delta = Number(d?.variables?.delta_signed);
        if (!Number.isFinite(delta)) return;
        const [lat, lng] = cellToLatLng(d.hex);
        result.push({ merc: lonLatToMerc(lng, lat), delta });
      });
    }
    if (showZones && geojsonData?.features) {
      geojsonData.features.forEach(feature => {
        const delta = Number(feature?.properties?.delta_signed);
        const centroid = getPolygonCentroid(feature?.geometry);
        if (Number.isFinite(delta) && centroid) result.push({ merc: lonLatToMerc(centroid[0], centroid[1]), delta });
      });
    }
    return result;
  }, [showDirectionSymbols, showHex, showZones, hexes, geojsonData]);

  useLayoutEffect(() => {
    drawSymbolsRef.current = () => {
      const canvas = overlayRef.current;
      const map = mapRef.current;
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      if (!map || !loadedRef.current || !symbols.length) return;
      const vp = map.camera.getViewProjectionMatrix();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      symbols.forEach(({ merc, delta }) => {
        const p = mercToScreen(map, merc[0], merc[1], vp);
        if (!p || p[0] < -20 || p[1] < -20 || p[0] > w + 20 || p[1] > h + 20) return;
        ctx.font = `${getDirectionSize(delta)}px monospace`;
        ctx.fillStyle = getDirectionColor(delta);
        ctx.fillText(getDirectionSymbol(delta), p[0], p[1]);
      });
    };
  });

  useEffect(() => {
    drawSymbolsRef.current();
  }, [symbols, ready, hexProjected, zoneProjected]);

  // ---- Hover: Autark picks only on double-click, so hit-test here --------------------------

  const setHover = (hex, zone) => {
    if (hoverRef.current.hex !== hex) onHexHover?.(hex);
    if (hoverRef.current.zone !== zone) onZoneHover?.(zone);
    hoverRef.current = { hex, zone };
  };

  const handlePointerMove = (event) => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || event.buttons) return;
    const [px, py] = pointerInElement(event);
    const [x, y] = screenToMerc(map, px, py);

    let object = null;
    let layerId = null;
    let zone = null;
    let hex = null;
    if (zoneProjected) {
      const index = hitTest(zoneProjected, x, y, 0);
      if (index >= 0) {
        object = geojsonData.features[zoneProjected.sourceIndex[index]];
        layerId = ZONE_LAYER;
        zone = getZoneFeatureId(object) || null;
      }
    }
    if (!object && hexProjected) {
      const [lng, lat] = mercToLonLat(x, y);
      const cell = latLngToCell(lat, lng, hexProjected.resolution);
      const index = hexProjected.indexByHex.get(cell);
      if (index !== undefined) {
        object = hexes[hexProjected.sourceIndex[index]];
        layerId = HEX_LAYER;
        hex = object.hex;
      }
    }
    setHover(hex, zone);

    if (!object) {
      setTooltip(null);
      return;
    }
    const content = customTooltip?.({ object, layer: { id: layerId } }) || defaultTooltip(object, layerId);
    setTooltip({ x: px, y: py, content });
  };

  const handlePointerLeave = () => {
    setHover(null, null);
    setTooltip(null);
  };

  const tooltipBody = tooltip && (typeof tooltip.content === 'string'
    ? { text: tooltip.content, style: {} }
    : { html: tooltip.content.html, style: tooltip.content.style || {} });

  return (
    <div
      ref={containerRef}
      className="nodrag nowheel ut-autark-map"
      style={{ position: 'relative', width: '100%', height: '100%', borderRadius: '0 0 8px 8px', overflow: 'hidden', background: '#f1f5f9' }}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      onPointerDown={() => { userMovedRef.current = true; }}
      onWheel={() => { userMovedRef.current = true; }}
    >
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block' }} />
      <canvas ref={overlayRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
      {error && <MapError message={error} />}

      {tooltipBody && (
        <div
          style={{
            position: 'absolute', left: tooltip.x + 12, top: tooltip.y + 12, zIndex: 20, pointerEvents: 'none',
            backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '11px', padding: '8px', borderRadius: '6px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.3)', maxWidth: '250px', ...tooltipBody.style,
          }}
          {...(tooltipBody.html ? { dangerouslySetInnerHTML: { __html: tooltipBody.html } } : { children: tooltipBody.text })}
        />
      )}

      {/* Minimized 2D density legend */}
      {!hideLegend && maxCount > 1 && (
        <div style={{
          position: 'absolute', bottom: '8px', left: '8px', zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.9)', padding: '1px 2px', borderRadius: '4px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)', fontSize: '8px', color: '#334155',
          display: 'flex', flexDirection: 'column', gap: '2px', border: '0.2px solid #cbd5e1',
        }}>
          <div style={{ fontWeight: 'bold' }}>Density</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>1</span>
            <div style={{ width: '40px', height: '6px', borderRadius: '3px', background: `linear-gradient(to right, ${hexScheme.stops.join(', ')})` }} />
            <span>{maxCount}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default H3PreviewMap;
