// Analysis nodes (docs/REDESIGN.md, phase 5): Sensitivity sweep, Validate against outcomes, and
// Dasymetric disaggregation. Like the plan nodes, they get their context from the canvas
// (data.context) and report changes and runs through callbacks.
import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Shuffle, Target, Layers3, Play, Loader2, X, AlertCircle } from 'lucide-react';

const shell = (accent, width) => ({
  width, background: '#fff', borderRadius: 8, border: `1px solid ${accent}66`, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
  fontSize: 11, fontFamily: 'Inter, system-ui, sans-serif',
});
const header = (bg, fg) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, padding: '6px 10px',
  background: bg, color: fg, fontWeight: 600, borderBottom: '1px solid #e2e8f0', borderRadius: '8px 8px 0 0',
});
const small = { fontSize: 9, color: '#64748b', fontWeight: 600 };
const input = { width: '100%', boxSizing: 'border-box', fontSize: 10, height: 22, border: '1px solid #cbd5e1', borderRadius: 4, padding: '0 4px', background: '#fff' };
const handle = (color, top) => ({ top, background: color, width: 8, height: 8, border: '2px solid #fff' });

function Header({ id, data, icon, title, bg, fg }) {
  const Icon = icon;
  return (
    <div style={header(bg, fg)}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon size={13} /> {title}</span>
      <button className="nodrag" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'inherit', padding: 2 }}
        title="Remove node" onClick={(e) => { e.stopPropagation(); data?.onDeleteNode?.(id); }}><X size={12} /></button>
    </div>
  );
}

function Errors({ items }) {
  const list = (items || []).filter(Boolean);
  if (!list.length) return null;
  return (
    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', borderRadius: 4, padding: '4px 6px', fontSize: 9 }}>
      {list.map((e, i) => <div key={i} style={{ display: 'flex', gap: 4 }}><AlertCircle size={10} style={{ flexShrink: 0, marginTop: 1 }} />{e}</div>)}
    </div>
  );
}

function RunButton({ ready, running, onClick, color }) {
  return (
    <button className="nodrag" disabled={!ready || running} onClick={onClick}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, height: 26, border: 'none', borderRadius: 6,
        background: ready ? color : '#cbd5e1', color: '#fff', fontWeight: 600, cursor: ready ? 'pointer' : 'not-allowed' }}>
      {running ? <Loader2 size={12} className="spin" /> : <Play size={12} />} Run
    </button>
  );
}

const toggle = (list, value) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

// ---------------------------------------------------------------------------------------------

