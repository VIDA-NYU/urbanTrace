// Data checks and corrections with atlas-clean (backend/cleaning.py).
import { API_BASE } from '../config/api';
import { getCatalogIndex, clearInAreaCache } from './scope';

async function call(method, path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined,
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof json.detail === 'string' ? json.detail : `HTTP ${response.status}`);
  return json;
}

const enc = encodeURIComponent;
export const checkDataset = (id) => call('POST', `/api/datasets/${enc(id)}/check`);

// Saving or removing corrections changes the data every view reads: refresh what is cached.
const refreshed = async (promise) => {
  const out = await promise;
  clearInAreaCache();
  await getCatalogIndex({ refresh: true });
  return out;
};
export const saveRecipe = (id, accept) => refreshed(call('POST', `/api/datasets/${enc(id)}/recipe`, { accept }));
export const deleteRecipe = (id) => refreshed(call('DELETE', `/api/datasets/${enc(id)}/recipe`));

// Locating rows from their addresses (backend/geocode.py). The preview sends nothing; starting
// sends the addresses to NYC GeoSearch and runs in the background, polled with getGeocode.
export const geocodePreview = (id, spec = {}) => call('POST', `/api/datasets/${enc(id)}/geocode/preview`, { spec });
export const startGeocode = (id, spec) => call('POST', `/api/datasets/${enc(id)}/geocode`, { spec });
export const getGeocode = (id) => call('GET', `/api/datasets/${enc(id)}/geocode`);
export const deleteGeocode = (id) => refreshed(call('DELETE', `/api/datasets/${enc(id)}/geocode`));
// After a run finishes, the dataset's locations changed: refresh what is cached
export const geocodeFinished = () => refreshed(Promise.resolve(null));
