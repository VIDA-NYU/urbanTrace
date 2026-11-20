// frontend/src/config/operations.js
import { 
  Layers, 
  Scissors, 
  Combine, 
  Map, 
  Filter, 
  Calculator,
  Network,    // Perfect for our Integration Pipeline
  Workflow,
  Shuffle,
  Target,
  Layers3,
  Hexagon     // Good for H3 operations if available, otherwise use Grid/Map
} from 'lucide-react';

export const OPERATION_CATEGORIES = [
  {
    id: 'plan',
    title: 'Plan (urbanweave)',
    color: '#6366f1',
    items: [
      { type: 'step', label: 'Step', icon: Workflow, desc: 'Match a source onto a target and aggregate' },
      { type: 'grid', label: 'H3 Grid', icon: Hexagon, desc: 'A grid target at a chosen resolution' },
      { type: 'calculate', label: 'Combine & Calculate', icon: Calculator, desc: 'Join steps on a target; derive a variable' },
    ]
  },
  {
    id: 'analysis',
    title: 'Analysis',
    color: '#db2777',
    items: [
      { type: 'sweep', label: 'Sensitivity Sweep', icon: Shuffle, desc: 'How ranks change across resolutions, zones and methods' },
      { type: 'validate', label: 'Validate', icon: Target, desc: 'Coverage and lift against known outcomes' },
      { type: 'dasymetric', label: 'Dasymetric', icon: Layers3, desc: 'Spread zone totals over finer units with priors' },
    ]
  },
  {
    id: 'h3_grid',
    title: 'Classic integration',
    color: '#3b82f6', // Blue to match the integration node
    items: [
      { 
        type: 'integrate', 
        label: 'Spatial Integration', 
        icon: Network, 
        desc: 'Grid then zones, with copilot operator suggestions' 
      },
      // { 
      //   type: 'intersect', 
      //   label: 'H3 Intersect', 
      //   icon: Scissors, 
      //   desc: 'Keep overlapping H3 cells' 
      // },
      // { 
      //   type: 'union', 
      //   label: 'H3 Union', 
      //   icon: Combine, 
      //   desc: 'Combine H3 datasets' 
      // },
      {
        type: 'compare',
        label: 'Compare Maps',
        icon: Map,
        desc: 'Spatial delta between two result maps'
      },
    ]
  }
  // ,
  // {
  //   id: 'geo',
  //   title: 'Vector Tools',
  //   color: '#ec4899', // Pink
  //   items: [
  //     { type: 'buffer', label: 'Buffer', icon: Layers, desc: 'Create zones around features' },
  //   ]
  // },
  // {
  //   id: 'attr',
  //   title: 'Attribute Tools',
  //   color: '#8b5cf6', // Violet
  //   items: [
  //     { type: 'filter', label: 'Filter', icon: Filter, desc: 'Select rows by condition' },
  //     { type: 'join', label: 'Table Join', icon: Map, desc: 'Merge by common column' },
  //     { type: 'calculate', label: 'Calculate Field', icon: Calculator, desc: 'Add new column formula' },
  //   ]
  // }
];