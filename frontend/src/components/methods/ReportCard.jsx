// What an integration step did, from urbanweave's reports (docs/REDESIGN.md, section 3.4): sources
// matched and left out by cause, repairs, time window and study area, the measuring CRS, and whether
// the method keeps totals.
import React, { useState } from 'react';
import { ChevronDown, ChevronRight, AlertTriangle } from 'lucide-react';

const causeText = (cause) => cause.replace(/_/g, ' ');

function Bar({ matched, total }) {
  const share = total ? matched / total : 0;
  return (
    <div style={{ height: 4, background: '#fee2e2', borderRadius: 2, overflow: 'hidden', margin: '3px 0' }}>
      <div style={{ width: `${share * 100}%`, height: '100%', background: share > 0.95 ? '#22c55e' : '#f59e0b' }} />
    </div>
  );
}

function Step({ label, report }) {
  const match = report?.match;
  if (!match) return null;
  const src = match.sources || {};
  const tgt = match.targets || {};
  const empty = (report.aggregate || []).find((a) => a.empty_targets != null)?.empty_targets;
  const unmatched = Object.entries(src.unmatched || {});
  const excluded = Object.entries(src.excluded || {});
  const missing = (report.aggregate || []).flatMap((a) => {
    const v = a.values || {};
    return v.missing ? [`${v.missing} missing value(s) left out of ${a.method}`] : [];
  });
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>{label}: <b>{match.method}</b></span>
        <span>{src.matched}/{src.total} matched</span>
      </div>
      <Bar matched={src.matched || 0} total={src.total || 0} />
      {unmatched.map(([cause, info]) => <div key={cause} style={{ color: '#b45309' }}>{info.count} unmatched: {causeText(cause)}</div>)}
      {excluded.map(([cause, info]) => <div key={cause} style={{ color: '#b45309' }}>{info.count} excluded: {causeText(cause)}</div>)}
      {missing.map((m) => <div key={m} style={{ color: '#b45309' }}>{m}</div>)}
      {tgt.total != null && (
        <div>{tgt.matched} of {tgt.total} targets received something{empty ? `; ${empty} received nothing` : ''}</div>
      )}
      <div style={{ color: '#64748b' }}>
        {match.assignment ? `${match.assignment} assignment` : ''}
        {match.measurement?.crs_name ? ` · measured in ${match.measurement.crs_name}` : ''}
      </div>
    </div>
  );
}

// A join on a key (urbanweave's reduce): how many keys the rows carried, and those matching no zone.
function KeyJoin({ report }) {
  if (report?.conversion !== 'reduce') return null;
  const unknown = report.unknown_keys || {};
  const sample = (unknown.sample || unknown.ids || []).slice(0, 5);
  return (
    <div style={{ marginTop: 4 }}>
      <div>Joined on <b>{report.by}</b>: rows with {report.groups} distinct key(s)</div>
      {unknown.count > 0 && (
        <div style={{ color: '#b45309' }}>
          {unknown.count} key(s) match no zone and were left out{sample.length ? ` (e.g. ${sample.join(', ')})` : ''}
        </div>
      )}
      {(report.reductions || []).filter((r) => r.rows_skipped).map((r) => (
        <div key={r.as} style={{ color: '#b45309' }}>{r.as}: {r.rows_skipped} row(s) with a missing value left out</div>
      ))}
      {(report.reductions || []).filter((r) => r.zero_denominator_targets).map((r) => (
        <div key={`${r.as}-z`} style={{ color: '#b45309' }}>{r.as}: {r.zero_denominator_targets} zone(s) with a zero denominator</div>
      ))}
    </div>
  );
}

// Zonal statistics of a raster: how the cells were weighted, and zones the raster missed
function Zonal({ report }) {
  if (report?.conversion !== 'zonal_stats') return null;
  const z = report.zones || {};
  const gaps = [['outside_raster', 'outside the raster'], ['no_cells', 'reached no cell'], ['cells_without_valid_values', 'only over cells with no data']]
    .filter(([k]) => z[k]?.count);
  return (
    <div style={{ marginTop: 4 }}>
      <div>Zonal statistics, <b>{report.method === 'cell_coverage' ? 'exact cell coverage' : 'cell centres'}</b>: {z.total} units,
        {' '}{(report.reads?.cells || 0).toLocaleString()} cells of {report.measurement?.cell_area_m2 || '?'} m² read</div>
      {gaps.map(([k, label]) => <div key={k} style={{ color: '#b45309' }}>{z[k].count} unit(s) {label}</div>)}
    </div>
  );
}

