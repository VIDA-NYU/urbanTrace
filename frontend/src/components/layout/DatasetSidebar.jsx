// frontend/src/components/DatasetSidebar.jsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin, RefreshCw, Map, Search, X } from 'lucide-react';
import DatasetCard from '../catalog/DatasetCard'; 

const toBBoxPolygonFeature = (bbox) => {
  if (!bbox) return null;

  const { minLng, minLat, maxLng, maxLat } = bbox;
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [minLng, minLat],
        [maxLng, minLat],
        [maxLng, maxLat],
        [minLng, maxLat],
        [minLng, minLat],
      ]],
    },
    properties: {},
  };
};

const normalizeBBox = (a, b) => {
  if (!a || !b) return null;
  return {
    minLng: Math.min(a.lng, b.lng),
    minLat: Math.min(a.lat, b.lat),
    maxLng: Math.max(a.lng, b.lng),
    maxLat: Math.max(a.lat, b.lat),
  };
};

const SpatialFilterMap = ({ draftBBox, onDraftBBoxChange }) => {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const dragStartRef = useRef(null);
  const isDraggingRef = useRef(false);
  const [mode, setMode] = useState('pan');

  // Attach/detach drawing handlers based on mode
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleMouseDown = (e) => {
      dragStartRef.current = { lng: e.lngLat.lng, lat: e.lngLat.lat };
      isDraggingRef.current = true;
    };

    const handleMouseMove = (e) => {
      if (!isDraggingRef.current || !dragStartRef.current) return;
      const currentPoint = { lng: e.lngLat.lng, lat: e.lngLat.lat };
      onDraftBBoxChange(normalizeBBox(dragStartRef.current, currentPoint));
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
    };

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        setMode('pan');
        onDraftBBoxChange(null);
      }
    };

    if (mode === 'draw') {
      // Disable map panning
      map.dragPan.disable();
      // Attach drawing handlers
      map.on('mousedown', handleMouseDown);
      map.on('mousemove', handleMouseMove);
      map.on('mouseup', handleMouseUp);
      window.addEventListener('keydown', handleEscape);
    } else {
      // Enable map panning
      map.dragPan.enable();
      // Detach drawing handlers
      map.off('mousedown', handleMouseDown);
      map.off('mousemove', handleMouseMove);
      map.off('mouseup', handleMouseUp);
      window.removeEventListener('keydown', handleEscape);
    }

    return () => {
      map.off('mousedown', handleMouseDown);
      map.off('mousemove', handleMouseMove);
      map.off('mouseup', handleMouseUp);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [mode, onDraftBBoxChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const cursor = mode === 'draw' ? 'crosshair' : 'grab';
    const canvas = map.getCanvas?.();
    const canvasContainer = map.getCanvasContainer?.();
    const container = map.getContainer?.();

    if (canvas) {
      canvas.style.setProperty('cursor', cursor, 'important');
    }

    if (canvasContainer) {
      canvasContainer.style.setProperty('cursor', cursor, 'important');
    }

    if (container) {
      container.style.setProperty('cursor', cursor, 'important');
    }

    return () => {
      if (canvas) canvas.style.removeProperty('cursor');
      if (canvasContainer) canvasContainer.style.removeProperty('cursor');
      if (container) container.style.removeProperty('cursor');
    };
  }, [mode]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: '/style.json',
      center: [-73.95, 40.72],
      zoom: 9,
      attributionControl: false,
    });

    mapRef.current = map;

    map.on('load', () => {
      map.addSource('bbox-source', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      });

      map.addLayer({
        id: 'bbox-fill',
        type: 'fill',
        source: 'bbox-source',
        paint: {
          'fill-color': '#2563eb',
          'fill-opacity': 0.18,
        },
      });

      map.addLayer({
        id: 'bbox-outline',
        type: 'line',
        source: 'bbox-source',
        paint: {
          'line-color': '#1d4ed8',
          'line-width': 2,
        },
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
      dragStartRef.current = null;
      isDraggingRef.current = false;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const source = map.getSource('bbox-source');
    if (!source) return;

    const feature = toBBoxPolygonFeature(draftBBox);
    source.setData({
      type: 'FeatureCollection',
      features: feature ? [feature] : [],
    });
  }, [draftBBox]);

  const mapStyle = {
    width: '100%',
    height: '220px',
    backgroundColor: '#f3f4f6',
  };

  const toggleMode = () => {
    if (mode === 'draw') {
      // Exiting draw mode: auto-switch to pan
      setMode('pan');
      onDraftBBoxChange(null);
    } else {
      // Entering draw mode
      setMode('draw');
    }
  };

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
      <div
        ref={mapContainerRef}
        style={mapStyle}
      />
      
      {/* Mode toggle button (top-right corner) */}
      <button
        onClick={toggleMode}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          padding: '6px 12px',
          fontSize: '12px',
          fontWeight: '500',
          borderRadius: '4px',
          border: 'none',
          cursor: 'pointer',
          backgroundColor: mode === 'draw' ? '#2563eb' : '#fff',
          color: mode === 'draw' ? '#fff' : '#374151',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
          transition: 'all 0.2s',
          zIndex: 10,
        }}
        title={mode === 'draw' ? 'Press Esc or click to exit draw mode' : 'Click to enter draw mode'}
      >
        {mode === 'draw' ? '✓ Drawing' : 'Draw'}
      </button>

      {/* Instruction text */}
      <div style={{ padding: '8px 10px', fontSize: '12px', color: '#4b5563', backgroundColor: '#fff' }}>
        {mode === 'draw' 
          ? 'Click and drag to draw a rectangle. Press Esc to cancel.'
          : 'Pan the map or click Draw to select an area.'}
      </div>
    </div>
  );
};

