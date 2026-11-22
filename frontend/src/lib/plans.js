// The canvas as an urbanweave plan (docs/REDESIGN.md, phase 4): Dataset nodes are sources or zones
// targets, H3 Grid nodes are grid targets, Step nodes are match + aggregate steps, Calculate nodes are
// derived variables. Results come back in columns; toSpatialData shapes them for the result maps.
import { API_BASE } from '../config/api';
import { normalizeDatasetId } from './collections';

async function post(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof json.detail === 'string' ? json.detail : `HTTP ${response.status}`);
  return json;
}

export const validatePlan = (plan, studyArea) => post('/api/plan/validate', { plan, study_area: studyArea || null });
export const runPlan = (body) => post('/api/plan/run', body);
// The copilot's method and reductions for a step (backend/suggest.py)
export const suggestStep = (body) => post('/api/copilot/suggest-step', body);
export const replayRun = (manifestPath) => post('/api/plan/replay', { manifest_path: manifestPath });

const kindCache = new Map();
export function getValueKindSuggestions(datasetId) {
  if (!kindCache.has(datasetId)) {
    kindCache.set(datasetId, fetch(`${API_BASE}/api/datasets/${encodeURIComponent(datasetId)}/value-kinds`)
      .then((r) => (r.ok ? r.json() : { columns: {} }))
      .then((j) => j.columns || {})
      .catch(() => { kindCache.delete(datasetId); return {}; }));
  }
  return kindCache.get(datasetId);
}

export const KINDS = ['extensive', 'intensive', 'categorical'];
export const KIND_COLORS = { extensive: '#2563eb', intensive: '#d97706', categorical: '#7c3aed' };

// The effective value kind of a dataset node's column: the analyst's choice, else the suggestion.
export const valueKindOf = (datasetData, column) => (
  datasetData?.valueKinds?.[column] || datasetData?.valueKindSuggestions?.[column]?.kind || null
);

const safeName = (text) => (text || 'x').replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'x';

// Inputs of a node by handle: {source: node, target: node, inputs: [nodes]}
export function inputsOf(nodeId, nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const out = { source: null, target: null, inputs: [] };
  for (const e of edges) {
    if (e.target !== nodeId) continue;
    const src = byId.get(e.source);
    if (!src) continue;
    if (e.targetHandle === 'target') out.target = src;
    else if (e.targetHandle === 'source') out.source = src;
    else out.inputs.push(src);
  }
  return out;
}

export const stepIdOf = (node) => safeName(node?.data?.stepId || node?.id);

// A join on a key offers urbanweave's reduce reductions: sum, and ratio_of_sums (sum of one column
// over the sum of another, per zone).
export const KEY_REDUCTIONS = ['sum', 'ratio_of_sums'];
export const keyReductionName = (r) => r.as || (r.method === 'ratio_of_sums'
  ? ['ratio', r.numerator, r.denominator].filter(Boolean).join('_') : ['sum', r.column].filter(Boolean).join('_'));
export function keyReductions(reductions = []) {
  return reductions.filter((r) => KEY_REDUCTIONS.includes(r.method)).map((r) => (r.method === 'ratio_of_sums'
    ? { method: r.method, numerator: r.numerator, denominator: r.denominator, as: safeName(keyReductionName(r)) }
    : { method: 'sum', column: r.column, as: safeName(keyReductionName(r)) }));
}