export const SweepNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const set = (patch) => data.onChange?.(id, patch);
  const resolutions = data.resolutions || [];
  const zoneAlts = data.zoneAlternatives || [];
  const methods = data.methods || [];
  const result = data.lastRun?.result;
  const nVariants = resolutions.length + zoneAlts.length + methods.length;
  const ready = !!ctx.stepId && !!data.column && nVariants > 0;
  return (
    <div style={shell('#db2777', 290)}>
      <Handle type="target" id="step" position={Position.Left} style={handle('#6366f1', 40)} />
      <Header id={id} data={data} icon={Shuffle} title="Sensitivity sweep" bg="#fdf2f8" fg="#9d174d" />
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ fontSize: 9, color: '#64748b' }}>
          {ctx.stepId ? <>Reruns <b>{ctx.stepId}</b> under each alternative and ranks its units ({ctx.targetLabel}).</> : 'Connect a step.'}
        </div>
        <label style={small}>
          Column
          <select className="nodrag" style={input} value={data.column || ''} onChange={(e) => set({ column: e.target.value })}>
            <option value="">Choose…</option>
            {(ctx.columns || []).map((c) => <option key={c.name} value={c.name}>{c.name}{c.kind ? ` (${c.kind})` : ''}</option>)}
          </select>
        </label>
        <div style={small}>Through an H3 grid at resolution</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[7, 8, 9, 10].map((r) => (
            <label key={r} style={{ display: 'flex', gap: 2, alignItems: 'center', fontSize: 10 }}>
              <input type="checkbox" className="nodrag" checked={resolutions.includes(r)} onChange={() => set({ resolutions: toggle(resolutions, r) })} /> {r}
            </label>
          ))}
        </div>
        <label style={small}>
          Through other zones (hold Cmd/Ctrl for several)
          <select multiple className="nodrag nowheel" style={{ ...input, height: 64 }} value={zoneAlts}
            onChange={(e) => set({ zoneAlternatives: [...e.target.selectedOptions].map((o) => o.value) })}>
            {(ctx.zoneDatasets || []).map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select>
        </label>
        <div style={small}>With another matching method</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {(ctx.methodChoices || []).map((m) => (
            <label key={m} style={{ display: 'flex', gap: 2, alignItems: 'center', fontSize: 10 }}>
              <input type="checkbox" className="nodrag" checked={methods.includes(m)} onChange={() => set({ methods: toggle(methods, m) })} /> {m.replace(/_/g, ' ')}
            </label>
          ))}
        </div>
        <label style={small}>
          A unit counts as top when it is in the highest {Math.round((data.topShare ?? 0.2) * 100)}%
          <input type="range" className="nodrag" min={5} max={50} step={5} value={Math.round((data.topShare ?? 0.2) * 100)}
            onChange={(e) => set({ topShare: Number(e.target.value) / 100 })} style={{ width: '100%' }} />
        </label>
        <Errors items={[...(ctx.problems || []), data.lastRun?.error]} />
        <RunButton ready={ready} running={data.lastRun?.running} onClick={() => data.onRun?.(id)} color="#db2777" />
        {result && (
          <div style={{ fontSize: 10, display: 'grid', gap: 3 }}>
            <div><b>{result.always_top}</b> of {result.units} units are in the top under every variant; <b>{result.sometimes_top}</b> only under some.</div>
            {(() => {
              const s = result.agreement.map((a) => a.spearman).filter((v) => v !== null);
              return s.length ? <div>Spearman between variants: {Math.min(...s).toFixed(2)} to {Math.max(...s).toFixed(2)}</div> : null;
            })()}
            {result.variants.filter((v) => !v.ok).map((v) => <div key={v.label} style={{ color: '#b45309' }}>{v.label}: {v.error}</div>)}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={handle('#db2777')} />
    </div>
  );
});

// ---------------------------------------------------------------------------------------------

