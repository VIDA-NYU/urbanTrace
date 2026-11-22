// A picker for one integration operator, driven by urbanweave's registry (docs/REDESIGN.md, 3.2 and 3.6):
// each choice shows its icon and the urbanweave method it runs; choices that do not fit are disabled
// with the reason; hovering shows a card with the method's figure, summary and assignment.
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';
import MethodIcon, { ReductionLabel } from './MethodIcon';
import { getOperators, getFigures, resolveOperator, operatorProblem, humanize } from '../../lib/registry';

const ASSIGNMENT_TEXT = {
  exclusive: 'Each source goes to at most one target: totals are kept.',
  normalized: 'Each source is split among its targets so its shares add to 1: totals are kept.',
  independent: 'Each target receives its own overlap: overlapping targets can together receive more than the source.',
  replicated: 'Each source is given whole to several targets: totals are not kept.',
  sampling: 'Each target copies the value of the source it falls in.',
};

function useRegistry() {
  const [state, setState] = useState({ payload: null, figures: null });
  useEffect(() => {
    let alive = true;
    Promise.all([getOperators(), getFigures()]).then(([payload, figures]) => alive && setState({ payload, figures }));
    return () => { alive = false; };
  }, []);
  return state;
}

function Glyph({ resolved, size = 14 }) {
  if (!resolved) return <MethodIcon method="" size={size} />;
  return resolved.isMatching ? <MethodIcon method={resolved.key} size={size} /> : <ReductionLabel name={resolved.key} size={size} />;
}

