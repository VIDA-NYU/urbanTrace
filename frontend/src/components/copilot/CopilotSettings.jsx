// Whether the copilot uses an LLM, and which (backend/copilot_settings.py). Without one, the copilot
// works by rules: dataset discovery by keywords, Step suggestions from urbanweave's registry, the
// priority map's directions from keyword lists (and asks the analyst when none applies). With one,
// it judges against the collection's goal. API keys are never entered here: hosted providers are
// usable when their key is in backend/.env; a local model (Ollama, LM Studio, llama.cpp, vLLM)
// needs none.
import React, { useCallback, useEffect, useState } from 'react';
import { Cpu, Loader2, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { copilotCall, getCopilotSettings } from '../../lib/copilot';

const call = copilotCall;

// The chip in the copilot bar: what the copilot runs on; opens the settings.
export function CopilotLlmChip({ status, onClick }) {
  const s = status?.settings;
  const on = s?.enabled;
  const label = !s ? 'LLM …' : on ? `LLM: ${s.provider === 'local' ? 'local' : s.provider}${s.model ? ` · ${s.model.replace(/^@[^/]+\//, '')}` : ''}` : 'LLM off · rules';
  return (
    <button type="button" onClick={onClick} title="Choose whether the copilot uses an LLM, and which"
      style={{ border: 'none', borderRadius: 999, padding: '4px 10px', fontSize: 10, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap',
        display: 'flex', alignItems: 'center', gap: 4, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis',
        background: on ? '#ede9fe' : '#fff7ed', color: on ? '#5b21b6' : '#9a3412' }}>
      <Cpu size={11} /> {label}
    </button>
  );
}

export default function CopilotSettings({ open, onClose, onChanged }) {
  const [status, setStatus] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [test, setTest] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const st = await getCopilotSettings();
      setStatus(st);
      setDraft({ ...st.settings });
    } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { if (open) { setTest(null); load(); } }, [open, load]);
  if (!open) return null;

  const providers = status?.providers || [];
  const chosen = providers.find((p) => p.id === draft?.provider);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));

  const save = async (body) => {
    setBusy(true); setError(null); setTest(null);
    try {
      const st = await call('POST', '/api/copilot/settings', body);
      setStatus(st); setDraft({ ...st.settings }); onChanged?.(st);
      return st;
    } catch (e) { setError(e.message); return null; } finally { setBusy(false); }
  };
  const runTest = async () => {
    const st = await save(draft);
    if (!st?.settings?.enabled) return;
    setBusy(true);
    try { setTest({ ok: true, ...(await call('POST', '/api/copilot/test')) }); } catch (e) { setTest({ ok: false, error: e.message }); }
    finally { setBusy(false); }
  };
  const recheckLocal = async () => { await save({ local_base_url: draft.local_base_url }); };

  const row = { display: 'grid', gap: 4, fontSize: 11 };
  const input = { height: 26, border: '1px solid #cbd5e1', borderRadius: 6, padding: '0 8px', fontSize: 12, color: '#0f172a', background: '#fff' };
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.35)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onMouseDown={onClose}>
      <div onMouseDown={(e) => e.stopPropagation()}
        style={{ width: 460, maxWidth: 'calc(100vw - 32px)', background: '#fff', color: '#0f172a', borderRadius: 10, boxShadow: '0 20px 40px rgba(0,0,0,0.2)', padding: 16, display: 'grid', gap: 12, fontSize: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <b style={{ fontSize: 14, display: 'flex', gap: 6, alignItems: 'center' }}><Cpu size={15} /> Copilot LLM</b>
          <button type="button" onClick={onClose} style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 2 }}><X size={15} /></button>
        </div>
        <div style={{ color: '#475569', lineHeight: 1.45 }}>
          Without an LLM the copilot works by rules: dataset search by keywords, Step suggestions from urbanweave&apos;s registry, and
          priority-map directions from keyword lists (it asks you when no rule applies). With an LLM it judges these against the
          collection&apos;s goal. Requests send the goal, dataset descriptions and profiles to the provider; a local model keeps them on this machine.
        </div>
        {!draft ? (error ? <div style={{ color: '#b91c1c' }}>{error}</div> : <Loader2 size={14} className="spin" />) : (
          <>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600 }}>
              <input type="checkbox" checked={!!draft.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
              Use an LLM
            </label>
            <div style={{ display: 'grid', gap: 6, opacity: draft.enabled ? 1 : 0.5 }}>
              {providers.map((p) => (
                <label key={p.id} style={{ display: 'grid', gridTemplateColumns: '18px 1fr', gap: 4, alignItems: 'start', cursor: 'pointer' }}>
                  <input type="radio" name="provider" checked={draft.provider === p.id} disabled={!draft.enabled}
                    onChange={() => set({ provider: p.id, model: p.id === draft.provider ? draft.model : (p.models?.[0] || p.default_model) })} />
                  <span>
                    <b>{p.label}</b>{' '}
                    {p.ready ? <span style={{ color: '#15803d' }}>available</span> : <span style={{ color: '#b45309' }}>not available</span>}
                    {!p.ready && p.why && <div style={{ fontSize: 10, color: '#64748b' }}>{p.why}</div>}
                  </span>
                </label>
              ))}
            </div>
            {draft.enabled && draft.provider === 'local' && (
              <div style={row}>
                <span style={{ fontWeight: 600 }}>Server address (OpenAI-compatible)</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input style={{ ...input, flex: 1 }} value={draft.local_base_url || ''} onChange={(e) => set({ local_base_url: e.target.value })} />
                  <button type="button" onClick={recheckLocal} disabled={busy} style={{ ...input, cursor: 'pointer' }}>Check</button>
                </div>
                <span style={{ fontSize: 10, color: '#64748b' }}>
                  Ollama: http://localhost:11434/v1 · LM Studio: http://localhost:1234/v1 · llama-server: http://localhost:8080/v1.
                  For dataset discovery the model must support tool calling.
                </span>
              </div>
            )}
            {draft.enabled && (
              <div style={row}>
                <span style={{ fontWeight: 600 }}>Model</span>
                {chosen?.models?.length ? (
                  <select style={input} value={draft.model || ''} onChange={(e) => set({ model: e.target.value })}>
                    {!chosen.models.includes(draft.model) && <option value={draft.model || ''}>{draft.model || 'choose…'}</option>}
                    {chosen.models.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                ) : (
                  <input style={input} value={draft.model || ''} placeholder={chosen?.default_model || 'model name'} onChange={(e) => set({ model: e.target.value })} />
                )}
              </div>
            )}
            {error && <div style={{ color: '#b91c1c', display: 'flex', gap: 4 }}><AlertCircle size={13} /> {error}</div>}
            {test && (test.ok
              ? <div style={{ color: '#15803d', display: 'flex', gap: 4 }}><CheckCircle2 size={13} /> {test.provider} · {test.model} answered in {test.seconds} s.</div>
              : <div style={{ color: '#b91c1c', display: 'flex', gap: 4 }}><AlertCircle size={13} /> {test.error}</div>)}
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 10, color: '#64748b' }}>
                {status?.settings?.source === 'interface' ? 'Chosen here; ' : 'From backend/.env; '}keys stay in backend/.env.
              </span>
              <span style={{ display: 'flex', gap: 6 }}>
                {draft.enabled && <button type="button" onClick={runTest} disabled={busy} style={{ ...input, cursor: 'pointer' }}>Save and test</button>}
                <button type="button" onClick={async () => { if (await save(draft)) onClose(); }} disabled={busy}
                  style={{ ...input, cursor: 'pointer', background: '#4f46e5', color: '#fff', border: 'none', fontWeight: 600 }}>
                  {busy ? <Loader2 size={12} className="spin" /> : 'Save'}
                </button>
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
