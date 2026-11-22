// Shared helpers for the Autark (WebGPU) map previews.
//
// Collections reach Autark in lon/lat (EPSG:4326, as the backend serves them) and Autark projects
// them into the map's workspace CRS, Web Mercator (EPSG:3857), which the basemap tiles use too.
// Autark also does hover, picking and tooltips. What stays here: framing (a first view that skips
// stray points), the camera as a Deck.GL-style view state for linked maps, colour schemes, and the
// React lifecycle.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AutkMap } from '@urban-toolkit/autk-map';

const R = 6378137;
const WORLD = 2 * Math.PI * R;
const MAX_LAT = 85.05112878;
// Deck.GL zoom convention: the whole world is 512 px wide at zoom 0. Keeping it lets the
// shared `globalViewState` ({ longitude, latitude, zoom }) stay meaningful across nodes.
const WORLD_PX_AT_ZOOM_0 = 512;

export const BASEMAP_SOURCE = {
  urlTemplate: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors',
  maxZoom: 16,
};

export const lonLatToMerc = (lon, lat) => {
  const clamped = Math.max(-MAX_LAT, Math.min(MAX_LAT, lat));
  return [R * (lon * Math.PI / 180), R * Math.log(Math.tan(Math.PI / 4 + (clamped * Math.PI / 180) / 2))];
};

export const mercToLonLat = (x, y) => [
  (x / R) * 180 / Math.PI,
  (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * 180 / Math.PI,
];

const growBounds = (b, coords) => {
  if (typeof coords[0] === 'number') {
    if (coords[0] < b[0]) b[0] = coords[0];
    if (coords[1] < b[1]) b[1] = coords[1];
    if (coords[0] > b[2]) b[2] = coords[0];
    if (coords[1] > b[3]) b[3] = coords[1];
  } else {
    coords.forEach(c => growBounds(b, c));
  }
  return b;
};

export const geometryBounds = (geometry) => {
  if (!geometry) return null;
  const b = [Infinity, Infinity, -Infinity, -Infinity];
  if (geometry.type === 'GeometryCollection') geometry.geometries.forEach(g => g && growBounds(b, g.coordinates));
  else growBounds(b, geometry.coordinates);
  return b[0] === Infinity ? null : b;
};

const mercBox = ([x0, y0, x1, y1]) => [...lonLatToMerc(x0, y0), ...lonLatToMerc(x1, y1)];

/**
 * Prepares a lon/lat collection for Autark, which projects it (load it with `sourceCrs: SOURCE_CRS`).
 * Features without geometry are dropped, so a feature's position in the layer (Autark's component
 * id, which hover and tooltips report) maps back to the original through `sourceIndex`.
 * `mercBounds` and `frameBounds` are in Web Mercator metres, the map's coordinates (see framingBounds).
 */
export const prepareCollection = (collection) => {
  const features = [];
  const sourceIndex = [];
  const boxes = [];
  (collection?.features || []).forEach((feature, i) => {
    const bounds = geometryBounds(feature?.geometry);
    if (!bounds || !bounds.every(Number.isFinite)) return;
    features.push({ type: 'Feature', id: features.length, properties: { ...(feature.properties || {}) }, geometry: feature.geometry });
    sourceIndex.push(i);
    boxes.push(mercBox(bounds));
  });
  const union = boxes.reduce((u, b) => [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])],
    [Infinity, Infinity, -Infinity, -Infinity]);
  return {
    collection: { type: 'FeatureCollection', features },
    sourceIndex,
    mercBounds: features.length ? union : null,
    frameBounds: features.length ? framingBounds(boxes) : null,
  };
};

/** The CRS collections are given to Autark in. */
export const SOURCE_CRS = 'EPSG:4326';

/**
 * Bounds to frame on first view. Some datasets carry bad geocodes far from the city (one school
 * dataset has half its points spread from Hawaii to Maine), and framing every feature would shrink
 * the real data to a speck. So the densest ~75 km area (3x3 cells of 25 km, Mercator metres) is
 * found, and the features there are framed, unless it already holds nearly everything.
 */
