import React, { memo, useMemo, useEffect, useState } from 'react';
import { Handle, Position, NodeResizeControl } from '@xyflow/react';
import { Map as MapIcon, Download, Hexagon, MapPin, Info, ChevronDown, ChevronUp, Crosshair } from 'lucide-react';
import H3PreviewDeckGL from '../../visualization/H3PreviewDeckGL'; 

const HOTSPOT_PALETTES = [
  { name: 'Fire',   emoji: '🔥', low: [253, 224,  71], high: [153,  27,  27] },
  { name: 'Ocean',  emoji: '🌊', low: [186, 230, 253], high: [  7,  89, 133] },
  { name: 'Forest', emoji: '🌿', low: [187, 247, 208], high: [ 20,  83,  45] },
  { name: 'Dusk',   emoji: '🌆', low: [233, 213, 255], high: [ 88,  28, 135] },
];

const getZoneFeatureId = (feature) => {
  const props = feature?.properties || {};
  return String(props.zone_id ?? props.ZONE_ID ?? props.OBJECTID ?? props.objectid ?? props.id ?? props.NAME ?? props.name ?? '');
};

const ResultMapNode = memo(({ id, data }) => {
  // DATA LINEAGE: Track lineage panel visibility
  const [lineageExpanded, setLineageExpanded] = useState(false);
  const provenance = data?.spatialData?.provenance;
  
  // CROSS-CANVAS CONNECTION: Highlight when topology row is hovered or focused
  const highlightedLogTs = data?.highlightedLogTs;
  const focusedLogTs = data?.focusedLogTs;
  const isHighlighted = (highlightedLogTs && provenance?.timestamp === highlightedLogTs) ||
                        (focusedLogTs && provenance?.timestamp === focusedLogTs);
  const isFocused = focusedLogTs && provenance?.timestamp === focusedLogTs;
  
  // GLOBAL VIEWPORT SYNC: Extract sync props from data
  const isMapSyncEnabled = data?.isMapSyncEnabled || false;
  const globalViewState = data?.globalViewState;
  const onGlobalViewStateChange = data?.onGlobalViewStateChange;
  
  // Check if this is a zoned result
  const isZoned = data?.spatialData?.isZoned;
  const outputMode = data?.spatialData?.outputMode || 'grid';
  
  // Grab the dictionary of hexagons (for grid output)
  const resultMapData = data?.spatialData?.data;

  // HOTSPOT SYNTHESIS: AI audit + synthesized priority score
  const [hotspotAudit, setHotspotAudit] = useState(null);
  const [hotspotLoading, setHotspotLoading] = useState(false);
  const [tweakOpen, setTweakOpen] = useState(false);
  const [cardVisible, setCardVisible] = useState(true);    // dismiss the intelligence card
  const [tweakAudits, setTweakAudits] = useState(null);   // user-edited copy of audit variables
  const [tweakGoal, setTweakGoal] = useState('');          // user-defined priority goal
  const [paletteIdx, setPaletteIdx] = useState(0);         // cycles through HOTSPOT_PALETTES
  
  // Grab the GeoJSON zones (for zoned output)
  const zoneGeoJson = data?.spatialData?.geojson;

  const isHotspotCandidate = useMemo(() => {
    return !!(provenance?.isMultivariate && provenance?.variables?.length > 1);
  }, [provenance]);

  useEffect(() => {
    if (!isHotspotCandidate || !provenance?.variables?.length) return;

    let cancelled = false;
    const loadAudit = async () => {
      setHotspotLoading(true);
      try {
        const payload = {
          source_variables: provenance.variables.map(v => ({
            dataset_name: v.dataset,
            column_name: v.targetColumn
          }))
        };

        const response = await fetch('http://localhost:8000/api/v1/copilot/synthesize-hotspot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Hotspot synthesis failed');
        const audit = await response.json();
        if (!cancelled) setHotspotAudit(audit);
      } catch (err) {
        console.error('Hotspot synthesis error:', err);
      } finally {
        if (!cancelled) setHotspotLoading(false);
      }
    };

    loadAudit();
    return () => { cancelled = true; };
  }, [isHotspotCandidate, provenance]);

  // Sync tweakAudits whenever a fresh audit arrives (also resets any manual edits)
  useEffect(() => {
    if (hotspotAudit?.variables?.length) {
      setTweakAudits(hotspotAudit.variables.map(v => ({ ...v })));
      setCardVisible(true);  // re-show card when a fresh audit arrives
    }
  }, [hotspotAudit]);

  // Re-run hotspot synthesis with the current tweakGoal
  const handleRerunWithGoal = async () => {
    if (!provenance?.variables?.length) return;
    setHotspotLoading(true);
    try {
      const payload = {
        source_variables: provenance.variables.map(v => ({
          dataset_name: v.dataset,
          column_name: v.targetColumn
        })),
        ...(tweakGoal.trim() ? { goal: tweakGoal.trim() } : {})
      };
      const response = await fetch('http://localhost:8000/api/v1/copilot/synthesize-hotspot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Hotspot re-run failed');
      const audit = await response.json();
      setHotspotAudit(audit);   // tweakAudits will be refreshed by the sync useEffect above
      setTweakOpen(false);
    } catch (err) {
      console.error('Hotspot re-run error:', err);
    } finally {
      setHotspotLoading(false);
    }
  };

  const hotspotHexData = useMemo(() => {
    const activeAudits = tweakAudits || hotspotAudit?.variables;
    if (!isHotspotCandidate || !resultMapData || !activeAudits?.length) return null;

    const audits = activeAudits;
    const varNames = audits.map(v => v.column_name);

    const stats = {};
    varNames.forEach(name => {
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      Object.values(resultMapData).forEach(info => {
        const val = info?.variables?.[name];
        if (typeof val === 'number' && !Number.isNaN(val)) {
          if (val < min) min = val;
          if (val > max) max = val;
        }
      });
      if (!Number.isFinite(min) || !Number.isFinite(max)) {
        min = 0; max = 1;
      }
      stats[name] = { min, max };
    });

    const totalWeight = audits.reduce((s, v) => s + (Number(v.weight) || 0), 0) || 1;
    const out = {};

    Object.entries(resultMapData).forEach(([hex, info]) => {
      const raws = audits.map(v => info?.variables?.[v.column_name]);
      const hasSignal = raws.some(raw => typeof raw === 'number' && !Number.isNaN(raw) && raw !== 0);
      if (!hasSignal) {
        out[hex] = {
          ...info,
          count: 0,
          variables: {
            ...info.variables,
            hotspot_score: 0
          },
          sample_props: {
            ...(info.sample_props || {}),
            hotspot_score: 0
          }
        };
        return;
      }

      let score = 0;
      audits.forEach(v => {
        const name = v.column_name;
        const raw = info?.variables?.[name];
        const { min, max } = stats[name];
        const denom = max - min;
        const hasValue = typeof raw === 'number' && !Number.isNaN(raw);
        let norm = 0;
        if (hasValue && denom > 0) {
          norm = (raw - min) / denom;
          if ((v.direction || '').toLowerCase() === 'inverted') norm = 1 - norm;
        }
        score += ((Number(v.weight) || 0) / totalWeight) * norm;
      });

      out[hex] = {
        ...info,
        count: score,
        variables: {
          ...info.variables,
          hotspot_score: score
        },
        sample_props: {
          ...(info.sample_props || {}),
          hotspot_score: score
        }
      };
    });

    return out;
  }, [isHotspotCandidate, resultMapData, hotspotAudit, tweakAudits]);

  const hotspotZoneGeoJson = useMemo(() => {
    const activeAudits = tweakAudits || hotspotAudit?.variables;
    if (!isHotspotCandidate || !zoneGeoJson?.features?.length || !activeAudits?.length) return null;

    const audits = activeAudits;
    const varNames = audits.map(v => v.column_name);

    const stats = {};
    varNames.forEach(name => {
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;

      zoneGeoJson.features.forEach(feature => {
        const val = feature?.properties?.[name];
        if (typeof val === 'number' && !Number.isNaN(val)) {
          if (val < min) min = val;
          if (val > max) max = val;
        }
      });

      if (!Number.isFinite(min) || !Number.isFinite(max)) {
        min = 0;
        max = 1;
      }
      stats[name] = { min, max };
    });

    const totalWeight = audits.reduce((s, v) => s + (Number(v.weight) || 0), 0) || 1;

    return {
      ...zoneGeoJson,
      features: zoneGeoJson.features.map(feature => {
        const raws = audits.map(v => feature?.properties?.[v.column_name]);
        const hasSignal = raws.some(raw => typeof raw === 'number' && !Number.isNaN(raw) && raw !== 0);
        if (!hasSignal) {
          return {
            ...feature,
            properties: {
              ...feature.properties,
              hotspot_score: 0
            }
          };
        }

        let score = 0;

        audits.forEach(v => {
          const name = v.column_name;
          const raw = feature?.properties?.[name];
          const { min, max } = stats[name];
          const denom = max - min;
          const hasValue = typeof raw === 'number' && !Number.isNaN(raw);
          let norm = 0;
          if (hasValue && denom > 0) {
            norm = (raw - min) / denom;
            if ((v.direction || '').toLowerCase() === 'inverted') norm = 1 - norm;
          }
          score += ((Number(v.weight) || 0) / totalWeight) * norm;
        });

        return {
          ...feature,
          properties: {
            ...feature.properties,
            hotspot_score: score
          }
        };
      })
    };
  }, [isHotspotCandidate, zoneGeoJson, hotspotAudit, tweakAudits]);
  
  // Determine what to show
  const showHex = !isZoned || outputMode === 'grid' || outputMode === 'both';
  const showZones = isZoned && (outputMode === 'zones' || outputMode === 'both');

  // Different colors for grid vs zones
  const usingHotspot = !!(hotspotHexData || hotspotZoneGeoJson);
  const activePalette = HOTSPOT_PALETTES[paletteIdx % HOTSPOT_PALETTES.length];
  const colorHex = usingHotspot ? '#dc2626' : (showZones && !showHex ? '#10b981' : (resultMapData?.color || '#10b981')); 
  const highlightedZoneId = data?.hoveredCompareFeatureType === 'zone' ? data?.hoveredCompareFeatureId : null;
  const highlightedHexId = data?.hoveredCompareFeatureType === 'hex' ? data?.hoveredCompareFeatureId : null;
  
  const rgbColor = useMemo(() => {
    const r = parseInt(colorHex.slice(1, 3), 16);
    const g = parseInt(colorHex.slice(3, 5), 16);
    const b = parseInt(colorHex.slice(5, 7), 16);
    return [r, g, b];
  }, [colorHex]);

  useEffect(() => {
    const timer = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 50);
    return () => clearTimeout(timer);
  }, []);

  // Determine node title
  const nodeTitle = useMemo(() => {
    if (isZoned) {
      if (outputMode === 'both') return 'H3 + Zones Result';
      if (outputMode === 'zones') return 'Zoned Result';
    }
    return data.name || 'H3 Integration Result';
  }, [isZoned, outputMode, data.name]);

  // Determine header icon
  const HeaderIcon = showZones && !showHex ? MapPin : Hexagon;

  const comparePayload = useMemo(() => {
    if (hotspotZoneGeoJson?.features?.length) {
      return {
        kind: 'zones',
        label: nodeTitle,
        geojson: {
          ...hotspotZoneGeoJson,
          features: hotspotZoneGeoJson.features.filter(feature => getZoneFeatureId(feature))
        }
      };
    }

    if (hotspotHexData && Object.keys(hotspotHexData).length > 0) {
      return {
        kind: 'hex',
        label: nodeTitle,
        hexData: hotspotHexData
      };
    }

    return null;
  }, [nodeTitle, hotspotZoneGeoJson, hotspotHexData]);

  useEffect(() => {
    if (!data?.onCompareDataReady) return;
    data.onCompareDataReady(id, comparePayload);
  }, [id, comparePayload, data?.onCompareDataReady]);

  return (
    <div style={{
      width: '100%',
      height: '100%',
      minWidth: '240px',
      minHeight: '240px',
      borderRadius: '8px',
      backgroundColor: '#fff', 
      border: isHighlighted ? `2px solid #0d9488` : `1px solid ${colorHex}`,
      boxShadow: isHighlighted 
        ? '0 0 20px rgba(13, 148, 136, 0.5), 0 0 40px rgba(13, 148, 136, 0.25)'
        : '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      transition: 'box-shadow 0.2s ease, border 0.2s ease',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <NodeResizeControl 
        minWidth={240} 
        minHeight={220}
        style={{ background: 'transparent', border: 'none' }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ position: 'absolute', right: 4, bottom: 4, cursor: 'nwse-resize' }}>
          <polyline points="21 15 21 21 15 21"></polyline>
          <line x1="21" y1="21" x2="15" y2="15"></line>
        </svg>
      </NodeResizeControl>

      {/* Header */}
      <div style={{ backgroundColor: colorHex, color: '#fff', padding: '8px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderRadius: '7px 7px 0 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 'bold' }}>
          <HeaderIcon size={14} /> {nodeTitle}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isZoned && (
            <div style={{ fontSize: '9px', backgroundColor: 'rgba(255,255,255,0.2)', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>
              {outputMode}
            </div>
          )}
          {/* CROSS-CANVAS CONNECTION: Trace Lineage toggle */}
          {provenance && data?.onTraceLineage && (
            <button
              onClick={() => data.onTraceLineage(isFocused ? null : provenance.timestamp)}
              className="nodrag"
              style={{
                background: isFocused ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.2)',
                border: 'none', borderRadius: '4px', padding: '2px 4px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', transition: 'background 0.15s ease',
              }}
              title={isFocused ? 'Release lineage trace' : 'Trace lineage in topology panel'}
            >
              <Crosshair size={12} style={{ color: isFocused ? colorHex : 'inherit' }} />
            </button>
          )}
          {/* DATA LINEAGE: Info toggle button */}
          {provenance && (
            <button
              onClick={() => setLineageExpanded(!lineageExpanded)}
              className="nodrag"
              style={{
                background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '4px',
                padding: '2px 4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px'
              }}
              title="View data lineage"
            >
              <Info size={12} />
              {lineageExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
          )}
        </div>
      </div>

      {/* Preview Area — IDENTICAL to original. Never changes size. */}
      <div style={{ 
        flexGrow: 1, 
        height: '100%',
        minHeight: '160px', 
        backgroundColor: '#f8fafc',
        position: 'relative',
        borderRadius: '0 0 8px 8px'
      }}>
        {(resultMapData || zoneGeoJson) && (
          <div style={{ position: 'absolute', inset: 0, borderRadius: '0 0 8px 8px', overflow: 'hidden' }}>
            <H3PreviewDeckGL 
              hexData={showHex ? (hotspotHexData || resultMapData) : null} 
              geojsonData={showZones ? (hotspotZoneGeoJson || zoneGeoJson) : null}
              color={rgbColor}
              useHotspotPalette={usingHotspot}
              hotspotPalette={usingHotspot ? activePalette : null}
              highlightedHexId={highlightedHexId}
              highlightedZoneId={highlightedZoneId}
              showHex={showHex}
              showZones={showZones}
              isMapSyncEnabled={isMapSyncEnabled}
              globalViewState={globalViewState}
              onGlobalViewStateChange={onGlobalViewStateChange}
            />
          </div>
        )}

        {/* HOTSPOT INTELLIGENCE CARD — shown when tweak panel is closed */}
        {isHotspotCandidate && !tweakOpen && cardVisible && hotspotAudit?.variables?.length > 0 && (
          <div
            className="nodrag"
            style={{
              position: 'absolute',
              right: 8,
              bottom: 8,
              width: '230px',
              zIndex: 9,
              background: 'rgba(255,255,255,0.96)',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              padding: '8px',
              fontSize: '9px',
              color: '#374151',
              boxShadow: '0 6px 16px rgba(0,0,0,0.12)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <div style={{ fontWeight: 700, fontSize: '10px', color: '#991b1b' }}>
                🎯 Hotspot Priority{tweakGoal ? ` · ${tweakGoal}` : ''}
              </div>
              <button
                className="nodrag"
                onClick={() => setCardVisible(false)}
                title="Dismiss"
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 0 0 4px', lineHeight: 1, color: '#9ca3af', fontSize: '11px', fontWeight: 700 }}
              >
                ✕
              </button>
            </div>
            {(tweakAudits || hotspotAudit.variables).map((v, idx) => {
              const totalW = (tweakAudits || hotspotAudit.variables).reduce((s, a) => s + (a.weight || 0), 0) || 1;
              const dispPct = Math.round((v.weight / totalW) * 100);
              return (
                <div key={`card-${v.column_name}-${idx}`} style={{ display: 'grid', gridTemplateColumns: '14px 1fr auto', gap: '4px', marginBottom: '4px', alignItems: 'center' }}>
                  <span style={{ color: v.direction === 'inverted' ? '#b45309' : '#047857' }}>
                    {v.direction === 'inverted' ? '↓' : '↑'}
                  </span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.reasoning}>{v.column_name}</span>
                  <span style={{ fontWeight: 600 }}>{dispPct}%</span>
                </div>
              );
            })}
            {/* Legend bar + action buttons */}
            <div style={{ marginTop: '6px', borderTop: '1px solid #fee2e2', paddingTop: '5px' }}>
              <div style={{ fontSize: '8px', color: '#7f1d1d', marginBottom: '5px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>{activePalette.emoji}</span>
                <span style={{ flex: 1 }}>{activePalette.name}: low → high priority</span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }}>
                <button
                  className="nodrag"
                  onClick={() => setTweakOpen(true)}
                  style={{ flex: 1, padding: '3px 2px', font: 'inherit', fontSize: '8px', background: '#fef9f9', border: '1px solid #fca5a5', borderRadius: '4px', cursor: 'pointer', color: '#991b1b', fontWeight: 600 }}
                >
                  🛠️ Tweak Weights
                </button>
                <button
                  className="nodrag"
                  onClick={() => setPaletteIdx(i => (i + 1) % HOTSPOT_PALETTES.length)}
                  style={{ flex: 1, padding: '3px 2px', font: 'inherit', fontSize: '8px', background: '#fef9f9', border: '1px solid #fca5a5', borderRadius: '4px', cursor: 'pointer', color: '#991b1b', fontWeight: 600 }}
                >
                  🎨 Change Palette
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TWEAK PANEL — replaces intelligence card when open */}
        {isHotspotCandidate && tweakOpen && (tweakAudits || []).length > 0 && (
          <div
            className="nodrag"
            style={{
              position: 'absolute',
              right: 8,
              bottom: 8,
              width: '250px',
              maxHeight: 'calc(100% - 16px)',
              overflowY: 'auto',
              zIndex: 10,
              background: 'rgba(255,255,255,0.98)',
              border: '1px solid #fca5a5',
              borderRadius: '8px',
              padding: '10px',
              fontSize: '10px',
              color: '#374151',
              boxShadow: '0 8px 24px rgba(0,0,0,0.15)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <div style={{ fontWeight: 700, fontSize: '10px', color: '#991b1b' }}>🛠️ Tweak Panel</div>
              <button
                className="nodrag"
                onClick={() => setTweakOpen(false)}
                title="Close"
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 0 0 4px', lineHeight: 1, color: '#9ca3af', fontSize: '11px', fontWeight: 700 }}
              >
                ✕
              </button>
            </div>
            {/* Goal */}
            <div style={{ fontWeight: 700, fontSize: '10px', color: '#991b1b', marginBottom: '5px' }}>
              🎯 Priority Goal
            </div>
            <input
              className="nodrag"
              type="text"
              value={tweakGoal}
              onChange={e => setTweakGoal(e.target.value)}
              placeholder="e.g. Pedestrian safety risk"
              style={{ width: '100%', boxSizing: 'border-box', marginBottom: '9px', padding: '4px 6px', borderRadius: '4px', border: '1px solid #fca5a5', font: 'inherit', fontSize: '9px', outline: 'none', backgroundColor: '#ffffff', color: '#374151', caretColor: '#374151' }}
            />
            {/* Weight + direction per variable */}
            <div style={{ fontWeight: 700, fontSize: '10px', color: '#991b1b', marginBottom: '4px' }}>
              🛠️ Weights &amp; Direction
            </div>
            {(tweakAudits || []).map((v, idx) => {
              const totalW = (tweakAudits || []).reduce((s, a) => s + (a.weight || 0), 0) || 1;
              const dispPct = Math.round((v.weight / totalW) * 100);
              return (
                <div key={`tweak-${v.column_name}-${idx}`} style={{ marginBottom: '9px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px', alignItems: 'center' }}>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, fontSize: '9px' }} title={v.column_name}>{v.column_name}</span>
                    <span style={{ fontWeight: 600, marginLeft: '6px', fontSize: '9px', minWidth: '28px', textAlign: 'right' }}>{dispPct}%</span>
                  </div>
                  <input
                    className="nodrag"
                    type="range" min={0} max={100} step={1}
                    value={Math.round((v.weight || 0) * 100)}
                    onChange={e => {
                      const w = parseInt(e.target.value) / 100;
                      setTweakAudits(prev => prev.map((a, i) => i === idx ? { ...a, weight: w } : a));
                    }}
                    style={{ width: '100%', cursor: 'pointer', accentColor: '#dc2626', marginBottom: '3px' }}
                  />
                  <button
                    className="nodrag"
                    onClick={() => setTweakAudits(prev => prev.map((a, i) => i === idx ? { ...a, direction: a.direction === 'inverted' ? 'normal' : 'inverted' } : a))}
                    style={{ font: 'inherit', fontSize: '8px', padding: '2px 7px', borderRadius: '4px', border: '1px solid #e5e7eb', background: v.direction === 'inverted' ? '#fef3c7' : '#f0fdf4', cursor: 'pointer', color: v.direction === 'inverted' ? '#b45309' : '#047857', fontWeight: 600 }}
                  >
                    {v.direction === 'inverted' ? '↓ Inverted' : '↑ Normal'}
                  </button>
                </div>
              );
            })}
            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '4px', marginTop: '6px', borderTop: '1px solid #fee2e2', paddingTop: '6px' }}>
              <button
                className="nodrag"
                onClick={handleRerunWithGoal}
                disabled={hotspotLoading}
                style={{ flex: 1, font: 'inherit', fontSize: '8px', padding: '5px 2px', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: hotspotLoading ? 'wait' : 'pointer', fontWeight: 600 }}
              >
                {hotspotLoading ? '⏳ Running…' : '🤖 Re-run AI'}
              </button>
              <button
                className="nodrag"
                onClick={() => setTweakOpen(false)}
                style={{ flex: 1, font: 'inherit', fontSize: '8px', padding: '5px 2px', background: '#f1f5f9', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', color: '#374151', fontWeight: 600 }}
              >
                ✓ Apply
              </button>
            </div>
          </div>
        )}

        {isHotspotCandidate && hotspotLoading && (
          <div className="nodrag" style={{ position: 'absolute', right: 8, top: 8, zIndex: 9, background: 'rgba(255,255,255,0.9)', border: '1px solid #e5e7eb', borderRadius: '6px', padding: '4px 6px', fontSize: '9px', color: '#6b7280' }}>
            Synthesizing hotspot…
          </div>
        )}

        {/* DATA LINEAGE: Panel as absolute overlay ON TOP of the map.
            Positioned inside the map container so it never affects the
            map container's dimensions — DeckGL never sees a resize. */}
        {provenance && lineageExpanded && (
          <div
            className="nodrag"
            style={{
              position: 'absolute',
              top: 0, left: 0, right: 0,
              zIndex: 10,
              backgroundColor: 'rgba(248, 250, 252, 0.97)',
              backdropFilter: 'blur(4px)',
              borderBottom: '1px solid #e2e8f0',
              padding: '10px',
              fontSize: '10px',
              color: '#334155',
              maxHeight: '70%',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            }}
          >
            {/* Header & Meta */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
              <span style={{ fontWeight: '600', color: '#0f172a' }}>📊 Data Lineage</span>
              <span style={{ fontSize: '8px', color: '#64748b' }}>
                {new Date(provenance.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>

            {/* Global Settings Badges */}
            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
              <span style={{ backgroundColor: '#e0e7ff', color: '#3730a3', padding: '2px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: '600' }}>
                H3 Res {provenance.resolution}
              </span>
              {provenance.zoningEnabled && provenance.targetZones && (
                <span style={{ backgroundColor: '#dcfce7', color: '#166534', padding: '2px 6px', borderRadius: '4px', fontSize: '9px', fontWeight: '600' }}>
                  Zones: {provenance.targetZones.replace(/^.*[\/]/, '')}
                </span>
              )}
            </div>

            {/* Variables Sequence */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {provenance.variables?.map((v, i) => (
                <div key={i} style={{
                  backgroundColor: '#fff', padding: '6px', borderRadius: '6px',
                  border: '1px solid #cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '700', color: '#0f172a', fontSize: '10px' }}>{v.targetColumn}</span>
                    <span style={{ fontSize: '8px', color: '#64748b', maxWidth: '80px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.dataset}>
                      {v.dataset?.replace(/^.*[\/]/, '')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                    <span style={{ backgroundColor: '#f1f5f9', color: '#475569', padding: '2px 4px', borderRadius: '3px', fontSize: '8px', border: '1px solid #e2e8f0' }} title={`Allocation: ${v.allocation}`}>
                      {v.allocation?.replace('Proportional', 'Prop.').replace('Weighted', 'Wt.')}
                    </span>
                    <span style={{ backgroundColor: '#f1f5f9', color: '#475569', padding: '2px 4px', borderRadius: '3px', fontSize: '8px', border: '1px solid #e2e8f0' }} title={`Grid Aggregation: ${v.aggregation}`}>
                      {v.aggregation?.replace('Aggregation', 'Agg')}
                    </span>
                    {v.zoningMapping && (
                      <span style={{ backgroundColor: '#f0fdf4', color: '#15803d', padding: '2px 4px', borderRadius: '3px', fontSize: '8px', border: '1px solid #bbf7d0' }} title={`Zone Mapping: ${v.zoningMapping}`}>
                        {v.zoningMapping?.replace('Zoning', 'Map')}
                      </span>
                    )}
                    {v.zoningAggregation && (
                      <span style={{ backgroundColor: '#f0fdf4', color: '#15803d', padding: '2px 4px', borderRadius: '3px', fontSize: '8px', border: '1px solid #bbf7d0' }} title={`Zone Aggregation: ${v.zoningAggregation}`}>
                        {v.zoningAggregation?.replace('Zoning', 'Agg')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <Handle type="target" position={Position.Left} style={{ width: '10px', height: '10px', background: '#fff', border: `2px solid ${colorHex}`, left: '-6px' }} />
      <Handle type="source" position={Position.Right} style={{ width: '10px', height: '10px', background: colorHex, border: '2px solid #fff', right: '-6px' }} />
      
      <style>{`
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
});

export default ResultMapNode;