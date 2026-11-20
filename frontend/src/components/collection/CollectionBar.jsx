// The collection bar (docs/REDESIGN.md, section 2.1): name and goal of the collection on the canvas,
// with new, open, save and export.
import React, { useEffect, useRef, useState } from 'react';
import { FolderOpen, Save, FilePlus, Download, Loader2, Trash2, X, MapPinned, Grid3x3, AlertTriangle, CheckCircle2, Workflow, Upload, FileText } from 'lucide-react';
import { listCollections, deleteCollection, importPackage } from '../../lib/collections';
import { StudyAreaPanel, CoverageModal, WarningsPanel } from './ScopePanels';

const bar = {
  position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)', zIndex: 100,
  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px', background: '#fff',
  border: '1px solid #cbd5e1', borderRadius: 8, boxShadow: '0 2px 6px rgba(0,0,0,0.08)', fontSize: 12,
  maxWidth: 'calc(100% - 340px)',
};
const iconButton = {
  display: 'flex', alignItems: 'center', gap: 4, padding: '5px 8px', border: '1px solid #e2e8f0',
  background: '#f8fafc', borderRadius: 6, cursor: 'pointer', color: '#334155', fontSize: 12, fontWeight: 600,
};
const panel = {
  position: 'absolute', top: 'calc(100% + 6px)', left: 0, width: 380, background: '#fff', border: '1px solid #cbd5e1',
  borderRadius: 8, boxShadow: '0 8px 20px rgba(0,0,0,0.12)', padding: 12, zIndex: 120,
};

