// urbanweave's operator registry, as /api/operators serves it (docs/REDESIGN.md, section 3.2).
import { API_BASE } from '../config/api';

let operatorsPromise = null;
export function getOperators() {
  if (!operatorsPromise) {
    operatorsPromise = fetch(`${API_BASE}/api/operators`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((payload) => { if (!payload) operatorsPromise = null; return payload; });
  }
  return operatorsPromise;
}

let figuresPromise = null;
// Figures from urbanweave's tutorials, exported by tools/export_method_figures.py
export function getFigures() {
  if (!figuresPromise) {
    figuresPromise = fetch('/methods/index.json').then((r) => (r.ok ? r.json() : null)).catch(() => null);
  }
  return figuresPromise;
}

export const humanize = (name = '') => name.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

// The registry entry behind a legacy operator name: {key, spec, info}
export function resolveOperator(payload, kind, name) {
  // Plan steps use urbanweave's own names: kind 'matching' (a method) or 'reduction'.
  if (kind === 'matching') {
    const spec = payload?.registry?.matching?.[name];
    return spec ? { key: name, spec, info: null, isMatching: true } : null;
  }
  if (kind === 'reduction') {
    const spec = payload?.registry?.aggregation?.[name];
    return spec ? { key: name, spec, info: null, isMatching: false } : null;
  }
  const info = payload?.legacy?.[kind]?.[name];
  if (!info) return null;
  const isMatching = kind === 'allocation' || kind === 'zoning_mapping';
  const key = isMatching ? info.method : info.reduction;
  const spec = isMatching ? payload.registry?.matching?.[key] : payload.registry?.aggregation?.[key];
  return { key, spec, info, isMatching };
}

const familyOf = (geometry = '') => geometry.replace(/^Multi/, '');

// Why an operator does not fit (empty string when it does), from the registry.
export function operatorProblem(payload, kind, name, { sourceGeometry, zoneGeometry, targetKind, targetGeometry, method, valueKind, column } = {}) {
  if (kind === 'matching') {
    const spec = payload?.registry?.matching?.[name];
    if (!spec) return '';
    if (sourceGeometry && !(spec.sources || []).map(familyOf).includes(familyOf(sourceGeometry))) return `Does not accept ${sourceGeometry} sources`;
    if (targetKind === 'h3' && !(spec.target_supports || []).includes('h3')) return 'Does not take an H3 grid as target';
    if (targetKind !== 'h3' && targetGeometry && !(spec.targets || []).map(familyOf).includes(familyOf(targetGeometry))) return `Does not accept ${targetGeometry} targets`;
    return '';
  }
  if (kind === 'reduction') {
    const spec = payload?.registry?.aggregation?.[name];
    if (!spec) return '';
    if (spec.serializable === false) return 'Cannot be saved in a plan';
    if (valueKind && !(spec.value_kinds || []).includes(valueKind)) return `Does not suit ${valueKind} values`;
    const provided = payload?.registry?.matching?.[method]?.match_quantities || [];
    const lacking = (spec.requires || []).filter((q) => q !== 'density_denominator' && !provided.includes(q));
    if (method && lacking.length) return `Needs ${lacking.join(', ')}, which ${method} does not provide`;
    if (spec.needs_column && column === '') return 'Needs a column';
    return '';
  }
  if (!payload?.legacy) return '';
  if (kind === 'allocation') {
    const allowed = sourceGeometry && payload.geometry_constraints?.[sourceGeometry];
    return allowed && !allowed.includes(name) ? `Does not accept ${sourceGeometry} sources` : '';
  }
  if (kind === 'zoning_mapping') {
    const resolved = resolveOperator(payload, kind, name);
    if (!resolved?.spec) return '';
    const zone = zoneGeometry || 'Polygon';
    let spec = resolved.spec;
    if (name === 'CentroidZoning' && familyOf(zone) === 'Point') spec = payload.registry.matching.sample;
    const targets = (spec.targets || []).map(familyOf);
    if (!targets.includes(familyOf(zone))) return `Does not map cells onto ${zone} zones`;
    if (!(spec.source_supports || []).includes('h3')) return 'Does not take H3 cells as sources';
  }
  return '';
}
