import React, { memo, useMemo, useCallback, useState } from 'react';
import { Handle, Position, NodeResizeControl } from '@xyflow/react';
import { GitCompareArrows, ArrowDown, ArrowUp, Minus, Eye, EyeOff, X } from 'lucide-react';
import H3PreviewDeckGL from '../../visualization/H3PreviewDeckGL';

const COMPARE_PALETTE = {
  low: [248, 250, 252],
  high: [31, 41, 55]
};

const getZoneFeatureId = (feature) => {
  const props = feature?.properties || {};
  return String(
    props.zone_id ?? props.ZONE_ID ?? props.OBJECTID ?? props.objectid ?? props.id ?? props.NAME ?? props.name ?? ''
  );
};

const getScoreLabel = (delta) => {
  const abs = Math.abs(delta || 0);
  if (abs >= 0.5) return 'Major Shift';
  if (abs >= 0.25) return 'Significant Change';
  if (abs >= 0.1) return 'Moderate Change';
  return 'Minor Change';
};

const deriveComparePayload = (item) => {
  if (item?.comparePayload) return item.comparePayload;

  const spatial = item?.spatialData;
  if (!spatial) return null;

  if (spatial?.geojson?.features?.length) {
    const excludeProps = ['zone_id', 'ZONE_ID', 'OBJECTID', 'objectid', 'Shape_Area', 'Shape_Leng'];
    const features = spatial.geojson.features
      .map(feature => {
        const props = feature?.properties || {};
        let score = Number(props.hotspot_score ?? props.zone_value ?? props.value ?? props.count);

        if (Number.isNaN(score)) {
          const numericVals = Object.entries(props)
            .filter(([key, val]) => !excludeProps.includes(key) && typeof val === 'number' && !Number.isNaN(val))
            .map(([, val]) => val);

          score = numericVals.length ? numericVals.reduce((sum, val) => sum + val, 0) : Number.NaN;
        }

        if (Number.isNaN(score)) return null;
        return {
          ...feature,
          properties: {
            ...props,
            hotspot_score: score
          }
        };
      })
      .filter(Boolean);

    if (features.length) {
      return {
        kind: 'zones',
        geojson: { type: 'FeatureCollection', features }
      };
    }
  }

  if (spatial?.data && typeof spatial.data === 'object') {
    const hexData = {};
    Object.entries(spatial.data).forEach(([hex, info]) => {
      const score = Number(info?.variables?.hotspot_score ?? info?.count);
      if (Number.isNaN(score)) return;
      hexData[hex] = {
        ...info,
        count: score,
        variables: {
          ...(info?.variables || {}),
          hotspot_score: score
        }
      };
    });

    if (Object.keys(hexData).length) {
      return {
        kind: 'hex',
        hexData
      };
    }
  }

  return null;
};