export const framingBounds = (featureBoundsList) => {
  const boxes = featureBoundsList.filter(Boolean);
  if (!boxes.length) return null;
  const union = (list) => list.reduce(
    (u, b) => [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])],
    [Infinity, Infinity, -Infinity, -Infinity],
  );
  const CELL = 25000;
  const cellOf = (b) => [Math.floor((b[0] + b[2]) / 2 / CELL), Math.floor((b[1] + b[3]) / 2 / CELL)];
  const counts = new Map();
  boxes.forEach(b => {
    const [cx, cy] = cellOf(b);
    const key = `${cx},${cy}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  let best = null;
  let bestCount = -1;
  counts.forEach((_, key) => {
    const [cx, cy] = key.split(',').map(Number);
    let n = 0;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) n += counts.get(`${cx + dx},${cy + dy}`) || 0;
    if (n > bestCount) {
      bestCount = n;
      best = [cx, cy];
    }
  });
  if (bestCount >= 0.95 * boxes.length) {
    // Nearly everything is in one area: frame the central 99.6% of the features, so a few strays (one
    // program site geocoded to Los Angeles) do not stretch the frame across a continent.
    if (boxes.length < 50) return union(boxes);
    const centres = boxes.map((b) => [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]);
    const xs = centres.map((c) => c[0]).sort((a, b) => a - b);
    const ys = centres.map((c) => c[1]).sort((a, b) => a - b);
    const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.round(f * (arr.length - 1))))];
    const [x0, x1, y0, y1] = [q(xs, 0.002), q(xs, 0.998), q(ys, 0.002), q(ys, 0.998)];
    return union(boxes.filter((b, i) => centres[i][0] >= x0 && centres[i][0] <= x1 && centres[i][1] >= y0 && centres[i][1] <= y1));
  }
  const cluster = boxes.filter(b => {
    const [cx, cy] = cellOf(b);
    return Math.abs(cx - best[0]) <= 1 && Math.abs(cy - best[1]) <= 1;
  });
  return union(cluster);
};

/** Autark layer type for a collection, from its first geometry. */
export const layerTypeFor = (collection) => {
  const type = collection?.features?.find(f => f.geometry)?.geometry?.type || '';
  if (type.includes('Point')) return 'points';
  if (type.includes('LineString')) return 'polylines';
  return 'polygons';
};

// ---------------------------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------------------------

const viewportCssHeight = (map) => map.canvas.clientHeight || 1;

// Autark's `lookAt` is not always on the ground: after a pan it sits one unit in front of the
// eye. The view centre and distance therefore come from where the centre ray meets z = 0.
const groundCentre = (map) => map.camera.getGroundPoint(0.5, 0.5, 1e7);

/** Map metres per CSS pixel at the view centre. */
export const metresPerPixel = (map) => {
  const cam = map.camera;
  const eye = cam.getEye();
  const [gx, gy] = groundCentre(map);
  const dist = Math.hypot(eye[0] - gx, eye[1] - gy, eye[2]);
  return (2 * dist * Math.tan(cam.getFovyRadians() / 2)) / viewportCssHeight(map);
};

const setTopDownCamera = (map, mercX, mercY, mpp) => {
  const cam = map.camera;
  const [ox, oy] = map.layerManager.origin;
  const height = (mpp * viewportCssHeight(map)) / (2 * Math.tan(cam.getFovyRadians() / 2));
  const lookAt = [mercX - ox, mercY - oy, 0];
  cam.resetCamera([0, 1, 0], lookAt, [lookAt[0], lookAt[1], height]);
  // CSS pixels, as Autark's own resize handler uses (zoom-at-cursor depends on it).
  cam.resize(map.canvas.offsetWidth, map.canvas.offsetHeight);
};

/** Frames a Web Mercator bounding box with Autark's fitBounds, leaving about `padding` CSS pixels on each side. */
export const fitMercBounds = (map, bounds, padding = 10) => {
  if (!bounds) return;
  const w = Math.max(map.canvas.clientWidth, 1);
  const h = Math.max(map.canvas.clientHeight, 1);
  const spanX = Math.max(bounds[2] - bounds[0], 50);
  const spanY = Math.max(bounds[3] - bounds[1], 50);
  const cx = (bounds[0] + bounds[2]) / 2;
  const cy = (bounds[1] + bounds[3]) / 2;
  const padX = (spanX / Math.max(w - 2 * padding, 1)) * padding;
  const padY = (spanY / Math.max(h - 2 * padding, 1)) * padding;
  map.fitBounds([cx - spanX / 2 - padX, cy - spanY / 2 - padY, cx + spanX / 2 + padX, cy + spanY / 2 + padY]);
  // CSS pixels, as Autark's own resize handler uses (zoom-at-cursor depends on it).
  map.camera.resize(map.canvas.offsetWidth, map.canvas.offsetHeight);
};

/** The camera as a Deck.GL-style view state, so the shared sync state keeps its shape. */
export const cameraToViewState = (map) => {
  const [gx, gy] = groundCentre(map);
  const [ox, oy] = map.layerManager.origin;
  const [longitude, latitude] = mercToLonLat(gx + ox, gy + oy);
  const zoom = Math.log2(WORLD / (WORLD_PX_AT_ZOOM_0 * metresPerPixel(map)));
  return { longitude, latitude, zoom, pitch: 0, bearing: 0 };
};

export const applyViewState = (map, viewState) => {
  if (!viewState || !Number.isFinite(viewState.zoom)) return;
  const [x, y] = lonLatToMerc(viewState.longitude, viewState.latitude);
  setTopDownCamera(map, x, y, WORLD / (WORLD_PX_AT_ZOOM_0 * 2 ** viewState.zoom));
};

/** CSS-pixel position of a Mercator point, or null when it is behind the camera. */
export const mercToScreen = (map, x, y, vp = map.camera.getViewProjectionMatrix()) => {
  const [ox, oy] = map.layerManager.origin;
  const lx = x - ox;
  const ly = y - oy;
  const cx = vp[0] * lx + vp[4] * ly + vp[12];
  const cy = vp[1] * lx + vp[5] * ly + vp[13];
  const cw = vp[3] * lx + vp[7] * ly + vp[15];
  if (cw <= 0) return null;
  return [((cx / cw + 1) / 2) * map.canvas.clientWidth, ((1 - cy / cw) / 2) * map.canvas.clientHeight];
};

// ---------------------------------------------------------------------------------------------
// Colors. Autark colours thematic layers with d3's named schemes only, so UrbanTrace's
// RGB ramps are matched to the nearest sequential scheme. `stops` approximate each scheme
// for the HTML legends.
// ---------------------------------------------------------------------------------------------

export const SCHEMES = {
  YlOrRd: { interpolator: 'interpolateYlOrRd', stops: ['#ffffcc', '#fd8d3c', '#800026'] },
  Reds: { interpolator: 'interpolateReds', stops: ['#fff5f0', '#fb6a4a', '#67000d'] },
  Oranges: { interpolator: 'interpolateOranges', stops: ['#fff5eb', '#fd8d3c', '#7f2704'] },
  Greens: { interpolator: 'interpolateGreens', stops: ['#f7fcf5', '#74c476', '#00441b'] },
  BuGn: { interpolator: 'interpolateBuGn', stops: ['#f7fcfd', '#66c2a4', '#00441b'] },
  Blues: { interpolator: 'interpolateBlues', stops: ['#f7fbff', '#6baed6', '#08306b'] },
  Purples: { interpolator: 'interpolatePurples', stops: ['#fcfbfd', '#9e9ac8', '#3f007d'] },
  RdPu: { interpolator: 'interpolateRdPu', stops: ['#fff7f3', '#f768a1', '#49006a'] },
  Greys: { interpolator: 'interpolateGreys', stops: ['#ffffff', '#969696', '#000000'] },
};

const hueSat = ([r, g, b]) => {
  const max = Math.max(r, g, b) / 255;
  const min = Math.min(r, g, b) / 255;
  const d = max - min;
  const sat = max === 0 ? 0 : d / max;
  if (d === 0) return [0, 0];
  let h;
  if (max === r / 255) h = ((g - b) / 255 / d) % 6;
  else if (max === g / 255) h = (b - r) / 255 / d + 2;
  else h = (r - g) / 255 / d + 4;
  return [(h * 60 + 360) % 360, sat];
};

/** Nearest sequential scheme for a single RGB colour. */
export const schemeForColor = (rgb) => {
  const [h, s] = hueSat(rgb);
  if (s < 0.15) return SCHEMES.Greys;
  if (h < 15 || h >= 345) return SCHEMES.Reds;
  if (h < 45) return SCHEMES.Oranges;
  if (h < 70) return SCHEMES.YlOrRd;
  if (h < 150) return SCHEMES.Greens;
  if (h < 190) return SCHEMES.BuGn;
  if (h < 250) return SCHEMES.Blues;
  if (h < 290) return SCHEMES.Purples;
  return SCHEMES.RdPu;
};

/** Nearest scheme for a { low, high } palette: a yellow low end means the yellow-to-red ramp. */
export const schemeForPalette = (palette) => {
  const [lowHue, lowSat] = hueSat(palette.low);
  if (lowSat > 0.4 && lowHue >= 40 && lowHue < 70) return SCHEMES.YlOrRd;
  return schemeForColor(palette.high);
};

export const colorMapFor = (scheme) => ({ interpolator: scheme.interpolator, domainSpec: { type: 'minMax' } });

// ---------------------------------------------------------------------------------------------
// React lifecycle
// ---------------------------------------------------------------------------------------------

/**
 * Creates an AutkMap on the canvas once it is mounted, and destroys it on unmount.
 * `onCameraChange(map)` runs after every camera change (drag, zoom, resize or code).
 */
/** Maps per canvas element, kept alive across React StrictMode's remount (see useAutarkMap). */
const LIVE_MAPS = new WeakMap();

export function useAutarkMap(canvasRef, { enabled = true, onCameraChange, onResize } = {}) {
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);
  const onCameraChangeRef = useRef(onCameraChange);
  const onResizeRef = useRef(onResize);
  useLayoutEffect(() => {
    onCameraChangeRef.current = onCameraChange;
    onResizeRef.current = onResize;
  });

  // Autark resizes only on window resize. React Flow lays nodes out (and lets the user resize them)
  // without one, so follow the canvas element itself; otherwise the map keeps its startup
  // resolution and aspect ratio, and looks stretched and small.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!ready || !canvas) return undefined;
    let last = '';
    const observer = new ResizeObserver(() => {
      const map = mapRef.current;
      const size = `${canvas.offsetWidth}x${canvas.offsetHeight}`;
      if (!map || size === last || !canvas.offsetWidth || !canvas.offsetHeight) return;
      last = size;
      map._resizeEvents?.resize();
      map.requestRender();
      onResizeRef.current?.(map);
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [canvasRef, ready]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!enabled || !canvas) return undefined;
    if (!navigator.gpu) return undefined;

    // React StrictMode unmounts and remounts every effect once in development. A second AutkMap on
    // the same canvas shares its WebGPU context, and destroying the first one unconfigures that
    // context, leaving the canvas blank. So disposal is deferred and an immediate remount reuses it.
    let entry = LIVE_MAPS.get(canvas);
    if (entry) {
      clearTimeout(entry.disposeTimer);
      entry.disposeTimer = null;
    } else {
      // The workspace CRS must be stated: Autark defaults to EPSG:3395 and then refuses the EPSG:3857
      // basemap tiles. Collections reach the map already in Web Mercator (projectCollection).
      const map = new AutkMap(canvas, false, { crs: 'EPSG:3857' });
      entry = {
        map,
        listener: null,
        disposeTimer: null,
        started: map.init().then(() => {
          map.style.setHighlightColor('#3b82f6');
          // MapCamera reports every change through `_onChange`; chain onto it to observe navigation.
          const camera = map.camera;
          const notify = camera._onChange;
          if (typeof notify === 'function') {
            camera._onChange = () => {
              notify();
              entry.listener?.();
            };
          }
          map.draw();
        }),
      };
      LIVE_MAPS.set(canvas, entry);
    }

    let cancelled = false;
    const { map } = entry;
    entry.listener = () => onCameraChangeRef.current?.(map);
    entry.started
      .then(() => {
        if (cancelled) return;
        mapRef.current = map;
        setReady(true);
      })
      .catch(err => {
        console.error('Autark map failed to start', err);
        if (!cancelled) setError(String(err?.message || err));
      });

    const current = entry;
    return () => {
      cancelled = true;
      current.listener = null;
      if (mapRef.current === map) mapRef.current = null;
      setReady(false);
      current.disposeTimer = setTimeout(() => {
        LIVE_MAPS.delete(canvas);
        current.started.catch(() => {}).then(() => map.destroy());
      }, 0);
    };
  }, [canvasRef, enabled]);

  const noWebGpu = typeof navigator !== 'undefined' && !navigator.gpu;
  return { mapRef, ready, error: noWebGpu ? 'This browser has no WebGPU, which the Autark map needs.' : error };
}