// Build the plan for the whole canvas, or only for *onlyStepIds* and the steps they depend on.
export function buildPlan(nodes, edges, onlyStepIds = null) {
  const stepNodes = nodes.filter((n) => n.type === 'stepNode');
  const sources = {};
  const targets = {};
  const sourceNameOf = new Map();
  const targetNameOf = new Map();
  const problems = {};

  const nameForSource = (dsNode) => {
    if (sourceNameOf.has(dsNode.id)) return sourceNameOf.get(dsNode.id);
    const stem = normalizeDatasetId(dsNode.data?.id || dsNode.data?.filename);
    let name = safeName(stem);
    while (sources[name] && sources[name].urbantrace?.node !== dsNode.id) name = `${name}_2`;
    sourceNameOf.set(dsNode.id, name);
    sources[name] = { kind: 'vector', columns: {}, urbantrace: { dataset: stem, node: dsNode.id, ...(dsNode.data?.timeWindow ? { time_window: dsNode.data.timeWindow } : {}) } };
    return name;
  };
  const nameForTarget = (tNode, idColumn = null) => {
    const memo = idColumn ? `${tNode.id}#${idColumn}` : tNode.id;
    if (targetNameOf.has(memo)) return targetNameOf.get(memo);
    let name;
    if (tNode.type === 'gridNode') {
      name = safeName(`h3_${tNode.data?.resolution || 9}_${tNode.id.slice(-4)}`);
      targets[name] = { kind: 'h3', resolution: Number(tNode.data?.resolution || 9) };
    } else {
      const stem = normalizeDatasetId(tNode.data?.id || tNode.data?.filename);
      // Zones identified by a code column are a target of their own (their IDs are the codes)
      name = safeName(idColumn ? `zones_${stem}_by_${idColumn}` : `zones_${stem}`);
      targets[name] = { kind: 'zones', urbantrace: { dataset: stem, node: tNode.id, ...(idColumn ? { id_column: idColumn } : {}) } };
    }
    targetNameOf.set(memo, name);
    return name;
  };

  // Steps in dependency order (a step reading another step comes after it).
  const order = [];
  const visiting = new Set();
  const visit = (node) => {
    if (order.includes(node) || visiting.has(node.id)) return;
    visiting.add(node.id);
    const { source } = inputsOf(node.id, nodes, edges);
    if (source?.type === 'stepNode') visit(source);
    visiting.delete(node.id);
    order.push(node);
  };
  const wanted = onlyStepIds ? stepNodes.filter((n) => onlyStepIds.includes(n.id)) : stepNodes;
  wanted.forEach(visit);

  const steps = [];
  for (const node of order) {
    const sid = stepIdOf(node);
    const { source, target } = inputsOf(node.id, nodes, edges);
    const d = node.data || {};
    if (!source || !target) {
      problems[sid] = [`Connect a ${!source ? 'source' : 'target'}.`];
      continue;
    }
    let sourceRef;
    if (source.type === 'stepNode') sourceRef = `@${stepIdOf(source)}`;
    else if (source.type === 'datasetNode') sourceRef = nameForSource(source);
    else { problems[sid] = ['The source must be a dataset or a step.']; continue; }
    if (!['datasetNode', 'gridNode'].includes(target.type)) { problems[sid] = ['The target must be zones or an H3 grid.']; continue; }
    if (d.mode === 'key') {
      const p = [];
      if (source.type !== 'datasetNode') p.push('A join on a key reads a dataset, not a step.');
      if (target.type !== 'datasetNode') p.push('A join on a key needs zones, not an H3 grid.');
      if (!d.keyBy) p.push('Choose the source column that holds the key.');
      if (!d.keyIdColumn) p.push('Choose the zones column that holds the same key.');
      if (p.length) { problems[sid] = p; continue; }
      const aggregate = keyReductions(d.reductions);
      steps.push({ id: sid, source: sourceRef, reduce: { by: d.keyBy, target: nameForTarget(target, d.keyIdColumn), aggregate } });
      const decl = sources[sourceRef].columns;
      decl[d.keyBy] = decl[d.keyBy] || {};
      for (const r of aggregate) {
        for (const col of [r.column, r.numerator, r.denominator].filter(Boolean)) {
          const kind = valueKindOf(source.data, col);
          decl[col] = kind ? { kind } : {};
        }
      }
      continue;
    }
    const targetRef = nameForTarget(target);
    const aggregate = (d.reductions || []).filter((r) => r.method).map((r) => {
      const out = { method: r.method, as: r.as || [r.method, r.column].filter(Boolean).join('_') };
      if (r.column) out.column = r.column;
      if (r.fillEmpty) out.fill_empty = 0;
      if (r.where?.column && r.where?.op) {
        const value = ['isnull', 'notnull'].includes(r.where.op) ? undefined
          : (r.where.value !== '' && !Number.isNaN(Number(r.where.value)) ? Number(r.where.value) : r.where.value);
        out.where = { column: r.where.column, op: r.where.op, ...(value !== undefined ? { value } : {}) };
      }
      return out;
    });
    const params = Object.fromEntries(Object.entries(d.params || {}).filter(([, v]) => v !== null && v !== '' && v !== undefined));
    steps.push({ id: sid, source: sourceRef, match: { method: d.method || 'contain', target: targetRef, ...params }, aggregate });
    // Declare the value kinds of the source columns this step reads.
    if (source.type === 'datasetNode') {
      const decl = sources[sourceRef].columns;
      for (const r of d.reductions || []) {
        for (const col of [r.column, r.where?.column].filter(Boolean)) {
          const kind = valueKindOf(source.data, col);
          decl[col] = kind ? { kind } : {};
        }
      }
    }
  }
  return { plan: { version: 1, sources, targets, steps }, problems, byStepNode: Object.fromEntries(order.map((n) => [n.id, stepIdOf(n)])) };
}