// One line that is visible while the card is closed: what went in and what it reached.
function summary(rep) {
  if (rep?.allocation?.conversion === 'zonal_stats') {
    const z = rep.allocation.zones || {};
    const gaps = ['outside_raster', 'no_cells', 'cells_without_valid_values'].reduce((s, k) => s + (z[k]?.count || 0), 0);
    return [rep.study_area ? `study area` : null, `zonal statistics onto ${z.total} units`, gaps ? `${gaps} without data` : null].filter(Boolean).join(' · ');
  }
  if (rep?.allocation?.conversion === 'reduce') {
    const a = rep.allocation;
    return [`joined on ${a.by}: ${a.groups} key(s)`, a.unknown_keys?.count ? `${a.unknown_keys.count} match no zone` : null].filter(Boolean).join(' · ');
  }
  const match = (rep?.allocation || rep?.zoning)?.match;
  if (!match) return null;
  const src = match.sources || {};
  const tgt = match.targets || {};
  const parts = [];
  if (rep.study_area) parts.push(`${rep.study_area.kept} of ${rep.study_area.features} in study area`);
  if (rep.outside_region) parts.push(`${rep.outside_region.outside} outside region`);
  parts.push(`${src.matched ?? 0}/${src.total ?? 0} matched`);
  if (tgt.total != null) parts.push(`${tgt.matched}/${tgt.total} targets`);
  return parts.join(' · ');
}

function hasWarnings(rep) {
  const steps = [rep?.allocation, rep?.zoning].filter(Boolean);
  return steps.some((s) => {
    const src = s.match?.sources || {};
    return Object.keys(src.unmatched || {}).length || Object.keys(src.excluded || {}).length || s.unknown_keys?.count > 0;
  }) || !!rep?.repaired_geometries;
}

export default function ReportCard({ reports, defaultOpen = false, title = 'What happened' }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!reports || !Object.keys(reports).length) return null;
  const warn = Object.values(reports).some(hasWarnings);
  return (
    <div className="nodrag nowheel" style={{ fontSize: 10, color: '#334155', border: '1px solid #e2e8f0', borderRadius: 6, background: '#fff', padding: '4px 8px' }}>
      <button type="button" onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        style={{ display: 'flex', alignItems: 'center', gap: 4, width: '100%', border: 'none', background: 'none', padding: 0, cursor: 'pointer', fontSize: 10, fontWeight: 700, color: '#0f172a' }}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />} {title}
        {warn && <AlertTriangle size={11} color="#d97706" style={{ marginLeft: 'auto' }} />}
      </button>
      {!open && Object.values(reports).map(summary).filter(Boolean).map((line, i) => (
        <div key={i} style={{ color: '#475569', marginTop: 2 }}>{line}</div>
      ))}
      {open && Object.entries(reports).map(([name, rep]) => (
        <div key={name} style={{ borderTop: '1px solid #f1f5f9', marginTop: 4, paddingTop: 4 }}>
          <div style={{ fontWeight: 600, color: '#4338ca', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={name}>{name}</div>
          {rep?.time_window && <div>Time window on {rep.time_window.column}: {rep.time_window.kept} of {rep.time_window.rows} rows</div>}
          {rep?.study_area && <div>Study area: {rep.study_area.kept} of {rep.study_area.features} features inside</div>}
          {rep?.outside_region && <div style={{ color: '#b45309' }}>{rep.outside_region.outside.toLocaleString()} of {rep.outside_region.rows.toLocaleString()} features lie outside the catalog's region and were left out</div>}
          {rep?.cleaning?.fixes?.length > 0 && <div>Corrected on load: {rep.cleaning.fixes.map((f) => `${f.action} (${f.rows} rows)`).join(', ')}</div>}
          {rep?.repaired_geometries && <div style={{ color: '#b45309' }}>{rep.repaired_geometries.count} invalid geometries repaired</div>}
          <KeyJoin report={rep?.allocation} />
          <Zonal report={rep?.allocation} />
          <Step label={rep?.zoning ? 'To grid' : 'Matched'} report={rep?.allocation} />
          <Step label="To zones" report={rep?.zoning} />
        </div>
      ))}
    </div>
  );
}
