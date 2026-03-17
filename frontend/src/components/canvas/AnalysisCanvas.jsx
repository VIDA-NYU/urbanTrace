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

const CanvasInner = ({ sidebarCollapsed, onLogActivity, highlightedLogTs, focusedLogTs, onTraceLineage, onActiveLogTimestampsChange }) => {
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
      const response = await fetch('http://localhost:8000/datasets');
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
    compareMapNode: CompareMapNode
  }), []);

  const handleCompareHover = useCallback((featureId, featureType) => {
    setHoveredCompareFeatureId(featureId || null);
    setHoveredCompareFeatureType(featureId ? featureType : null);
  }, []);

  const handleDeleteNode = useCallback((nodeId) => {
    setEdges(eds => eds.filter(edge => edge.source !== nodeId && edge.target !== nodeId));
    setNodes(nds => nds.filter(node => node.id !== nodeId));
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
  useMemo(() => {
    setNodes(nds => nds.map(node => {
      if (node.type === 'resultMapNode' || node.type === 'datasetNode') {
        return {
          ...node,
          data: {
            ...node.data,
            isMapSyncEnabled,
            globalViewState,
            onGlobalViewStateChange: setGlobalViewState,
            onDeleteNode: handleDeleteNode
          }
        };
      }
      return node;
    }));
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
            onDeleteNode: handleDeleteNode
          }
        };
      }
      return node;
    }));
  }, [highlightedLogTs, focusedLogTs, onTraceLineage, hoveredCompareFeatureId, hoveredCompareFeatureType, handleDeleteNode]);

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
        inheritedColumn: inheritedColumn
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

  const addDatasetNodeById = useCallback(async (datasetId, colorBy) => {
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
          ...(resolvedColorBy ? { selectedColumn: resolvedColorBy, colorBy: resolvedColorBy } : {}),
        },
      };

      return nds.concat(newNode);
    });

    return true;
  }, [
    fetchAvailableDatasets,
    findDatasetById,
    handleDatasetColumnChange,
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

    const wasApplied = await addDatasetNodeById(action.datasetId, action.colorBy);
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
      let newNodeData = { ...dataItem };

      // 5. Inject specific handlers based on the node type
      if (newNodeType === 'operationNode') {
          newNodeData.color = dataItem.opType === 'buffer' ? '#ec4899' : '#8b5cf6';
      } else if (newNodeType === 'integrationNode') {
          // Inject the callback so the node can talk back to the canvas when the API finishes
          newNodeData.onIntegrationComplete = handleIntegrationComplete;
          newNodeData.onLogActivity = onLogActivity; // ACTIVITY LOG: Pass audit trail callback
          newNodeData.onDeleteNode = handleDeleteNode;
        } else if (newNodeType === 'compareMapNode') {
          newNodeData.onCompareHover = handleCompareHover;
          newNodeData.connectedResults = [];
          newNodeData.isMapSyncEnabled = isMapSyncEnabled;
          newNodeData.globalViewState = globalViewState;
          newNodeData.onGlobalViewStateChange = setGlobalViewState;
          newNodeData.onDeleteNode = handleDeleteNode;
      } else {
          // DatasetNode: inject column select callback for state inheritance
          // Also include sync props for viewport linking
          newNodeData.onShowInfo = handleShowInfo;
          newNodeData.onColumnChange = handleDatasetColumnChange;
          newNodeData.isMapSyncEnabled = isMapSyncEnabled;
          newNodeData.globalViewState = globalViewState;
          newNodeData.onGlobalViewStateChange = setGlobalViewState;
          newNodeData.onDeleteNode = handleDeleteNode;
      }

      const newNode = {
        id: nodeId,
        type: newNodeType, 
        position,
        data: newNodeData,
      };

      console.log('Adding new node:', newNode);

      setNodes((nds) => nds.concat(newNode));
      if (newNodeType === 'datasetNode') {
        queueAutoSuggestRequest(dataItem);
      }
    },
    [
      globalViewState,
      handleDatasetColumnChange,
      handleIntegrationComplete,
      handleShowInfo,
      isMapSyncEnabled,
      onLogActivity,
      screenToFlowPosition,
      createColumnSelectHandler,
      handleCompareHover,
      handleDeleteNode,
      queueAutoSuggestRequest,
    ]
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
          right: '10px',
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

const AnalysisCanvas = ({ sidebarCollapsed, onLogActivity, highlightedLogTs, focusedLogTs, onTraceLineage, onActiveLogTimestampsChange }) => (
  <ReactFlowProvider>
    <CanvasInner
      sidebarCollapsed={sidebarCollapsed}
      onLogActivity={onLogActivity}
      highlightedLogTs={highlightedLogTs}
      focusedLogTs={focusedLogTs}
      onTraceLineage={onTraceLineage}
      onActiveLogTimestampsChange={onActiveLogTimestampsChange}
    />
  </ReactFlowProvider>
);

export default AnalysisCanvas;
