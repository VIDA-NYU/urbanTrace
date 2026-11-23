// Locate rows without a location from their addresses (backend/geocode.py), a section of the Check
// data dialog. Nothing is sent until the analyst presses Locate: the preview counts the rows and
// addresses locally. Then the addresses go to NYC GeoSearch, each answer is checked against the
// address sent, and the locations that check out are saved and used whenever the dataset loads.
import React, { useEffect, useRef, useState } from 'react';
import { MapPin, Loader2 } from 'lucide-react';
import { geocodePreview, startGeocode, getGeocode, deleteGeocode, geocodeFinished } from '../../lib/cleaning';

const ROLES = [
  ['address', 'Address (number and street)'], ['house', 'House number'], ['street', 'Street'],
  ['borough', 'Borough'], ['zip', 'ZIP code'],
];
const STATUS = {
  different: 'answered with a different address', not_found: 'not found', outside_region: "outside the catalog's region",
  without_house_number: 'without a house number (not sent)',
};

function Summary({ r }) {
  const rs = r.rows_by_status || {};
  return (
    <div style={{ display: 'grid', gap: 2 }}>
      <div><b>{(r.located || 0).toLocaleString()}</b> of {(r.missing || 0).toLocaleString()} rows without a location were located
        {r.saved ? ` (${r.service}, ${String(r.saved).slice(0, 10)})` : ''}.</div>
      {Object.entries(STATUS).filter(([k]) => rs[k]).map(([k, label]) => (
        <div key={k} style={{ color: '#92400e' }}>{rs[k].toLocaleString()} rows {label}</div>
      ))}
      {(r.examples || []).length > 0 && (
        <details style={{ marginTop: 2 }}>
          <summary style={{ cursor: 'pointer', color: '#475569' }}>Examples not used</summary>
          {(r.examples || []).map((e) => (
            <div key={e.address} style={{ fontSize: 11, color: '#475569' }}>
              {e.address} → {e.answer || 'no answer'} <i>({e.why || STATUS[e.status] || e.status})</i>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

export default function LocateFromAddresses({ datasetId, onChanged }) {
  const [preview, setPreview] = useState(null);
  const [spec, setSpec] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [again, setAgain] = useState(false);       // after a run: show the columns to locate again
  const timer = useRef(null);

  // First look: suggested columns, and whatever was saved or is running
  useEffect(() => {
    let alive = true;
    Promise.all([geocodePreview(datasetId), getGeocode(datasetId)]).then(([p, g]) => {
      if (!alive) return;
      setPreview(p); setSpec(p.spec || p.suggested || {});
      if (g.job?.state === 'running') setJob(g.job);
    }).catch((e) => alive && setError(e.message));
    return () => { alive = false; clearTimeout(timer.current); };
  }, [datasetId]);

  // Changing a column recounts (still sending nothing)
  const changeSpec = async (patch) => {
    const next = { ...spec, ...patch };
    if (patch.address) { delete next.house; delete next.street; }
    if (patch.house || patch.street) delete next.address;
    Object.keys(next).forEach((k) => { if (!next[k]) delete next[k]; });
    setSpec(next);
    try { setPreview(await geocodePreview(datasetId, next)); setError(null); } catch (e) { setError(e.message); }
  };

  const poll = async () => {
    try {
      const g = await getGeocode(datasetId);
      setJob(g.job);
      if (g.job?.state === 'running') { timer.current = setTimeout(poll, 1000); return; }
      if (g.job?.state === 'done') {
        setAgain(false);
        await geocodeFinished();
        setPreview(await geocodePreview(datasetId, spec));
        onChanged?.();
      }
    } catch (e) { setError(e.message); }
  };
  const locate = async () => {
    setBusy(true); setError(null);
    try { setJob((await startGeocode(datasetId, spec)).job); timer.current = setTimeout(poll, 800); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    setBusy(true);
    try { await deleteGeocode(datasetId); setJob(null); setPreview(await geocodePreview(datasetId, spec)); onChanged?.(); } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  if (!preview) return error ? <div style={{ color: '#b91c1c' }}>{error}</div> : null;
  const saved = preview.saved;
  const columns = preview.columns || [];
  const hasAddress = spec?.address || (spec?.house && spec?.street);
  const running = job?.state === 'running';
  // Nothing to do: every row has a location and nothing was located before
  if (preview.missing === 0 && !saved) return null;

  const select = (role) => (
    <select value={spec?.[role] || ''} onChange={(e) => changeSpec({ [role]: e.target.value })} disabled={running}
      style={{ height: 24, fontSize: 11, border: '1px solid #cbd5e1', borderRadius: 4, color: '#0f172a', background: '#fff', minWidth: 0 }}>
      <option value="">—</option>
      {columns.map((c) => <option key={c} value={c}>{c}</option>)}
    </select>
  );
  return (
    <div style={{ border: '1px solid #bfdbfe', borderLeft: '3px solid #2563eb', borderRadius: 6, padding: 8, marginTop: 4, background: '#eff6ff', display: 'grid', gap: 6 }}>
      <b style={{ display: 'flex', alignItems: 'center', gap: 6 }}><MapPin size={13} color="#2563eb" /> Locate rows from their addresses</b>
      {saved && !running && (
        <div style={{ background: '#fff', border: '1px solid #dbeafe', borderRadius: 4, padding: 6 }}>
          <Summary r={saved} />
          <div style={{ color: '#475569', marginTop: 4 }}>These locations are used whenever the dataset loads (maps, steps, analyses, exports), which say so.</div>
        </div>
      )}
      {preview.missing > 0 && saved && !running && !again && (
        <button type="button" onClick={() => setAgain(true)}
          style={{ justifySelf: 'start', border: 'none', background: 'none', color: '#2563eb', cursor: 'pointer', padding: 0, fontSize: 11 }}>
          Change the address columns and locate again…
        </button>
      )}
      {preview.missing > 0 && (!saved || running || again) && (
        <>
          <div style={{ color: '#334155' }}>
            {preview.missing.toLocaleString()} of {(preview.rows || 0).toLocaleString()} rows have no location in the file.
            {hasAddress ? '' : ' Choose the columns that hold their address.'}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 6 }}>
            {ROLES.filter(([role]) => (spec?.address ? role !== 'house' && role !== 'street' : true)).map(([role, label]) => (
              <label key={role} style={{ display: 'grid', gap: 2, fontSize: 10, color: '#475569', fontWeight: 600 }}>{label}{select(role)}</label>
            ))}
          </div>
          {hasAddress && (
            <div style={{ color: '#334155', lineHeight: 1.45 }}>
              <b>{preview.addresses.toLocaleString()}</b> distinct addresses with a house number
              {preview.without_house_number ? `; ${preview.without_house_number.toLocaleString()} rows have none and cannot be placed on a building` : ''}.
              {preview.sample?.length ? <span style={{ color: '#64748b' }}> For example: {preview.sample.slice(0, 3).join(' · ')}.</span> : null}
              {preview.too_many && <div style={{ color: '#b91c1c' }}>Too many addresses for one run.</div>}
            </div>
          )}
          {running && (
            <div>
              <div style={{ height: 6, background: '#dbeafe', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{ width: `${job.total ? (100 * job.done) / job.total : 3}%`, height: '100%', background: '#2563eb', transition: 'width 0.4s' }} />
              </div>
              <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                <Loader2 size={11} className="spin" /> {job.total ? `${job.done.toLocaleString()} of ${job.total.toLocaleString()} addresses` : 'Starting…'}
              </div>
            </div>
          )}
          {job?.state === 'failed' && <div style={{ color: '#b91c1c' }}>{job.error}</div>}
          {!preview.enabled && <div style={{ color: '#b45309' }}>Geocoding is turned off on this server (URBANTRACE_GEOCODER=off).</div>}
          {preview.enabled && hasAddress && !running && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 10, color: '#475569', lineHeight: 1.4 }}>
                Sends these addresses to {preview.service} ({new URL(preview.url).host}, NYC Planning&apos;s free geocoder). An answer is used
                only if its house number, street and borough are the ones sent.
              </span>
              <button disabled={busy || !preview.addresses || preview.too_many} onClick={locate}
                style={{ padding: '6px 10px', borderRadius: 6, border: 'none', background: preview.addresses ? '#2563eb' : '#94a3b8', color: '#fff', cursor: preview.addresses ? 'pointer' : 'default', whiteSpace: 'nowrap' }}>
                Locate {preview.addresses.toLocaleString()} addresses
              </button>
            </div>
          )}
        </>
      )}
      {saved && !running && (
        <div><button disabled={busy} onClick={remove}
          style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #fecaca', background: '#fff', color: '#b91c1c', cursor: 'pointer', fontSize: 11 }}>
          Remove located locations</button></div>
      )}
      {error && <div style={{ color: '#b91c1c' }}>{error}</div>}
    </div>
  );
}
