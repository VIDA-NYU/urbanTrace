// frontend/src/components/DatasetNode.jsx
import React, { memo, useEffect, useMemo, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Database, Layers, Palette, Info, X, Clock, ShieldCheck } from 'lucide-react';
import CheckDataModal from '../../catalog/CheckDataModal';
import VectorPreviewMap from '../../visualization/VectorPreviewMap';
import { API_BASE } from '../../../config/api';
import { getCatalogIndex } from '../../../lib/scope';

// Time window on the source (redesign section 4.1): integrations use only rows in [start, end].
function TimeWindow({ nodeId, datasetId, value, onChange }) {
  const [time, setTime] = useState(null);
  useEffect(() => {
    let alive = true;
    getCatalogIndex().then((idx) => { if (alive) setTime(idx[datasetId]?.time || null); });
    return () => { alive = false; };
  }, [datasetId]);
  if (!time || !time.columns?.length) return null;
  const w = value || {};
  const set = (patch) => {
    const next = { column: w.column || time.columns[0], start: w.start || '', end: w.end || '', ...patch };
    onChange?.(nodeId, next.start || next.end ? next : null);
  };
  const inputStyle = { fontSize: '9px', border: '1px solid #cbd5e1', borderRadius: '3px', padding: '0 2px', height: '16px', minWidth: 0 };
  return (
    <div className="nodrag" title={`Data from ${time.start} to ${time.end}. Set a window to integrate only those rows.`}
      style={{ padding: '3px 8px 4px', borderTop: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '9px', color: w.start || w.end ? '#1d4ed8' : '#64748b' }}>
      <Clock size={10} style={{ flexShrink: 0 }} />
      {time.columns.length > 1 && (
        <select value={w.column || time.columns[0]} onChange={(e) => set({ column: e.target.value })} style={{ ...inputStyle, width: '52px' }}>
          {time.columns.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}
      <input type="date" value={w.start || ''} min={time.start} max={time.end} onChange={(e) => set({ start: e.target.value })} style={{ ...inputStyle, flex: 1 }} />
      –
      <input type="date" value={w.end || ''} min={time.start} max={time.end} onChange={(e) => set({ end: e.target.value })} style={{ ...inputStyle, flex: 1 }} />
    </div>
  );
}

const DatasetNode = memo(({ id, data }) => {
  const meta = data.metadata || {};
  const columns = meta.columns;
  const name = meta.name || data.name || 'Untitled';
  const filename = data.filename || name + '.geojson';
  const datasetId = data.id || filename.replace(/\.geojson$/i, '');

  // Data checks (atlas-clean): whether corrections are saved, and a revision that makes the preview
  // reload after they change.
  const [checking, setChecking] = useState(false);
  const [rev, setRev] = useState(0);
  const [corrected, setCorrected] = useState(false);
  const [located, setLocated] = useState(false);
  useEffect(() => {
    let alive = true;
    getCatalogIndex().then((idx) => { if (alive) { setCorrected(Boolean(idx[datasetId]?.corrected)); setLocated(Boolean(idx[datasetId]?.located)); } });
    return () => { alive = false; };
  }, [datasetId, rev]);
  
  // GLOBAL VIEWPORT SYNC: Extract sync props from data
  const isMapSyncEnabled = data.isMapSyncEnabled || false;
  const globalViewState = data.globalViewState;
  const onGlobalViewStateChange = data.onGlobalViewStateChange;

  const numericColumns = useMemo(
    () => (Array.isArray(columns) ? columns : []).filter((column) =>
      ['Integer', 'Float', 'http://schema.org/Integer', 'http://schema.org/Float'].includes(column.structural_type)
      || column.mean !== undefined
    ),
    [columns]
  );

  const selectedColumn = typeof data.selectedColumn === 'string'
    ? data.selectedColumn
    : (typeof data.colorBy === 'string' ? data.colorBy : '');

  const handleColumnChange = (value) => {
    if (typeof data.onColumnChange === 'function') {
      data.onColumnChange(id, value);
      return;
    }
    if (typeof data.onColumnSelect === 'function') {
      data.onColumnSelect(value);
    }
    if (typeof data.onColorByChange === 'function') {
      data.onColorByChange(id, value);
    }
  };

  return (
    <div style={{
      width: '220px',
      backgroundColor: '#fff',
      borderRadius: '8px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      border: '1px solid #e2e8f0',
      overflow: 'hidden',
      fontSize: '12px',
      fontFamily: 'Inter, system-ui, sans-serif'
    }}>
      {/* 1. Header */}
      <div style={{
        backgroundColor: '#eff6ff',
        padding: '3px 4px 3px 8px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between', // Pushes items to edges
        gap: '4px'
      }}>
        {/* Left: Icon + Name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', overflow: 'hidden' }}>
          <Database size={11} color="#2563eb" style={{ flexShrink: 0 }} />
          <span title={name} style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#1e3a8a', 
            whiteSpace: 'nowrap', 
            overflow: 'hidden', 
            textOverflow: 'ellipsis' 
          }}>
            {name}
          </span>
        </div>

        {/* Right: Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0px', flexShrink: 0 }}>
          <button 
            className="nodrag" // Crucial: Prevents dragging when clicking button
            onClick={(e) => {
               e.stopPropagation(); // Prevents selecting the node
               // We check if the parent passed a handler function
               if (data.onShowInfo) {
                   data.onShowInfo(data); 
               } else {
                   alert("Metadata:\n" + JSON.stringify(meta, null, 2)); // Fallback
               }
            }}
            title="See Dataset Details"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              borderRadius: '4px',
              transition: 'background 0.2s, color 0.2s'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#dbeafe'; e.currentTarget.style.color = '#2563eb'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#64748b'; }}
          >
            <Info size={12} />
          </button>

          {meta.geometricType !== 'Raster' && <button
            className="nodrag"
            onClick={(e) => { e.stopPropagation(); setChecking(true); }}
            title={corrected || located ? `${[corrected && 'Corrections saved (atlas-clean)', located && 'rows located from their addresses'].filter(Boolean).join('; ')}: check again or remove them` : 'Check this dataset for data-quality problems (atlas-clean) and locate rows from their addresses'}
            style={{ background: corrected || located ? '#ccfbf1' : 'none', border: 'none', cursor: 'pointer', padding: '3px', display: 'flex',
              alignItems: 'center', gap: 2, color: corrected || located ? '#0f766e' : '#64748b', borderRadius: '4px', fontSize: 9, fontWeight: 600 }}
          >
            <ShieldCheck size={12} />{[corrected && 'Corrected', located && 'Located'].filter(Boolean).join(' · ')}
          </button>}

          <button
            className="nodrag"
            onClick={(e) => {
              e.stopPropagation();
              data?.onDeleteNode?.(id);
            }}
            title="Remove node"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#64748b',
              borderRadius: '4px',
              transition: 'background 0.2s, color 0.2s'
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#fee2e2'; e.currentTarget.style.color = '#b91c1c'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#64748b'; }}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* 2. Map Preview */}
      {checking && (
        <CheckDataModal datasetId={datasetId} name={name} onClose={() => setChecking(false)}
          onChanged={() => { setRev((r) => r + 1); data.onCorrected?.(id); }} />
      )}
      {meta.geometricType === 'Raster' ? (
        // A raster dataset (backend/rasters.py): a picture of it, values light to dark green
        <div style={{ height: 150, background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
          <img src={`${API_BASE}/api/rasters/${encodeURIComponent(datasetId)}/preview.png`} alt={name}
            style={{ maxWidth: '100%', maxHeight: '100%', imageRendering: 'pixelated' }} />
          <span style={{ position: 'absolute', bottom: 3, left: 6, fontSize: 9, color: '#475569', background: 'rgba(255,255,255,0.85)', padding: '0 4px', borderRadius: 3 }}>
            {meta.raster?.units ? `${meta.columns?.[0]?.name} (${meta.raster.units})` : meta.columns?.[0]?.name} · {meta.raster?.resolution_m ? `${meta.raster.resolution_m} m cells` : ''}
          </span>
        </div>
      ) : (
      <VectorPreviewMap
        height={150}
        filename={filename}
        rev={rev}
        selectedColumn={selectedColumn}
        isMapSyncEnabled={isMapSyncEnabled}
        globalViewState={globalViewState}
        onGlobalViewStateChange={onGlobalViewStateChange}
      />
      )}

      {/* 3. Controls: column picker, then geometry type and row count, on one row */}
      <div style={{ padding: '4px 8px', backgroundColor: '#fff', borderTop: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Palette size={10} color="#64748b" style={{ flexShrink: 0 }} aria-label="Color by column" />
        <select
          value={selectedColumn}
          onChange={(e) => handleColumnChange(e.target.value)}
          className="nodrag"
          title="Color by column"
          style={{
            flexGrow: 1,
            width: '0',
            padding: '0 2px',
            fontSize: '10px',
            borderRadius: '3px',
            border: '1px solid #cbd5e1',
            backgroundColor: '#fff',
            color: '#334155',
            outline: 'none',
            cursor: 'pointer',
            height: '18px'
          }}
        >
          <option value="" style={{ color: '#64748b' }}>Default (Blue)</option>
          {numericColumns.map(col => (
            <option key={col.name} value={col.name} style={{ color: '#0f172a' }}>
              {col.name}
            </option>
          ))}
        </select>
        <div
          title={`${meta.geometricType || 'Unknown'} · ${meta.nb_rows?.toLocaleString() || 0} ${meta.geometricType === 'Raster' ? 'cells' : 'rows'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '3px', color: '#94a3b8', fontSize: '9px', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          <Layers size={9} /> {meta.geometricType || 'Unknown'} · {meta.nb_rows?.toLocaleString() || 0}
        </div>
      </div>

      <TimeWindow nodeId={id} datasetId={(data.id || filename).replace(/\.geojson$/i, '')}
        value={data.timeWindow} onChange={data.onTimeWindowChange} />

      {/* Connector */}
      <Handle type="source" position={Position.Right} style={{ background: '#2563eb', width: '8px', height: '8px', right: '-4px', border: '2px solid white' }} />
    </div>
  );
});

export default DatasetNode;