const DatasetSidebar = () => {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLocationFilterOpen, setIsLocationFilterOpen] = useState(false);
  const [draftBBox, setDraftBBox] = useState(null);
  const [appliedBBox, setAppliedBBox] = useState(null);

  const fetchDatasets = (bbox = null) => {
    setLoading(true);
    const params = bbox
      ? {
          min_lng: bbox.minLng,
          min_lat: bbox.minLat,
          max_lng: bbox.maxLng,
          max_lat: bbox.maxLat,
        }
      : undefined;

    axios.get('http://localhost:8000/datasets', { params })
      .then(res => {
        setDatasets(res.data.datasets);
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching datasets", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  useEffect(() => {
    setDraftBBox(appliedBBox);
  }, [appliedBBox]);

  const handleDragStart = (event, dataset) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(dataset));
    event.dataTransfer.effectAllowed = 'move';
  };

  const clearSearch = () => {
    setSearchTerm('');
  };

  const applyLocationFilter = () => {
    if (!draftBBox) return;
    setAppliedBBox(draftBBox);
    fetchDatasets(draftBBox);
  };

  const clearLocationFilter = () => {
    setDraftBBox(null);
    setAppliedBBox(null);
    fetchDatasets(null);
  };

  const bboxLabel = useMemo(() => {
    if (!appliedBBox) return '';
    const { minLng, minLat, maxLng, maxLat } = appliedBBox;
    return `${minLat.toFixed(3)}, ${minLng.toFixed(3)} → ${maxLat.toFixed(3)}, ${maxLng.toFixed(3)}`;
  }, [appliedBBox]);

  const filteredDatasets = datasets.filter(ds => {
    const name = ds.metadata?.name || ds.name || "";
    return name.toLowerCase().includes(searchTerm.toLowerCase());
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', backgroundColor: '#f9fafb' }}>
      
      {/* 1. Fixed Header Section */}
      <div style={{ 
        padding: '20px', 
        borderBottom: '1px solid #e5e7eb', 
        backgroundColor: '#fff',
        flexShrink: 0 
      }}>
        {/* Title Row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#111827', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Map size={24} color="#2563eb" /> UrbanTrace
          </h2>
          <button 
            onClick={fetchDatasets} 
            title="Refresh Library"
            style={{ 
              background: 'none', border: 'none', cursor: 'pointer', padding: '4px',
              borderRadius: '4px', color: '#6b7280', display: 'flex', alignItems: 'center',
              justifyContent: 'center', transition: 'background 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <RefreshCw size={18} className={loading ? "spin" : ""} />
          </button>
        </div>

        {/* Search Input Row */}
        <div style={{ position: 'relative', width: '100%' }}>
          
          {/* Search Icon (Left) */}
          <Search 
            size={16} 
            color="#9ca3af" 
            style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} 
          />
          
          <input 
            type="text" 
            placeholder="Search datasets..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 30px 8px 34px', // Right padding increased to 30px to make room for X
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              fontSize: '0.875rem',
              outline: 'none',
              backgroundColor: '#f9fafb',
              color: '#70757d',        // Your custom color
              boxSizing: 'border-box'  // Prevents overflow
            }}
            onFocus={(e) => e.target.style.borderColor = '#2563eb'}
            onBlur={(e) => e.target.style.borderColor = '#e5e7eb'}
          />

          {/* Clear Button (Right) - Only shows when there is text */}
          {searchTerm && (
            <button 
              onClick={clearSearch}
              title="Clear search"
              style={{ 
                position: 'absolute', 
                right: '8px', 
                top: '50%', 
                transform: 'translateY(-50%)',
                background: 'none', 
                border: 'none', 
                cursor: 'pointer', 
                padding: '2px',
                display: 'flex',
                alignItems: 'center',
                color: '#6b7280'
              }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <button
            onClick={() => setIsLocationFilterOpen((prev) => !prev)}
            style={{
              width: '100%',
              border: '1px solid #dbeafe',
              background: '#eff6ff',
              color: '#1d4ed8',
              borderRadius: '6px',
              padding: '8px 10px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <MapPin size={14} />
            {isLocationFilterOpen ? 'Hide Location Filter' : 'Filter by Location'}
          </button>

          {appliedBBox && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px',
                border: '1px solid #bfdbfe',
                background: '#eff6ff',
                color: '#1e3a8a',
                borderRadius: '999px',
                padding: '5px 10px',
                fontSize: '11px',
              }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                Location filter active · {bboxLabel}
              </span>
              <button
                onClick={clearLocationFilter}
                title="Clear location filter"
                style={{
                  border: 'none',
                  background: 'transparent',
                  color: '#1e3a8a',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <X size={14} />
              </button>
            </div>
          )}

          {isLocationFilterOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <SpatialFilterMap draftBBox={draftBBox} onDraftBBoxChange={setDraftBBox} />
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={applyLocationFilter}
                  disabled={!draftBBox || loading}
                  style={{
                    flex: 1,
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px',
                    background: !draftBBox || loading ? '#cbd5e1' : '#2563eb',
                    color: '#fff',
                    cursor: !draftBBox || loading ? 'not-allowed' : 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                  }}
                >
                  Apply filter
                </button>
                <button
                  onClick={() => setDraftBBox(null)}
                  disabled={!draftBBox || loading}
                  style={{
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    padding: '8px 10px',
                    background: '#fff',
                    color: '#374151',
                    cursor: !draftBBox || loading ? 'not-allowed' : 'pointer',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    opacity: !draftBBox || loading ? 0.6 : 1,
                  }}
                >
                  Reset
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 2. Scrollable List Section */}
      <div style={{ flexGrow: 1, overflowY: 'auto', padding: '15px' }}>
        {loading && <p style={{ fontSize: '0.8rem', color: '#666', textAlign: 'center' }}>Loading datasets...</p>}
        
        {!loading && filteredDatasets.length === 0 && (
          <div style={{ textAlign: 'center', color: '#9ca3af', marginTop: '20px', fontSize: '0.9rem' }}>
            {searchTerm ? 'No matching datasets' : 'No datasets found'}
          </div>
        )}

        {filteredDatasets.map(ds => (
          <DatasetCard 
            key={ds.id || ds.filename} 
            dataset={ds} 
            onDragStart={handleDragStart} 
          />
        ))}
      </div>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default DatasetSidebar;