const CompareMapNode = memo(({ id, data }) => {
  const [showDirectionIcons, setShowDirectionIcons] = useState(false);
  const connectedResults = data?.connectedResults || [];
  const validInputs = connectedResults
    .map(item => ({
      ...item,
      resolvedPayload: deriveComparePayload(item)
    }))
    .filter(item => item?.resolvedPayload);
  const [leftInput, rightInput] = validInputs;

  const handleZoneHover = useCallback((featureId) => {
    data?.onCompareHover?.(featureId || null, featureId ? 'zone' : null);
  }, [data]);

  const handleHexHover = useCallback((hexId) => {
    data?.onCompareHover?.(hexId || null, hexId ? 'hex' : null);
  }, [data]);

  const comparison = useMemo(() => {
    if (validInputs.length < 2) {
      return { status: 'waiting', message: 'Connect two Hotspot Result maps to compare spatial change.' };
    }

    const a = leftInput.resolvedPayload;
    const b = rightInput.resolvedPayload;

    if (!a || !b) {
      return { status: 'waiting', message: 'Waiting for both source maps to finish preparing hotspot scores.' };
    }

    if (a.kind !== b.kind) {
      return { status: 'invalid', message: 'Both inputs must use the same output type (zones or H3 grid).' };
    }

    if (a.kind === 'zones') {
      const aMap = new Map((a.geojson?.features || []).map(feature => [getZoneFeatureId(feature), feature]));
      const bMap = new Map((b.geojson?.features || []).map(feature => [getZoneFeatureId(feature), feature]));
      const sharedIds = [...aMap.keys()].filter(key => key && bMap.has(key));

      if (!sharedIds.length) {
        return { status: 'invalid', message: 'No shared zone IDs found between the two result maps.' };
      }

      const features = sharedIds.map(zoneId => {
        const featureA = aMap.get(zoneId);
        const featureB = bMap.get(zoneId);
        const scoreA = Number(featureA?.properties?.hotspot_score) || 0;
        const scoreB = Number(featureB?.properties?.hotspot_score) || 0;
        const delta = scoreB - scoreA;
        const magnitude = Math.abs(delta);
        const label = featureB?.properties?.name || featureB?.properties?.NAME || featureB?.properties?.district || featureB?.properties?.District || `Zone ${zoneId}`;

        return {
          ...featureB,
          properties: {
            ...featureB.properties,
            zone_id: zoneId,
            compare_label: label,
            map1_score: scoreA,
            map2_score: scoreB,
            delta_signed: delta,
            diff_magnitude: magnitude,
            hotspot_score: magnitude,
            source1_label: leftInput.label,
            source2_label: rightInput.label
          }
        };
      });

      return {
        status: 'ready',
        kind: 'zones',
        geojson: { type: 'FeatureCollection', features },
        changedCount: features.filter(f => (f.properties?.diff_magnitude || 0) > 0.001).length,
        maxDiff: Math.max(...features.map(f => f.properties?.diff_magnitude || 0), 1e-6)
      };
    }

    const aHex = a.hexData || {};
    const bHex = b.hexData || {};
    const sharedHexes = Object.keys(aHex).filter(hex => bHex[hex]);

    if (!sharedHexes.length) {
      return { status: 'invalid', message: 'No shared H3 cells found between the two result maps.' };
    }

    const hexData = {};
    sharedHexes.forEach(hex => {
      const scoreA = Number(aHex[hex]?.variables?.hotspot_score ?? aHex[hex]?.count) || 0;
      const scoreB = Number(bHex[hex]?.variables?.hotspot_score ?? bHex[hex]?.count) || 0;
      const delta = scoreB - scoreA;
      const magnitude = Math.abs(delta);

      hexData[hex] = {
        count: magnitude,
        variables: {
          map1_score: scoreA,
          map2_score: scoreB,
          delta_signed: delta,
          diff_magnitude: magnitude
        },
        sample_props: {
          map1_score: scoreA,
          map2_score: scoreB,
          delta_signed: delta,
          diff_magnitude: magnitude,
          source1_label: leftInput.label,
          source2_label: rightInput.label
        }
      };
    });

    return {
      status: 'ready',
      kind: 'hex',
      hexData,
      changedCount: sharedHexes.filter(hex => (hexData[hex]?.count || 0) > 0.001).length,
      maxDiff: Math.max(...sharedHexes.map(hex => hexData[hex]?.count || 0), 1e-6)
    };
  }, [validInputs, leftInput, rightInput]);

  const customTooltip = useCallback(({ object, layer }) => {
    if (!object) return null;

    if (layer?.id === 'zone-layer') {
      const props = object.properties || {};
      const delta = Number(props.delta_signed) || 0;
      const directionText = delta > 0 ? 'Increase' : delta < 0 ? 'Decrease' : 'No Change';
      const icon = delta > 0 ? '⬆' : delta < 0 ? '⬇' : '•';

      return {
        html: `
          <div style="font-family: sans-serif;">
            <div style="font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
              📍 ${props.compare_label || props.zone_id || 'Zone'}
            </div>
            <div><strong>${props.source1_label || 'Map 1'}:</strong> ${(Number(props.map1_score) || 0).toFixed(2)}</div>
            <div><strong>${props.source2_label || 'Map 2'}:</strong> ${(Number(props.map2_score) || 0).toFixed(2)}</div>
            <div style="margin-top: 4px;"><strong>Total Shift:</strong> ${delta >= 0 ? '+' : ''}${delta.toFixed(2)} ${icon} ${getScoreLabel(delta)} ${directionText}</div>
          </div>
        `,
        style: {
          backgroundColor: '#111827',
          color: '#f8fafc',
          fontSize: '11px',
          padding: '8px',
          borderRadius: '6px',
          boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
          maxWidth: '260px',
          border: '1px solid #374151'
        }
      };
    }

    if (layer?.id === 'h3-hexagon-layer') {
      const delta = Number(object?.variables?.delta_signed) || 0;
      const icon = delta > 0 ? '⬆' : delta < 0 ? '⬇' : '•';
      const source1 = object?.props?.source1_label || 'Map 1';
      const source2 = object?.props?.source2_label || 'Map 2';
      return {
        html: `
          <div style="font-family: sans-serif;">
            <div style="font-weight: bold; margin-bottom: 6px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
              Hex: ${object.hex.slice(0, 8)}...
            </div>
            <div><strong>${source1}:</strong> ${(Number(object?.variables?.map1_score) || 0).toFixed(2)}</div>
            <div><strong>${source2}:</strong> ${(Number(object?.variables?.map2_score) || 0).toFixed(2)}</div>
            <div style="margin-top: 4px;"><strong>Total Shift:</strong> ${delta >= 0 ? '+' : ''}${delta.toFixed(2)} ${icon} ${getScoreLabel(delta)}</div>
          </div>
        `,
        style: {
          backgroundColor: '#111827',
          color: '#f8fafc',
          fontSize: '11px',
          padding: '8px',
          borderRadius: '6px',
          boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
          maxWidth: '260px',
          border: '1px solid #374151'
        }
      };
    }

    return null;
  }, []);

  const colorHex = '#4b5563';

  return (
    <div style={{
      width: '100%',
      height: '100%',
      minWidth: '560px',
      minHeight: '540px',
      borderRadius: '8px',
      backgroundColor: '#fff',
      border: '1px solid #4b5563',
      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <NodeResizeControl minWidth={260} minHeight={220} style={{ background: 'transparent', border: 'none' }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ position: 'absolute', right: 4, bottom: 4, cursor: 'nwse-resize' }}>
          <polyline points="21 15 21 21 15 21"></polyline>
          <line x1="21" y1="21" x2="15" y2="15"></line>
        </svg>
      </NodeResizeControl>

      <div style={{ backgroundColor: colorHex, color: '#fff', padding: '8px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderRadius: '7px 7px 0 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 'bold' }}>
          <GitCompareArrows size={14} /> Spatial Delta Map
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ fontSize: '9px', backgroundColor: 'rgba(255,255,255,0.15)', padding: '2px 6px', borderRadius: '4px' }}>
            Degree of Change
          </div>
          <button
            className="nodrag"
            onClick={(e) => {
              e.stopPropagation();
              data?.onDeleteNode?.(id);
            }}
            title="Remove node"
            style={{
              border: 'none',
              background: 'rgba(255,255,255,0.2)',
              color: '#fff',
              width: '18px',
              height: '18px',
              borderRadius: '4px',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0
            }}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      <div style={{ flexGrow: 1, minHeight: '160px', backgroundColor: '#f8fafc', position: 'relative', borderRadius: '0 0 8px 8px' }}>
        {comparison.status === 'ready' ? (
          <>
            <div style={{ position: 'absolute', inset: 0, borderRadius: '0 0 8px 8px', overflow: 'hidden' }}>
              <H3PreviewDeckGL
                hexData={comparison.kind === 'hex' ? comparison.hexData : null}
                geojsonData={comparison.kind === 'zones' ? comparison.geojson : null}
                color={[75, 85, 99]}
                useHotspotPalette={true}
                hotspotPalette={COMPARE_PALETTE}
                showDirectionSymbols={showDirectionIcons}
                showHex={comparison.kind === 'hex'}
                showZones={comparison.kind === 'zones'}
                isMapSyncEnabled={data?.isMapSyncEnabled}
                globalViewState={data?.globalViewState}
                onGlobalViewStateChange={data?.onGlobalViewStateChange}
                hideLegend={true}
                customTooltip={customTooltip}
                onZoneHover={comparison.kind === 'zones' ? handleZoneHover : undefined}
                onHexHover={comparison.kind === 'hex' ? handleHexHover : undefined}
              />
            </div>

            <div className="nodrag" style={{ position: 'absolute', right: 8, top: 8, zIndex: 10, background: 'rgba(255,255,255,0.96)', border: '1px solid #d1d5db', borderRadius: '8px', padding: '8px', width: '180px', fontSize: '9px', color: '#374151', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                <div style={{ fontWeight: 700, fontSize: '10px', color: '#111827' }}>Δ Comparison</div>
                <button
                  className="nodrag"
                  onClick={() => setShowDirectionIcons(prev => !prev)}
                  title={showDirectionIcons ? 'Hide direction symbols overlay' : 'Show direction symbols overlay'}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '20px',
                    height: '20px',
                    borderRadius: '4px',
                    border: '1px solid #d1d5db',
                    background: showDirectionIcons ? '#e2e8f0' : '#fff',
                    color: '#334155',
                    cursor: 'pointer',
                    padding: 0
                  }}
                >
                  {showDirectionIcons ? <Eye size={12} /> : <EyeOff size={12} />}
                </button>
              </div>
              {/* <div style={{ marginBottom: '4px' }}><strong>{leftInput?.label || 'Map 1'}</strong> → <strong>{rightInput?.label || 'Map 2'}</strong></div> */}
              <div style={{ marginBottom: '4px' }}><strong>Compare how priority scores differ between the two maps. </strong></div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '3px' }}>
                <ArrowUp size={10} color="#374151" /> Higher in Map 2
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '3px' }}>
                <ArrowDown size={10} color="#374151" /> Lower in Map 2
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '5px' }}>
                <Minus size={10} color="#374151" /> No change
              </div>
              <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: '5px', color: '#4b5563' }}>
                {comparison.changedCount} areas changed
              </div>
            </div>

            <div className="nodrag" style={{ position: 'absolute', left: 8, bottom: 36, zIndex: 10, backgroundColor: 'rgba(255, 255, 255, 0.92)', padding: '4px 6px', borderRadius: '4px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', fontSize: '8px', color: '#334155', display: 'flex', flexDirection: 'column', gap: '3px', border: '1px solid #d1d5db' }}>
              <div style={{ fontWeight: 'bold' }}>Degree of Change</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>0</span>
                <div style={{ width: '48px', height: '6px', borderRadius: '3px', background: 'linear-gradient(to right, rgba(248,250,252,1), rgba(31,41,55,1))' }} />
                <span>{comparison.maxDiff.toFixed(2)}</span>
              </div>
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '16px', color: comparison.status === 'invalid' ? '#b91c1c' : '#64748b', textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
                {comparison.status === 'invalid' ? 'Comparison unavailable' : 'Waiting for inputs'}
              </div>
              <div style={{ fontSize: '10px' }}>{comparison.message}</div>
            </div>
          </div>
        )}
      </div>

      <Handle id="compare-a" type="target" position={Position.Left} style={{ top: '35%', width: '10px', height: '10px', background: '#fff', border: `2px solid ${colorHex}`, left: '-6px' }} />
      <Handle id="compare-b" type="target" position={Position.Left} style={{ top: '65%', width: '10px', height: '10px', background: '#fff', border: `2px solid ${colorHex}`, left: '-6px' }} />
    </div>
  );
});

export default CompareMapNode;
