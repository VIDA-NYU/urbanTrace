// Study area picker, coverage view and warnings for the collection bar (docs/REDESIGN.md, phase 2).
import React, { useEffect, useMemo, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import { geoMercator, geoPath } from 'd3-geo';
import { getStudyAreaOptions, resolveStudyArea, getCoverage } from '../../lib/scope';
import { rewindForD3 } from '../../lib/geo';

const panelStyle = {
  position: 'absolute', top: 'calc(100% + 6px)', left: 0, width: 400, background: '#fff', border: '1px solid #cbd5e1',
  borderRadius: 8, boxShadow: '0 8px 20px rgba(0,0,0,0.12)', padding: 12, zIndex: 120, fontSize: 12,
};
const label = { display: 'block', fontWeight: 600, margin: '8px 0 4px', color: '#334155' };
const input = { width: '100%', boxSizing: 'border-box', padding: '5px 6px', border: '1px solid #cbd5e1', borderRadius: 6, fontSize: 12 };

function Header({ title, onClose }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontWeight: 700 }}>
      {title} <X size={14} style={{ cursor: 'pointer' }} onClick={onClose} />
    </div>
  );
}

export function StudyAreaPanel({ value, zoneDatasets, onApply, onClose }) {
  const [kind, setKind] = useState(value?.kind || 'zones');
  const [dataset, setDataset] = useState(value?.dataset || '');
  const [column, setColumn] = useState(value?.column || '');
  const [values, setValues] = useState(value?.values || []);
  const [bbox, setBbox] = useState((value?.bbox || ['', '', '', '']).map(String));
  const [name, setName] = useState(value?.name || '');
  // Results are kept with the request they answer, so a stale one is never shown.
  const [loadedOptions, setLoadedOptions] = useState({ key: null, value: null, error: '' });
  const [resolved, setResolved] = useState({ key: null, value: null, error: '' });

  useEffect(() => {
    if (kind !== 'zones' || !dataset) return undefined;
    let alive = true;
    getStudyAreaOptions(dataset)
      .then((value) => alive && setLoadedOptions({ key: dataset, value, error: '' }))
      .catch((e) => alive && setLoadedOptions({ key: dataset, value: null, error: e.message }));
    return () => { alive = false; };
  }, [kind, dataset]);
  const options = kind === 'zones' && loadedOptions.key === dataset ? loadedOptions.value : null;

  const spec = useMemo(() => {
    if (kind === 'bbox') {
      const nums = bbox.map(Number);
      return nums.every((n) => Number.isFinite(n)) && bbox.every((v) => v !== '') ? { kind, bbox: nums, name: name || 'Box' } : null;
    }
    if (!dataset) return null;
    return { kind, dataset, ...(column ? { column, values } : {}), name: name || (values.length ? values.join(', ') : dataset) };
  }, [kind, dataset, column, values, bbox, name]);

  const specKey = spec ? JSON.stringify(spec) : null;
  useEffect(() => {
    if (!specKey) return undefined;
    const t = setTimeout(() => {
      resolveStudyArea(JSON.parse(specKey))
        .then((value) => setResolved({ key: specKey, value, error: '' }))
        .catch((e) => setResolved({ key: specKey, value: null, error: e.message }));
    }, 300);
    return () => clearTimeout(t);
  }, [specKey]);
  const summary = resolved.key === specKey ? resolved.value : null;
  const error = (resolved.key === specKey && resolved.error)
    || (kind === 'zones' && loadedOptions.key === dataset && loadedOptions.error) || '';

  const columnValues = options?.columns.find((c) => c.name === column)?.values || [];
  return (
    <div style={panelStyle}>
      <Header title="Study area" onClose={onClose} />
      <div style={{ color: '#475569', lineHeight: 1.4 }}>
        Integrations are limited to this area, search can filter to datasets that reach it, and exports are clipped to it.
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        {[['zones', 'Zones from a dataset'], ['bbox', 'A box']].map(([k, l]) => (
          <label key={k} style={{ display: 'flex', gap: 4, cursor: 'pointer' }}>
            <input type="radio" checked={kind === k} onChange={() => setKind(k)} /> {l}
          </label>
        ))}
      </div>
      {kind === 'zones' ? (
        <>
          <span style={label}>Zones dataset</span>
          <select style={input} value={dataset} onChange={(e) => { setDataset(e.target.value); setColumn(''); setValues([]); }}>
            <option value="">Choose a polygon dataset…</option>
            {zoneDatasets.map((d) => <option key={d.id} value={d.id}>{d.name || d.id}</option>)}
          </select>
          {dataset && !options && !error && <div style={{ marginTop: 6 }}><Loader2 size={12} /> reading zones…</div>}
          {options && (
            <>
              <span style={label}>Keep only zones where (optional)</span>
              <select style={input} value={column} onChange={(e) => { setColumn(e.target.value); setValues([]); }}>
                <option value="">All {options.features} zones</option>
                {options.columns.map((c) => <option key={c.name} value={c.name}>{c.name} ({c.values.length} values)</option>)}
              </select>
              {column && (
                <select multiple style={{ ...input, height: 110, marginTop: 6 }} value={values}
                  onChange={(e) => setValues([...e.target.selectedOptions].map((o) => o.value))}>
                  {columnValues.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <span style={label}>Bounding box (longitude and latitude, EPSG:4326)</span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {['min longitude', 'min latitude', 'max longitude', 'max latitude'].map((p, i) => (
              <input key={p} style={input} placeholder={p} value={bbox[i]}
                onChange={(e) => setBbox((b) => b.map((v, j) => (j === i ? e.target.value : v)))} />
            ))}
          </div>
        </>
      )}
      <span style={label}>Name</span>
      <input style={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Manhattan" />
      <div style={{ marginTop: 8, minHeight: 16, color: error ? '#b91c1c' : '#475569' }}>
        {error || (summary ? `${summary.area_km2.toLocaleString()} km²` : '')}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8, justifyContent: 'flex-end' }}>
        {value && <button onClick={() => onApply(null)} style={{ ...input, width: 'auto', cursor: 'pointer' }}>Remove study area</button>}
        <button disabled={!spec || !summary} onClick={() => onApply(spec)}
          style={{ ...input, width: 'auto', cursor: 'pointer', background: spec && summary ? '#2563eb' : '#cbd5e1', color: '#fff', border: 'none' }}>
          Apply
        </button>
      </div>
    </div>
  );
}

const COVER_COLORS = ['#e2e8f0', '#bfdbfe', '#60a5fa', '#2563eb', '#1e3a8a'];

export function CoverageModal({ datasets, studyArea, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!datasets.length) return;
    getCoverage(datasets, studyArea).then(setData).catch((e) => setError(e.message));
  }, [datasets, studyArea]);
  const width = 560;
  const height = 420;
  const paths = useMemo(() => {
    if (!data) return null;
    const fc = { type: 'FeatureCollection', features: [...data.features] };
    if (data.study_area) fc.features.push({ type: 'Feature', geometry: data.study_area.geometry, properties: { area: true } });
    if (!fc.features.length) return [];
    fc.features = fc.features.map(rewindForD3);
    const projection = geoMercator().fitSize([width, height], fc);
    const path = geoPath(projection);
    return fc.features.map((f, i) => ({ d: path(f), f, key: i }));
  }, [data]);
  const max = Math.max(1, datasets.length);
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.35)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ background: '#fff', borderRadius: 10, padding: 16, width: 620, maxWidth: '95vw', fontSize: 12 }}>
        <Header title="Where the datasets have data" onClose={onClose} />
        {!datasets.length && <div>Add datasets to the canvas first.</div>}
        {error && <div style={{ color: '#b91c1c' }}>{error}</div>}
        {datasets.length > 0 && !data && !error && <div><Loader2 size={14} /> computing coverage…</div>}
        {paths && (
          <>
            <svg width={width} height={height} style={{ background: '#f8fafc', borderRadius: 6, maxWidth: '100%' }}>
              {paths.filter((p) => !p.f.properties.area).map((p) => (
                <path key={p.key} d={p.d} fill={COVER_COLORS[Math.min(COVER_COLORS.length - 1, Math.round((p.f.properties.n / max) * (COVER_COLORS.length - 1)))]}
                  stroke="none"><title>{p.f.properties.datasets.join(', ')}</title></path>
              ))}
              {paths.filter((p) => p.f.properties.area).map((p) => (
                <path key={p.key} d={p.d} fill="none" stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4 3" />
              ))}
            </svg>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '6px 0 10px', color: '#475569' }}>
              Datasets with data in a cell (about 500 m):
              {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
                <span key={n} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 12, height: 12, background: COVER_COLORS[Math.min(COVER_COLORS.length - 1, Math.round((n / max) * (COVER_COLORS.length - 1)))], display: 'inline-block' }} /> {n}
                </span>
              ))}
              {data.study_area && <span style={{ color: '#dc2626' }}>– – study area</span>}
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr style={{ textAlign: 'left', color: '#64748b' }}><th>Dataset</th><th>Cells</th>{data.study_area && <th>Share of study area</th>}</tr></thead>
              <tbody>
                {Object.entries(data.datasets).map(([id, info]) => (
                  <tr key={id} style={{ borderTop: '1px solid #f1f5f9' }}>
                    <td>{id}{info.approximate ? ' (from its extent)' : ''}</td>
                    <td>{info.has_grid ? info.cells : '—'}</td>
                    {data.study_area && (
                      <td style={{ color: info.share_of_area < 0.5 ? '#b45309' : '#0f172a' }}
                        title={info.measure === 'spread'
                          ? `Points: the part of the study area their spread reaches. ${info.points_inside} points inside (${Math.round(info.share_of_rows * 100)}% of the dataset), counted from its density grid.`
                          : 'Share of the study area\'s 500 m cells where the dataset has data.'}>
                        {info.share_of_area != null ? `${Math.round(info.share_of_area * 100)}%` : '—'}
                        {info.measure === 'spread' && <span style={{ color: '#64748b' }}> · {info.points_inside} points</span>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}

export function WarningsPanel({ warnings, onClose }) {
  return (
    <div style={{ ...panelStyle, left: 'auto', right: 0 }}>
      <Header title="Checks" onClose={onClose} />
      {warnings.length === 0
        ? <div style={{ color: '#16a34a' }}>No problems found: the periods overlap and the datasets reach the study area.</div>
        : warnings.map((w, i) => <div key={i} style={{ padding: '6px 0', borderTop: i ? '1px solid #f1f5f9' : 'none', color: '#92400e' }}>{w.message}</div>)}
    </div>
  );
}
