// Plan nodes (docs/REDESIGN.md, phase 4): H3 Grid (a target), Step (match + aggregate), Calculate
// (derived variables). The canvas gives each node its context (what is connected, value kinds,
// validation problems) in data.context and handles changes and runs through callbacks.
import React, { memo, useEffect, useRef, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Hexagon, Route, Download, Workflow, Calculator, Play, Loader2, X, Plus, Trash2, AlertCircle, Filter, Sparkles } from 'lucide-react';
import { getHexagonEdgeLengthAvg } from 'h3-js';
import OperatorSelect, { ParamForm } from '../../methods/OperatorSelect';
import ReportCard from '../../methods/ReportCard';
import { KINDS, KIND_COLORS, KEY_REDUCTIONS, keyReductionName, RASTER_REDUCTIONS } from '../../../lib/plans';
import { networkStatus, downloadNetwork } from '../../../lib/osm';

const shell = (accent, width) => ({
  width, background: '#fff', borderRadius: 8, border: `1px solid ${accent}55`, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
  fontSize: 11, fontFamily: 'Inter, system-ui, sans-serif', overflow: 'visible', color: '#0f172a',
});
const header = (bg, fg) => ({
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, padding: '6px 10px',
  background: bg, color: fg, fontWeight: 600, borderBottom: '1px solid #e2e8f0', borderRadius: '8px 8px 0 0',
});
const small = { fontSize: 9, color: '#64748b', fontWeight: 600 };
const input = { width: '100%', boxSizing: 'border-box', fontSize: 10, height: 22, border: '1px solid #cbd5e1', borderRadius: 4, padding: '0 4px', background: '#fff', color: '#0f172a' };
const iconBtn = { border: 'none', background: 'transparent', cursor: 'pointer', padding: 2, display: 'inline-flex', color: 'inherit' };

function DeleteButton({ id, data }) {
  return (
    <button className="nodrag" style={iconBtn} title="Remove node" onClick={(e) => { e.stopPropagation(); data?.onDeleteNode?.(id); }}>
      <X size={12} />
    </button>
  );
}

function Problems({ problems }) {
  if (!problems?.length) return null;
  return (
    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', borderRadius: 4, padding: '4px 6px', fontSize: 9, display: 'grid', gap: 2 }}>
      {problems.map((p, i) => <div key={i} style={{ display: 'flex', gap: 4 }}><AlertCircle size={10} style={{ flexShrink: 0, marginTop: 1 }} />{p}</div>)}
    </div>
  );
}

export function KindChip({ kind, onChange, disabled }) {
  const next = KINDS[(KINDS.indexOf(kind) + 1) % KINDS.length];
  return (
    <button type="button" className="nodrag" disabled={disabled || !onChange}
      title={kind ? `${kind} value: click to change` : 'value kind unknown: click to set'}
      onClick={(e) => { e.stopPropagation(); onChange?.(kind ? next : 'extensive'); }}
      style={{
        minWidth: 18, height: 18, borderRadius: 9, border: `1.5px solid ${KIND_COLORS[kind] || '#cbd5e1'}`,
        color: KIND_COLORS[kind] || '#94a3b8', background: '#fff', fontSize: 9, fontWeight: 700, cursor: onChange ? 'pointer' : 'default', padding: 0,
      }}>
      {kind ? kind[0].toUpperCase() : '?'}
    </button>
  );
}

// ---------------------------------------------------------------------------------------------

