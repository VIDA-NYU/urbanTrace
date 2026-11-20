// frontend/src/components/catalog/DatasetDetailsModal.jsx
// Dataset info box. Shows the dataset's description and its newest profile (atlas-profiler 0.1.0,
// data/metadata_v2), fetched from /datasets/{id}/details when the box opens; datasets without one
// fall back to the metadata that came with the catalog.
import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, Layers, Type, Calendar, AlertCircle, FileText, MapPin, ExternalLink } from 'lucide-react';
import { API_BASE } from '../../config/api';

const API = API_BASE;

// Helper to parse CSV lines while respecting quotes (for geometry strings)
const parseCSVLine = (line) => {
  const result = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
};

// A CRS is a name ("EPSG:4326") or a GeoJSON object ({ type: 'name', properties: { name } })
const crsLabel = (crs) => {
  if (!crs) return null;
  if (typeof crs === 'string') return crs;
  const name = crs.properties?.name;
  if (typeof name === 'string') return name.replace(/^urn:ogc:def:crs:/, '').replace('::', ':');
  return null;
};

const shortType = (uri) => (uri ? String(uri).split('/').pop() : '');

const typeColors = {
  Integer: '#3b82f6',
  Float: '#06b6d4',
  Text: '#10b981',
  DateTime: '#8b5cf6',
  Boolean: '#ec4899',
  Geometry: '#f59e0b',
  MissingData: '#9ca3af',
};

const columnType = (col) => {
  if (['geometry', 'the_geom'].includes(col.name)) return 'Geometry';
  const sem = (col.semantic_types || []).map(shortType);
  if (sem.includes('DateTime')) return 'DateTime';
  if (sem.includes('Boolean')) return 'Boolean';
  const s = shortType(col.structural_type);
  if (s === 'GeoCoordinates' || s === 'GeoShape') return 'Geometry';
  return typeColors[s] ? s : 'Text';
};

// Semantic types worth showing next to the type (Text and Enumeration are common and say little)
const columnTags = (col) => {
  const tags = (col.semantic_types || []).map(shortType)
    .filter((t) => !['Text', 'DateTime', 'Boolean'].includes(t));
  if (col.geo_classifier?.label && !tags.includes(col.geo_classifier.label)) tags.push(col.geo_classifier.label);
  return tags;
};

const fmtNumber = (v) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
  const n = Number(v);
  if (Number.isInteger(n)) return n.toLocaleString();
  const abs = Math.abs(n);
  return n.toLocaleString(undefined, { maximumFractionDigits: abs >= 100 ? 1 : abs >= 1 ? 2 : 4 });
};

const fmtBytes = (bytes) => {
  if (!bytes) return null;
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
};

// POSIX seconds -> date, with the time when the data is finer than a day
const fmtTime = (seconds, precision) => {
  if (seconds === null || seconds === undefined) return '-';
  const iso = new Date(seconds * 1000).toISOString();
  return ['hour', 'minute', 'second'].includes(precision) ? `${iso.slice(0, 16).replace('T', ' ')} UTC` : iso.slice(0, 10);
};

const fmtDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return '-';
  const steps = [['year', 365.25 * 86400], ['day', 86400], ['hour', 3600], ['minute', 60], ['second', 1]];
  for (const [unit, size] of steps) {
    if (seconds >= size) {
      const v = seconds / size;
      const r = v >= 10 ? Math.round(v) : Math.round(v * 10) / 10;
      return `${r} ${unit}${r === 1 ? '' : 's'}`;
    }
  }
  return `${seconds} s`;
};

