import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { 
  ReactFlow, Background, Controls, useReactFlow, ReactFlowProvider, 
  addEdge, applyNodeChanges, applyEdgeChanges 
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Link, Unlink } from 'lucide-react';

// 1. Import components
import DatasetNode from './nodes/DatasetNode'; 
import OperationNode from './nodes/OperationNode';
import IntegrationNode from './nodes/IntegrationNode'; // <--- NEW Import
import DatasetDetailsModal from '../catalog/DatasetDetailsModal'; 
import ResultMapNode from './nodes/ResultMapNode'; // Add this at the top
import CompareMapNode from './nodes/CompareMapNode';
import FloatingCopilotInput from '../copilot/FloatingCopilotInput';
import { API_BASE } from '../../config/api';
import CollectionBar from '../collection/CollectionBar';
import {
  getCollection, createCollection, updateCollection, exportCollection,
  serializeCanvas, collectionDatasets, collectionIntegrations, downloadBlob,
} from '../../lib/collections';
import { checkCollection, resolveStudyArea } from '../../lib/scope';
import { GridNode, StepNode, CalculateNode } from './nodes/PlanNodes';
import { SweepNode, ValidateNode, DasymetricNode } from './nodes/AnalysisNodes';
import { runSweep, runValidation, runDasymetric, reportUrl, METHODS_FOR } from '../../lib/analysis';
import {
  buildPlan, buildDerived, validatePlan, runPlan, replayRun, toSpatialData, inputsOf, stepIdOf, valueKindOf,
  getValueKindSuggestions,
} from '../../lib/plans';

// Value kind of a step's output column, from the reduction that made it (as urbanweave assigns it)
const OUTPUT_KIND = {
  count: 'extensive', weighted_count: 'extensive', density: 'intensive', mean: 'intensive', weighted_mean: 'intensive',
  median: 'intensive', weighted_median: 'intensive', majority: 'categorical', shares: 'intensive',
};

// The nodes connected to one input handle of a node
const edgesInto = (nodeId, handle, nodes, edges) => edges
  .filter((e) => e.target === nodeId && e.targetHandle === handle)
  .map((e) => nodes.find((n) => n.id === e.source))
  .filter(Boolean);

const stemOf = (node) => String(node?.data?.id || node?.data?.filename || '').replace(/\.geojson$/i, '');

// The configuration of an analysis node, as the collection records it and the API takes it
function analysisConfig(node, nodes, edges) {
  const d = node.data || {};
  if (node.type === 'sweepNode') {
    const step = edgesInto(node.id, 'step', nodes, edges)[0];
    if (!step || !d.column) return null;
    const variants = [
      ...(d.resolutions || []).map((r) => ({ via: { kind: 'h3', resolution: r } })),
      ...(d.zoneAlternatives || []).map((z) => ({ via: { kind: 'zones', dataset: z } })),
      ...(d.methods || []).map((m) => ({ method: m })),
    ];
    return { step: stepIdOf(step), column: d.column, variants, top_share: d.topShare ?? 0.2 };
  }
  if (node.type === 'validateNode') {
    const res = edgesInto(node.id, 'result', nodes, edges)[0];
    const out = edgesInto(node.id, 'outcomes', nodes, edges)[0];
    if (!res || !out || !d.column) return null;
    const quantiles = String(d.quantiles || '0.5, 0.6, 0.7').split(/[,\s]+/).map(Number).filter((q) => q > 0 && q < 1);
    const derivedId = res.type === 'calculateNode' ? buildDerived(nodes, edges).find((x) => x.node === res.id)?.id : null;
    return { ...(derivedId ? { derived_id: derivedId } : { step: stepIdOf(res) }), column: d.column,
      outcomes: { dataset: stemOf(out), ...(out.data?.timeWindow ? { time_window: out.data.timeWindow } : {}) }, quantiles };
  }
  if (node.type === 'dasymetricNode') {
    const z = edgesInto(node.id, 'zones', nodes, edges)[0];
    const t = edgesInto(node.id, 'target', nodes, edges)[0];
    const priors = edgesInto(node.id, 'prior', nodes, edges);
    if (!z || !t || !priors.length || !(d.totals || []).length) return null;
    return {
      zones: { dataset: stemOf(z), totals: d.totals },
      target: t.type === 'gridNode' ? { kind: 'h3', resolution: Number(t.data?.resolution || 9) } : { kind: 'zones', dataset: stemOf(t) },
      priors: priors.map((p) => ({ dataset: stemOf(p), column: d.priorWeights?.[p.id]?.column || null, weight: d.priorWeights?.[p.id]?.weight ?? 1 })),
      normalize: d.normalize === 'none' ? null : (d.normalize || 'share'), fallback: d.fallback || 'area',
    };
  }
  return null;
}

// The analyses of the canvas: analysis nodes, and priority indexes set on plan results
function collectionAnalyses(nodes, edges) {
  const out = [];
  const names = { sweepNode: 'sweep', validateNode: 'validation', dasymetricNode: 'dasymetric' };
  for (const n of nodes) {
    if (names[n.type]) {
      const config = analysisConfig(n, nodes, edges);
      if (!config) continue;
      if (config.derived_id) { config.derived = config.derived_id; delete config.derived_id; }
      out.push({ id: n.id, kind: names[n.type], name: n.data?.name || `${names[n.type]} ${n.id.slice(-4)}`, config });
    }
    if (n.type === 'resultMapNode' && n.data?.priority?.variables?.length && n.data?.spatialData?.request?.plan_step) {
      out.push({ id: `priority_${n.id}`, kind: 'priority', name: `Priority: ${n.data.spatialData.request.plan_step}`,
        config: { result: n.data.spatialData.request.plan_step, ...n.data.priority } });
    }
  }
  return out;
}

const EMPTY_COLLECTION = {
  id: null, name: 'Untitled collection', goal: '', notes: '', study_area: null, analyses: [], integrations: [],
};

