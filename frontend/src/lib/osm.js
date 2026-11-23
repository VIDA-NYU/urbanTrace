// Street networks from OpenStreetMap for the study area (backend/osm.py).
import { API_BASE } from '../config/api';

async function post(path, body) {
  const r = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`);
  return j;
}

export const networkStatus = (studyArea, networkType) => post('/api/osm/network', { study_area: studyArea, network_type: networkType });
export const downloadNetwork = (studyArea, networkType) => post('/api/osm/network/download', { study_area: studyArea, network_type: networkType });
