import React, { useState } from 'react';
import { 
  Sun, BrainCircuit, Scan, ShieldCheck, 
  ListTodo, Globe, Sparkles, ChevronRight 
} from 'lucide-react';

export default function JarvisProtocolBar({ onExecuteCommand, onOpenProductivity }) {
  const [researchTopic, setResearchTopic] = useState('');
  const [isResearchInputOpen, setIsResearchInputOpen] = useState(false);

  const handleResearchSubmit = (e) => {
    e.preventDefault();
    if (researchTopic.trim()) {
      onExecuteCommand(`Conduct deep research on ${researchTopic.trim()}`);
      setResearchTopic('');
      setIsResearchInputOpen(false);
    }
  };

  return (
    <div className="shrink-0 relative z-20 px-6 py-2 bg-black/85 border-b border-cyan-500/30 backdrop-blur-md flex items-center justify-between gap-3 overflow-x-auto no-scrollbar text-xs">
      <div className="flex items-center space-x-2 shrink-0">
        <div className="flex items-center space-x-1.5 text-cyan-400 font-orbitron font-semibold text-[11px] tracking-wider">
          <Sparkles className="w-3.5 h-3.5 text-cyan-300 animate-pulse" />
          <span>JARVIS PROTOCOLS</span>
          <ChevronRight className="w-3 h-3 text-cyan-600" />
        </div>

        {/* Morning Protocol */}
        <button
          onClick={() => onExecuteCommand("run morning protocol")}
          className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]"
          title="Run Morning Executive Briefing"
        >
          <Sun className="w-3.5 h-3.5 text-amber-400" />
          <span>Morning Briefing</span>
        </button>

        {/* Focus Protocol */}
        <button
          onClick={() => onExecuteCommand("engage focus mode")}
          className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]"
          title="Deep Work Focus Mode (Lo-Fi/Synthwave + Clean Desktop)"
        >
          <BrainCircuit className="w-3.5 h-3.5 text-purple-400" />
          <span>Focus Mode</span>
        </button>

        {/* Inspect Screen */}
        <button
          onClick={() => onExecuteCommand("look at my screen and analyze what is on display")}
          className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]"
          title="Inspect Screen with Windows Native OCR & Vision Analysis"
        >
          <Scan className="w-3.5 h-3.5 text-cyan-300" />
          <span>Inspect Screen</span>
        </button>

        {/* System Audit */}
        <button
          onClick={() => onExecuteCommand("run system audit")}
          className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]"
          title="Audit System Resources, Free Memory & Flush DNS"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>System Audit</span>
        </button>

        {/* Tasks & Agenda */}
        <button
          onClick={onOpenProductivity}
          className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech hover:shadow-[0_0_10px_rgba(0,240,255,0.3)]"
          title="Open Tasks, Notes & Timers Deck"
        >
          <ListTodo className="w-3.5 h-3.5 text-cyan-400" />
          <span>Tasks & Timers</span>
        </button>
      </div>

      {/* Deep Research Fast Input */}
      <div className="flex items-center space-x-2 shrink-0">
        {isResearchInputOpen ? (
          <form onSubmit={handleResearchSubmit} className="flex items-center space-x-1.5 animate-fade-in">
            <input
              type="text"
              value={researchTopic}
              onChange={(e) => setResearchTopic(e.target.value)}
              placeholder="Research topic (e.g. quantum annealing, Bambu A1 nozzle PID)..."
              autoFocus
              className="bg-black/80 border border-cyan-400 rounded-lg px-2.5 py-1 text-xs text-cyan-100 placeholder-cyan-600/70 focus:outline-none w-64 font-mono-tech"
            />
            <button
              type="submit"
              className="px-2.5 py-1 bg-cyan-500 hover:bg-cyan-400 text-black font-orbitron font-bold text-[11px] rounded-lg transition-all"
            >
              GO
            </button>
            <button
              type="button"
              onClick={() => setIsResearchInputOpen(false)}
              className="text-cyan-500 hover:text-cyan-300 text-xs px-1"
            >
              ✕
            </button>
          </form>
        ) : (
          <button
            onClick={() => setIsResearchInputOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-1 bg-gradient-to-r from-blue-950/40 to-cyan-950/40 hover:from-blue-900/50 hover:to-cyan-900/50 border border-blue-500/40 hover:border-cyan-400 rounded-lg text-cyan-200 transition-all font-mono-tech"
            title="Conduct Multi-Source Deep Web Research"
          >
            <Globe className="w-3.5 h-3.5 text-blue-400" />
            <span>Deep Research</span>
          </button>
        )}
      </div>
    </div>
  );
}