function OpenPanel({ onOpen, onClose }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const fileRef = useRef(null);
  const onImport = async (file) => {
    if (!file) return;
    try {
      const out = await importPackage(file);
      if (out.missing_datasets?.length) {
        setError(`Imported; not in this catalog: ${out.missing_datasets.join(', ')}`);
      }
      onOpen(out.collection.id);
    } catch (e) {
      setError(e.message);
    }
  };
  const load = () => listCollections().then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);
  return (
    <div style={panel}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontWeight: 700 }}>
        Open a collection <X size={14} style={{ cursor: 'pointer' }} onClick={onClose} />
      </div>
      <input ref={fileRef} type="file" accept=".zip" style={{ display: 'none' }} onChange={(e) => onImport(e.target.files?.[0])} />
      <button onClick={() => fileRef.current?.click()} style={{ ...iconButton, width: '100%', justifyContent: 'center', marginBottom: 8 }}>
        <Upload size={13} /> Import an exported package (.zip)
      </button>
      {error && <div style={{ color: '#b91c1c' }}>{error}</div>}
      {!items && !error && <Loader2 size={14} className="spin" />}
      {items && items.length === 0 && <div style={{ color: '#64748b' }}>No saved collections yet.</div>}
      <div style={{ maxHeight: 300, overflowY: 'auto' }}>
        {items?.map((c) => (
          <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', borderTop: '1px solid #f1f5f9' }}>
            <button onClick={() => onOpen(c.id)} style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
              <div style={{ fontWeight: 600, color: '#0f172a' }}>{c.name}</div>
              <div style={{ color: '#64748b', fontSize: 11 }}>
                {c.datasets} datasets · {c.integrations} integrations · {(c.updated_at || '').slice(0, 16).replace('T', ' ')}
              </div>
            </button>
            <Trash2 size={13} color="#94a3b8" style={{ cursor: 'pointer' }} title="Delete"
              onClick={async () => { await deleteCollection(c.id); load(); }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ExportPanel({ onExport, onClose, busy }) {
  const [embed, setEmbed] = useState('auto');
  const [formats, setFormats] = useState({ parquet: true, gpkg: true, geojson: false });
  const toggle = (key) => setFormats((f) => ({ ...f, [key]: !f[key] }));
  const chosen = Object.keys(formats).filter((k) => formats[k]);
  return (
    <div style={{ ...panel, left: 'auto', right: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontWeight: 700 }}>
        Export the collection <X size={14} style={{ cursor: 'pointer' }} onClick={onClose} />
      </div>
      <div style={{ color: '#475569', marginBottom: 8, lineHeight: 1.4 }}>
        A zip with a <code>datapackage.json</code> manifest, the data and a README, for QGIS, GeoPandas, R or a notebook.
      </div>
      <div style={{ fontWeight: 600, margin: '8px 0 4px' }}>Datasets</div>
      {[
        ['auto', 'Embed datasets whose license is recorded; reference the rest'],
        ['always', 'Embed every dataset (I have checked the publishers’ terms)'],
        ['never', 'Reference datasets by their source; embed none'],
      ].map(([value, label]) => (
        <label key={value} style={{ display: 'flex', gap: 6, alignItems: 'flex-start', marginBottom: 4, cursor: 'pointer' }}>
          <input type="radio" checked={embed === value} onChange={() => setEmbed(value)} /> {label}
        </label>
      ))}
      <div style={{ fontWeight: 600, margin: '8px 0 4px' }}>Formats</div>
      <div style={{ display: 'flex', gap: 12 }}>
        {[['parquet', 'GeoParquet'], ['gpkg', 'GeoPackage'], ['geojson', 'GeoJSON']].map(([key, label]) => (
          <label key={key} style={{ display: 'flex', gap: 4, cursor: 'pointer' }}>
            <input type="checkbox" checked={formats[key]} onChange={() => toggle(key)} /> {label}
          </label>
        ))}
      </div>
      <button disabled={busy || chosen.length === 0} onClick={() => onExport({ embed, formats: chosen })}
        style={{ ...iconButton, marginTop: 12, width: '100%', justifyContent: 'center', background: '#2563eb', color: '#fff', borderColor: '#2563eb' }}>
        {busy ? <Loader2 size={13} /> : <Download size={13} />} {busy ? 'Preparing…' : 'Download zip'}
      </button>
    </div>
  );
}

export default function CollectionBar({
  collection, dirty, status, onRename, onGoalChange, onNew, onOpen, onSave, onExport, exporting,
  zoneDatasets = [], onStudyAreaChange, coverageDatasets = [], warnings = [],
  hasPlan = false, onRunAll, onReplay, canReplay = false, onDownloadPlan, onReport,
}) {
  const [open, setOpen] = useState(null); // 'open' | 'export' | 'goal' | 'area' | 'checks'
  const [coverageOpen, setCoverageOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(null); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);
  return (
    <div style={bar} ref={ref}>
      <input value={collection.name} onChange={(e) => onRename(e.target.value)} title="Collection name"
        style={{ border: 'none', fontWeight: 700, fontSize: 13, color: '#0f172a', width: 190, outline: 'none' }} />
      <button style={{ ...iconButton, fontWeight: 500, maxWidth: 220, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}
        onClick={() => setOpen(open === 'goal' ? null : 'goal')} title={collection.goal || 'Describe what this collection is for'}>
        {collection.goal ? `Goal: ${collection.goal}` : 'Add a goal'}
      </button>
      <button style={{ ...iconButton, fontWeight: 500 }} onClick={() => setOpen(open === 'area' ? null : 'area')}
        title="Study area: limits integrations, search and exports">
        <MapPinned size={13} /> {collection.study_area ? (collection.study_area.name || 'Study area') : 'No study area'}
      </button>
      <button style={iconButton} onClick={() => setCoverageOpen(true)} title="Where the datasets on the canvas have data">
        <Grid3x3 size={13} />
      </button>
      <button style={{ ...iconButton, color: warnings.length ? '#b45309' : '#16a34a' }}
        onClick={() => setOpen(open === 'checks' ? null : 'checks')}
        title={warnings.length ? `${warnings.length} warning(s)` : 'No problems found'}>
        {warnings.length ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}{warnings.length || ''}
      </button>
      <span style={{ color: dirty ? '#b45309' : '#16a34a', fontSize: 11, minWidth: 64 }}>{status || (dirty ? 'Unsaved' : 'Saved')}</span>
      <button style={iconButton} onClick={onNew} title="New collection"><FilePlus size={13} /></button>
      <button style={iconButton} onClick={() => setOpen(open === 'open' ? null : 'open')} title="Open a collection"><FolderOpen size={13} /></button>
      <button style={iconButton} onClick={onSave} title="Save the collection"><Save size={13} /> Save</button>
      {hasPlan && (
        <button style={iconButton} onClick={() => setOpen(open === 'plan' ? null : 'plan')} title="The plan built from the canvas">
          <Workflow size={13} /> Plan
        </button>
      )}
      <button style={iconButton} onClick={onReport} title="A printable report of the collection: datasets, results, analyses, caveats">
        <FileText size={13} /> Report
      </button>
      <button style={iconButton} onClick={() => setOpen(open === 'export' ? null : 'export')} title="Export the collection"><Download size={13} /> Export</button>
      {open === 'goal' && (
        <div style={panel}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Goal of this collection</div>
          <textarea value={collection.goal} onChange={(e) => onGoalChange(e.target.value)} rows={4}
            placeholder="e.g. Identify neighborhoods where after-school programs are most needed"
            style={{ width: '100%', boxSizing: 'border-box', fontSize: 12, padding: 6, border: '1px solid #cbd5e1', borderRadius: 6 }} />
        </div>
      )}
      {open === 'open' && <OpenPanel onClose={() => setOpen(null)} onOpen={(id) => { setOpen(null); onOpen(id); }} />}
      {open === 'export' && <ExportPanel busy={exporting} onClose={() => setOpen(null)} onExport={onExport} />}
      {open === 'area' && (
        <StudyAreaPanel value={collection.study_area} zoneDatasets={zoneDatasets} onClose={() => setOpen(null)}
          onApply={(spec) => { onStudyAreaChange(spec); setOpen(null); }} />
      )}
      {open === 'checks' && <WarningsPanel warnings={warnings} onClose={() => setOpen(null)} />}
      {open === 'plan' && (
        <div style={{ ...panel, left: 'auto', right: 0, width: 300, display: 'grid', gap: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
            Plan <X size={14} style={{ cursor: 'pointer' }} onClick={() => setOpen(null)} />
          </div>
          <div style={{ color: '#475569', lineHeight: 1.4 }}>
            The steps on the canvas form an urbanweave plan. Recording a run stores its inputs by fingerprint, so it can be replayed and checked later.
          </div>
          <button style={iconButton} onClick={() => { setOpen(null); onRunAll(); }}>Run all steps and record the run</button>
          <button style={{ ...iconButton, opacity: canReplay ? 1 : 0.5 }} disabled={!canReplay} onClick={() => { setOpen(null); onReplay(); }}
            title={canReplay ? 'Rerun the last recorded run from its pinned inputs' : 'Record a run first'}>Replay the last recorded run</button>
          <button style={iconButton} onClick={() => { setOpen(null); onDownloadPlan(); }}>Download plan.json</button>
        </div>
      )}
      {coverageOpen && <CoverageModal datasets={coverageDatasets} studyArea={collection.study_area} onClose={() => setCoverageOpen(false)} />}
    </div>
  );
}