export const ValidateNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const set = (patch) => data.onChange?.(id, patch);
  const table = data.lastRun?.result?.table;
  const ready = !!ctx.resultId && !!ctx.outcomes && !!data.column;
  return (
    <div style={shell('#0891b2', 300)}>
      <Handle type="target" id="result" position={Position.Left} style={handle('#6366f1', 40)} />
      <Handle type="target" id="outcomes" position={Position.Left} style={handle('#f59e0b', 66)} />
      <Header id={id} data={data} icon={Target} title="Validate against outcomes" bg="#ecfeff" fg="#155e75" />
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr', rowGap: 3, fontSize: 10 }}>
          <span style={small}>Result</span><span style={{ color: ctx.resultId ? '#0f172a' : '#b45309' }}>{ctx.resultId || 'connect a step or Calculate'}</span>
          <span style={small}>Outcomes</span><span style={{ color: ctx.outcomes ? '#0f172a' : '#b45309' }}>{ctx.outcomes || 'connect a dataset of points'}</span>
        </div>
        <label style={small}>
          Rank units by
          <select className="nodrag" style={input} value={data.column || ''} onChange={(e) => set({ column: e.target.value })}>
            <option value="">Choose…</option>
            {(ctx.columns || []).map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
        </label>
        <label style={small}>
          Quantiles
          <input className="nodrag" style={input} value={data.quantiles || '0.5, 0.6, 0.7'} onChange={(e) => set({ quantiles: e.target.value })} />
        </label>
        <Errors items={[...(ctx.problems || []), data.lastRun?.error]} />
        <RunButton ready={ready} running={data.lastRun?.running} onClick={() => data.onRun?.(id)} color="#0891b2" />
        {table && (
          <table style={{ fontSize: 9, borderCollapse: 'collapse', width: '100%' }}>
            <thead><tr style={{ color: '#64748b', textAlign: 'left' }}><th>Quantile</th><th>Coverage</th><th>In top</th><th>Baseline</th><th>Lift</th></tr></thead>
            <tbody>
              {table.map((r) => (
                <tr key={r.quantile} style={{ borderTop: '1px solid #f1f5f9' }}>
                  <td>{r.quantile}</td><td>{r.coverage != null ? `${(r.coverage * 100).toFixed(1)}%` : '—'}</td>
                  <td>{r.n_high}/{r.n_total}</td><td>{r.baseline}</td><td><b>{r.lift ?? '—'}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {table?.some((r) => r.note) && (
          <div style={{ fontSize: 9, color: '#b45309' }}>
            {[...new Set(table.filter((r) => r.note).map((r) => r.note))].join('; ')}. Quantiles with tied values select the same units.
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={handle('#0891b2')} />
    </div>
  );
});

// ---------------------------------------------------------------------------------------------

export const DasymetricNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const set = (patch) => data.onChange?.(id, patch);
  const totals = data.totals || [];
  const weights = data.priorWeights || {};
  const ready = !!ctx.zones && !!ctx.target && (ctx.priors || []).length > 0 && totals.length > 0;
  return (
    <div style={shell('#7c3aed', 290)}>
      <Handle type="target" id="zones" position={Position.Left} style={handle('#7c3aed', 40)} />
      <Handle type="target" id="target" position={Position.Left} style={handle('#0ea5e9', 64)} />
      <Handle type="target" id="prior" position={Position.Left} style={handle('#f59e0b', 88)} />
      <Header id={id} data={data} icon={Layers3} title="Dasymetric disaggregation" bg="#f5f3ff" fg="#5b21b6" />
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ fontSize: 9, color: '#64748b' }}>
          Spreads each zone's total over finer targets in proportion to the prior points, keeping every zone's total.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '50px 1fr', rowGap: 3, fontSize: 10 }}>
          <span style={small}>Zones</span><span style={{ color: ctx.zones ? '#0f172a' : '#b45309' }}>{ctx.zones?.label || 'connect zones with totals'}</span>
          <span style={small}>Target</span><span style={{ color: ctx.target ? '#0f172a' : '#b45309' }}>{ctx.target?.label || 'connect an H3 grid or zones'}</span>
          <span style={small}>Priors</span><span style={{ color: ctx.priors?.length ? '#0f172a' : '#b45309' }}>{ctx.priors?.length ? `${ctx.priors.length} dataset(s)` : 'connect point datasets'}</span>
        </div>
        <label style={small}>
          Totals to spread (hold Cmd/Ctrl for several)
          <select multiple className="nodrag nowheel" style={{ ...input, height: 56 }} value={totals}
            onChange={(e) => set({ totals: [...e.target.selectedOptions].map((o) => o.value) })}>
            {(ctx.zones?.columns || []).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        {(ctx.priors || []).map((p) => (
          <label key={p.nodeId} style={{ ...small, display: 'grid', gridTemplateColumns: '1fr 70px 50px', gap: 4, alignItems: 'center' }}>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={p.label}>{p.label}</span>
            <select className="nodrag" style={{ ...input, height: 20 }} value={weights[p.nodeId]?.column || ''}
              onChange={(e) => set({ priorWeights: { ...weights, [p.nodeId]: { ...weights[p.nodeId], column: e.target.value } } })}>
              <option value="">count</option>
              {p.columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input type="number" className="nodrag" min={0} step="any" style={{ ...input, height: 20 }} title="weight"
              value={weights[p.nodeId]?.weight ?? 1}
              onChange={(e) => set({ priorWeights: { ...weights, [p.nodeId]: { ...weights[p.nodeId], weight: Number(e.target.value) } } })} />
          </label>
        ))}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          <label style={small}>
            Normalize priors
            <select className="nodrag" style={input} value={data.normalize ?? 'share'} onChange={(e) => set({ normalize: e.target.value })}>
              <option value="share">share</option><option value="minmax">min-max</option><option value="none">none</option>
            </select>
          </label>
          <label style={small}>
            Zone without prior
            <select className="nodrag" style={input} value={data.fallback || 'area'} onChange={(e) => set({ fallback: e.target.value })}>
              <option value="area">spread by area</option><option value="none">leave unallocated</option>
            </select>
          </label>
        </div>
        <Errors items={[...(ctx.problems || []), data.lastRun?.error]} />
        <RunButton ready={ready} running={data.lastRun?.running} onClick={() => data.onRun?.(id)} color="#7c3aed" />
      </div>
      <Handle type="source" position={Position.Right} style={handle('#7c3aed')} />
    </div>
  );
});
