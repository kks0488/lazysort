import React, { useState } from 'react';
import axios from 'axios';
import { FolderSearch, Layers, Play, RotateCcw, CheckCircle, AlertTriangle } from 'lucide-react';

const Organizer = () => {
  const [folderPath, setFolderPath] = useState('');
  const [scanResult, setScanResult] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const handleScan = async () => {
    if (!folderPath) return;
    setLoading(true);
    setStatus('Scanning folder...');
    try {
      const res = await axios.post('http://localhost:2424/organize/scan', { folder_path: folderPath });
      setScanResult(res.data);
      setStatus('Scan complete.');
    } catch (err) {
      console.error(err);
      setStatus('Error scanning folder.');
    }
    setLoading(false);
  };

  const handleCluster = async () => {
    if (!folderPath) return;
    setLoading(true);
    setStatus('Clustering images with Gemini...');
    try {
      const res = await axios.post('http://localhost:2424/organize/cluster', { folder_path: folderPath });
      setClusters(res.data);
      setStatus('Clustering complete.');
    } catch (err) {
      console.error(err);
      setStatus('Error clustering.');
    }
    setLoading(false);
  };

  const handleExecute = async () => {
    if (!clusters) return;
    setLoading(true);
    setStatus('Moving files...');
    
    // Prepare moves based on clusters
    // This is a simplified logic. Ideally we let user review.
    // For MVP, we move files to "Groups/ClusterName"
    
    const moves = [];
    clusters.forEach(cluster => {
        const targetDir = `${folderPath}/그룹/${cluster.name}`;
        cluster.files.forEach(file => {
            moves.push({ src: file, dst: `${targetDir}/${file.split('/').pop()}` });
        });
    });
    
    // Also handle junk from scanResult if available?
    // Let's stick to clusters for now.
    
    try {
      const res = await axios.post('http://localhost:2424/organize/execute', { moves });
      setStatus(`Moved ${res.data.processed} files.`);
    } catch (err) {
      console.error(err);
      setStatus('Error executing moves.');
    }
    setLoading(false);
  };

  const handleRollback = async () => {
    setLoading(true);
    setStatus('Rolling back...');
    try {
      const res = await axios.post('http://localhost:2424/organize/rollback');
      setStatus(`Rolled back ${res.data.rolled_back} operations.`);
    } catch (err) {
      console.error(err);
      setStatus('Error rolling back.');
    }
    setLoading(false);
  };

  return (
    <div className="p-6 bg-gray-900 text-white min-h-screen">
      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Layers className="text-blue-400" /> The Organizer
      </h2>

      {/* Input */}
      <div className="mb-8">
        <label className="block text-sm font-medium text-gray-400 mb-2">Target Folder Path</label>
        <div className="flex gap-4">
          <input 
            type="text" 
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="/Users/username/Pictures/..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <button 
            onClick={handleScan}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <FolderSearch size={18} /> Scan
          </button>
        </div>
      </div>

      {/* Status Bar */}
      {status && (
        <div className="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700 text-blue-300">
          {status}
        </div>
      )}

      {/* Scan Results */}
      {scanResult && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h3 className="text-lg font-semibold mb-2 text-red-400 flex items-center gap-2">
              <AlertTriangle size={18} /> Junk / Duplicates
            </h3>
            <p className="text-3xl font-bold">{scanResult.duplicates.length + scanResult.low_res.length + scanResult.screenshots.length}</p>
            <p className="text-sm text-gray-500">Files to clean</p>
          </div>
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h3 className="text-lg font-semibold mb-2 text-green-400 flex items-center gap-2">
              <CheckCircle size={18} /> Valid Images
            </h3>
            <p className="text-3xl font-bold">{scanResult.valid.length}</p>
            <p className="text-sm text-gray-500">Ready for clustering</p>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4 mb-8">
        <button 
          onClick={handleCluster}
          disabled={loading || !scanResult}
          className="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-bold transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          <Layers size={20} /> Run AI Clustering
        </button>
        <button 
          onClick={handleExecute}
          disabled={loading || !clusters}
          className="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          <Play size={20} /> Execute Moves
        </button>
        <button 
          onClick={handleRollback}
          disabled={loading}
          className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded-lg font-bold transition-colors disabled:opacity-50 flex items-center gap-2 ml-auto"
        >
          <RotateCcw size={20} /> Undo Last Batch
        </button>
      </div>

      {/* Clusters Preview */}
      {clusters && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {clusters.map((cluster) => (
            <div key={cluster.cluster_id} className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
              <div className="p-4 border-b border-gray-700 bg-gray-800/50">
                <h3 className="font-bold text-lg">{cluster.name}</h3>
                <span className="text-sm text-gray-400">{cluster.files.length} files</span>
              </div>
              <div className="p-4 max-h-60 overflow-y-auto space-y-2">
                {cluster.files.map((file, idx) => (
                  <div key={idx} className="text-xs text-gray-400 truncate">
                    {file.split('/').pop()}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Organizer;