// Tiny histogram from the profile's plot: grey end bars count values outside the plotted range
const Sparkline = ({ plot }) => {
  const data = plot?.data || [];
  if (!data.length) return <span style={{ color: '#9ca3af' }}>-</span>;
  const bars = [
    ...(plot.below ? [{ count: plot.below, outside: true }] : []),
    ...data.map((d) => ({ count: d.count || 0 })),
    ...(plot.above ? [{ count: plot.above, outside: true }] : []),
  ];
  const width = 96;
  const height = 22;
  const max = Math.max(...bars.map((b) => b.count), 1);
  const w = width / bars.length;
  const label = plot.type === 'histogram_categorical' || plot.type === 'histogram_text'
    ? data.slice(0, 5).map((d) => `${d.bin}: ${d.count}`).join('\n')
    : `${bars.length} bars${plot.below || plot.above ? `; ${plot.below || 0} below, ${plot.above || 0} above the range` : ''}`;
  return (
    <svg width={width} height={height} role="img" aria-label="distribution">
      <title>{label}</title>
      {bars.map((b, i) => {
        const h = b.count ? Math.max(1, (b.count / max) * height) : 0;
        return <rect key={i} x={i * w + 0.5} y={height - h} width={Math.max(w - 1, 0.5)} height={h}
                     fill={b.outside ? '#d1d5db' : '#3b82f6'} />;
      })}
    </svg>
  );
};

