// The copilot's LLM settings (backend/copilot_settings.py).
import { API_BASE } from '../config/api';

export async function copilotCall(method, path, body) {
  const r = await fetch(`${API_BASE}${path}`, {
    method, headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`);
  return j;
}

export const getCopilotSettings = () => copilotCall('GET', '/api/copilot/settings');
