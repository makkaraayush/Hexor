import React, { useState } from 'react';
import { Sparkles, BrainCircuit, ShieldCheck, Terminal, Plus, Check } from 'lucide-react';

export default function SkillEvolutionVault({ 
  skills = [], 
  onLearnSkill 
}) {
  const [newSkillInput, setNewSkillInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLearn = async (e) => {
    e.preventDefault();
    if (!newSkillInput.trim() || isSubmitting) return;
    setIsSubmitting(true);
    if (onLearnSkill) {
      await onLearnSkill(newSkillInput);
    }
    setNewSkillInput('');
    setIsSubmitting(false);
  };

  return (
    <div className="relative flex flex-col bg-black/60 border border-cyan-500/30 rounded-xl p-3.5 backdrop-blur-md glow-cyan">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20">
        <div className="flex items-center space-x-2">
          <BrainCircuit className="w-4 h-4 text-purple-400 animate-pulse" />
          <span className="font-orbitron font-bold text-xs tracking-wider text-purple-200">
            NEURAL SKILL VAULT & EVOLUTION
          </span>
        </div>
        <span className="font-mono-tech text-[10px] text-purple-400 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-500/30">
          {skills.length} ACTIVE TOOLS
        </span>
      </div>

      {/* Active Skills Matrix */}
      <div className="mt-2.5 flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
        {skills.map((s, idx) => {
          const isCustom = s.category === "custom";
          return (
            <div
              key={idx}
              className={`flex items-center space-x-1 px-2 py-1 rounded text-[10px] font-mono-tech border ${
                isCustom 
                  ? 'bg-purple-950/40 border-purple-400/60 text-purple-200' 
                  : 'bg-cyan-950/40 border-cyan-500/30 text-cyan-300'
              }`}
            >
              {isCustom ? (
                <Sparkles className="w-3 h-3 text-purple-400" />
              ) : (
                <ShieldCheck className="w-3 h-3 text-cyan-400" />
              )}
              <span className="truncate max-w-[120px]">{s.name}</span>
            </div>
          );
        })}
      </div>

      {/* Teach Hexor A New Skill Input */}
      <form onSubmit={handleLearn} className="mt-2.5 flex items-center space-x-1.5">
        <input
          type="text"
          value={newSkillInput}
          onChange={(e) => setNewSkillInput(e.target.value)}
          placeholder="Teach Hexor something new (e.g. 'Currency Converter')..."
          className="flex-1 bg-purple-950/30 border border-purple-500/30 rounded px-2.5 py-1 text-xs text-purple-200 placeholder-purple-500/60 focus:outline-none focus:border-purple-400 font-mono-tech"
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex items-center space-x-1 px-2.5 py-1 bg-purple-600/40 hover:bg-purple-600/60 border border-purple-400 text-purple-100 rounded text-xs font-orbitron transition-all"
        >
          {isSubmitting ? (
            <span className="animate-spin text-xs">⟳</span>
          ) : (
            <>
              <Plus className="w-3 h-3" />
              <span>EVOLVE</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}