// The derived variables of the canvas (Calculate nodes).
export function buildDerived(nodes, edges) {
  return nodes.filter((n) => n.type === 'calculateNode').map((n) => {
    const { inputs } = inputsOf(n.id, nodes, edges);
    return {
      id: safeName(n.data?.calcId || n.id),
      node: n.id,
      inputs: inputs.filter((i) => i.type === 'stepNode').map(stepIdOf),
      expression: n.data?.expression || '',
      as: safeName(n.data?.as || 'derived'),
      kind: n.data?.kind || 'intensive',
    };
  });
}

// Plan results (columns) in the shape ResultMapNode, CompareMapNode and the provenance panel read.
export function toSpatialData(payload, { stepId, plan, reports, sourceLabel, methodLabel, reductionsByColumn = {}, durationMs, displayColumn, multivariate = true }) {
  const columns = Object.keys(payload.columns || {});
  const primary = displayColumn && columns.includes(displayColumn) ? displayColumn : columns[columns.length - 1];
  const isZoned = payload.target?.kind === 'zones';
  const variables = columns.map((c) => ({
    dataset: sourceLabel || stepId, targetColumn: c, outputName: c, allocation: methodLabel,
    aggregation: reductionsByColumn[c] || null, zoningMapping: null, zoningAggregation: null,
    valueKind: payload.kinds?.[c] || null,
  }));
  const provenance = {
    timestamp: new Date().toISOString(), durationMs, isMultivariate: multivariate && columns.length > 1,
    resolution: payload.target?.resolution || null, zoningEnabled: isZoned,
    targetZones: isZoned ? payload.target?.dataset : null, outputMode: isZoned ? 'zones' : 'grid', variables,
    planStep: stepId,
  };
  const base = {
    status: 'success', engine: 'urbanweave-plan', isMultivariate: multivariate && columns.length > 1, isZoned,
    outputMode: isZoned ? 'zones' : 'grid', provenance, columns: payload.columns, kinds: payload.kinds,
    targetIds: payload.target_ids, primaryColumn: primary,
    reports: reports ? { [stepId]: { allocation: reports } } : null,
    request: { plan_step: stepId, plan },
  };
  if (isZoned) {
    const geojson = payload.geojson && {
      ...payload.geojson,
      features: payload.geojson.features.map((f) => ({ ...f, properties: { ...f.properties, __display_column: primary } })),
    };
    return { ...base, geojson, zone_count: geojson?.features?.length || 0 };
  }
  const data = {};
  payload.target_ids.forEach((id, i) => {
    const vars = Object.fromEntries(columns.map((c) => [c, payload.columns[c][i]]));
    if (columns.every((c) => vars[c] === null || vars[c] === undefined)) return; // missing everywhere
    const value = vars[primary];
    data[id] = { count: typeof value === 'number' ? value : 0, variables: vars, sample_props: {} };
  });
  return { ...base, data, hex_count: Object.keys(data).length };
}
