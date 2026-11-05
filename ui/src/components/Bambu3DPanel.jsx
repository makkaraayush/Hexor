import React, { useState, useEffect, useRef } from 'react';
import { 
  Box, Flame, Layers, Play, Pause, Square, 
  Lightbulb, CheckCircle2, XCircle, Search, Cpu, Eye, FolderKanban, RotateCw 
} from 'lucide-react';
import Mesh3DViewer from './Mesh3DViewer';

export default function Bambu3DPanel({ 
  bambuData = {}, 
  pendingApproval = null, 
  onApprove, 
  onReject,
  onAction 
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('telemetry'); // 'telemetry' | '3d_mesh'
  const [savedModels, setSavedModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const lastSeenApprovalIdRef = useRef(null);

  const state = bambuData.state || "IDLE";
  const nozzleTemp = Math.round(bambuData.nozzle_temp || 24);
  const nozzleTarget = Math.round(bambuData.nozzle_target || 0);
  const bedTemp = Math.round(bambuData.bed_temp || 22);
  const bedTarget = Math.round(bambuData.bed_target || 0);
  const progress = bambuData.progress_percent || 0;
  const currentLayer = bambuData.current_layer || 0;
  const totalLayers = bambuData.total_layers || 0;
  const speed = bambuData.speed_level || "standard";
  const lightOn = bambuData.light_on ?? true;
  const modelName = bambuData.model_name || "Standby";

  // Auto-switch to 3D view only once when a new print approval arrives
  useEffect(() => {
    if (pendingApproval?.stl_url) {
      const approvalId = pendingApproval.id || pendingApproval.model_name;
      if (approvalId && approvalId !== lastSeenApprovalIdRef.current) {
        lastSeenApprovalIdRef.current = approvalId;
        setViewMode('3d_mesh');
      }
    }
  }, [pendingApproval]);

  // Fetch local 3D models repository
  const fetchModelsList = async () => {
    try {
      const res = await fetch('/api/models/list');
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        setSavedModels(data.models);
        if (!selectedModel) {
          setSelectedModel(data.models[0]);
        }
      }
    } catch (e) {}
  };

  useEffect(() => {
    fetchModelsList();
  }, [pendingApproval]);

  const getStatusColor = () => {
    switch (state) {
      case "PRINTING": return "text-emerald-400 border-emerald-500/50 bg-emerald-950/20";
      case "PREPARING": return "text-amber-400 border-amber-500/50 bg-amber-950/20";
      case "PAUSED": return "text-yellow-400 border-yellow-500/50 bg-yellow-950/20";
      case "ERROR": return "text-red-400 border-red-500/50 bg-red-950/20";
      default: return "text-cyan-400 border-cyan-500/30 bg-cyan-950/20";
    }
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim() && onAction) {
      onAction('search_models', { query: searchQuery });
    }
  };

  const activeStlUrl = pendingApproval?.stl_url || selectedModel?.stl_url;
  const activeMeshAnalysis = pendingApproval?.mesh_analysis || selectedModel?.metrics;
  const activeModelTitle = pendingApproval?.model_name || selectedModel?.category || "Interactive 3D Model";

  return (
    <div className="relative flex flex-col h-full bg-black/60 border border-cyan-500/30 rounded-xl p-4 backdrop-blur-md overflow-hidden glow-cyan">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20">
        <div className="flex items-center space-x-2">
          <Box className="w-5 h-5 text-cyan-400 animate-pulse" />
          <span className="font-orbitron font-bold text-sm tracking-wider text-cyan-200">
            BAMBU LAB A1
          </span>
        </div>

        {/* Tab switch buttons */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => setViewMode('telemetry')}
            className={`px-2 py-0.5 rounded text-[11px] font-orbitron transition-all ${
              viewMode === 'telemetry' 
                ? 'bg-cyan-500/30 border border-cyan-400 text-cyan-100 shadow-[0_0_8px_rgba(0,240,255,0.3)]' 
                : 'text-cyan-500 hover:text-cyan-300'
            }`}
          >
            STATUS
          </button>
          <button
            onClick={() => setViewMode('3d_mesh')}
            className={`px-2 py-0.5 rounded text-[11px] font-orbitron flex items-center space-x-1 transition-all ${
              viewMode === '3d_mesh' 
                ? 'bg-cyan-500/30 border border-cyan-400 text-cyan-100 shadow-[0_0_8px_rgba(0,240,255,0.3)]' 
                : 'text-cyan-500 hover:text-cyan-300'
            }`}
          >
            <Eye className="w-3 h-3 text-cyan-400 mr-0.5" />
            <span>3D MESH</span>
          </button>
          <div className={`px-2 py-0.5 rounded text-[11px] font-orbitron font-semibold border ${getStatusColor()}`}>
            {state}
          </div>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto mt-2">
        {viewMode === '3d_mesh' ? (
          /* 3D Mesh Studio Tab */
          <div className="flex-1 flex flex-col space-y-2">
            {savedModels.length > 0 && (
              <div className="flex items-center space-x-2 bg-black/50 border border-cyan-500/20 rounded-lg p-1.5">
                <FolderKanban className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <select
                  value={selectedModel?.filename || ''}
                  onChange={(e) => {
                    const m = savedModels.find(x => x.filename === e.target.value);
                    if (m) setSelectedModel(m);
                  }}
                  className="bg-transparent text-xs text-cyan-200 font-mono-tech focus:outline-none w-full cursor-pointer"
                >
                  {savedModels.map((m) => (
                    <option key={m.stl_url} value={m.filename} className="bg-slate-900 text-cyan-200">
                      models/{m.category}/{m.filename}
                    </option>
                  ))}
                </select>
                <button
                  onClick={fetchModelsList}
                  className="p-1 text-cyan-400 hover:text-cyan-200"
                  title="Refresh models folder"
                >
                  <RotateCw className="w-3 h-3" />
                </button>
              </div>
            )}

            {activeStlUrl ? (
              <div className="flex-1 min-h-[200px]">
                <Mesh3DViewer 
                  stlUrl={activeStlUrl}
                  meshAnalysis={activeMeshAnalysis}
                  modelName={activeModelTitle}
                  height="200px"
                />
              </div>
            ) : (
              <div className="flex-1 min-h-[160px] flex flex-col items-center justify-center border border-dashed border-cyan-500/30 rounded-xl p-4 text-center">
                <Box className="w-8 h-8 text-cyan-500/60 mb-2 animate-bounce" />
                <p className="text-xs text-cyan-300 font-mono-tech">No 3D model loaded yet.</p>
                <p className="text-[10px] text-cyan-500/70 mt-1">
                  Say: "Hey Hexor, find me a phone stand to 3D print"
                </p>
              </div>
            )}
          </div>
        ) : (
          /* Telemetry View Tab */
          <div className="flex-1 flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-center justify-between text-xs text-cyan-400/80 mb-1">
                <span className="font-mono-tech truncate max-w-[200px]">
                  JOB: <strong className="text-cyan-200">{modelName}</strong>
                </span>
                <span className="font-mono-tech text-[10px] text-cyan-500">
                  {bambuData.lan_ip || "LAN MODE"}
                </span>
              </div>

              <form onSubmit={handleSearchSubmit} className="relative mt-1">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Find 3D model (e.g. phone stand, clip)..."
                  className="w-full bg-cyan-950/40 border border-cyan-500/30 rounded-lg px-3 py-1.5 pl-8 text-xs text-cyan-200 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
                />
                <Search className="w-3.5 h-3.5 text-cyan-400 absolute left-2.5 top-2.5" />
              </form>

              <div className="grid grid-cols-2 gap-2 mt-2">
                <div className="bg-black/50 border border-cyan-500/20 rounded-lg p-2 flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-1 text-amber-400 text-[11px] font-semibold">
                      <Flame className="w-3.5 h-3.5" />
                      <span>NOZZLE (0.4mm)</span>
                    </div>
                    <div className="font-orbitron text-base font-bold text-amber-200 mt-0.5">
                      {nozzleTemp}°C
                      <span className="text-[10px] font-normal text-amber-500/80 ml-1">/ {nozzleTarget}°C</span>
                    </div>
                  </div>
                  <div className="w-7 h-7 rounded-full border border-amber-500/30 flex items-center justify-center bg-amber-950/30">
                    <div 
                      className="w-4 h-4 rounded-full bg-amber-500/40 transition-all duration-300"
                      style={{ transform: `scale(${Math.min(1.2, Math.max(0.3, nozzleTemp / 240))})` }}
                    />
                  </div>
                </div>

                <div className="bg-black/50 border border-cyan-500/20 rounded-lg p-2 flex items-center justify-between">
                  <div>
                    <div className="flex items-center space-x-1 text-cyan-400 text-[11px] font-semibold">
                      <Layers className="w-3.5 h-3.5" />
                      <span>PEI BED</span>
                    </div>
                    <div className="font-orbitron text-base font-bold text-cyan-200 mt-0.5">
                      {bedTemp}°C
                      <span className="text-[10px] font-normal text-cyan-500/80 ml-1">/ {bedTarget}°C</span>
                    </div>
                  </div>
                  <div className="w-7 h-7 rounded-full border border-cyan-500/30 flex items-center justify-center bg-cyan-950/30">
                    <div 
                      className="w-4 h-4 rounded-full bg-cyan-500/40 transition-all duration-300"
                      style={{ transform: `scale(${Math.min(1.2, Math.max(0.3, bedTemp / 70))})` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-2 bg-black/50 border border-cyan-500/20 rounded-lg p-2">
                <div className="flex justify-between items-center text-xs font-mono-tech mb-1">
                  <span className="text-cyan-400">PROGRESS</span>
                  <span className="text-cyan-200 font-bold">{progress}%</span>
                </div>
                <div className="w-full bg-cyan-950/60 h-2 rounded-full overflow-hidden border border-cyan-500/30">
                  <div 
                    className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full transition-all duration-500 rounded-full"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono-tech text-cyan-500 mt-1">
                  <span>LAYER: {currentLayer} / {totalLayers || 380}</span>
                  <span>EST: {bambuData.remaining_minutes || 0} MIN</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Pending Print Approval Dossier (Visible in both modes) */}
      {pendingApproval && (
        <div className="mt-2 p-2.5 bg-cyan-950/80 border border-amber-400/80 rounded-xl backdrop-blur-lg shrink-0">
          <div className="flex items-center justify-between text-amber-300 text-xs font-orbitron font-bold">
            <span className="flex items-center space-x-1">
              <Cpu className="w-3.5 h-3.5 text-amber-400 animate-spin" />
              <span>APPROVAL REQUIRED</span>
            </span>
            <button 
              onClick={() => setViewMode(viewMode === '3d_mesh' ? 'telemetry' : '3d_mesh')}
              className="text-[10px] text-cyan-300 underline font-mono-tech flex items-center space-x-0.5 hover:text-cyan-100"
            >
              <Eye className="w-3 h-3" />
              <span>{viewMode === '3d_mesh' ? 'View Telemetry' : 'Inspect 3D'}</span>
            </button>
          </div>

          <div className="mt-1 text-xs text-cyan-200">
            <div className="font-semibold text-xs text-cyan-100">{pendingApproval.model_name}</div>
            {pendingApproval.parameters && (
              <div className="grid grid-cols-2 gap-0.5 text-[10px] font-mono-tech mt-1 text-cyan-300/80">
                <div>Material: <span className="text-amber-300">{pendingApproval.parameters.material}</span></div>
                <div>Layer: <span className="text-cyan-100">{pendingApproval.parameters.layer_height}</span></div>
                <div>Infill: <span className="text-cyan-100">{pendingApproval.parameters.infill}</span></div>
                <div>Est. Time: <span className="text-emerald-300">{pendingApproval.parameters.estimated_time}</span></div>
              </div>
            )}
          </div>

          <div className="mt-2 flex space-x-2">
            <button
              onClick={() => onApprove && onApprove()}
              className="flex-1 flex items-center justify-center space-x-1 py-1 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-black font-orbitron font-bold text-xs rounded-lg transition-all shadow-[0_0_12px_rgba(16,185,129,0.5)]"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>APPROVE & SEND PRINT</span>
            </button>
            <button
              onClick={() => onReject && onReject()}
              className="px-2.5 py-1 bg-red-950/60 border border-red-500/50 hover:bg-red-900/50 text-red-300 font-orbitron text-xs rounded-lg transition-all"
            >
              <XCircle className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Hardware Controls Bar (Speed, Chamber Light, Pause/Resume, Abort) - ALWAYS VISIBLE */}
      <div className="mt-2 pt-2 border-t border-cyan-500/20 flex items-center justify-between space-x-1 shrink-0">
        <div className="flex items-center space-x-1">
          {["silent", "standard", "sport", "ludicrous"].map((lvl) => (
            <button
              key={lvl}
              onClick={() => onAction && onAction('set_speed', { speed_level: lvl })}
              className={`px-1.5 py-1 text-[10px] font-orbitron uppercase rounded border transition-all ${
                speed === lvl 
                  ? 'bg-cyan-500/30 border-cyan-400 text-cyan-100 shadow-[0_0_8px_rgba(0,240,255,0.4)]' 
                  : 'bg-black/40 border-cyan-500/20 text-cyan-500 hover:text-cyan-300'
              }`}
            >
              {lvl.substring(0, 4)}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-1">
          <button
            onClick={() => onAction && onAction('toggle_light')}
            className={`p-1.5 rounded border transition-all ${
              lightOn 
                ? 'bg-amber-500/20 border-amber-400/50 text-amber-300 shadow-[0_0_8px_rgba(251,191,36,0.3)]' 
                : 'bg-black/40 border-cyan-500/20 text-cyan-600'
            }`}
            title="Toggle Chamber Light"
          >
            <Lightbulb className="w-3.5 h-3.5" />
          </button>
          {state === "PRINTING" ? (
            <button
              onClick={() => onAction && onAction('pause_print')}
              className="p-1.5 rounded bg-yellow-500/20 border border-yellow-500/40 text-yellow-300 hover:bg-yellow-500/30"
              title="Pause"
            >
              <Pause className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={() => onAction && onAction('resume_print')}
              className="p-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30"
              title="Resume"
            >
              <Play className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={() => onAction && onAction('stop_print')}
            className="p-1.5 rounded bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30"
            title="Abort"
          >
            <Square className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