export const GridNode = memo(({ id, data }) => {
  const res = Number(data.resolution || 9);
  const edgeKm = getHexagonEdgeLengthAvg(res, 'km');
  return (
    <div style={shell('#0ea5e9', 190)}>
      <div style={header('#f0f9ff', '#0369a1')}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Hexagon size={13} /> H3 grid</span>
        <DeleteButton id={id} data={data} />
      </div>
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <label style={small}>
          Resolution
          <select className="nodrag" style={input} value={res} onChange={(e) => data.onChange?.(id, { resolution: Number(e.target.value) })}>
            {[5, 6, 7, 8, 9, 10, 11].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <div style={{ fontSize: 9, color: '#64748b' }}>
          Cells about {edgeKm < 1 ? `${Math.round(edgeKm * 1000)} m` : `${edgeKm.toFixed(1)} km`} across an edge
          ({(2.598 * edgeKm * edgeKm).toFixed(edgeKm < 1 ? 2 : 1)} km²). The grid covers the study area, or the sources it receives.
        </div>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#0ea5e9', width: 8, height: 8, border: '2px solid #fff' }} />
    </div>
  );
});

// ---------------------------------------------------------------------------------------------

// A street network target (backend/osm.py): the study area's street segments or intersections from
// OpenStreetMap, downloaded once per area and network type and kept for later runs.
// Seconds since a download started, stamped when its status arrives
const withElapsed = (s) => ({ ...s, elapsed: s?.job?.started ? Math.round(Date.now() / 1000 - s.job.started) : 0 });
const NETWORKS = [['drive', 'Drivable streets'], ['walk', 'Walkable paths'], ['bike', 'Bikeable'], ['all', 'All ways']];

export const StreetsNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const network = data.network || 'drive';
  const kind = data.kind || 'osm_streets';
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const areaKey = JSON.stringify(ctx.studyArea || null);

  useEffect(() => {
    let alive = true;
    clearTimeout(timer.current);
    if (!ctx.studyArea) return undefined;          // nothing to look up; the node says to choose one
    const look = async () => {
      try {
        const s = await networkStatus(ctx.studyArea, network);
        if (!alive) return;
        setStatus(withElapsed(s));
        setError(null);
        if (s.job?.state === 'running') timer.current = setTimeout(look, 2000);
        else if (s.job?.state === 'failed') setError(s.job.error);
      } catch (e) { if (alive) setError(e.message); }
    };
    look();
    return () => { alive = false; clearTimeout(timer.current); };
  }, [areaKey, network]); // eslint-disable-line react-hooks/exhaustive-deps

  const download = async () => {
    setError(null);
    try {
      const { job } = await downloadNetwork(ctx.studyArea, network);
      setStatus((s) => ({ ...(s || {}), job }));
      const poll = async () => {
        const s = await networkStatus(ctx.studyArea, network);
        setStatus(withElapsed(s));
        if (s.job?.state === 'running') timer.current = setTimeout(poll, 2000);
        else if (s.job?.state === 'failed') setError(s.job.error);
      };
      timer.current = setTimeout(poll, 2000);
    } catch (e) { setError(e.message); }
  };

  const running = status?.job?.state === 'running';
  const elapsed = status?.elapsed || 0;
  return (
    <div style={shell('#0ea5e9', 220)}>
      <div style={header('#f0f9ff', '#0369a1')}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Route size={13} /> Streets (OSM)</span>
        <DeleteButton id={id} data={data} />
      </div>
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ display: 'flex', border: '1px solid #bae6fd', borderRadius: 6, overflow: 'hidden', fontSize: 10 }}>
          {[['osm_streets', 'Segments'], ['osm_intersections', 'Intersections']].map(([k, label]) => (
            <button key={k} type="button" className="nodrag" onClick={() => data.onChange?.(id, { kind: k })}
              style={{ flex: 1, border: 'none', padding: '3px 0', cursor: 'pointer', fontWeight: 600,
                background: kind === k ? '#0284c7' : '#fff', color: kind === k ? '#fff' : '#0369a1' }}>{label}</button>
          ))}
        </div>
        <label style={small}>
          Network
          <select className="nodrag" style={input} value={network} onChange={(e) => data.onChange?.(id, { network: e.target.value })}>
            {NETWORKS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
        {!ctx.studyArea && <div style={{ fontSize: 9, color: '#b45309' }}>Choose a study area: the street network is downloaded for it.</div>}
        {ctx.studyArea && status && !running && (status.downloaded
          ? <div style={{ fontSize: 9, color: '#0f766e' }}>
              Downloaded {String(status.downloaded_at || '').slice(0, 10)}: {(status.edges || 0).toLocaleString()} edges, {(status.nodes || 0).toLocaleString()} nodes ({status.km2} km²).
            </div>
          : <div style={{ fontSize: 9, color: '#475569' }}>
              Not downloaded yet ({status.km2} km²). Downloads from OpenStreetMap can take a few minutes for a borough.
            </div>)}
        {running && <div style={{ fontSize: 9, color: '#0369a1', display: 'flex', gap: 4, alignItems: 'center' }}><Loader2 size={10} className="spin" /> Downloading from OpenStreetMap… {elapsed}s</div>}
        {ctx.studyArea && status && !running && (
          <button className="nodrag" onClick={download} disabled={status.km2 > (status.max_km2 || Infinity)}
            title={status.downloaded ? 'Download the network again (OpenStreetMap changes)' : "Download the study area's street network"}
            style={{ ...iconBtn, justifySelf: 'start', gap: 4, fontSize: 10, color: '#0369a1', border: '1px solid #bae6fd', background: '#f0f9ff', padding: '3px 8px', borderRadius: 6 }}>
            <Download size={11} /> {status.downloaded ? 'Download again' : 'Download'}
          </button>
        )}
        {error && <Problems problems={[error]} />}
        <div style={{ fontSize: 8, color: '#94a3b8' }}>© OpenStreetMap contributors (ODbL)</div>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#0ea5e9', width: 8, height: 8, border: '2px solid #fff' }} />
    </div>
  );
});

