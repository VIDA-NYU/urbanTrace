import React, { useMemo, useState, useEffect, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import { GeoJsonLayer, TextLayer } from '@deck.gl/layers';
import { cellToLatLng } from 'h3-js';
import { Layers } from 'lucide-react'; 

const H3PreviewDeckGL = ({ 
  hexData, 
  geojsonData, 
  color = [236, 72, 153], 
  useHotspotPalette = false,
  hotspotPalette = null,  // { low: [r,g,b], high: [r,g,b] } – overrides default fire palette
  highlightedHexId = null,
  highlightedZoneId = null,
  onHexHover,
  onZoneHover,
  hideLegend = false,
  customTooltip = null,
  showDirectionSymbols = false,
  showHex = true, 
  showZones = false,
  // GLOBAL VIEWPORT SYNC: Props for linked camera
  isMapSyncEnabled = false,
  globalViewState,
  onGlobalViewStateChange
}) => {  
  // 👇 1. Add a ref to track the container and a state for readiness
    const containerRef = useRef(null);
    const [isReady, setIsReady] = useState(false);
    
    const [is3D, setIs3D] = useState(false);
    const [localViewState, setLocalViewState] = useState({
      longitude: -74.0,
      latitude: 40.7,
      zoom: 10,
      pitch: 0, 
      bearing: 0
    });
    
    // GLOBAL VIEWPORT SYNC: Use global or local viewState
    const viewState = isMapSyncEnabled && globalViewState ? globalViewState : localViewState;
  
    // 👇 2. THE SHIELD: Wait until React Flow gives this container actual dimensions (> 0)
    useEffect(() => {
      if (!containerRef.current) return;
      const observer = new ResizeObserver(entries => {
        const { width, height } = entries[0].contentRect;
        if (width > 0 && height > 0) {
          setIsReady(true);
        }
      });
      observer.observe(containerRef.current);
      return () => observer.disconnect();
    }, []);

  const handleToggleMode = () => {
    const nextIs3D = !is3D;
    setIs3D(nextIs3D);
    
    const nextViewState = {
      ...viewState,
      pitch: nextIs3D ? 45 : 0,  
      bearing: nextIs3D ? viewState.bearing : 0 
    };
    
    // GLOBAL VIEWPORT SYNC: Update appropriate state
    if (isMapSyncEnabled && onGlobalViewStateChange) {
      onGlobalViewStateChange(nextViewState);
    } else {
      setLocalViewState(nextViewState);
    }
  };
  
  // GLOBAL VIEWPORT SYNC: Handler for view state changes
  const handleViewStateChange = ({ viewState: newViewState }) => {
    if (isMapSyncEnabled && onGlobalViewStateChange) {
      onGlobalViewStateChange(newViewState);
    } else {
      setLocalViewState(newViewState);
    }
  };

  const getZoneFeatureId = (feature) => {
    const props = feature?.properties || {};
    return String(props.zone_id ?? props.ZONE_ID ?? props.OBJECTID ?? props.objectid ?? props.id ?? props.NAME ?? props.name ?? '');
  };

  const { data, maxCount, variableNames } = useMemo(() => {
    if (!hexData) {
      console.log("Warning: No hexData provided to H3PreviewDeckGL. DeckGL will render an empty map.");
      return { data: [], maxCount: 1, variableNames: [] };
    }
    let max = 1;
    let varNames = new Set();
    
    const parsedData = Object.entries(hexData).map(([hexId, info]) => {
      if (info.count > max) max = info.count;
      
      // Track variable names from multivariate data
      if (info.variables) {
        Object.keys(info.variables).forEach(name => varNames.add(name));
      }
      
      return {
        hex: hexId,
        count: info.count,
        variables: info.variables || {},
        sources: info.sources || [],
        props: info.sample_props || {}
      };
    });
    
    return { data: parsedData, maxCount: max, variableNames: [...varNames] };
  }, [hexData]);

  // Process GeoJSON zone data (handles both single-variable zone_value and multivariate columns)
  const { zoneFeatures, maxZoneValue, zoneVariableNames } = useMemo(() => {
    if (!geojsonData?.features) {
      return { zoneFeatures: null, maxZoneValue: 1, zoneVariableNames: [] };
    }
    
    let max = 1;
    let varNames = new Set();
    
    // Detect variable names (any numeric property that isn't zone_id or geometry-related)
    const excludeProps = ['zone_id', 'geometry', 'OBJECTID', 'Shape_Area', 'Shape_Leng'];
    
    geojsonData.features.forEach(f => {
      const props = f.properties || {};
      
      // Sum all numeric variable values for intensity
      let totalVal = 0;
      Object.entries(props).forEach(([key, val]) => {
        if (!excludeProps.includes(key) && typeof val === 'number' && !isNaN(val)) {
          varNames.add(key);
          totalVal += val;
        }
      });
      
      // Track max for color intensity
      if (props.zone_value !== undefined) {
        if (props.zone_value > max) max = props.zone_value;
      } else if (totalVal > max) {
        max = totalVal;
      }
    });
    
    return { zoneFeatures: geojsonData, maxZoneValue: max, zoneVariableNames: [...varNames] };
  }, [geojsonData]);

  const getDirectionSymbol = (delta) => {
    const abs = Math.abs(Number(delta) || 0);
    if (abs < 0.1) return '•';
    return delta > 0 ? '⬆' : '⬇';
  };

  const getDirectionColor = (delta) => {
    const abs = Math.abs(Number(delta) || 0);
    if (abs < 0.1) return [107, 114, 128, 255];
    return delta > 0 ? [22, 163, 74, 255] : [220, 38, 38, 255];
  };

  const getDirectionSize = (delta) => {
    const abs = Math.abs(Number(delta) || 0);
    if (abs >= 0.5) return 28;
    if (abs >= 0.25) return 20;
    if (abs >= 0.1) return 14;
    return 8;
  };

  const getPolygonCentroid = (geometry) => {
    const type = geometry?.type;
    const coords = geometry?.coordinates;
    if (!type || !coords) return null;

    let points = [];
    if (type === 'Polygon') {
      points = coords.flat(1);
    } else if (type === 'MultiPolygon') {
      points = coords.flat(2);
    }

    const validPoints = points.filter(point => Array.isArray(point) && point.length >= 2 && typeof point[0] === 'number' && typeof point[1] === 'number');
    if (!validPoints.length) return null;

    const { sumLng, sumLat } = validPoints.reduce((acc, point) => {
      return {
        sumLng: acc.sumLng + point[0],
        sumLat: acc.sumLat + point[1]
      };
    }, { sumLng: 0, sumLat: 0 });

    return [sumLng / validPoints.length, sumLat / validPoints.length];
  };

  const layers = useMemo(() => {
    const result = [];

    // H3 Hexagon Layer (if showing hex data)
    if (showHex && data.length > 0) {
      result.push(
        new H3HexagonLayer({
          id: 'h3-hexagon-layer',
          data,
          pickable: true,
          wireframe: false,
          stroked: true,
          filled: true,
          extruded: is3D, 
          elevationScale: 20,
          getHexagon: d => d.hex,
          onHover: info => onHexHover?.(info?.object?.hex || null),
          getFillColor: d => {
            const intensity = maxCount > 1 ? (d.count / maxCount) : 1;
            if (useHotspotPalette) {
              const low  = hotspotPalette?.low  ?? [253, 224,  71];  // default: yellow
              const high = hotspotPalette?.high ?? [153,  27,  27];  // default: deep red
              const r = Math.round(low[0] + (high[0] - low[0]) * intensity);
              const g = Math.round(low[1] + (high[1] - low[1]) * intensity);
              const b = Math.round(low[2] + (high[2] - low[2]) * intensity);
              const alpha = is3D ? 210 : Math.floor(100 + (140 * intensity));
              return [r, g, b, alpha];
            }
            const alpha = is3D ? 200 : Math.floor(80 + (175 * intensity));
            return [color[0], color[1], color[2], alpha];
          },
          getLineColor: d => d.hex === highlightedHexId ? [59, 130, 246, 255] : [255, 255, 255, 80],
          lineWidthMinPixels: highlightedHexId ? 3 : 1,
          getElevation: d => d.count
        })
      );
    }

    // GeoJSON Zone Layer (if showing zones)
    if (showZones && zoneFeatures) {
      // Preprocess to compute total value per zone for multivariate
      const excludeProps = ['zone_id', 'geometry', 'OBJECTID', 'Shape_Area', 'Shape_Leng'];
      
      result.push(
        new GeoJsonLayer({
          id: 'zone-layer',
          data: zoneFeatures,
          pickable: true,
          stroked: true,
          filled: true,
          extruded: is3D,
          wireframe: is3D,
          lineWidthMinPixels: 1,
          onHover: info => onZoneHover?.(getZoneFeatureId(info?.object) || null),
          getFillColor: f => {
            const props = f.properties || {};
            if (useHotspotPalette) {
              const score = typeof props.hotspot_score === 'number' ? props.hotspot_score : 0;
              const intensity = Math.max(0, Math.min(1, score));
              const low  = hotspotPalette?.low  ?? [253, 224,  71];
              const high = hotspotPalette?.high ?? [153,  27,  27];
              const r = Math.round(low[0] + (high[0] - low[0]) * intensity);
              const g = Math.round(low[1] + (high[1] - low[1]) * intensity);
              const b = Math.round(low[2] + (high[2] - low[2]) * intensity);
              const alpha = is3D ? 200 : Math.floor(90 + (140 * intensity));
              return [r, g, b, alpha];
            }
            // Sum all variable values for intensity
            let totalVal = props.zone_value || 0;
            if (!props.zone_value) {
              Object.entries(props).forEach(([key, val]) => {
                if (!excludeProps.includes(key) && typeof val === 'number' && !isNaN(val)) {
                  totalVal += val;
                }
              });
            }
            const intensity = maxZoneValue > 0 ? (totalVal / maxZoneValue) : 0;
            // Use a different color scheme for zones (green)
            const alpha = is3D ? 180 : Math.floor(60 + (140 * intensity));
            return [16, 185, 129, alpha]; // Emerald green
          },
          getLineColor: f => getZoneFeatureId(f) === highlightedZoneId ? [59, 130, 246, 255] : [15, 118, 110, 200],
          getLineWidth: f => getZoneFeatureId(f) === highlightedZoneId ? 4 : 2,
          getElevation: f => {
            const props = f.properties || {};
            let totalVal = props.zone_value || 0;
            if (!props.zone_value) {
              Object.entries(props).forEach(([key, val]) => {
                if (!excludeProps.includes(key) && typeof val === 'number' && !isNaN(val)) {
                  totalVal += val;
                }
              });
            }
            return totalVal * 10;
          },
          elevationScale: is3D ? 50 : 0
        })
      );
    }

    if (showDirectionSymbols && showHex && data.length > 0) {
      const symbolHexData = data
        .map(d => ({
          ...d,
          deltaSigned: Number(d?.variables?.delta_signed)
        }))
        .filter(d => Number.isFinite(d.deltaSigned));

      if (symbolHexData.length) {
        result.push(
          new TextLayer({
            id: 'direction-symbols-hex',
            data: symbolHexData,
            pickable: false,
            billboard: true,
            sizeUnits: 'pixels',
            getPosition: d => {
              try {
                const [lat, lng] = cellToLatLng(d.hex);
                return [lng, lat];
              } catch {
                return null;
              }
            },
            getText: d => getDirectionSymbol(d.deltaSigned),
            getColor: d => getDirectionColor(d.deltaSigned),
            getSize: d => getDirectionSize(d.deltaSigned),
            getTextAnchor: 'middle',
            getAlignmentBaseline: 'center',
            characterSet: ['⬆', '⬇', '•'],
            fontFamily: 'monospace'
          })
        );
      }
    }

    if (showDirectionSymbols && showZones && zoneFeatures?.features?.length) {
      const symbolZoneData = zoneFeatures.features
        .map(feature => {
          const deltaSigned = Number(feature?.properties?.delta_signed);
          const centroid = getPolygonCentroid(feature?.geometry);
          if (!Number.isFinite(deltaSigned) || !centroid) return null;
          return {
            feature,
            deltaSigned,
            centroid
          };
        })
        .filter(Boolean);

      if (symbolZoneData.length) {
        result.push(
          new TextLayer({
            id: 'direction-symbols-zone',
            data: symbolZoneData,
            pickable: false,
            billboard: true,
            sizeUnits: 'pixels',
            getPosition: d => d.centroid,
            getText: d => getDirectionSymbol(d.deltaSigned),
            getColor: d => getDirectionColor(d.deltaSigned),
            getSize: d => getDirectionSize(d.deltaSigned),
            getTextAnchor: 'middle',
            getAlignmentBaseline: 'center',
            characterSet: ['⬆', '⬇', '•'],
            fontFamily: 'monospace'
          })
        );
      }
    }

    return result;
  }, [data, maxCount, zoneFeatures, maxZoneValue, showHex, showZones, showDirectionSymbols, is3D, color, useHotspotPalette, hotspotPalette, highlightedHexId, highlightedZoneId, onHexHover, onZoneHover]);

  // Auto-fit to zone bounds if showing zones
  useEffect(() => {
    if (showZones && zoneFeatures?.features?.length > 0) {
      // Calculate centroid of first feature as initial view
      const firstFeature = zoneFeatures.features[0];
      const coords = firstFeature.geometry?.coordinates;
      if (coords && coords[0] && coords[0][0]) {
        // Handle polygon coordinates
        const flatCoords = coords[0].flat ? coords[0] : coords[0][0];
        if (flatCoords && flatCoords.length >= 2) {
          const lng = flatCoords[0];
          const lat = flatCoords[1];
          if (typeof lng === 'number' && typeof lat === 'number') {
            setLocalViewState(prev => ({
              ...prev,
              longitude: lng,
              latitude: lat,
              zoom: 10
            }));
          }
        }
      }
    }
  }, [zoneFeatures, showZones]);

  return (
      <div ref={containerRef} className="nodrag nowheel" style={{ position: 'relative', width: '100%', height: '100%', borderRadius: '0 0 8px 8px', overflow: 'hidden' }}>       {/* 👇 4. Wrap DeckGL so it physically cannot render while dimensions are 0x0 */}
       {isReady && (
        <DeckGL
          viewState={viewState}
          onViewStateChange={handleViewStateChange}
          controller={true}
          layers={layers}
          getTooltip={({ object, layer }) => {
            if (!object) return null;

            if (customTooltip) {
              const custom = customTooltip({ object, layer });
              if (custom) return custom;
            }
            
            // Handle H3 hexagon tooltip
            if (layer?.id === 'h3-hexagon-layer') {
              // Build variable values display for multivariate
              let variablesHtml = '';
              if (object.variables && Object.keys(object.variables).length > 0) {
                variablesHtml = Object.entries(object.variables)
                  .map(([name, val]) => `<div><strong>${name}:</strong> ${typeof val === 'number' ? val.toFixed(2) : val}</div>`)
                  .join('');
              } else {
                variablesHtml = `<div><strong>Value:</strong> ${object.count}</div>`;
              }
              
              return {
                html: `
                  <div style="font-family: sans-serif;">
                    <div style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
                      Hex ID: ${object.hex.slice(0, 8)}...
                    </div>
                    ${variablesHtml}
                    ${object.sources?.length ? `<div style="margin-top: 4px;"><strong>Sources:</strong> ${object.sources.join(', ')}</div>` : ''}
                  </div>
                `,
                style: {
                  backgroundColor: '#1e293b',
                  color: '#f8fafc',
                  fontSize: '11px',
                  padding: '8px',
                  borderRadius: '6px',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
                  maxWidth: '250px',
                  border: '1px solid #334155'
                }
              };
            }
            
            // Handle Zone polygon tooltip
            if (layer?.id === 'zone-layer' && object.properties) {
              const props = object.properties;
              const excludeProps = ['zone_id', 'geometry', 'OBJECTID', 'Shape_Area', 'Shape_Leng'];
              
              // Build variables display for multivariate zones
              let variablesHtml = '';
              if (props.zone_value !== undefined) {
                variablesHtml = `<div><strong>Value:</strong> ${props.zone_value?.toFixed(2) || 'N/A'}</div>`;
              } else {
                // Show all numeric variables
                const varEntries = Object.entries(props)
                  .filter(([key, val]) => !excludeProps.includes(key) && typeof val === 'number' && !isNaN(val));
                
                if (varEntries.length > 0) {
                  variablesHtml = varEntries
                    .map(([name, val]) => `<div><strong>${name}:</strong> ${val.toFixed(2)}</div>`)
                    .join('');
                } else {
                  variablesHtml = '<div>No values</div>';
                }
              }
              
              return {
                html: `
                  <div style="font-family: sans-serif;">
                    <div style="font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid #475569; padding-bottom: 4px;">
                      Zone: ${props.zone_id || 'Unknown'}
                    </div>
                    ${variablesHtml}
                  </div>
                `,
                style: {
                  backgroundColor: '#064e3b',
                  color: '#f8fafc',
                  fontSize: '11px',
                  padding: '8px',
                  borderRadius: '6px',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
                  maxWidth: '250px',
                  border: '1px solid #10b981'
                }
              };
            }
            
            return null;
          }}
        />
       )}
      
      {/* 👇 NEW: Minimized 2D Density Legend */}
      {!hideLegend && !is3D && maxCount > 1 && (
        <div style={{
          position: 'absolute', bottom: '8px', left: '8px', zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.9)', 
          padding: '1px 2px', // 👈 Tighter padding
          borderRadius: '4px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          fontSize: '8px',    // 👈 Smaller font size
          color: '#334155', display: 'flex', flexDirection: 'column', gap: '2px',
          border: '0.2px solid #cbd5e1'
        }}>
          <div style={{ fontWeight: 'bold' }}>Density</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span>1</span>
            <div style={{
              width: '40px',  // 👈 Narrower bar
              height: '6px',  // 👈 Thinner bar
              borderRadius: '3px',
              background: `linear-gradient(to right, rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.3), rgba(${color[0]}, ${color[1]}, ${color[2]}, 1))`
            }} />
            <span>{maxCount}</span>
          </div>
        </div>
      )}

      <button
        onClick={handleToggleMode}
        title={is3D ? "Switch to 2D Density Map" : "Switch to 3D Extruded Map"}
        style={{
          position: 'absolute', bottom: '8px', right: '8px', zIndex: 10,
          backgroundColor: '#fff', color: '#334155', border: '1px solid #cbd5e1',
          borderRadius: '4px', padding: '4px 8px', cursor: 'pointer',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center',
          gap: '6px', fontSize: '11px', fontWeight: 'bold'
        }}
      >
        <Layers size={14} />
        {is3D ? '3D' : '2D'}
      </button>
    </div>
  );
};

export default H3PreviewDeckGL;