// The toolbox: nodes that can be dragged onto the canvas (OperationsSidebar maps each type to a node).
import { Calculator, Hexagon, Layers3, Map, Route, Shuffle, Target, Workflow } from 'lucide-react';

export const OPERATION_CATEGORIES = [
  {
    id: 'plan',
    title: 'Plan (urbanweave)',
    color: '#6366f1',
    items: [
      { type: 'step', label: 'Step', icon: Workflow, desc: 'Match a source onto a target and aggregate' },
      { type: 'grid', label: 'H3 Grid', icon: Hexagon, desc: 'A grid target at a chosen resolution' },
      { type: 'streets', label: 'Streets (OSM)', icon: Route, desc: "The study area's street segments or intersections as a target" },
      { type: 'calculate', label: 'Combine & Calculate', icon: Calculator, desc: 'Join steps on a target; derive a variable' },
    ],
  },
  {
    id: 'analysis',
    title: 'Analysis',
    color: '#db2777',
    items: [
      { type: 'sweep', label: 'Sensitivity Sweep', icon: Shuffle, desc: 'How ranks change across resolutions, zones and methods' },
      { type: 'validate', label: 'Validate', icon: Target, desc: 'Coverage and lift against known outcomes' },
      { type: 'dasymetric', label: 'Dasymetric', icon: Layers3, desc: 'Spread zone totals over finer units with priors' },
      { type: 'compare', label: 'Compare Maps', icon: Map, desc: 'Spatial delta between two result maps' },
    ],
  },
];