// ---------------------------------------------------------------------------------------------

const WHERE_OPS = ['==', '!=', '<', '<=', '>', '>=', 'isnull', 'notnull'];

function ReductionRow({ r, ctx, method, onPatch, onRemove, onKind }) {
  const columns = ctx.source?.columns || [];
  const col = columns.find((c) => c.name === r.column);
  const kind = col?.kind || null;
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 6, display: 'grid', gap: 4, background: '#f8fafc' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 4, alignItems: 'end' }}>
        <OperatorSelect kind="reduction" value={r.method} compact method={method} valueKind={kind}
          column={r.column || ''} onChange={(m) => onPatch({ method: m, as: r.asEdited ? r.as : [m, r.column].filter(Boolean).join('_') })} />
        <select className="nodrag" style={{ ...input, height: 20, marginTop: 4 }} value={r.column || ''}
          onChange={(e) => onPatch({ column: e.target.value, as: r.asEdited ? r.as : [r.method, e.target.value].filter(Boolean).join('_') })}>
          <option value="">(no column)</option>
          {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
        <div style={{ display: 'flex', gap: 2, alignItems: 'center', paddingBottom: 1 }}>
          {r.column && <KindChip kind={kind} onChange={ctx.source?.datasetNodeId ? (k) => onKind(r.column, k) : null} />}
          <button className="nodrag" style={{ ...iconBtn, color: '#94a3b8' }} title="Remove" onClick={onRemove}><Trash2 size={11} /></button>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 4, alignItems: 'center' }}>
        <input className="nodrag" style={{ ...input, height: 20 }} value={r.as || ''} placeholder="output name"
          title="Output column name" onChange={(e) => onPatch({ as: e.target.value.replace(/[^A-Za-z0-9_]/g, '_'), asEdited: true })} />
        {['count', 'weighted_count', 'sum'].includes(r.method) && (
          <label style={{ ...small, display: 'flex', gap: 2, alignItems: 'center' }} title="Targets with no match get 0 instead of missing">
            <input type="checkbox" className="nodrag" checked={!!r.fillEmpty} onChange={(e) => onPatch({ fillEmpty: e.target.checked })} /> 0 if none
          </label>
        )}
        <button className="nodrag" style={{ ...iconBtn, color: r.where ? '#2563eb' : '#94a3b8' }} title="Only matches where…"
          onClick={() => onPatch({ where: r.where ? null : { column: columns[0]?.name || '', op: '==', value: '' } })}>
          <Filter size={11} />
        </button>
      </div>
      {r.where && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 54px 1fr', gap: 4 }}>
          <select className="nodrag" style={{ ...input, height: 20 }} value={r.where.column} onChange={(e) => onPatch({ where: { ...r.where, column: e.target.value } })}>
            {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
          </select>
          <select className="nodrag" style={{ ...input, height: 20 }} value={r.where.op} onChange={(e) => onPatch({ where: { ...r.where, op: e.target.value } })}>
            {WHERE_OPS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          {!['isnull', 'notnull'].includes(r.where.op) && (
            <input className="nodrag" style={{ ...input, height: 20 }} value={r.where.value} placeholder="value"
              onChange={(e) => onPatch({ where: { ...r.where, value: e.target.value } })} />
          )}
        </div>
      )}
    </div>
  );
}

