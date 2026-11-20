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
      <div style={{ color: '#64748b' }}>
        {match.assignment ? `${match.assignment} assignment` : ''}
        {match.measurement?.crs_name ? ` · measured in ${match.measurement.crs_name}` : ''}
      </div>
    </div>
  );
}

function hasWarnings(rep) {
  const steps = [rep?.allocation, rep?.zoning].filter(Boolean);
  return steps.some((s) => {
    const src = s.match?.sources || {};
    return Object.keys(src.unmatched || {}).length || Object.keys(src.excluded || {}).length;
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
      {open && Object.entries(reports).map(([name, rep]) => (
        <div key={name} style={{ borderTop: '1px solid #f1f5f9', marginTop: 4, paddingTop: 4 }}>
          <div style={{ fontWeight: 600, color: '#4338ca', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={name}>{name}</div>
          {rep?.time_window && <div>Time window on {rep.time_window.column}: {rep.time_window.kept} of {rep.time_window.rows} rows</div>}
          {rep?.study_area && <div>Study area: {rep.study_area.kept} of {rep.study_area.features} features inside</div>}
          {rep?.repaired_geometries && <div style={{ color: '#b45309' }}>{rep.repaired_geometries.count} invalid geometries repaired</div>}
          <Step label="To grid" report={rep?.allocation} />
          <Step label="To zones" report={rep?.zoning} />
        </div>
      ))}
    </div>
  );
}
