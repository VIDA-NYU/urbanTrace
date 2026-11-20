// Study area, coverage, time and checks (docs/REDESIGN.md, phase 2).
import { API_BASE } from '../config/api';

async function post(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof json.detail === 'string' ? json.detail : `HTTP ${response.status}`);
  return json;
}

let indexPromise = null;
// One row per dataset (bbox, time range, geometry, rows); fetched once and shared.
export function getCatalogIndex({ refresh = false } = {}) {
  if (!indexPromise || refresh) {
    indexPromise = fetch(`${API_BASE}/api/catalog/index`)
      .then((r) => (r.ok ? r.json() : { datasets: [] }))
      .then((j) => Object.fromEntries((j.datasets || []).map((d) => [d.id, d])))
      .catch(() => { indexPromise = null; return {}; });
  }
  return indexPromise;
}

export const getStudyAreaOptions = async (datasetId) => {
  const response = await fetch(`${API_BASE}/api/study-area/options/${encodeURIComponent(datasetId)}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
};
export const resolveStudyArea = (spec) => post('/api/study-area/resolve', spec);
export const getCoverage = (datasets, studyArea) => post('/api/coverage', { datasets, study_area: studyArea || null });
export const checkCollection = (doc) => post('/api/collections/check', doc);

export const bboxIntersects = (a, b) => !!(a && b && a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1]);

// Does a dataset's time range overlap [fromYear, toYear]? Datasets without time pass.
export function overlapsPeriod(time, fromYear, toYear) {
  if (!time || (!fromYear && !toYear)) return true;
  const start = time.start ? Number(time.start.slice(0, 4)) : -Infinity;
  const end = time.end ? Number(time.end.slice(0, 4)) : Infinity;
  return (!fromYear || end >= Number(fromYear)) && (!toYear || start <= Number(toYear));
}
