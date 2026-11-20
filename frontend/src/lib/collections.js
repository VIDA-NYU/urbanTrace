// Client for the collections API (docs/REDESIGN.md, section 2) and helpers to turn the canvas into a
// collection document and back.
import { API_BASE } from '../config/api';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // not JSON
    }
    throw new Error(detail);
  }
  return response;
}

export const listCollections = async () => (await (await request('/api/collections')).json()).collections || [];
export const getCollection = async (id) => (await request(`/api/collections/${id}`)).json();
export const createCollection = async (doc) =>
  (await request('/api/collections', { method: 'POST', body: JSON.stringify(doc) })).json();
export const updateCollection = async (id, doc) =>
  (await request(`/api/collections/${id}`, { method: 'PUT', body: JSON.stringify(doc) })).json();
export const deleteCollection = async (id) => request(`/api/collections/${id}`, { method: 'DELETE' });

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function filenameFrom(response, fallback) {
  const header = response.headers.get('content-disposition') || '';
  const match = header.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

export async function exportCollection(id, options) {
  const response = await request(`/api/collections/${id}/export`, { method: 'POST', body: JSON.stringify(options) });
  downloadBlob(await response.blob(), filenameFrom(response, 'collection.zip'));
}

export async function exportResult(body) {
  const response = await request('/api/results/export', { method: 'POST', body: JSON.stringify(body) });
  downloadBlob(await response.blob(), filenameFrom(response, 'result.zip'));
}

// ---------------------------------------------------------------------------------------------
// Canvas <-> collection

export const normalizeDatasetId = (value) => {
  if (typeof value !== 'string') return '';
  return value.trim().replace(/\.geojson$/i, '').split('/').pop();
};

// Node data keys that are not saved: callbacks are re-attached on load, results are recomputed.
const TRANSIENT_KEYS = new Set([
  'spatialData', 'comparePayload', 'connectedResults', 'metadata', 'connectedDatasetMetadata',
  'connectedZoneMetadata', 'globalViewState', 'isMapSyncEnabled', 'highlightedLogTs', 'focusedLogTs',
  'hoveredCompareFeatureId', 'hoveredCompareFeatureType',
]);
// Outputs are not saved as nodes; they are recomputed from the saved integrations.
const OUTPUT_NODE_TYPES = new Set(['resultMapNode', 'compareMapNode']);

function serializableData(data = {}) {
  const out = {};
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === 'function' || TRANSIENT_KEYS.has(key)) continue;
    if (key === 'connectedDatasets' && Array.isArray(value)) {
      out[key] = value.map(({ metadata, ...rest }) => rest); // eslint-disable-line no-unused-vars
      continue;
    }
    out[key] = value;
  }
  return JSON.parse(JSON.stringify(out));
}

export function serializeCanvas(nodes, edges) {
  const kept = nodes.filter((n) => !OUTPUT_NODE_TYPES.has(n.type));
  const keptIds = new Set(kept.map((n) => n.id));
  return {
    nodes: kept.map((n) => ({ id: n.id, type: n.type, position: n.position, data: serializableData(n.data) })),
    edges: edges
      .filter((e) => keptIds.has(e.source) && keptIds.has(e.target))
      .map(({ id, source, target, sourceHandle, targetHandle }) => ({ id, source, target, sourceHandle, targetHandle })),
  };
}

// The datasets of the collection: every dataset node, with the columns it is colored by or
// integrated on, and who added it and why.
export function collectionDatasets(nodes) {
  const byId = new Map();
  const ensure = (id) => {
    if (!byId.has(id)) byId.set(id, { id, columns: [], value_kinds: {}, added_by: 'user', rationale: null });
    return byId.get(id);
  };
  for (const node of nodes) {
    if (node.type !== 'datasetNode') continue;
    const id = normalizeDatasetId(node.data?.id || node.data?.filename);
    if (!id) continue;
    const entry = ensure(id);
    if (node.data?.selectedColumn && !entry.columns.includes(node.data.selectedColumn)) {
      entry.columns.push(node.data.selectedColumn);
    }
    if (node.data?.addedBy === 'copilot') entry.added_by = 'copilot';
    if (node.data?.copilotReason) entry.rationale = node.data.copilotReason;
    Object.assign(entry.value_kinds, node.data?.valueKinds || {});
  }
  for (const node of nodes) {
    const variables = node.type === 'resultMapNode' ? node.data?.spatialData?.request?.variables || [] : [];
    for (const v of variables) {
      const id = normalizeDatasetId(v.dataset_path);
      if (!byId.has(id)) continue;
      const entry = byId.get(id);
      if (v.target_column && !entry.columns.includes(v.target_column)) entry.columns.push(v.target_column);
    }
  }
  return [...byId.values()];
}

// The integrations of the collection: one per result on the canvas, with its request and rationale.
export function collectionIntegrations(nodes, edges) {
  return nodes
    .filter((n) => n.type === 'resultMapNode' && n.data?.spatialData?.request)
    .map((n) => {
      const sd = n.data.spatialData;
      const sourceEdge = edges.find((e) => e.target === n.id);
      const rationale = {};
      for (const v of sd.provenance?.variables || []) {
        if (v?.rationale) rationale[`${v.dataset}::${v.targetColumn}`] = v.rationale;
      }
      return {
        id: n.id,
        node_id: sourceEdge?.source || null,
        name: n.data?.name || 'Integration',
        request: sd.request,
        rationale,
        created_at: sd.provenance?.timestamp || null,
      };
    });
}