function Card({ resolved, figures, problem, name }) {
  if (!resolved?.spec) return null;
  const figure = resolved.isMatching ? figures?.methods?.[resolved.key] : null;
  const assignment = resolved.spec.assignment;
  return (
    <div style={{ width: 300, background: '#fff', border: '1px solid #cbd5e1', borderRadius: 8, boxShadow: '0 8px 22px rgba(0,0,0,0.15)', padding: 10, fontSize: 11, color: '#334155' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>
        <Glyph resolved={resolved} size={16} /> {humanize(resolved.key)}
        <span style={{ fontWeight: 400, color: '#94a3b8', fontSize: 10 }}>({name})</span>
      </div>
      {figure && <img src={`/methods/${figures.figures[figure].file}`} alt="" style={{ width: '100%', borderRadius: 4, background: '#fcfcfb', margin: '4px 0' }} />}
      <div style={{ lineHeight: 1.4 }}>{resolved.spec.summary}</div>
      {assignment && <div style={{ marginTop: 6, color: '#475569' }}><b>{humanize(assignment)}.</b> {ASSIGNMENT_TEXT[assignment] || ''}</div>}
      {resolved.spec.value_kinds && <div style={{ marginTop: 6 }}>Suits {resolved.spec.value_kinds.join(', ')} values.</div>}
      {problem && <div style={{ marginTop: 6, color: '#b45309' }}>{problem}.</div>}
    </div>
  );
}

export default function OperatorSelect({ kind, value, onChange, options, sourceGeometry, targetKind, targetGeometry, method, valueKind, column, disabled, title, accent = '#cbd5e1', compact }) {
  const { payload, figures } = useRegistry();
  const [open, setOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const [rect, setRect] = useState(null);
  const buttonRef = useRef(null);
  const listRef = useRef(null);

  useLayoutEffect(() => {
    if (open && buttonRef.current) setRect(buttonRef.current.getBoundingClientRect());
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (buttonRef.current?.contains(e.target) || listRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    const onScroll = () => setOpen(false);
    document.addEventListener('mousedown', close);
    window.addEventListener('wheel', onScroll, { passive: true });
    return () => { document.removeEventListener('mousedown', close); window.removeEventListener('wheel', onScroll); };
  }, [open]);

  const ctx = { sourceGeometry, targetKind, targetGeometry, method, valueKind, column };
  // The registry's own list when it has loaded; the passed list is only a fallback.
  const registryKeys = kind === 'matching' ? Object.keys(payload?.registry?.matching || {})
    : kind === 'reduction' ? Object.keys(payload?.registry?.aggregation || {}).filter((k) => payload.registry.aggregation[k].serializable !== false)
      : payload?.[kind];
  // Legacy operator names: the registry's list wins. Plan steps may narrow the list with *options*.
  const native = kind === 'matching' || kind === 'reduction';
  const choices = (native ? (options || registryKeys) : (registryKeys || options)) || [];
  const current = resolveOperator(payload, kind, value);
  const currentProblem = operatorProblem(payload, kind, value, ctx);
  const height = compact ? 20 : 22;
  const hovered = hover ? resolveOperator(payload, kind, hover) : null;

  return (
    <>
      <button ref={buttonRef} type="button" className="nodrag" disabled={disabled} title={title || current?.spec?.summary || value}
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        style={{
          display: 'flex', alignItems: 'center', gap: 5, width: '100%', height, marginTop: 4, padding: '0 6px',
          border: `1px solid ${currentProblem ? '#f59e0b' : accent}`, borderRadius: 4, background: '#fff', cursor: disabled ? 'default' : 'pointer',
          fontSize: compact ? 9 : 10, color: '#334155', boxSizing: 'border-box', opacity: disabled ? 0.65 : 1,
        }}>
        <Glyph resolved={current} size={compact ? 12 : 14} />
        <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {current ? humanize(current.key) : value}
        </span>
        <ChevronDown size={11} color="#94a3b8" />
      </button>
      {open && rect && createPortal(
        <div ref={listRef} className="nodrag nowheel" onMouseLeave={() => setHover(null)}
          style={{ position: 'fixed', left: rect.left, top: rect.bottom + 4, zIndex: 1000, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <div style={{ width: Math.max(rect.width, 210), background: '#fff', border: '1px solid #cbd5e1', borderRadius: 6, boxShadow: '0 8px 22px rgba(0,0,0,0.15)', padding: 4, maxHeight: 320, overflowY: 'auto' }}>
            {choices.map((name) => {
              const resolved = resolveOperator(payload, kind, name);
              const problem = operatorProblem(payload, kind, name, ctx);
              return (
                <button key={name} type="button" disabled={!!problem}
                  onMouseEnter={() => setHover(name)}
                  onClick={() => { onChange(name); setOpen(false); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '5px 6px', border: 'none', borderRadius: 4,
                    background: name === value ? '#eff6ff' : (hover === name ? '#f8fafc' : 'transparent'),
                    cursor: problem ? 'not-allowed' : 'pointer', textAlign: 'left', color: problem ? '#94a3b8' : '#0f172a', fontSize: 11,
                  }}>
                  <Glyph resolved={resolved} size={16} />
                  <span style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{resolved ? humanize(resolved.key) : name}</div>
                    <div style={{ fontSize: 9, color: problem ? '#d97706' : '#94a3b8' }}>{problem || name}</div>
                  </span>
                </button>
              );
            })}
          </div>
          {hovered && <Card resolved={hovered} figures={figures} name={hover} problem={operatorProblem(payload, kind, hover, ctx)} />}
        </div>,
        document.body,
      )}
    </>
  );
}

// The parameters of a matching method, from the registry (types, units, defaults, choices).
export function ParamForm({ method, values = {}, onChange }) {
  const { payload } = useRegistry();
  const resolved = method ? resolveOperator(payload, 'matching', method) : null;
  const entries = Object.entries(resolved?.spec?.params || {});
  if (!entries.length) return null;
  const input = { width: '100%', boxSizing: 'border-box', fontSize: 9, height: 20, border: '1px solid #cbd5e1', borderRadius: 4, padding: '0 4px' };
  return (
    <div className="nodrag" style={{ display: 'grid', gap: 4, marginTop: 4 }}>
      {entries.map(([name, spec]) => {
        const shown = values[name] ?? (name === 'bandwidth' && !method ? 1000 : spec.default ?? '');
        const set = (v) => onChange({ ...values, [name]: v });
        return (
          <label key={name} title={spec.summary || ''} style={{ fontSize: 8, color: '#64748b', fontWeight: 600 }}>
            {humanize(name)}{spec.unit ? ` (${spec.unit})` : ''}{spec.required ? ' *' : ''}
            {spec.choices ? (
              <select value={shown} onChange={(e) => set(e.target.value)} style={input}>
                {spec.choices.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            ) : spec.type === 'boolean' ? (
              <input type="checkbox" checked={!!shown} onChange={(e) => set(e.target.checked)} />
            ) : (
              <input type="number" value={shown ?? ''} min={spec.minimum ?? (spec.exclusive_minimum != null ? spec.exclusive_minimum : undefined)}
                step={spec.type === 'integer' ? 1 : 'any'} onChange={(e) => set(e.target.value === '' ? null : Number(e.target.value))} style={input} />
            )}
          </label>
        );
      })}
    </div>
  );
}