// One summary of a raster under each zone or cell (zonal statistics)
const RASTER_LABELS = { weighted_mean: 'mean, by area covered', mean: 'mean of cells', sum: 'sum, by area covered', min: 'min', max: 'max',
  count: 'number of cells', majority: 'most common value', shares: 'share of each value' };
function RasterReductionRow({ r, band, onPatch, onRemove }) {
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 6, display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 4, background: '#f8fafc', alignItems: 'center' }}>
      <select className="nodrag" style={{ ...input, height: 20 }} value={r.method}
        onChange={(e) => onPatch({ method: e.target.value, column: band, as: r.asEdited ? r.as : `${e.target.value}_${band}` })}>
        {RASTER_REDUCTIONS.map((m) => <option key={m} value={m}>{RASTER_LABELS[m] || m}</option>)}
      </select>
      <input className="nodrag" style={{ ...input, height: 20 }} value={r.as || ''} placeholder={`${r.method}_${band}`} title="Output column name"
        onChange={(e) => onPatch({ as: e.target.value.replace(/[^A-Za-z0-9_]/g, '_'), asEdited: true })} />
      <button className="nodrag" style={{ ...iconBtn, color: '#94a3b8' }} title="Remove" onClick={onRemove}><Trash2 size={11} /></button>
    </div>
  );
}

// One reduction of a join on a key: a sum of a column, or a ratio of two sums.
function KeyReductionRow({ r, columns, onPatch, onRemove }) {
  const colSelect = (field, placeholder) => (
    <select className="nodrag" style={{ ...input, height: 20 }} value={r[field] || ''} title={placeholder}
      onChange={(e) => onPatch({ [field]: e.target.value })}>
      <option value="">{placeholder}</option>
      {columns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
    </select>
  );
  return (
    <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 6, display: 'grid', gap: 4, background: '#f8fafc' }}>
      <div style={{ display: 'grid', gridTemplateColumns: r.method === 'ratio_of_sums' ? '86px 1fr 1fr auto' : '86px 1fr auto', gap: 4, alignItems: 'center' }}>
        <select className="nodrag" style={{ ...input, height: 20 }} value={r.method}
          onChange={(e) => onPatch({ method: e.target.value })}
          title={r.method === 'ratio_of_sums' ? 'Per zone: the sum of one column over the sum of another (a rate)' : 'Per zone: the sum of a column over the rows with its key'}>
          {KEY_REDUCTIONS.map((m) => <option key={m} value={m}>{m === 'ratio_of_sums' ? 'ratio of sums' : m}</option>)}
        </select>
        {r.method === 'ratio_of_sums' ? <>{colSelect('numerator', 'numerator')}{colSelect('denominator', 'denominator')}</> : colSelect('column', 'column')}
        <button className="nodrag" style={{ ...iconBtn, color: '#94a3b8' }} title="Remove" onClick={onRemove}><Trash2 size={11} /></button>
      </div>
      <input className="nodrag" style={{ ...input, height: 20 }} value={r.as || ''} placeholder={keyReductionName({ ...r, as: '' })}
        title="Output column name" onChange={(e) => onPatch({ as: e.target.value.replace(/[^A-Za-z0-9_]/g, '_') })} />
    </div>
  );
}

const KEY_HINT = /^(bbl|bin|zip|zipcode|zip_code|postcode|postal_code|modzcta|zcta|geoid|boro_?cd|community_?district|nta_?code|ntacode|nta2020|census_?tract|ct2020|boroct2020)$/i;

// Why the copilot suggested this method and these reductions, and what urbanweave's registry changed.
function SuggestionNote({ suggestion, onDismiss }) {
  if (!suggestion || suggestion.loading) return null;
  if (suggestion.error) return <div style={{ fontSize: 10, color: '#b91c1c' }}>{suggestion.error}</div>;
  return (
    <div className="nodrag nowheel" style={{ fontSize: 10, color: '#4c1d95', background: '#f5f3ff', border: '1px solid #ddd6fe', borderRadius: 6, padding: '5px 7px', lineHeight: 1.4, maxHeight: 140, overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginBottom: 2 }}>
        <span>{suggestion.engine === 'llm' ? 'Copilot suggestion' : 'Suggested by rules (no LLM configured)'}</span>
        <X size={11} style={{ cursor: 'pointer' }} onClick={onDismiss} />
      </div>
      <div>{suggestion.reasoning}</div>
      {(suggestion.notes || []).map((n) => <div key={n} style={{ color: '#b45309', marginTop: 2 }}>Registry check: {n}</div>)}
    </div>
  );
}