const DatasetDetailsModal = ({ dataset, onClose }) => {
  const datasetId = String(dataset?.id || dataset?.filename || '').replace(/\.geojson$/, '');
  // { id, data }: data is the server's answer for that dataset id (null if it failed)
  const [fetched, setFetched] = useState(null);

  useEffect(() => {
    if (!datasetId) return undefined;
    let cancelled = false;
    fetch(`${API}/datasets/${encodeURIComponent(datasetId)}/details`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((data) => { if (!cancelled) setFetched({ id: datasetId, data }); });
    return () => { cancelled = true; };
  }, [datasetId]);

  const loading = Boolean(datasetId) && fetched?.id !== datasetId;
  const details = loading ? null : fetched?.data;

  if (!dataset) return null;

  const oldMeta = dataset.metadata || {};
  const profile = details?.profile;
  const meta = profile || oldMeta;
  const columns = meta.columns || [];
  const nbRows = meta.nb_rows;
  const sampling = profile?.computed_on?.sampling;
  const sampled = sampling && sampling.method !== 'none' && sampling.rows < sampling.of;
  const temporal = meta.temporal_coverage || [];
  const spatial = (meta.spatial_coverage || []).filter((e) => e.ranges?.[0]?.range?.coordinates?.length === 2);

  // The new profiles have no sample rows; the old metadata does
  const sampleRows = oldMeta.sample ? oldMeta.sample.trim().split('\n') : [];
  const sampleHeaders = sampleRows.length > 0 ? parseCSVLine(sampleRows[0]) : [];
  const sampleBody = sampleRows.slice(1).map((row) => parseCSVLine(row));

  const presentTypes = [...new Set(columns.map(columnType))];
  const missingColumns = columns.filter((c) => (c.missing_values_ratio || 0) > 0).length;
  const hasRanges = columns.some((c) => c.min !== undefined || c.mean !== undefined);

  // Rendered into <body> so the sidebar's or canvas's stacking context cannot put other panels above it
  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
        backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center',
        zIndex: 1000, backdropFilter: 'blur(2px)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          backgroundColor: 'white', width: '960px', maxWidth: 'calc(100vw - 32px)', maxHeight: '90vh',
          borderRadius: '12px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '20px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{ minWidth: 0 }}>
            <h2 style={{ margin: 0, fontSize: '1.5rem', color: '#111827' }}>{dataset.name || meta.name || datasetId}</h2>
            <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>{dataset.filename}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
            {details?.report_url && (
              <a href={`${API}${details.report_url}`} target="_blank" rel="noreferrer" style={reportLinkStyle}>
                <ExternalLink size={14} /> Full profile report
              </a>
            )}
            <button onClick={onClose} aria-label="Close" style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
              <X size={24} color="#6b7280" />
            </button>
          </div>
        </div>

        {/* Content - Scrollable */}
        <div style={{ padding: '24px', overflowY: 'auto' }}>
          {details?.description && (
            <p style={{ margin: '0 0 24px 0', fontSize: '0.9rem', lineHeight: 1.55, color: '#374151' }}>{details.description}</p>
          )}
          {loading && <p style={{ margin: '0 0 16px 0', fontSize: '0.8rem', color: '#9ca3af' }}>Loading profile…</p>}

          {/* Summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '28px' }}>
            <div style={cardStyle}>
              <h4 style={headerStyle}><FileText size={16} /> General</h4>
              <div style={rowStyle}><span>Rows:</span> <strong>{nbRows?.toLocaleString() || '-'}</strong></div>
              {sampling && (
                <div style={rowStyle}>
                  <span>Profiled:</span>
                  <strong>{sampled ? `${sampling.rows.toLocaleString()} sampled rows` : 'every row'}</strong>
                </div>
              )}
              <div style={rowStyle}><span>Columns:</span> <strong>{meta.nb_columns ?? columns.length}</strong></div>
              <div style={rowStyle}><span>Size:</span> <strong>{fmtBytes(profile?.size) || dataset.size || 'Unknown'}</strong></div>
              <div style={rowStyle}>
                <span>Geometry:</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Layers size={14} /> {meta.geometricType || 'None'}</span>
              </div>
              {crsLabel(meta.crs) && <div style={rowStyle}><span>CRS:</span> <strong>{crsLabel(meta.crs)}</strong></div>}
            </div>

            <div style={cardStyle}>
              <h4 style={headerStyle}><Type size={16} /> Data types</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                {presentTypes.map((type) => (
                  <span key={type} style={{ backgroundColor: typeColors[type] || '#9ca3af', color: 'white', padding: '4px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600 }}>
                    {type} · {columns.filter((c) => columnType(c) === type).length}
                  </span>
                ))}
              </div>
              <div style={{ ...rowStyle, marginTop: '12px' }}>
                <span><AlertCircle size={13} style={{ verticalAlign: '-2px' }} /> Columns with missing values:</span>
                <strong>{missingColumns}</strong>
              </div>
            </div>

            <div style={cardStyle}>
              <h4 style={headerStyle}><Calendar size={16} /> Time coverage</h4>
              {temporal.length === 0 && <span style={mutedStyle}>No date or time columns.</span>}
              {temporal.map((t, i) => {
                const r = t.ranges?.[0]?.range || {};
                const s = t.sampling;
                return (
                  <div key={i} style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#374151' }}>
                    <strong>{(t.column_names || []).join(', ')}</strong>
                    <div>{fmtTime(r.gte, t.temporal_precision)} → {fmtTime(r.lte, t.temporal_precision)}</div>
                    <div style={mutedStyle}>
                      {t.temporal_precision ? `recorded to the ${t.temporal_precision}` : ''}
                      {s?.median_interval_seconds !== undefined ? `; typical interval ${fmtDuration(s.median_interval_seconds)}${s.regular ? ' (regular)' : ''}` : ''}
                      {s?.largest_gap_seconds ? `; largest gap ${fmtDuration(s.largest_gap_seconds)}` : ''}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={cardStyle}>
              <h4 style={headerStyle}><MapPin size={16} /> Spatial coverage</h4>
              {spatial.length === 0 && <span style={mutedStyle}>No spatial extent in the profile.</span>}
              {spatial.map((e, i) => {
                const [[minLon, maxLat], [maxLon, minLat]] = e.ranges[0].range.coordinates;
                return (
                  <div key={i} style={{ marginBottom: '8px', fontSize: '0.8rem', color: '#374151' }}>
                    <strong>{(e.column_names || []).join(' / ')}</strong>
                    {e.number !== undefined && <span style={mutedStyle}> · {e.number.toLocaleString()} points</span>}
                    <div style={mutedStyle}>
                      lat {minLat.toFixed(3)} to {maxLat.toFixed(3)}, lon {minLon.toFixed(3)} to {maxLon.toFixed(3)}
                    </div>
                    {(e.number_zero_coordinates > 0 || e.number_outside_envelope > 0) && (
                      <div style={mutedStyle}>
                        {e.number_zero_coordinates > 0 ? `${e.number_zero_coordinates.toLocaleString()} at (0, 0); ` : ''}
                        {e.number_outside_envelope > 0 ? `${e.number_outside_envelope.toLocaleString()} outside the extent` : ''}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Columns */}
          <h3 style={{ fontSize: '1.1rem', marginBottom: '10px', color: '#374151' }}>Columns</h3>
          <div style={{ overflowX: 'auto', marginBottom: '8px', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem' }}>
              <thead style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <tr>
                  <th style={thStyle}>Column</th>
                  <th style={thStyle}>Type</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Distinct</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Missing</th>
                  {hasRanges && <th style={thStyle}>Range</th>}
                  {hasRanges && <th style={{ ...thStyle, textAlign: 'right' }}>Mean</th>}
                  <th style={thStyle}>Distribution</th>
                </tr>
              </thead>
              <tbody>
                {columns.map((col, idx) => {
                  const missing = col.missing_values_ratio || 0;
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={tdStyle}><b>{col.name}</b></td>
                      <td style={tdStyle}>
                        {columnType(col)}
                        {columnTags(col).map((t) => <span key={t} style={tagStyle}>{t}</span>)}
                      </td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>
                        {col.num_distinct_values !== undefined ? `${col.num_distinct_values_is_approximate ? '≈ ' : ''}${fmtNumber(col.num_distinct_values)}` : '-'}
                      </td>
                      <td style={{ ...tdStyle, textAlign: 'right', color: missing > 0 ? '#ef4444' : '#10b981' }}>
                        {missing > 0 ? `${(missing * 100).toFixed(missing < 0.01 ? 2 : 1)}%` : '0'}
                      </td>
                      {hasRanges && <td style={tdStyle}>{col.min !== undefined ? `${fmtNumber(col.min)} – ${fmtNumber(col.max)}` : ''}</td>}
                      {hasRanges && <td style={{ ...tdStyle, textAlign: 'right' }}>{col.mean !== undefined ? fmtNumber(col.mean) : ''}</td>}
                      <td style={{ ...tdStyle, paddingTop: '4px', paddingBottom: '4px' }}><Sparkline plot={col.plot} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {profile && (
            <p style={{ ...mutedStyle, margin: '0 0 28px 0' }}>
              {sampled
                ? `Types, distributions and missing values come from ${sampling.rows.toLocaleString()} randomly sampled rows; counts, ranges and coverage from every row.`
                : 'Computed from every row.'}{' '}
              Grey bars count values outside the plotted range. Hover a distribution for details.
            </p>
          )}

          {sampleBody.length > 0 && (
            <>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '10px', color: '#374151' }}>Sample data</h3>
              <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                  <thead style={{ backgroundColor: '#f3f4f6' }}>
                    <tr>{sampleHeaders.map((h, i) => <th key={i} style={thStyle}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {sampleBody.slice(0, 5).map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #eee' }}>
                        {row.map((cell, j) => (
                          <td key={j} style={{ ...tdStyle, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis' }} title={cell}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
};

// Internal Styles
const cardStyle = { backgroundColor: '#f9fafb', padding: '15px', borderRadius: '8px', border: '1px solid #e5e7eb' };
const headerStyle = { margin: '0 0 10px 0', fontSize: '0.9rem', color: '#4b5563', display: 'flex', alignItems: 'center', gap: '6px' };
const rowStyle = { display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '0.85rem', marginBottom: '6px', color: '#374151' };
const mutedStyle = { fontSize: '0.75rem', color: '#6b7280' };
const thStyle = { padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#4b5563', whiteSpace: 'nowrap' };
const tdStyle = { padding: '7px 12px', color: '#1f2937', verticalAlign: 'middle' };
const tagStyle = { marginLeft: '6px', padding: '1px 6px', borderRadius: '8px', backgroundColor: '#eef2ff', color: '#4338ca', fontSize: '0.7rem' };
const reportLinkStyle = {
  display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 10px', borderRadius: '6px',
  border: '1px solid #d1d5db', color: '#1f2937', fontSize: '0.8rem', textDecoration: 'none', whiteSpace: 'nowrap',
};

export default DatasetDetailsModal;
