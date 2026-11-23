// Glyphs for urbanweave's matching methods (docs/REDESIGN.md, section 3.6), drawn on Lucide's 24 px
// grid with a 2 px stroke so they sit with the rest of the interface. Reductions use short labels.
import React from 'react';

const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };
const F = { fill: 'currentColor', stroke: 'none' };

const GLYPHS = {
  contain: (<><rect x="4" y="4" width="16" height="16" rx="1" {...S} /><circle cx="12" cy="12" r="2.5" {...F} /></>),
  centroid: (<><rect x="3" y="3" width="18" height="18" rx="1" {...S} opacity="0.45" />
    <path d="M7 16 L9 7 L17 9 L16 17 Z" {...S} /><path d="M12 10.5v3M10.5 12h3" {...S} /></>),
  representative_point: (<><path d="M4 5h16v14h-6v-8h-4v8H4z" {...S} /><circle cx="7" cy="12" r="2" {...F} /></>),
  nearest: (<><circle cx="5" cy="12" r="2.2" {...F} /><path d="M8 12h6M12 9.5 14.5 12 12 14.5" {...S} />
    <rect x="16" y="8" width="5" height="8" rx="1" {...S} /></>),
  nearest_segment: (<><circle cx="12" cy="6" r="2.2" {...F} /><path d="M3 18h18" {...S} /><path d="M12 9v7" {...S} strokeDasharray="2 2" /></>),
  nearest_node: (<><circle cx="5" cy="6" r="2.2" {...F} /><path d="M16 16 L21 21M16 16 L21 11M16 16 L9 20" {...S} />
    <circle cx="16" cy="16" r="1.8" {...S} /><path d="M7 8l6 6" {...S} strokeDasharray="2 2" /></>),
  within_distance: (<><circle cx="12" cy="12" r="2.2" {...F} /><circle cx="12" cy="12" r="8.5" {...S} strokeDasharray="3 2.5" /></>),
  area_overlap: (<><rect x="3" y="3" width="12" height="12" rx="1" {...S} /><rect x="9" y="9" width="12" height="12" rx="1" {...S} />
    <rect x="9" y="9" width="6" height="6" {...F} opacity="0.6" /></>),
  length_weighted: (<><rect x="6" y="6" width="12" height="12" rx="1" {...S} opacity="0.55" />
    <path d="M2 20 L6 16" {...S} strokeWidth="1.3" /><path d="M6 16 L18 8" {...S} strokeWidth="3" />
    <path d="M18 8 L22 5" {...S} strokeWidth="1.3" /></>),
  largest_overlap: (<><rect x="2" y="5" width="10" height="14" rx="1" {...S} opacity="0.55" />
    <rect x="12" y="5" width="10" height="14" rx="1" {...S} opacity="0.55" />
    <path d="M6 9h10v6H6z" {...S} /><path d="M6 9h6v6H6z" {...F} opacity="0.6" /></>),
  polygon_to_lines: (<><rect x="5" y="5" width="14" height="14" rx="1" {...F} opacity="0.25" />
    <path d="M2 12h3" {...S} strokeWidth="1.3" /><path d="M5 12h14" {...S} strokeWidth="3" /><path d="M19 12h3" {...S} strokeWidth="1.3" /></>),
  gaussian: (<><circle cx="12" cy="12" r="2.2" {...F} /><circle cx="12" cy="12" r="5.5" {...S} opacity="0.65" />
    <circle cx="12" cy="12" r="9" {...S} opacity="0.3" /></>),
  sample: (<><path d="M4 4h16v16H4zM12 4v16M4 12h16" {...S} opacity="0.55" /><rect x="12" y="4" width="8" height="8" {...F} opacity="0.45" />
    <circle cx="16" cy="8" r="1.8" {...F} /></>),
};
const FALLBACK = (<><rect x="3" y="7" width="8" height="10" rx="1" {...S} /><path d="M13 12h7M17 9l3 3-3 3" {...S} /></>);

const REDUCTION_LABELS = {
  count: '#', weighted_count: '#w', sum: 'Σ', density: '/km²', mean: 'x̄', weighted_mean: 'x̄w', median: 'med',
  weighted_median: 'medw', min: 'min', max: 'max', majority: 'mode', shares: '%', first: '1st', last: 'last',
  join: 'join', custom: 'f(x)',
};

export function ReductionLabel({ name, size = 16 }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: size, height: size,
      fontSize: Math.max(8, size * 0.55), fontWeight: 700, color: 'currentColor', fontFamily: 'ui-monospace, Menlo, monospace',
      border: '1.5px solid currentColor', borderRadius: 3, padding: '0 2px', boxSizing: 'border-box', lineHeight: 1,
    }}>{REDUCTION_LABELS[name] || name.slice(0, 3)}</span>
  );
}

export default function MethodIcon({ method, size = 16, title }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}
      style={{ flexShrink: 0 }}>
      {title && <title>{title}</title>}
      {GLYPHS[method] || FALLBACK}
    </svg>
  );
}
