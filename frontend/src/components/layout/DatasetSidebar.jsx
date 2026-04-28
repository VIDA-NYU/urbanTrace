// frontend/src/components/DatasetSidebar.jsx
import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { RefreshCw, Map, Search, Upload, X } from 'lucide-react'; // Added X here
import DatasetCard from '../catalog/DatasetCard'; 

const DatasetSidebar = () => {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const uploadInputRef = useRef(null);

  const fetchDatasets = () => {
    setLoading(true);
    axios.get('http://localhost:8000/datasets')
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

  const handleDragStart = (event, dataset) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(dataset));
    event.dataTransfer.effectAllowed = 'move';
  };

  const clearSearch = () => {
    setSearchTerm('');
  };

  const handleUploadPick = () => {
    if (uploadInputRef.current) {
      uploadInputRef.current.click();
    }
  };

  const handleUploadFileChange = (event) => {
    const file = event.target.files?.[0] || null;
    setUploadError('');
    setUploadSuccess('');

    if (!file) {
      setSelectedUploadFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.geojson')) {
      setSelectedUploadFile(null);
      setUploadError('Only .geojson files are allowed.');
      return;
    }

    setSelectedUploadFile(file);
  };

  const handleUploadGeojson = async () => {
    if (!selectedUploadFile || isUploading) return;

    setIsUploading(true);
    setUploadError('');
    setUploadSuccess('');

    try {
      const formData = new FormData();
      formData.append('file', selectedUploadFile);

      const response = await axios.post('http://localhost:8000/datasets/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const uploadedName = response?.data?.filename || selectedUploadFile.name;
      const geoType = response?.data?.geometricType || 'Unknown';
      setUploadSuccess(`Uploaded ${uploadedName} (geometricType: ${geoType})`);
      setSelectedUploadFile(null);
      if (uploadInputRef.current) {
        uploadInputRef.current.value = '';
      }
      fetchDatasets();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      setUploadError(typeof detail === 'string' ? detail : 'Upload failed. Please check the GeoJSON file.');
    } finally {
      setIsUploading(false);
    }
  };

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
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={() => setIsUploadModalOpen(true)}
              title="Upload GeoJSON"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
                color: '#6b7280',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f3f4f6'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <Upload size={16} />
            </button>

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

        {/* Upload controls moved to modal — keeps sidebar clean */}
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

      {/* Upload Modal */}
      {isUploadModalOpen && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
          <div style={{ width: '420px', background: '#fff', borderRadius: '8px', padding: '20px', boxShadow: '0 10px 30px rgba(0,0,0,0.15)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Upload GeoJSON Dataset</h3>
              <button onClick={() => setIsUploadModalOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280' }} title="Close">✕</button>
            </div>

            <input
              ref={uploadInputRef}
              type="file"
              accept=".geojson,application/geo+json,application/json"
              onChange={handleUploadFileChange}
              style={{ display: 'none' }}
            />

            <div
              onClick={handleUploadPick}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files?.[0] || null;
                if (file) {
                  const fakeEvent = { target: { files: [file] } };
                  handleUploadFileChange(fakeEvent);
                }
              }}
              style={{
                border: '1px dashed #d1d5db',
                borderRadius: '6px',
                padding: '18px',
                textAlign: 'center',
                cursor: 'pointer',
                color: '#6b7280',
                marginBottom: '12px'
              }}
            >
              <Upload size={24} />
              <div style={{ fontSize: '0.9rem', marginTop: '8px' }}>{selectedUploadFile ? selectedUploadFile.name : 'Click or drop a .geojson file here'}</div>
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => { setSelectedUploadFile(null); if (uploadInputRef.current) uploadInputRef.current.value = ''; }} style={{ background: 'none', border: '1px solid #e5e7eb', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer', color: '#374151' }}>Clear</button>
              <button onClick={handleUploadGeojson} disabled={!selectedUploadFile || isUploading} style={{ background: !selectedUploadFile || isUploading ? '#cbd5e1' : '#2563eb', color: '#fff', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: !selectedUploadFile || isUploading ? 'not-allowed' : 'pointer' }}>{isUploading ? 'Uploading…' : 'Upload'}</button>
            </div>

            <div style={{ marginTop: '12px', minHeight: '20px' }}>
              {uploadError && <div style={{ fontSize: '0.9rem', color: '#b91c1c' }}>{uploadError}</div>}
              {uploadSuccess && <div style={{ fontSize: '0.9rem', color: '#166534' }}>{uploadSuccess}</div>}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default DatasetSidebar;