const CanvasInner = ({ sidebarCollapsed, onLogActivity, highlightedLogTs, focusedLogTs, onTraceLineage, onActiveLogTimestampsChange, onStudyAreaResolved }) => {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [viewingDataset, setViewingDataset] = useState(null);
  
  // GLOBAL VIEWPORT SYNC: Linked camera states for comparative analysis
  const [isMapSyncEnabled, setIsMapSyncEnabled] = useState(false);
  const [globalViewState, setGlobalViewState] = useState({
    longitude: -73.98,
    latitude: 40.75,
    zoom: 11,
    pitch: 0,
    bearing: 0
  });
  const [hoveredCompareFeatureId, setHoveredCompareFeatureId] = useState(null);
  const [hoveredCompareFeatureType, setHoveredCompareFeatureType] = useState(null);
  const [availableDatasets, setAvailableDatasets] = useState([]);
  const [copilotSuggestions, setCopilotSuggestions] = useState([]);
  const [autoSuggestRequest, setAutoSuggestRequest] = useState(null);

  // COLLECTION (redesign section 2.1): what is saved, reopened and exported
  const [collection, setCollection] = useState(EMPTY_COLLECTION);
  const [savedSnapshot, setSavedSnapshot] = useState(null);
  const [collectionStatus, setCollectionStatus] = useState('');
  const [exporting, setExporting] = useState(false);
  const [warnings, setWarnings] = useState([]);
  const [planProblems, setPlanProblems] = useState({});
  const [lastManifestPath, setLastManifestPath] = useState(null);

  const { screenToFlowPosition, getNodes, getEdges } = useReactFlow();
  
  // SIDEBAR RESIZE FIX: Trigger React Flow resize recalculation after sidebar transition
  useEffect(() => {
    // Wait for CSS transition to complete (300ms), then trigger resize
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 320);
    return () => clearTimeout(timer);
  }, [sidebarCollapsed]);

  const normalizeDatasetId = useCallback((value) => {
    if (typeof value !== 'string') return '';
    let normalized = value.trim();
    if (normalized.endsWith('.geojson')) {
      normalized = normalized.slice(0, -8);
    }
    return normalized;
  }, []);

  const isNumericColumn = useCallback((column) => {
    if (!column || typeof column !== 'object') return false;
    return (
      ['Integer', 'Float', 'http://schema.org/Integer', 'http://schema.org/Float'].includes(column.structural_type)
      || column.mean !== undefined
    );
  }, []);

  const fetchAvailableDatasets = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/datasets`);
      if (!response.ok) {
        throw new Error(`Failed to fetch datasets: HTTP ${response.status}`);
      }
      const payload = await response.json();
      const datasets = Array.isArray(payload?.datasets) ? payload.datasets : [];
      setAvailableDatasets(datasets);
      return datasets;
    } catch (error) {
      console.error('Failed to load datasets for copilot validation:', error);
      return [];
    }
  }, []);

  useEffect(() => {
    fetchAvailableDatasets();
  }, [fetchAvailableDatasets]);

  const findDatasetById = useCallback((datasetId, datasets = availableDatasets) => {
    const normalizedTarget = normalizeDatasetId(datasetId);
    if (!normalizedTarget) return null;

    return (
      datasets.find((dataset) => {
        const candidates = [
          dataset?.id,
          dataset?.filename,
          dataset?.metadata?.name,
          dataset?.name,
        ]
          .map(normalizeDatasetId)
          .filter(Boolean);
        return candidates.includes(normalizedTarget);
      }) || null
    );
  }, [availableDatasets, normalizeDatasetId]);

  const resolveValidColorByForDataset = useCallback((dataset, requestedColorBy) => {
    if (typeof requestedColorBy !== 'string') return '';
    const normalizedRequested = requestedColorBy.trim();
    if (!normalizedRequested) return '';

    const columns = Array.isArray(dataset?.metadata?.columns) ? dataset.metadata.columns : [];
    const numericColumns = columns.filter(isNumericColumn);
    const match = numericColumns.find((column) => {
      const columnName = typeof column?.name === 'string' ? column.name : '';
      return columnName.toLowerCase() === normalizedRequested.toLowerCase();
    });
    return match?.name || '';
  }, [isNumericColumn]);

  const getSuggestionKey = useCallback((suggestion) => {
    if (!suggestion || typeof suggestion !== 'object') return '';

    const explicitId = typeof suggestion.id === 'string' ? suggestion.id.trim() : '';
    if (explicitId) return explicitId;

    const action = (suggestion.action && typeof suggestion.action === 'object')
      ? suggestion.action
      : {};
    const suggestionType = (
      typeof suggestion.type === 'string' && suggestion.type.trim()
        ? suggestion.type.trim()
        : (typeof action.type === 'string' ? action.type.trim() : 'suggestion')
    );
    const datasetId = normalizeDatasetId(suggestion.datasetId || action.datasetId);
    const colorByValue = suggestion.colorBy || action.colorBy;
    const colorBy = typeof colorByValue === 'string' ? colorByValue.trim() : '';

    return `${suggestionType}:${datasetId}:${colorBy || 'default'}`;
  }, [normalizeDatasetId]);

  const normalizeCopilotSuggestion = useCallback((rawSuggestion) => {
    if (!rawSuggestion || typeof rawSuggestion !== 'object') return null;

    const rawAction = (rawSuggestion.action && typeof rawSuggestion.action === 'object')
      ? rawSuggestion.action
      : {};
    const actionType = (
      typeof rawAction.type === 'string' && rawAction.type.trim()
        ? rawAction.type.trim()
        : (typeof rawSuggestion.type === 'string' ? rawSuggestion.type.trim() : '')
    );

    if (actionType !== 'add_dataset_node') {
      return null;
    }

    const datasetId = normalizeDatasetId(rawSuggestion.datasetId || rawAction.datasetId);
    if (!datasetId) {
      return null;
    }

    const colorByValue = rawSuggestion.colorBy || rawAction.colorBy;
    const colorBy = typeof colorByValue === 'string' ? colorByValue.trim() : '';
    const reason = typeof rawSuggestion.reason === 'string' ? rawSuggestion.reason.trim() : '';
    const dataset = findDatasetById(datasetId);
    const metadata = (dataset?.metadata && typeof dataset.metadata === 'object') ? dataset.metadata : {};
    const displayName = metadata?.name || dataset?.name || datasetId;

    const suggestion = {
      ...rawSuggestion,
      id: getSuggestionKey(rawSuggestion),
      type: 'add_dataset_node',
      status: typeof rawSuggestion.status === 'string' && rawSuggestion.status.trim()
        ? rawSuggestion.status.trim()
        : 'pending',
      title: typeof rawSuggestion.title === 'string' && rawSuggestion.title.trim()
        ? rawSuggestion.title.trim()
        : `Add ${displayName}`,
      datasetId,
      displayName,
      geometryType: metadata?.geometricType || '',
      rowCount: metadata?.nb_rows,
      action: {
        type: 'add_dataset_node',
        datasetId,
        ...(colorBy ? { colorBy } : {}),
      },
    };

    if (colorBy) {
      suggestion.colorBy = colorBy;
    }
    if (reason) {
      suggestion.reason = reason;
    }

    return suggestion;
  }, [findDatasetById, getSuggestionKey, normalizeDatasetId]);

  const queueAutoSuggestRequest = useCallback((dataset) => {
    if (!dataset || typeof dataset !== 'object') {
      return;
    }

    const datasetId = normalizeDatasetId(
      dataset.id || dataset.filename || dataset.metadata?.name || dataset.name
    );
    if (!datasetId) {
      return;
    }

    const displayName = dataset.metadata?.name || dataset.name || datasetId;
    setAutoSuggestRequest({
      id: `auto_suggest_${datasetId}_${Date.now()}`,
      datasetId,
      displayName,
      trigger: 'manual_dataset_add',
      timestamp: Date.now(),
    });
  }, [normalizeDatasetId]);

  // 2. Register the custom node types
  const nodeTypes = useMemo(() => ({
    datasetNode: DatasetNode,
    operationNode: OperationNode,
    integrationNode: IntegrationNode, // <--- NEW Registration
    resultMapNode: ResultMapNode,
    compareMapNode: CompareMapNode,
    gridNode: GridNode,
    stepNode: StepNode,
    calculateNode: CalculateNode,
    sweepNode: SweepNode,
    validateNode: ValidateNode,
    dasymetricNode: DasymetricNode,
  }), []);

  // A Result Map's priority index (weights, directions, rationale), recorded as an analysis
  const handlePriorityChange = useCallback((nodeId, priority) => {
    setNodes((nds) => nds.map((n) => (n.id === nodeId && JSON.stringify(n.data?.priority) !== JSON.stringify(priority)
      ? { ...n, data: { ...n.data, priority } } : n)));
  }, []);

  const handleCompareHover = useCallback((featureId, featureType) => {
    setHoveredCompareFeatureId(featureId || null);
    setHoveredCompareFeatureType(featureId ? featureType : null);
  }, []);

  const handleDeleteNode = useCallback((nodeId) => {
    setEdges(eds => eds.filter(edge => edge.source !== nodeId && edge.target !== nodeId));
    setNodes(nds => {
      const deletedNode = nds.find(node => node.id === nodeId);

      return nds
        .filter(node => node.id !== nodeId)
        .map(node => {
          if (!deletedNode || !node?.data) return node;

          // Keep IntegrationNode in sync when a dataset node is deleted.
          if (node.type === 'integrationNode' && deletedNode.type === 'datasetNode') {
            const nextConnectedDatasets = Array.isArray(node.data.connectedDatasets)
              ? node.data.connectedDatasets.filter(dataset => dataset.nodeId !== nodeId)
              : [];

            const nextData = {
              ...node.data,
              connectedDatasets: nextConnectedDatasets
            };

            const deletedFilename = deletedNode.data?.filename;
            if (nextConnectedDatasets.length === 0) {
              nextData.connectedDatasetFilename = null;
              nextData.connectedDatasetMetadata = null;
            }

            if (deletedFilename && node.data.connectedZoneFilename === deletedFilename) {
              nextData.connectedZoneFilename = null;
              nextData.connectedZoneMetadata = null;
            }

            return {
              ...node,
              data: nextData
            };
          }

          // Keep CompareMapNode in sync when a result map node is deleted.
          if (node.type === 'compareMapNode' && deletedNode.type === 'resultMapNode') {
            const nextConnectedResults = Array.isArray(node.data.connectedResults)
              ? node.data.connectedResults.filter(result => result.nodeId !== nodeId)
              : [];

            return {
              ...node,
              data: {
                ...node.data,
                connectedResults: nextConnectedResults
              }
            };
          }

          return node;
        });
    });
  }, []);

  const hydrateCompareNodes = useCallback((nodeList, edgeList) => {
    return nodeList.map(node => {
      if (node.type !== 'compareMapNode') return node;

      const connectedResults = edgeList
        .filter(e => e.target === node.id)
        .map(e => nodeList.find(n => n.id === e.source))
        .filter(sourceNode => sourceNode?.type === 'resultMapNode')
        .slice(0, 2)
        .map(sourceNode => ({
          nodeId: sourceNode.id,
          label: sourceNode.data?.name || 'Result Map',
          comparePayload: sourceNode.data?.comparePayload || null,
          spatialData: sourceNode.data?.spatialData || null
        }));

      const prevConnections = node.data?.connectedResults || [];
      const sameConnections =
        prevConnections.length === connectedResults.length &&
        prevConnections.every((prev, idx) => {
          const next = connectedResults[idx];
          return (
            prev?.nodeId === next?.nodeId &&
            prev?.label === next?.label &&
            prev?.comparePayload === next?.comparePayload &&
            prev?.spatialData === next?.spatialData
          );
        });
      const sameHover = node.data?.hoveredCompareFeatureId === hoveredCompareFeatureId && node.data?.hoveredCompareFeatureType === hoveredCompareFeatureType;
      const sameSync = node.data?.isMapSyncEnabled === isMapSyncEnabled && node.data?.globalViewState === globalViewState;
      const sameFns =
        node.data?.onCompareHover === handleCompareHover &&
        node.data?.onGlobalViewStateChange === setGlobalViewState &&
        node.data?.onDeleteNode === handleDeleteNode;

      if (sameConnections && sameHover && sameSync && sameFns) {
        return node;
      }

      return {
        ...node,
        data: {
          ...node.data,
          connectedResults,
          hoveredCompareFeatureId,
          hoveredCompareFeatureType,
          onCompareHover: handleCompareHover,
          isMapSyncEnabled,
          globalViewState,
          onGlobalViewStateChange: setGlobalViewState,
          onDeleteNode: handleDeleteNode
        }
      };
    });
  }, [globalViewState, handleCompareHover, handleDeleteNode, hoveredCompareFeatureId, hoveredCompareFeatureType, isMapSyncEnabled]);

  const onNodesChange = useCallback((changes) => setNodes((nds) => applyNodeChanges(changes, nds)), []);
  
  // CONNECTION-DRIVEN STATE: Clear node data when edges are deleted
  const onEdgesChange = useCallback((changes) => {
    // Handle edge removals BEFORE applying changes (so we can still access the edge data)
    const removals = changes.filter(change => change.type === 'remove');
    
    if (removals.length > 0) {
      setEdges((currentEdges) => {
        // Find edge data BEFORE they're removed
        const edgesToRemove = removals
          .map(r => currentEdges.find(e => e.id === r.id))
          .filter(Boolean);
        
        if (edgesToRemove.length > 0) {
          // Clear connected data from target nodes
          setNodes((nds) => {
            return nds.map(node => {
              const removedEdgesForNode = edgesToRemove.filter(e => e.target === node.id);
              
              if (removedEdgesForNode.length === 0) return node;
              
              let updatedData = { ...node.data };
              
              removedEdgesForNode.forEach(edge => {
                if (edge.targetHandle === 'zones') {
                  // Zone connection removed - clear zone data
                  updatedData.connectedZoneFilename = null;
                  updatedData.connectedZoneMetadata = null;
                } else {
                  // Source dataset connection removed - remove from connectedDatasets
                  const sourceNodeId = edge.source;
                  if (updatedData.connectedDatasets) {
                    updatedData.connectedDatasets = updatedData.connectedDatasets.filter(
                      d => d.nodeId !== sourceNodeId
                    );
                    // Update legacy single-dataset field if array is empty
                    if (updatedData.connectedDatasets.length === 0) {
                      updatedData.connectedDatasetFilename = null;
                      updatedData.connectedDatasetMetadata = null;
                    }
                  }
                }
              });
              
              return { ...node, data: updatedData };
            });
          });
        }
        
        // Now apply the edge changes (remove the edges)
        return applyEdgeChanges(changes, currentEdges);
      });
    } else {
      // No removals - just apply changes normally
      setEdges((eds) => applyEdgeChanges(changes, eds));
    }
  }, [setEdges, setNodes]);

  // 3. The Handler for when the Integration API finishes
  const handleIntegrationComplete = useCallback((sourceNodeId, integrationData) => {
    // 1. Generate unique IDs OUTSIDE the state setters. 
    // Using randomUUID prevents identical millisecond collisions.
    const uniqueId = typeof crypto !== 'undefined' && crypto.randomUUID 
      ? crypto.randomUUID().slice(0, 8) 
      : Date.now(); 
      
    const resultNodeId = `result_${uniqueId}`;
    const newEdgeId = `e-${sourceNodeId}-${resultNodeId}`;

    // 2. Safely update nodes
    setNodes((nds) => {
      const sourceNode = nds.find(n => n.id === sourceNodeId);
      if (!sourceNode) return nds;

      const resultNode = {
        id: resultNodeId,
        type: 'resultMapNode', 
        position: { x: sourceNode.position.x + 350, y: sourceNode.position.y },
        data: {
          name: 'H3 Integration Result',
          isResult: true, 
          spatialData: integrationData,
          // GLOBAL VIEWPORT SYNC: Pass sync props to ResultMapNode
          isMapSyncEnabled,
          globalViewState,
          onGlobalViewStateChange: setGlobalViewState,
          onDeleteNode: handleDeleteNode
        }
      };

      return [...nds, resultNode];
    });

    // 3. Safely update edges as a completely separate operation
    setEdges((eds) => {
      // Bulletproof check: If this edge ID already exists, don't add it again
      if (eds.some(e => e.id === newEdgeId)) return eds;

      return [
        ...eds,
        { 
          id: newEdgeId, 
          source: sourceNodeId, 
          target: resultNodeId, 
          animated: true, 
          style: { stroke: '#3b82f6', strokeWidth: 2 } 
        }
      ];
    });
  }, [setEdges, setNodes, isMapSyncEnabled, globalViewState, setGlobalViewState, handleDeleteNode]); // Ensure setNodes is in the dependency array

  // GLOBAL VIEWPORT SYNC: Update existing ResultMapNodes and DatasetNodes when sync state changes
  useEffect(() => {
    setNodes((nds) => {
      let hasChanges = false;

      const nextNodes = nds.map((node) => {
        if (node.type !== 'resultMapNode' && node.type !== 'datasetNode') {
          return node;
        }

        const data = node.data || {};
        const needsUpdate =
          data.isMapSyncEnabled !== isMapSyncEnabled
          || data.globalViewState !== globalViewState
          || data.onGlobalViewStateChange !== setGlobalViewState
          || data.onDeleteNode !== handleDeleteNode;

        if (!needsUpdate) {
          return node;
        }

        hasChanges = true;
        return {
          ...node,
          data: {
            ...data,
            isMapSyncEnabled,
            globalViewState,
            onGlobalViewStateChange: setGlobalViewState,
            onDeleteNode: handleDeleteNode
          }
        };
      });

      return hasChanges ? nextNodes : nds;
    });
  }, [isMapSyncEnabled, globalViewState, handleDeleteNode]);

  useEffect(() => {
    setNodes(nds => hydrateCompareNodes(nds, edges));
  }, [edges, hydrateCompareNodes]);

  // CROSS-CANVAS CONNECTION: Push highlightedLogTs, focusedLogTs, and onTraceLineage to all ResultMapNodes
  useEffect(() => {
    setNodes(nds => nds.map(node => {
      if (node.type === 'resultMapNode') {
        return {
          ...node,
          data: {
            ...node.data,
            highlightedLogTs,
            focusedLogTs,
            onTraceLineage,
            hoveredCompareFeatureId,
            hoveredCompareFeatureType,
            onCompareDataReady: handleCompareDataReady,
            onPriorityChange: handlePriorityChange,
            onDeleteNode: handleDeleteNode
          }
        };
      }
      return node;
    }));
  }, [highlightedLogTs, focusedLogTs, onTraceLineage, hoveredCompareFeatureId, hoveredCompareFeatureType, handleDeleteNode, handlePriorityChange]);

  const handleCompareDataReady = useCallback((nodeId, comparePayload) => {
    setNodes(nds => {
      const updatedNodes = nds.map(node => {
        if (node.id !== nodeId) return node;
        if (node.data?.comparePayload === (comparePayload || null)) {
          return node;
        }
        return {
          ...node,
          data: {
            ...node.data,
            comparePayload: comparePayload || null
          }
        };
      });
      return hydrateCompareNodes(updatedNodes, edges);
    });
  }, [edges, hydrateCompareNodes]);

  useEffect(() => {
    if (!onActiveLogTimestampsChange) return;

    const activeTimestamps = nodes
      .filter(node => node.type === 'resultMapNode')
      .map(node => node.data?.spatialData?.provenance?.timestamp)
      .filter(Boolean);

    onActiveLogTimestampsChange(activeTimestamps);
  }, [nodes, onActiveLogTimestampsChange]);


  // 4. Update onConnect to pass data between nodes
  const onConnect = useCallback((params) => {
    // Get current nodes state OUTSIDE of setNodes callback for early validation
    const currentNodes = getNodes();
    const sourceNode = currentNodes.find(n => n.id === params.source);
    const targetNode = currentNodes.find(n => n.id === params.target);

    if (targetNode?.type === 'compareMapNode') {
      if (sourceNode?.type !== 'resultMapNode') {
        alert('Compare Map only accepts Result Map nodes as inputs.');
        return;
      }

      const currentEdges = getEdges();
      const existingInputs = currentEdges.filter(e => e.target === params.target);
      const alreadyConnected = existingInputs.some(e => e.source === params.source);

      if (alreadyConnected) return;
      if (existingInputs.length >= 2) {
        alert('Compare Map accepts only two input result maps.');
        return;
      }

      setEdges((eds) => addEdge({
        ...params,
        animated: true,
        style: { stroke: '#4b5563', strokeWidth: 2 }
      }, eds));
      return;
    }

    // ANALYSIS NODES (redesign phase 5): which nodes each input handle takes, and whether it takes several
    const ANALYSIS_INPUTS = {
      sweepNode: { step: [['stepNode'], false] },
      validateNode: { result: [['stepNode', 'calculateNode'], false], outcomes: [['datasetNode'], false] },
      dasymetricNode: { zones: [['datasetNode'], false], target: [['gridNode', 'datasetNode'], false], prior: [['datasetNode'], true] },
    };
    if (ANALYSIS_INPUTS[targetNode?.type]) {
      const rule = ANALYSIS_INPUTS[targetNode.type][params.targetHandle];
      if (!rule || !rule[0].includes(sourceNode?.type)) return;
      setEdges((eds) => {
        const kept = rule[1]
          ? eds.filter((e) => !(e.target === params.target && e.source === params.source && e.targetHandle === params.targetHandle))
          : eds.filter((e) => !(e.target === params.target && e.targetHandle === params.targetHandle));
        return addEdge({ ...params, style: { stroke: '#db2777', strokeWidth: 2 } }, kept);
      });
      return;
    }

    // PLAN NODES (redesign phase 4): a step takes one source and one target; Calculate takes steps.
    if (targetNode?.type === 'stepNode' || targetNode?.type === 'calculateNode') {
      const handle = params.targetHandle;
      let ok = false;
      if (targetNode.type === 'stepNode' && handle === 'source') ok = ['datasetNode', 'stepNode'].includes(sourceNode?.type) && sourceNode.id !== targetNode.id;
      if (targetNode.type === 'stepNode' && handle === 'target') ok = ['datasetNode', 'gridNode'].includes(sourceNode?.type);
      if (targetNode.type === 'calculateNode') ok = sourceNode?.type === 'stepNode';
      if (!ok) return;
      setEdges((eds) => {
        const kept = targetNode.type === 'stepNode'
          ? eds.filter((e) => !(e.target === params.target && e.targetHandle === handle)) // one per handle
          : eds.filter((e) => !(e.target === params.target && e.source === params.source));
        return addEdge({ ...params, animated: false, style: { stroke: handle === 'target' ? '#0ea5e9' : '#6366f1', strokeWidth: 2 } }, kept);
      });
      return;
    }

    // Early return if not a valid connection to IntegrationNode
    if (targetNode?.type !== 'integrationNode' || !sourceNode?.data?.filename) {
      return;
    }

    const handleId = params.targetHandle;

    // SINGLE ZONE RESTRICTION: Check BEFORE calling setNodes
    if (handleId === 'zones' && targetNode.data.connectedZoneFilename) {
      alert('Only one zoning dataset can be connected at a time. Please disconnect the current zone dataset first.');
      return; // Exit early - don't call setNodes or setEdges
    }

    // Now handle the valid connection
    if (handleId === 'zones') {
      // Zone connection - add edge and update node data
      setEdges((eds) => addEdge(params, eds));
      setNodes((nds) => nds.map(node => {
        if (node.id === params.target) {
          return {
            ...node,
            data: {
              ...node.data,
              connectedZoneFilename: sourceNode.data.filename,
              connectedZoneMetadata: sourceNode.data.metadata
            }
          };
        }
        return node;
      }));
    } else {
      // Source dataset connection - MULTIVARIATE SUPPORT
      const existingDatasets = targetNode.data.connectedDatasets || [];
      
      // Check if this dataset is already connected
      const alreadyConnected = existingDatasets.some(d => d.nodeId === sourceNode.id);
      if (alreadyConnected) {
        return; // Don't add duplicate
      }

      // Add the edge
      setEdges((eds) => addEdge(params, eds));
      
      // CONTEXTUAL STATE INHERITANCE:
      // Pass upstream node's selected column to pre-populate Variable Card
      const inheritedColumn = sourceNode.data.selectedColumn || sourceNode.data.colorBy || '';
      
      const newDataset = {
        id: `var_${Date.now()}`,
        nodeId: sourceNode.id,
        filename: sourceNode.data.filename,
        metadata: sourceNode.data.metadata,
        inheritedColumn: inheritedColumn,
        timeWindow: sourceNode.data.timeWindow || null
      };
      
      setNodes((nds) => nds.map(node => {
        if (node.id === params.target) {
          return {
            ...node,
            data: {
              ...node.data,
              // Keep legacy single-dataset fields for backward compatibility
              connectedDatasetFilename: sourceNode.data.filename,
              connectedDatasetMetadata: sourceNode.data.metadata,
              // NEW: Array of all connected datasets for multivariate
              connectedDatasets: [...existingDatasets, newDataset]
            }
          };
        }
        return node;
      }));
    }
  }, [setNodes, setEdges, getNodes, getEdges]);

  const handleShowInfo = useCallback((nodeData) => {
    setViewingDataset(nodeData); 
  }, []);

  const handleDatasetColumnChange = useCallback((nodeId, nextColumn) => {
    if (!nodeId) return;
    const selectedColumn = typeof nextColumn === 'string' ? nextColumn : '';
    const downstreamNodeIds = new Set(
      getEdges()
        .filter((edge) => edge.source === nodeId)
        .map((edge) => edge.target)
    );

    setNodes((nds) =>
      nds.map((node) => {
        if (!node) return node;

        if (node.id === nodeId && node.type === 'datasetNode') {
          const nodeData = (node.data && typeof node.data === 'object') ? node.data : {};
          return {
            ...node,
            data: {
              ...nodeData,
              selectedColumn,
              colorBy: selectedColumn,
            },
          };
        }

        if (
          !downstreamNodeIds.has(node.id)
          || node.type !== 'integrationNode'
          || !Array.isArray(node.data?.connectedDatasets)
        ) {
          return node;
        }

        let changed = false;
        const updatedDatasets = node.data.connectedDatasets.map((dataset) => {
          if (dataset.nodeId !== nodeId || dataset.inheritedColumn === selectedColumn) {
            return dataset;
          }
          changed = true;
          return { ...dataset, inheritedColumn: selectedColumn };
        });

        if (!changed) {
          return node;
        }

        return {
          ...node,
          data: {
            ...node.data,
            connectedDatasets: updatedDatasets,
          },
        };
      })
    );
  }, [getEdges]);

  // TIME WINDOW (redesign section 4.1): set on a dataset node, carried to the integrations it feeds
  const handleDatasetTimeWindowChange = useCallback((nodeId, timeWindow) => {
    setNodes((nds) => nds.map((node) => {
      if (node.id === nodeId && node.type === 'datasetNode') {
        return { ...node, data: { ...node.data, timeWindow: timeWindow || null } };
      }
      if (node.type === 'integrationNode' && Array.isArray(node.data?.connectedDatasets)
          && node.data.connectedDatasets.some((d) => d.nodeId === nodeId)) {
        return {
          ...node,
          data: {
            ...node.data,
            connectedDatasets: node.data.connectedDatasets.map((d) => (
              d.nodeId === nodeId ? { ...d, timeWindow: timeWindow || null } : d)),
          },
        };
      }
      return node;
    }));
  }, []);

  const addDatasetNodeById = useCallback(async (datasetId, colorBy, provenance = {}) => {
    const normalizedId = normalizeDatasetId(datasetId);
    if (!normalizedId) {
      console.warn(`[Copilot] add_dataset_node ignored: invalid dataset_id='${datasetId}'`);
      return false;
    }

    let dataset = findDatasetById(normalizedId);
    if (!dataset) {
      const refreshedDatasets = await fetchAvailableDatasets();
      dataset = findDatasetById(normalizedId, refreshedDatasets);
    }

    if (!dataset) {
      console.warn(`[Copilot] add_dataset_node ignored: unknown dataset_id='${datasetId}'`);
      return false;
    }

    const resolvedColorBy = resolveValidColorByForDataset(dataset, colorBy);
    if (typeof colorBy === 'string' && colorBy.trim() && !resolvedColorBy) {
      console.warn(
        `[Copilot] add_dataset_node ignored invalid colorBy='${colorBy}' for dataset_id='${datasetId}'`
      );
    }

    setNodes((nds) => {
      const existingIndex = nds.findIndex((node) => {
        if (!node || node.type !== 'datasetNode') return false;
        const nodeData = (node.data && typeof node.data === 'object') ? node.data : {};
        const existingId = normalizeDatasetId(
          nodeData.id || nodeData.filename || nodeData.metadata?.name || nodeData.name
        );
        return existingId === normalizedId;
      });
      if (existingIndex >= 0) {
        if (!resolvedColorBy) return nds;
        return nds.map((node, idx) => {
          if (idx !== existingIndex) return node;
          const nodeData = (node.data && typeof node.data === 'object') ? node.data : {};
          return {
            ...node,
            data: {
              ...nodeData,
              selectedColumn: resolvedColorBy,
              colorBy: resolvedColorBy,
              onColumnChange: handleDatasetColumnChange,
            },
          };
        });
      }

      const datasetNodeCount = nds.filter((node) => node?.type === 'datasetNode').length;
      const newNode = {
        id: `node_dataset_${normalizedId}_${Date.now()}`,
        type: 'datasetNode',
        position: {
          x: 120 + (datasetNodeCount % 3) * 280,
          y: 100 + Math.floor(datasetNodeCount / 3) * 240,
        },
        data: {
          ...dataset,
          onShowInfo: handleShowInfo,
          onColumnChange: handleDatasetColumnChange,
          onTimeWindowChange: handleDatasetTimeWindowChange,
          ...(resolvedColorBy ? { selectedColumn: resolvedColorBy, colorBy: resolvedColorBy } : {}),
          ...(provenance.addedBy ? { addedBy: provenance.addedBy } : {}),
          ...(provenance.reason ? { copilotReason: provenance.reason } : {}),
        },
      };

      return nds.concat(newNode);
    });

    return true;
  }, [
    fetchAvailableDatasets,
    findDatasetById,
    handleDatasetColumnChange,
    handleDatasetTimeWindowChange,
    handleShowInfo,
    normalizeDatasetId,
    resolveValidColorByForDataset,
  ]);

  const handleCopilotSuggestions = useCallback((incomingSuggestions) => {
    if (!Array.isArray(incomingSuggestions) || incomingSuggestions.length === 0) {
      return;
    }

    setCopilotSuggestions((prev) => {
      const seen = new Set(prev.map(getSuggestionKey).filter(Boolean));
      const nextSuggestions = [];

      for (const rawSuggestion of incomingSuggestions) {
        const suggestion = normalizeCopilotSuggestion(rawSuggestion);
        if (!suggestion) continue;

        const suggestionKey = getSuggestionKey(suggestion);
        if (!suggestionKey || seen.has(suggestionKey)) continue;

        seen.add(suggestionKey);
        nextSuggestions.push(suggestion);
      }

      return nextSuggestions.length > 0 ? nextSuggestions.concat(prev) : prev;
    });
  }, [getSuggestionKey, normalizeCopilotSuggestion]);

  const removeCopilotSuggestion = useCallback((targetSuggestion) => {
    const targetKey = getSuggestionKey(targetSuggestion);
    if (!targetKey) return;

    setCopilotSuggestions((prev) => {
      const next = prev.filter((suggestion) => getSuggestionKey(suggestion) !== targetKey);
      return next.length !== prev.length ? next : prev;
    });
  }, [getSuggestionKey]);

  const handleAcceptSuggestion = useCallback(async (suggestion) => {
    if (!suggestion || typeof suggestion !== 'object') {
      return false;
    }

    const action = (suggestion.action && typeof suggestion.action === 'object')
      ? suggestion.action
      : suggestion;

    if (action.type !== 'add_dataset_node') {
      return false;
    }

    const wasApplied = await addDatasetNodeById(action.datasetId, action.colorBy, {
      addedBy: 'copilot',
      reason: suggestion.reason || '',
    });
    if (wasApplied) {
      removeCopilotSuggestion(suggestion);
    }
    return wasApplied;
  }, [addDatasetNodeById, removeCopilotSuggestion]);

  const handleRejectSuggestion = useCallback((suggestion) => {
    const suggestionKey = getSuggestionKey(suggestion);
    if (!suggestionKey) {
      return false;
    }

    const exists = copilotSuggestions.some(
      (candidate) => getSuggestionKey(candidate) === suggestionKey
    );
    if (exists) {
      removeCopilotSuggestion(suggestion);
    }
    return exists;
  }, [copilotSuggestions, getSuggestionKey, removeCopilotSuggestion]);

  // PLAN NODE STATE (redesign phase 4)
  const handlePlanNodeChange = useCallback((nodeId, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n)));
  }, []);
  const handleValueKindChange = useCallback((datasetNodeId, column, kind) => {
    setNodes((nds) => nds.map((n) => (n.id === datasetNodeId
      ? { ...n, data: { ...n.data, valueKinds: { ...(n.data?.valueKinds || {}), [column]: kind } } } : n)));
  }, []);
  const runPlanNodeRef = React.useRef(null);
  const runAnalysisNodeRef = React.useRef(null);

  const attachCallbacks = useCallback((type, data) => {
    const next = { ...data };
    if (type === 'operationNode') {
      next.color = data.opType === 'buffer' ? '#ec4899' : '#8b5cf6';
    } else if (type === 'integrationNode') {
      next.studyArea = collection.study_area || null;
      next.onIntegrationComplete = handleIntegrationComplete;
      next.onLogActivity = onLogActivity;
      next.onDeleteNode = handleDeleteNode;
    } else if (type === 'compareMapNode') {
      next.onCompareHover = handleCompareHover;
      next.connectedResults = next.connectedResults || [];
      next.isMapSyncEnabled = isMapSyncEnabled;
      next.globalViewState = globalViewState;
      next.onGlobalViewStateChange = setGlobalViewState;
      next.onDeleteNode = handleDeleteNode;
    } else if (['sweepNode', 'validateNode', 'dasymetricNode'].includes(type)) {
      next.onChange = handlePlanNodeChange;
      next.onRun = (nodeId) => runAnalysisNodeRef.current?.(nodeId);
      next.onDeleteNode = handleDeleteNode;
    } else if (type === 'stepNode' || type === 'calculateNode' || type === 'gridNode') {
      next.onChange = handlePlanNodeChange;
      next.onRun = type === 'calculateNode' ? (nodeId) => runPlanNodeRef.current?.(nodeId, 'calculate')
        : (nodeId) => runPlanNodeRef.current?.(nodeId, 'step');
      next.onValueKindChange = handleValueKindChange;
      next.onDeleteNode = handleDeleteNode;
      if (type === 'stepNode' && !next.stepId) {
        next.method = next.method || 'contain';
        next.reductions = next.reductions || [{ method: 'count', column: '', as: 'count', fillEmpty: true }];
      }
      if (type === 'gridNode' && !next.resolution) next.resolution = 9;
      if (type === 'calculateNode') { next.as = next.as || 'derived'; next.kind = next.kind || 'intensive'; }
    } else if (type === 'datasetNode') {
      next.onShowInfo = handleShowInfo;
      next.onColumnChange = handleDatasetColumnChange;
      next.onTimeWindowChange = handleDatasetTimeWindowChange;
      next.isMapSyncEnabled = isMapSyncEnabled;
      next.globalViewState = globalViewState;
      next.onGlobalViewStateChange = setGlobalViewState;
      next.onDeleteNode = handleDeleteNode;
    }
    return next;
  }, [collection.study_area, globalViewState, handleCompareHover, handleDatasetColumnChange, handleDatasetTimeWindowChange,
      handleDeleteNode, handleIntegrationComplete, handleShowInfo, isMapSyncEnabled, onLogActivity, handlePlanNodeChange,
      handleValueKindChange]);

  // ---------------------------------------------------------------------------------------------
  // COLLECTION: build the document from the canvas, save it, reopen it, export it

  const collectionDoc = useMemo(() => ({
    name: collection.name,
    goal: collection.goal,
    notes: collection.notes,
    study_area: collection.study_area,
    datasets: collectionDatasets(nodes, edges),
    plan: (() => {
      const { plan } = buildPlan(nodes, edges);
      return plan.steps.length ? plan : null;
    })(),
    derived: buildDerived(nodes, edges).filter((d) => d.inputs.length),
    analyses: collectionAnalyses(nodes, edges),
    // Integrations saved earlier stay while their integration node is on the canvas; results on
    // the canvas add or replace them.
    integrations: (() => {
      const current = collectionIntegrations(nodes, edges);
      const nodeIds = new Set(nodes.map((n) => n.id));
      const currentIds = new Set(current.map((i) => i.id));
      const kept = (collection.integrations || []).filter((i) => !currentIds.has(i.id) && nodeIds.has(i.node_id));
      return [...kept, ...current];
    })(),
    canvas: serializeCanvas(nodes, edges),
  }), [collection, nodes, edges]);
  const collectionJson = useMemo(() => JSON.stringify(collectionDoc), [collectionDoc]);
  const collectionDirty = savedSnapshot === null
    ? (nodes.length > 0 || collection.goal !== '' || collection.name !== EMPTY_COLLECTION.name)
    : collectionJson !== savedSnapshot;

  const saveCollection = useCallback(async () => {
    setCollectionStatus('Saving…');
    try {
      const saved = collection.id
        ? await updateCollection(collection.id, collectionDoc)
        : await createCollection(collectionDoc);
      setCollection((c) => ({ ...c, id: saved.id }));
      setSavedSnapshot(collectionJson);
      setCollectionStatus('');
      return saved.id;
    } catch (error) {
      setCollectionStatus(`Save failed: ${error.message}`);
      return null;
    }
  }, [collection.id, collectionDoc, collectionJson]);

  const confirmDiscard = useCallback(() => (
    !collectionDirty || window.confirm('Discard unsaved changes to this collection?')
  ), [collectionDirty]);

  const newCollection = useCallback(() => {
    if (!confirmDiscard()) return;
    setNodes([]);
    setEdges([]);
    setCollection(EMPTY_COLLECTION);
    setSavedSnapshot(null);
    setCollectionStatus('');
  }, [confirmDiscard]);

  const openCollection = useCallback(async (id) => {
    if (!confirmDiscard()) return;
    setCollectionStatus('Opening…');
    try {
      const doc = await getCollection(id);
      const datasets = await fetchAvailableDatasets();
      const savedNodes = doc.canvas?.nodes || [];
      const savedEdges = doc.canvas?.edges || [];
      const byNodeId = new Map(savedNodes.map((n) => [n.id, n]));
      const restored = savedNodes.map((n) => {
        let data = { ...n.data };
        if (n.type === 'datasetNode') {
          const dataset = findDatasetById(data.id || data.filename, datasets);
          data = { ...(dataset || {}), ...data, metadata: dataset?.metadata || null };
        }
        if (n.type === 'integrationNode') {
          // Re-link the inputs from the edges, with fresh dataset metadata.
          const connectedDatasets = [];
          data.connectedZoneFilename = null;
          data.connectedZoneMetadata = null;
          for (const e of savedEdges.filter((edge) => edge.target === n.id)) {
            const src = byNodeId.get(e.source);
            const dataset = src ? findDatasetById(src.data?.id || src.data?.filename, datasets) : null;
            if (!src || !dataset) continue;
            if (e.targetHandle === 'zones') {
              data.connectedZoneFilename = dataset.filename;
              data.connectedZoneMetadata = dataset.metadata;
            } else {
              connectedDatasets.push({
                id: `var_${e.source}`, nodeId: e.source, filename: dataset.filename, metadata: dataset.metadata,
                inheritedColumn: src.data?.selectedColumn || '', timeWindow: src.data?.timeWindow || null,
              });
            }
          }
          data.connectedDatasets = connectedDatasets;
          data.connectedDatasetFilename = connectedDatasets[0]?.filename || null;
          data.connectedDatasetMetadata = connectedDatasets[0]?.metadata || null;
        }
        return { id: n.id, type: n.type, position: n.position, data: attachCallbacks(n.type, data) };
      });
      setNodes(restored);
      setEdges(savedEdges);
      const loaded = {
        id: doc.id, name: doc.name, goal: doc.goal || '', notes: doc.notes || '',
        study_area: doc.study_area || null, analyses: doc.analyses || [], integrations: doc.integrations || [],
      };
      setCollection(loaded);
      // The snapshot is taken from the restored canvas on the next render (see effect below).
      setSavedSnapshot('__pending__');
      setCollectionStatus(doc.integrations?.length ? 'Opened: run integrations to see results' : '');
    } catch (error) {
      setCollectionStatus(`Open failed: ${error.message}`);
    }
  }, [attachCallbacks, confirmDiscard, fetchAvailableDatasets, findDatasetById]);

  useEffect(() => {
    if (savedSnapshot === '__pending__') setSavedSnapshot(collectionJson);
  }, [savedSnapshot, collectionJson]);

  // STUDY AREA (redesign phase 2): integrations use it; the sidebar filters search by its extent.
  useEffect(() => {
    const area = collection.study_area || null;
    setNodes((nds) => {
      let changed = false;
      const next = nds.map((node) => {
        if (node.type !== 'integrationNode' || node.data?.studyArea === area) return node;
        changed = true;
        return { ...node, data: { ...node.data, studyArea: area } };
      });
      return changed ? next : nds;
    });
    if (!onStudyAreaResolved) return;
    if (!area) { onStudyAreaResolved(null); return; }
    let alive = true;
    resolveStudyArea(area).then((summary) => alive && onStudyAreaResolved(summary)).catch(() => alive && onStudyAreaResolved(null));
    return () => { alive = false; };
  }, [collection.study_area, onStudyAreaResolved]);

  // CHECKS: periods that do not overlap, datasets that miss the study area (debounced)
  const checksKey = useMemo(() => JSON.stringify({
    datasets: collectionDoc.datasets.map(({ id, time_window }) => ({ id, time_window })),
    study_area: collectionDoc.study_area,
  }), [collectionDoc.datasets, collectionDoc.study_area]);
  useEffect(() => {
    const body = JSON.parse(checksKey);
    if (!body.datasets.length) { setWarnings([]); return; }
    const t = setTimeout(() => {
      checkCollection(body).then((r) => setWarnings(r.warnings || [])).catch(() => setWarnings([]));
    }, 500);
    return () => clearTimeout(t);
  }, [checksKey]);

  // VALUE KIND SUGGESTIONS for dataset nodes, from their profiles (redesign section 3.3)
  useEffect(() => {
    nodes.filter((n) => n.type === 'datasetNode' && !n.data?.valueKindSuggestions).forEach((n) => {
      const stem = normalizeDatasetId(n.data?.id || n.data?.filename);
      if (!stem) return;
      getValueKindSuggestions(stem).then((suggestions) => {
        setNodes((nds) => nds.map((m) => (m.id === n.id && !m.data?.valueKindSuggestions
          ? { ...m, data: { ...m.data, valueKindSuggestions: suggestions } } : m)));
      });
    });
  }, [nodes, normalizeDatasetId]);

  // PLAN VALIDATION (debounced): problems by step, shown on the step nodes
  const planKey = useMemo(() => JSON.stringify(buildPlan(nodes, edges).plan), [nodes, edges]);
  useEffect(() => {
    const plan = JSON.parse(planKey);
    if (!plan.steps.length) { setPlanProblems({}); return undefined; }
    const t = setTimeout(() => {
      validatePlan(plan, collection.study_area).then((r) => setPlanProblems(r.problems || {})).catch(() => {});
    }, 600);
    return () => clearTimeout(t);
  }, [planKey, collection.study_area]);

  // CONTEXT of each plan node: what is connected, columns with value kinds, problems
  useEffect(() => {
    const { problems: localProblems } = buildPlan(nodes, edges);
    const columnsOfStep = (stepNode) => (stepNode.data?.reductions || []).filter((r) => r.method).map((r) => {
      const alias = r.as || [r.method, r.column].filter(Boolean).join('_');
      let kind = OUTPUT_KIND[r.method] || null;
      if (!kind) {
        const { source } = inputsOf(stepNode.id, nodes, edges);
        kind = source?.type === 'datasetNode' ? valueKindOf(source.data, r.column) : null;
      }
      return { name: alias, kind };
    });
    const describeTarget = (t) => {
      if (!t) return null;
      if (t.type === 'gridNode') return { kind: 'h3', label: `H3 grid, resolution ${t.data?.resolution || 9}`, geometry: 'Polygon' };
      return { kind: 'zones', label: t.data?.metadata?.name || t.data?.name || t.data?.id, geometry: t.data?.metadata?.geometricType || 'Polygon' };
    };
    const contexts = {};
    for (const n of nodes) {
      if (n.type === 'stepNode') {
        const { source, target } = inputsOf(n.id, nodes, edges);
        let src = null;
        if (source?.type === 'datasetNode') {
          const cols = (source.data?.metadata?.columns || []).map((c) => c.name).filter(Boolean);
          src = {
            label: source.data?.metadata?.name || source.data?.name || source.data?.id, geometry: source.data?.metadata?.geometricType,
            columns: cols.map((name) => ({ name, kind: valueKindOf(source.data, name) })), datasetNodeId: source.id,
          };
        } else if (source?.type === 'stepNode') {
          const upTarget = describeTarget(inputsOf(source.id, nodes, edges).target);
          src = { label: `@${stepIdOf(source)}`, geometry: upTarget?.geometry || 'Polygon', columns: columnsOfStep(source), isStep: true };
        }
        const sid = stepIdOf(n);
        contexts[n.id] = { source: src, target: describeTarget(target), problems: [...(localProblems[sid] || []), ...(planProblems[sid] || [])] };
      } else if (n.type === 'calculateNode') {
        const { inputs } = inputsOf(n.id, nodes, edges);
        const steps = inputs.filter((i) => i.type === 'stepNode');
        const targetIds = new Set(steps.map((s) => inputsOf(s.id, nodes, edges).target?.id).filter(Boolean));
        contexts[n.id] = {
          inputs: steps.map((s) => ({ stepId: stepIdOf(s), columns: columnsOfStep(s) })),
          problems: targetIds.size > 1 ? ['The connected steps must share one target.'] : [],
        };
      }
    }
    for (const n of nodes) {
      if (n.type === 'sweepNode') {
        const step = edgesInto(n.id, 'step', nodes, edges)[0];
        if (!step) { contexts[n.id] = { problems: [] }; continue; }
        const { source, target } = inputsOf(step.id, nodes, edges);
        const geom = (source?.type === 'datasetNode' ? source.data?.metadata?.geometricType : 'Polygon') || 'Polygon';
        const family = geom.replace(/^Multi/, '');
        contexts[n.id] = {
          stepId: stepIdOf(step), targetLabel: describeTarget(target)?.label || 'its target',
          columns: columnsOfStep(step).filter((c) => c.kind !== 'categorical'),
          methodChoices: (METHODS_FOR[family] || []).filter((m) => m !== step.data?.method),
          zoneDatasets: availableDatasets.filter((d) => /Polygon/.test(d?.metadata?.geometricType || ''))
            .map((d) => ({ id: normalizeDatasetId(d.id || d.filename), name: d.metadata?.name || d.name })),
          problems: [],
        };
      } else if (n.type === 'validateNode') {
        const res = edgesInto(n.id, 'result', nodes, edges)[0];
        const out = edgesInto(n.id, 'outcomes', nodes, edges)[0];
        let columns = [];
        let resultId = null;
        if (res?.type === 'stepNode') { resultId = stepIdOf(res); columns = columnsOfStep(res); }
        if (res?.type === 'calculateNode') {
          const d = buildDerived(nodes, edges).find((x) => x.node === res.id);
          resultId = d?.id;
          columns = inputsOf(res.id, nodes, edges).inputs.filter((i) => i.type === 'stepNode').flatMap(columnsOfStep);
          if (d?.expression) columns = [...columns, { name: d.as, kind: d.kind }];
        }
        contexts[n.id] = { resultId, columns: columns.filter((c) => c.kind !== 'categorical'),
          outcomes: out ? (out.data?.metadata?.name || out.data?.id) : null, problems: [] };
      } else if (n.type === 'dasymetricNode') {
        const z = edgesInto(n.id, 'zones', nodes, edges)[0];
        const t = edgesInto(n.id, 'target', nodes, edges)[0];
        const priors = edgesInto(n.id, 'prior', nodes, edges);
        const numeric = (ds) => (ds?.data?.metadata?.columns || []).filter((c) =>
          ['http://schema.org/Integer', 'http://schema.org/Float', 'Integer', 'Float'].includes(c.structural_type) || c.mean !== undefined).map((c) => c.name);
        contexts[n.id] = {
          zones: z ? { label: z.data?.metadata?.name || z.data?.id, columns: numeric(z) } : null,
          target: describeTarget(t),
          priors: priors.map((p) => ({ nodeId: p.id, label: p.data?.metadata?.name || p.data?.id, columns: numeric(p) })),
          problems: [],
        };
      }
    }
    setNodes((nds) => {
      let changed = false;
      const next = nds.map((n) => {
        const ctx = contexts[n.id];
        if (!ctx || JSON.stringify(ctx) === JSON.stringify(n.data?.context)) return n;
        changed = true;
        return { ...n, data: { ...n.data, context: ctx } };
      });
      return changed ? next : nds;
    });
  }, [nodes, edges, planProblems, availableDatasets, normalizeDatasetId]);

  // RUNNING a step or a calculation: results in columns, shown in a Result Map connected to the node
  const showPlanResult = useCallback((nodeId, spatialData, name) => {
    const resultEdge = getEdges().find((e) => e.source === nodeId && getNodes().find((n) => n.id === e.target)?.type === 'resultMapNode');
    if (resultEdge) {
      setNodes((nds) => nds.map((n) => (n.id === resultEdge.target ? { ...n, data: { ...n.data, name, spatialData } } : n)));
      return;
    }
    const resultNodeId = `result_${(crypto.randomUUID?.() || String(Date.now())).slice(0, 8)}`;
    setNodes((nds) => {
      const src = nds.find((n) => n.id === nodeId);
      if (!src) return nds;
      return [...nds, {
        id: resultNodeId, type: 'resultMapNode', position: { x: src.position.x + 360, y: src.position.y },
        data: { name, isResult: true, spatialData, isMapSyncEnabled, globalViewState, onGlobalViewStateChange: setGlobalViewState, onDeleteNode: handleDeleteNode },
      }];
    });
    setEdges((eds) => [...eds, { id: `e-${nodeId}-${resultNodeId}`, source: nodeId, target: resultNodeId, animated: true, style: { stroke: '#6366f1', strokeWidth: 2 } }]);
  }, [getEdges, getNodes, globalViewState, handleDeleteNode, isMapSyncEnabled]);

  const runPlanNode = useCallback(async (nodeId, mode) => {
    const all = getNodes();
    const allEdges = getEdges();
    const node = all.find((n) => n.id === nodeId);
    if (!node) return;
    const setRun = (lastRun) => handlePlanNodeChange(nodeId, { lastRun });
    const started = performance.now();
    setRun({ running: true });
    try {
      let stepNodeIds = [nodeId];
      let derived = null;
      if (mode === 'calculate') {
        const steps = inputsOf(nodeId, all, allEdges).inputs.filter((i) => i.type === 'stepNode');
        stepNodeIds = steps.map((s) => s.id);
        derived = buildDerived(all, allEdges).filter((d) => d.node === nodeId);
      }
      const { plan, problems, byStepNode } = buildPlan(all, allEdges, stepNodeIds);
      const own = mode === 'step' ? problems[byStepNode[nodeId] || stepIdOf(node)] : null;
      if (own?.length) throw new Error(own.join(' '));
      const outputs = mode === 'step' ? [byStepNode[nodeId]] : [];
      const out = await runPlan({ plan, study_area: collection.study_area || null, outputs, derived });
      const key = mode === 'step' ? byStepNode[nodeId] : derived[0].id;
      const payload = out.steps[key];
      const step = plan.steps.find((s) => s.id === key);
      const srcInfo = step ? out.inputs?.[step.source] : null;
      const spatialData = toSpatialData(payload, {
        stepId: key, plan, reports: out.reports?.[key] || null,
        sourceLabel: srcInfo?.dataset || (mode === 'calculate' ? `derived from ${derived[0].inputs.join(', ')}` : key),
        methodLabel: step?.match?.method || 'combine',
        reductionsByColumn: Object.fromEntries((step?.aggregate || []).map((r) => [r.as, r.method])),
        durationMs: Math.round(performance.now() - started),
      });
      const reports = mode === 'step' ? { [key]: { allocation: out.reports?.[key], ...(srcInfo?.time_window ? { time_window: srcInfo.time_window } : {}),
        ...(srcInfo?.study_area ? { study_area: srcInfo.study_area } : {}), ...(srcInfo?.repaired_geometries ? { repaired_geometries: srcInfo.repaired_geometries } : {}) } } : null;
      setRun({ running: false, reports, durationMs: spatialData.provenance.durationMs });
      showPlanResult(nodeId, { ...spatialData, reports: reports || spatialData.reports }, mode === 'step' ? `Step ${key}` : `Derived: ${derived[0].as}`);
      onLogActivity?.({ status: 'success', ...spatialData.provenance, reports: reports || spatialData.reports });
    } catch (error) {
      setRun({ running: false, error: error.message });
    }
  }, [collection.study_area, getEdges, getNodes, handlePlanNodeChange, onLogActivity, showPlanResult]);
  useEffect(() => { runPlanNodeRef.current = runPlanNode; }, [runPlanNode]);

  const runAnalysisNode = useCallback(async (nodeId) => {
    const all = getNodes();
    const allEdges = getEdges();
    const node = all.find((n) => n.id === nodeId);
    if (!node) return;
    const setRun = (lastRun) => handlePlanNodeChange(nodeId, { lastRun });
    const started = performance.now();
    setRun({ running: true });
    const studyArea = collection.study_area || null;
    try {
      const config = analysisConfig(node, all, allEdges);
      if (!config) throw new Error('Connect the inputs first.');
      let payload;
      let display;
      let title;
      let result = null;
      if (node.type === 'sweepNode') {
        const step = edgesInto(nodeId, 'step', all, allEdges)[0];
        const { plan } = buildPlan(all, allEdges, [step.id]);
        payload = await runSweep({ plan, study_area: studyArea, ...config });
        display = 'top_share';
        title = `Sweep: ${config.column}`;
        result = payload.sweep;
      } else if (node.type === 'validateNode') {
        const res = edgesInto(nodeId, 'result', all, allEdges)[0];
        const stepIds = res.type === 'calculateNode' ? inputsOf(res.id, all, allEdges).inputs.filter((i) => i.type === 'stepNode').map((s) => s.id) : [res.id];
        const { plan } = buildPlan(all, allEdges, stepIds);
        const derived = res.type === 'calculateNode' ? buildDerived(all, allEdges).filter((d) => d.node === res.id) : null;
        payload = await runValidation({ plan, study_area: studyArea, ...config, derived });
        display = config.column;
        title = `Validation: ${config.column}`;
        result = payload.validation;
      } else {
        payload = await runDasymetric({ study_area: studyArea, ...config });
        display = Object.keys(payload.columns)[0];
        title = `Dasymetric: ${display}`;
      }
      const spatialData = toSpatialData(payload, { stepId: title, plan: null, sourceLabel: title, methodLabel: node.type.replace('Node', ''),
        durationMs: Math.round(performance.now() - started), displayColumn: display, multivariate: false });
      setRun({ running: false, result });
      showPlanResult(nodeId, spatialData, title);
    } catch (error) {
      setRun({ running: false, error: error.message });
    }
  }, [collection.study_area, getEdges, getNodes, handlePlanNodeChange, showPlanResult]);
  useEffect(() => { runAnalysisNodeRef.current = runAnalysisNode; }, [runAnalysisNode]);

  // RUN ALL and record a manifest (for replay and for the export), from the collection bar
  const runAllRecorded = useCallback(async () => {
    const { plan } = buildPlan(nodes, edges);
    if (!plan.steps.length) { setCollectionStatus('No steps to run'); return; }
    const id = await saveCollection();
    if (!id) return;
    setCollectionStatus('Running the plan…');
    try {
      const out = await runPlan({ plan, study_area: collection.study_area || null, outputs: plan.steps.map((s) => s.id),
        derived: buildDerived(nodes, edges).filter((d) => d.inputs.length), record: true, collection_id: id });
      setLastManifestPath(out.manifest_path);
      setCollectionStatus(`Ran ${plan.steps.length} step(s); run recorded`);
    } catch (error) {
      setCollectionStatus(`Run failed: ${error.message}`);
    }
  }, [collection.study_area, edges, nodes, saveCollection]);

  const zoneDatasets = useMemo(() => availableDatasets
    .filter((d) => /Polygon/.test(d?.metadata?.geometricType || ''))
    .map((d) => ({ id: normalizeDatasetId(d.id || d.filename), name: d.metadata?.name || d.name }))
    .sort((a, b) => (a.name || '').localeCompare(b.name || '')), [availableDatasets, normalizeDatasetId]);

  const handleExport = useCallback(async (options) => {
    setExporting(true);
    try {
      const id = collectionDirty || !collection.id ? await saveCollection() : collection.id;
      if (!id) return;
      await exportCollection(id, options);
      setCollectionStatus('');
    } catch (error) {
      setCollectionStatus(`Export failed: ${error.message}`);
    } finally {
      setExporting(false);
    }
  }, [collection.id, collectionDirty, saveCollection]);

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const dataString = event.dataTransfer.getData('application/reactflow');
      if (!dataString) return;
      
      const dataItem = JSON.parse(dataString); 
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });

      // Determine type dynamically based on what was dragged from the sidebar
      const newNodeType = dataItem.type || 'datasetNode';
      const nodeId = `node_${Date.now()}`;
      // Inject the handlers each node type needs to talk back to the canvas
      const seed = { ...dataItem };
      if (newNodeType === 'stepNode') {
        const taken = new Set(getNodes().filter((n) => n.type === 'stepNode').map((n) => n.data?.stepId));
        let k = 1;
        while (taken.has(`step_${k}`)) k += 1;
        seed.stepId = `step_${k}`;
        seed.method = 'contain';
        seed.reductions = [{ method: 'count', column: '', as: 'count', fillEmpty: true }];
      }
      const newNodeData = attachCallbacks(newNodeType, seed);

      const newNode = {
        id: nodeId,
        type: newNodeType, 
        position,
        data: newNodeData,
      };

      setNodes((nds) => nds.concat(newNode));
      if (newNodeType === 'datasetNode') {
        queueAutoSuggestRequest(dataItem);
      }
    },
    [attachCallbacks, getNodes, screenToFlowPosition, queueAutoSuggestRequest]
  );

  return (
    <div style={{ width: '100%', height: '100%', backgroundColor: '#f8fafc', position: 'relative' }}>
      {/* GLOBAL VIEWPORT SYNC: Toggle button */}
      <button
        onClick={() => setIsMapSyncEnabled(!isMapSyncEnabled)}
        title={isMapSyncEnabled ? 'Maps Linked - Click to unlink' : 'Link all map viewports'}
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          zIndex: 100,
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '8px 12px',
          backgroundColor: isMapSyncEnabled ? '#3b82f6' : '#fff',
          color: isMapSyncEnabled ? '#fff' : '#64748b',
          border: `1px solid ${isMapSyncEnabled ? '#3b82f6' : '#cbd5e1'}`,
          borderRadius: '6px',
          fontSize: '12px',
          fontWeight: '600',
          cursor: 'pointer',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          transition: 'all 0.2s'
        }}
      >
        {isMapSyncEnabled ? <Link size={14} /> : <Unlink size={14} />}
        {isMapSyncEnabled ? 'Maps Linked' : 'Link Maps'}
      </button>

      <CollectionBar
        collection={collection}
        dirty={collectionDirty}
        status={collectionStatus}
        exporting={exporting}
        onRename={(name) => setCollection((c) => ({ ...c, name }))}
        onGoalChange={(goal) => setCollection((c) => ({ ...c, goal }))}
        onNew={newCollection}
        onOpen={openCollection}
        onSave={saveCollection}
        onExport={handleExport}
        zoneDatasets={zoneDatasets}
        onStudyAreaChange={(study_area) => setCollection((c) => ({ ...c, study_area }))}
        coverageDatasets={collectionDoc.datasets.map((d) => d.id)}
        warnings={[...warnings, ...(planProblems._plan || []).map((message) => ({ kind: 'plan', message }))]}
        hasPlan={!!collectionDoc.plan}
        onReport={async () => {
          const id = collectionDirty || !collection.id ? await saveCollection() : collection.id;
          if (id) window.open(reportUrl(id), '_blank', 'noopener');
        }}
        onRunAll={runAllRecorded}
        canReplay={!!lastManifestPath}
        onReplay={async () => {
          setCollectionStatus('Replaying…');
          try {
            const r = await replayRun(lastManifestPath);
            setCollectionStatus(r.ok ? 'Replay matched every input' : `Replay: ${r.message}`);
          } catch (error) {
            setCollectionStatus(`Replay failed: ${error.message}`);
          }
        }}
        onDownloadPlan={() => downloadBlob(new Blob([JSON.stringify(collectionDoc.plan, null, 1)], { type: 'application/json' }), 'plan.json')}
      />

      <div style={{ width: '100%', height: '100%' }} onDrop={onDrop} onDragOver={onDragOver}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          edgesReconnectable={false}
          fitView
          // Fitting a single small node would zoom in (1.7x) and blow up its text; never fit past 100%
          fitViewOptions={{ maxZoom: 1 }}
        >
          <Background variant="dots" gap={20} size={1} color="#cbd5e1" />
          <Controls />
        </ReactFlow>
      </div>

      <FloatingCopilotInput
        nodes={nodes}
        edges={edges}
        suggestions={copilotSuggestions}
        autoSuggestRequest={autoSuggestRequest}
        onCopilotSuggestions={handleCopilotSuggestions}
        onAcceptSuggestion={handleAcceptSuggestion}
        onRejectSuggestion={handleRejectSuggestion}
      />

      {viewingDataset && (
        <DatasetDetailsModal
          open={!!viewingDataset}
          dataset={viewingDataset}
          onClose={() => setViewingDataset(null)} 
        />
      )}
    </div>
  );
};

const AnalysisCanvas = ({ sidebarCollapsed, onLogActivity, highlightedLogTs, focusedLogTs, onTraceLineage, onActiveLogTimestampsChange, onStudyAreaResolved }) => (
  <ReactFlowProvider>
    <CanvasInner
      sidebarCollapsed={sidebarCollapsed}
      onLogActivity={onLogActivity}
      highlightedLogTs={highlightedLogTs}
      focusedLogTs={focusedLogTs}
      onTraceLineage={onTraceLineage}
      onActiveLogTimestampsChange={onActiveLogTimestampsChange}
      onStudyAreaResolved={onStudyAreaResolved}
    />
  </ReactFlowProvider>
);

export default AnalysisCanvas;
