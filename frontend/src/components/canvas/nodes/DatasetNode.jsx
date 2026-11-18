// frontend/src/components/DatasetNode.jsx
import React, { memo, useMemo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Database, Layers, Palette, Info, X } from 'lucide-react'; // Added Info icon
import VectorPreviewMap from '../../visualization/VectorPreviewMap';

const DatasetNode = memo(({ id, data }) => {
  const meta = data.metadata || {};
  const columns = meta.columns;
  const name = meta.name || data.name || 'Untitled';
  const filename = data.filename || name + '.geojson';
  
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
      <VectorPreviewMap
        height={150}
        filename={filename} 
        selectedColumn={selectedColumn}
        isMapSyncEnabled={isMapSyncEnabled}
        globalViewState={globalViewState}
        onGlobalViewStateChange={onGlobalViewStateChange}
      />

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
          title={`${meta.geometricType || 'Unknown'} · ${meta.nb_rows?.toLocaleString() || 0} rows`}
          style={{ display: 'flex', alignItems: 'center', gap: '3px', color: '#94a3b8', fontSize: '9px', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          <Layers size={9} /> {meta.geometricType || 'Unknown'} · {meta.nb_rows?.toLocaleString() || 0}
        </div>
      </div>

      {/* Connector */}
      <Handle type="source" position={Position.Right} style={{ background: '#2563eb', width: '8px', height: '8px', right: '-4px', border: '2px solid white' }} />
    </div>
  );
});

export default DatasetNode;