export const StepNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const method = data.method || 'contain';
  const reductions = data.reductions || [];
  const set = (patch) => data.onChange?.(id, patch);
  const patchReduction = (i, patch) => set({ reductions: reductions.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const rasterMode = ctx.source?.geometry === 'Raster';
  const band = ctx.source?.columns?.[0]?.name || 'band_1';
  const keyMode = !rasterMode && data.mode === 'key';
  const keyReady = keyMode && data.keyBy && data.keyIdColumn
    && reductions.some((r) => (r.method === 'ratio_of_sums' ? r.numerator && r.denominator : r.method === 'sum' && r.column));
  const ready = ctx.source && ctx.target && (keyMode ? keyReady : rasterMode ? reductions.some((r) => RASTER_REDUCTIONS.includes(r.method)) : reductions.some((r) => r.method));
  // A raster source starts with the usual summary of a percentage or rate: its mean, by area covered
  const defaultCount = reductions.length === 1 && reductions[0].method === 'count' && !reductions[0].column && !reductions[0].asEdited;
  useEffect(() => {
    if (rasterMode && defaultCount) set({ reductions: [{ method: 'weighted_mean', column: band, as: `weighted_mean_${band}` }] });
  }, [rasterMode, defaultCount, band]); // eslint-disable-line react-hooks/exhaustive-deps
  const sourceColumns = ctx.source?.columns || [];
  const targetColumns = ctx.target?.columns || [];
  // Switching modes starts the reductions afresh: the two modes offer different ones. A key column
  // with a familiar name (zipcode, bbl, ...) is chosen for the analyst.
  const setMode = (mode) => {
    if (mode === (data.mode || 'location')) return;
    if (mode === 'key') {
      const guess = (cols) => cols.find((c) => KEY_HINT.test(c)) || '';
      set({ mode, keyBy: data.keyBy || guess(sourceColumns.map((c) => c.name)), keyIdColumn: data.keyIdColumn || guess(targetColumns),
        reductions: [{ method: 'sum', column: '', as: '' }], suggestion: null });
    } else {
      set({ mode: 'location', reductions: [{ method: 'count', column: '', as: 'count', fillEmpty: true }] });
    }
  };
  return (
    <div style={shell('#6366f1', 300)}>
      <Handle type="target" id="source" position={Position.Left} style={{ top: 46, background: '#6366f1', width: 8, height: 8, border: '2px solid #fff' }} />
      <Handle type="target" id="target" position={Position.Left} style={{ top: 72, background: '#0ea5e9', width: 8, height: 8, border: '2px solid #fff' }} />
      <div style={header('#eef2ff', '#4338ca')}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Workflow size={13} />
          <input className="nodrag" value={data.stepId || ''} onChange={(e) => set({ stepId: e.target.value.replace(/[^A-Za-z0-9_]/g, '_') })}
            title="Step id (used in the plan)" style={{ border: 'none', background: 'transparent', fontWeight: 600, color: '#4338ca', width: 150, fontSize: 11 }} />
        </span>
        <DeleteButton id={id} data={data} />
      </div>
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '52px 1fr', rowGap: 4, fontSize: 10 }}>
          <span style={small}>Source</span>
          <span style={{ color: ctx.source ? '#0f172a' : '#b45309', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ctx.source ? `${ctx.source.label} · ${ctx.source.geometry || ''}` : 'connect a dataset or step'}
          </span>
          <span style={small}>Target</span>
          <span style={{ color: ctx.target ? '#0f172a' : '#b45309', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ctx.target ? ctx.target.label : 'connect zones or an H3 grid'}
          </span>
        </div>
        {rasterMode ? (
          <div style={{ fontSize: 9, color: '#475569', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, padding: '4px 6px', lineHeight: 1.4 }}>
            <b style={{ color: '#166534' }}>Zonal statistics.</b> The raster&apos;s cells under each zone or H3 cell, each weighted by the share of it
            inside (exact coverage). Targets: zones or an H3 grid.
          </div>
        ) : (<>
        <div style={{ display: 'flex', border: '1px solid #c7d2fe', borderRadius: 6, overflow: 'hidden', fontSize: 10 }}>
          {[['location', 'Match by location'], ['key', 'Join on a key']].map(([m, label]) => (
            <button key={m} type="button" className="nodrag" onClick={() => setMode(m)}
              title={m === 'key' ? 'Rows carry a code (ZIP, BBL, district, ...) that identifies the zone: sum them onto the zone with that code' : 'Match features to zones or cells by where they are'}
              style={{ flex: 1, border: 'none', padding: '3px 0', cursor: 'pointer', fontWeight: 600,
                background: (data.mode || 'location') === m ? '#4f46e5' : '#fff', color: (data.mode || 'location') === m ? '#fff' : '#4338ca' }}>
              {label}
            </button>
          ))}
        </div>
        {keyMode ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              <label style={small}>
                Key in the source
                <select className="nodrag" style={input} value={data.keyBy || ''} onChange={(e) => set({ keyBy: e.target.value })}>
                  <option value="">choose…</option>
                  {sourceColumns.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
                </select>
              </label>
              <label style={small}>
                Same key in the zones
                <select className="nodrag" style={input} value={data.keyIdColumn || ''} onChange={(e) => set({ keyIdColumn: e.target.value })}
                  disabled={ctx.target?.kind !== 'zones'}>
                  <option value="">{ctx.target?.kind === 'zones' ? 'choose…' : 'connect zones'}</option>
                  {targetColumns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>
            <div style={{ fontSize: 9, color: '#64748b' }}>
              Rows go to the zone whose key matches, wherever they are on the map; keys are compared as text (11211 = "11211"). Rows whose key matches no zone are reported.
            </div>
          </>
        ) : (<>
        <button className="nodrag" disabled={!ctx.source || ctx.source.isStep || !ctx.target || data.suggestion?.loading}
          onClick={() => data.onSuggest?.(id)}
          title={ctx.source?.isStep ? 'Suggestions need a dataset as source' : "Suggest a method and reductions for this step and the collection's goal"}
          style={{ ...iconBtn, justifySelf: 'start', color: '#7c3aed', border: '1px solid #ddd6fe', background: '#f5f3ff', padding: '3px 8px', borderRadius: 6, fontSize: 10, gap: 4,
            opacity: !ctx.source || ctx.source.isStep || !ctx.target ? 0.5 : 1 }}>
          {data.suggestion?.loading ? <Loader2 size={11} className="spin" /> : <Sparkles size={11} />} Suggest
        </button>
        <SuggestionNote suggestion={data.suggestion} onDismiss={() => set({ suggestion: null })} />
        <label style={small}>
          Matching
          <OperatorSelect kind="matching" value={method} onChange={(m) => set({ method: m, params: {} })}
            sourceGeometry={ctx.source?.geometry} targetKind={ctx.target?.kind} targetGeometry={ctx.target?.geometry} />
        </label>
        <ParamForm method={method} values={data.params || {}} onChange={(params) => set({ params })} />
        </>)}
        </>)}
        <div style={{ ...small, display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
          Aggregate
          <button className="nodrag" style={{ ...iconBtn, color: '#4338ca', fontSize: 9, gap: 2 }}
            onClick={() => set({ reductions: [...reductions, rasterMode ? { method: 'max', column: band, as: `max_${band}` } : keyMode ? { method: 'sum', column: '', as: '' } : { method: 'count', column: '', as: 'count', fillEmpty: true }] })}>
            <Plus size={11} /> add
          </button>
        </div>
        {rasterMode && reductions.map((r, i) => (
          <RasterReductionRow key={i} r={r} band={band}
            onPatch={(patch) => patchReduction(i, patch)}
            onRemove={() => set({ reductions: reductions.filter((_, j) => j !== i) })} />
        ))}
        {keyMode && reductions.map((r, i) => (
          <KeyReductionRow key={i} r={r} columns={sourceColumns}
            onPatch={(patch) => patchReduction(i, patch)}
            onRemove={() => set({ reductions: reductions.filter((_, j) => j !== i) })} />
        ))}
        {!keyMode && !rasterMode && reductions.map((r, i) => (
          <ReductionRow key={i} r={r} ctx={ctx} method={method}
            onPatch={(patch) => patchReduction(i, patch)}
            onRemove={() => set({ reductions: reductions.filter((_, j) => j !== i) })}
            onKind={(column, kind) => data.onValueKindChange?.(ctx.source.datasetNodeId, column, kind)} />
        ))}
        <Problems problems={ctx.problems} />
        {data.lastRun?.error && <Problems problems={[data.lastRun.error]} />}
        <button className="nodrag" disabled={!ready || data.lastRun?.running} onClick={() => data.onRun?.(id)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, height: 26, border: 'none', borderRadius: 6,
            background: ready ? '#4f46e5' : '#cbd5e1', color: '#fff', fontWeight: 600, cursor: ready ? 'pointer' : 'not-allowed' }}>
          {data.lastRun?.running ? <Loader2 size={12} className="spin" /> : <Play size={12} />} Run step
        </button>
        {data.lastRun?.reports && <ReportCard reports={data.lastRun.reports} />}
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#6366f1', width: 8, height: 8, border: '2px solid #fff' }} />
    </div>
  );
});

// ---------------------------------------------------------------------------------------------

export const CalculateNode = memo(({ id, data }) => {
  const ctx = data.context || {};
  const set = (patch) => data.onChange?.(id, patch);
  const columns = (ctx.inputs || []).flatMap((i) => i.columns.map((c) => ({ ...c, step: i.stepId })));
  const ready = (ctx.inputs || []).length > 0;
  return (
    <div style={shell('#059669', 280)}>
      <Handle type="target" id="inputs" position={Position.Left} style={{ background: '#059669', width: 8, height: 8, border: '2px solid #fff' }} />
      <div style={header('#ecfdf5', '#047857')}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Calculator size={13} /> Combine & calculate</span>
        <DeleteButton id={id} data={data} />
      </div>
      <div style={{ padding: 10, display: 'grid', gap: 6 }}>
        <div style={{ fontSize: 9, color: '#64748b' }}>
          Joins the outputs of the steps connected here (they must share a target) and, optionally, adds a column computed from them.
        </div>
        {columns.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {columns.map((c) => (
              <button key={`${c.step}.${c.name}`} type="button" className="nodrag" title={`${c.step}: click to insert`}
                onClick={() => set({ expression: `${data.expression || ''}${data.expression ? ' ' : ''}${c.name}` })}
                style={{ display: 'flex', gap: 3, alignItems: 'center', fontSize: 9, border: '1px solid #e2e8f0', borderRadius: 10, padding: '1px 6px', background: '#fff', cursor: 'pointer' }}>
                <KindChip kind={c.kind} disabled /> {c.name}
              </button>
            ))}
          </div>
        )}
        <label style={small}>
          Expression (optional)
          <input className="nodrag" style={input} value={data.expression || ''} placeholder="e.g. crashes / population * 1000"
            onChange={(e) => set({ expression: e.target.value })} />
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px', gap: 6 }}>
          <label style={small}>
            Output name
            <input className="nodrag" style={input} value={data.as || ''} placeholder="derived"
              onChange={(e) => set({ as: e.target.value.replace(/[^A-Za-z0-9_]/g, '_') })} />
          </label>
          <label style={small}>
            Value kind
            <select className="nodrag" style={input} value={data.kind || 'intensive'} onChange={(e) => set({ kind: e.target.value })}>
              {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </label>
        </div>
        <Problems problems={ctx.problems} />
        {data.lastRun?.error && <Problems problems={[data.lastRun.error]} />}
        <button className="nodrag" disabled={!ready || data.lastRun?.running} onClick={() => data.onRun?.(id)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, height: 26, border: 'none', borderRadius: 6,
            background: ready ? '#059669' : '#cbd5e1', color: '#fff', fontWeight: 600, cursor: ready ? 'pointer' : 'not-allowed' }}>
          {data.lastRun?.running ? <Loader2 size={12} className="spin" /> : <Play size={12} />} Run
        </button>
      </div>
      <Handle type="source" position={Position.Right} style={{ background: '#059669', width: 8, height: 8, border: '2px solid #fff' }} />
    </div>
  );
});
