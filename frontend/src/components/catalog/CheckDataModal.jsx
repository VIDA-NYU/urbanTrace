// Check a dataset with atlas-clean: issues with proposed fixes; accepted fixes are saved as a recipe
// that is replayed whenever the dataset loads (backend/cleaning.py).
import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Loader2, ShieldCheck } from 'lucide-react';
import { checkDataset, saveRecipe, deleteRecipe } from '../../lib/cleaning';
import LocateFromAddresses from './LocateFromAddresses';

const GEOMETRY_FIXES = new Set(['swap_xy', 'set_crs', 'make_valid']);
const SEVERITY = { error: ['#b91c1c', '#fef2f2'], warning: ['#b45309', '#fffbeb'], info: ['#475569', '#f8fafc'] };
const ACTIONS = {
  swap_xy: 'Swap latitude and longitude', set_crs: 'Declare the coordinate system', make_valid: 'Repair geometry',
  flag_rows: 'Flag rows (adds a column)', set_null: 'Treat as missing',
};

export default function CheckDataModal({ datasetId, name, onClose, onChanged }) {
  const [state, setState] = useState({ loading: true });
  const [accepted, setAccepted] = useState(() => new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    checkDataset(datasetId).then((out) => {
      if (!alive) return;
      setState({ out });
      // Coordinate and geometry fixes for errors start ticked; attribute fixes (placeholders, flags)
      // and everything else are the analyst's call
      const severityOf = Object.fromEntries(out.issues.map((i) => [i.id, i.severity]));
      setAccepted(new Set(out.fixes.filter((f) => severityOf[f.issue_id] === 'error' && GEOMETRY_FIXES.has(f.action)).map((f) => f.id)));
    }).catch((e) => alive && setState({ error: e.message }));
    return () => { alive = false; };
  }, [datasetId]);

  const toggle = (id) => setAccepted((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const save = async () => {
    setSaving(true);
    try { await saveRecipe(datasetId, [...accepted]); onChanged?.(); onClose(); } catch (e) { setState((s) => ({ ...s, error: e.message })); setSaving(false); }
  };
  const remove = async () => {
    setSaving(true);
    try { await deleteRecipe(datasetId); onChanged?.(); onClose(); } catch (e) { setState((s) => ({ ...s, error: e.message })); setSaving(false); }
  };

  const out = state.out;
  const fixesOf = (issueId) => (out?.fixes || []).filter((f) => f.issue_id === issueId);
  return createPortal(
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.35)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: '#fff', borderRadius: 10, padding: 16, width: 600, maxWidth: '95vw', maxHeight: '85vh', overflowY: 'auto', fontSize: 12, color: '#0f172a' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}><ShieldCheck size={15} color="#0f766e" /> Check {name}</b>
          <X size={15} style={{ cursor: 'pointer' }} onClick={onClose} />
        </div>
        <div style={{ color: '#475569', lineHeight: 1.45, marginBottom: 10 }}>
          atlas-clean's spatial checks, against where the catalog's data lies
          {out?.extent ? ` (${out.extent.map((v) => v.toFixed(2)).join(', ')})` : ''}. Accepted fixes are saved for this
          dataset and applied every time it is used: maps, steps, analyses and exports, which say so.
        </div>
        {state.loading && <div><Loader2 size={14} className="spin" /> Checking…</div>}
        {state.error && <div style={{ color: '#b91c1c', marginBottom: 8 }}>{state.error}</div>}
        {out?.recipe && (
          <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 6, padding: 8, marginBottom: 10 }}>
            <b>Corrections saved{out.recipe.saved ? ` on ${out.recipe.saved.slice(0, 10)}` : ''}:</b>
            {(out.recipe.fixes || []).map((f) => <div key={f.id}>{ACTIONS[f.action] || f.action}: {f.rationale}</div>)}
            <div style={{ color: '#475569', marginTop: 4 }}>The check below runs on the file as it is, before these corrections.</div>
          </div>
        )}
        {out && !out.issues.length && <div style={{ color: '#0f766e' }}>No problems found.</div>}
        {out?.issues.map((issue) => {
          const [fg, bg] = SEVERITY[issue.severity] || SEVERITY.info;
          return (
            <div key={issue.id} style={{ border: '1px solid #e2e8f0', borderLeft: `3px solid ${fg}`, borderRadius: 6, padding: 8, marginBottom: 8, background: bg }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span><b style={{ color: fg, textTransform: 'capitalize' }}>{issue.severity}</b> · {issue.message}</span>
                <span style={{ color: '#64748b', whiteSpace: 'nowrap' }}>{issue.affected_rows ? `${issue.affected_rows.toLocaleString()} rows` : ''}</span>
              </div>
              {fixesOf(issue.id).map((f) => (
                <label key={f.id} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', marginTop: 6, cursor: 'pointer' }}>
                  <input type="checkbox" checked={accepted.has(f.id)} onChange={() => toggle(f.id)} />
                  <span><b>{ACTIONS[f.action] || f.action}</b> — {f.rationale}</span>
                </label>
              ))}
            </div>
          );
        })}
        <LocateFromAddresses datasetId={datasetId} onChanged={onChanged} />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
          <span>{out?.recipe && <button disabled={saving} onClick={remove} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #fecaca', background: '#fff', color: '#b91c1c', cursor: 'pointer' }}>Remove saved corrections</button>}</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer' }}>Cancel</button>
            <button disabled={saving || !accepted.size} onClick={save}
              style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: accepted.size ? '#0f766e' : '#94a3b8', color: '#fff', cursor: accepted.size ? 'pointer' : 'default' }}>
              {saving ? 'Saving…' : `Apply ${accepted.size} fix${accepted.size === 1 ? '' : 'es'}`}
            </button>
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
