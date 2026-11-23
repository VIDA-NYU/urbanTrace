// Analyses (docs/REDESIGN.md, phase 5): sweeps, validation against outcomes, dasymetric.
import { API_BASE } from '../config/api';

async function post(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof json.detail === 'string' ? json.detail : `HTTP ${response.status}`);
  return json;
}

export const runSweep = (body) => post('/api/analysis/sweep', body);
export const runValidation = (body) => post('/api/analysis/validate', body);
export const runDasymetric = (body) => post('/api/analysis/dasymetric', body);
export const reportUrl = (collectionId) => `${API_BASE}/api/collections/${collectionId}/report`;

// Matching methods worth comparing for a source geometry (a variant that does not fit is reported, not fatal)
export const METHODS_FOR = {
  Point: ['contain', 'nearest', 'gaussian'],
  LineString: ['length_weighted', 'centroid', 'largest_overlap'],
  Polygon: ['area_overlap', 'centroid', 'largest_overlap', 'representative_point'],
};
