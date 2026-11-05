import React, { useState, useEffect } from 'react';
import { 
  X, CheckSquare, Square, Plus, Trash2, StickyNote, 
  Clock, CheckCircle2, ListTodo, ShieldAlert, Sparkles 
} from 'lucide-react';

export default function ProductivityModal({ isOpen, onClose, onAction, onNotify }) {
  const [activeTab, setActiveTab] = useState('tasks'); // 'tasks' | 'notes' | 'timers'
  const [data, setData] = useState({ tasks: [], notes: [] });
  const [newTaskText, setNewTaskText] = useState('');
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [newNoteContent, setNewNoteContent] = useState('');
  const [customTimerMins, setCustomTimerMins] = useState(15);
  const [timerLabel, setTimerLabel] = useState('Print Check');

  const fetchData = async () => {
    try {
      const res = await fetch('/api/productivity/data');
      const d = await res.json();
      if (d) setData(d);
    } catch (e) {}
  };

  useEffect(() => {
    if (isOpen) fetchData();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!newTaskText.trim()) return;
    try {
      await fetch('/api/productivity/task/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: newTaskText.trim() })
      });
      setNewTaskText('');
      fetchData();
    } catch (e) {}
  };

  const handleToggleTask = async (taskId) => {
    try {
      await fetch('/api/productivity/task/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      fetchData();
    } catch (e) {}
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await fetch('/api/productivity/task/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
      });
      fetchData();
    } catch (e) {}
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!newNoteContent.trim()) return;
    try {
      await fetch('/api/productivity/note/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newNoteTitle.trim(), content: newNoteContent.trim() })
      });
      setNewNoteTitle('');
      setNewNoteContent('');
      fetchData();
    } catch (e) {}
  };

  const handleStartTimer = (mins, label) => {
    if (onAction) {
      onAction(`Set a timer for ${mins} minutes for ${label}`);
    }
    if (onNotify) {
      onNotify(`Timer initialized for ${mins} minutes: ${label}`);
    }
    onClose();
  };

  const pendingTasks = data.tasks.filter(t => !t.completed);
  const completedTasks = data.tasks.filter(t => t.completed);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-2xl bg-[#030914] border border-cyan-500/40 rounded-2xl shadow-[0_0_50px_rgba(0,240,255,0.2)] flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-500/20 bg-cyan-950/20">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-400 flex items-center justify-center">
              <ListTodo className="w-4 h-4 text-cyan-300" />
            </div>
            <div>
              <h2 className="font-orbitron font-bold text-sm tracking-wider text-cyan-100">
                JARVIS PRODUCTIVITY DECK
              </h2>
              <p className="font-mono-tech text-[10px] text-cyan-500">
                ACTIVE AGENDA & LOCAL INTELLIGENCE MEMORY
              </p>
            </div>
          </div>

          {/* Tab Selector */}
          <div className="flex items-center space-x-1 bg-black/60 p-1 rounded-lg border border-cyan-500/30">
            <button
              onClick={() => setActiveTab('tasks')}
              className={`px-3 py-1 rounded text-xs font-orbitron transition-all ${
                activeTab === 'tasks'
                  ? 'bg-cyan-500/30 text-cyan-100 border border-cyan-400'
                  : 'text-cyan-500 hover:text-cyan-300'
              }`}
            >
              TASKS ({pendingTasks.length})
            </button>
            <button
              onClick={() => setActiveTab('notes')}
              className={`px-3 py-1 rounded text-xs font-orbitron transition-all ${
                activeTab === 'notes'
                  ? 'bg-cyan-500/30 text-cyan-100 border border-cyan-400'
                  : 'text-cyan-500 hover:text-cyan-300'
              }`}
            >
              NOTES ({data.notes.length})
            </button>
            <button
              onClick={() => setActiveTab('timers')}
              className={`px-3 py-1 rounded text-xs font-orbitron transition-all ${
                activeTab === 'timers'
                  ? 'bg-cyan-500/30 text-cyan-100 border border-cyan-400'
                  : 'text-cyan-500 hover:text-cyan-300'
              }`}
            >
              TIMERS
            </button>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-cyan-400 hover:text-cyan-100 hover:bg-cyan-950/40 rounded-lg transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTab === 'tasks' && (
            <div className="space-y-4">
              {/* Add Task Input */}
              <form onSubmit={handleAddTask} className="flex space-x-2">
                <input
                  type="text"
                  value={newTaskText}
                  onChange={(e) => setNewTaskText(e.target.value)}
                  placeholder="Add new directive (e.g. 'Level Bambu A1 bed', 'Review G-code')..."
                  className="flex-1 bg-black/50 border border-cyan-500/30 rounded-xl px-4 py-2 text-xs text-cyan-100 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
                />
                <button
                  type="submit"
                  className="px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-orbitron text-xs rounded-xl flex items-center space-x-1.5 transition-all shadow-[0_0_12px_rgba(0,240,255,0.3)]"
                >
                  <Plus className="w-4 h-4" />
                  <span>ADD</span>
                </button>
              </form>

              {/* Pending Tasks */}
              <div className="space-y-2">
                <div className="text-[11px] font-orbitron text-cyan-400 uppercase tracking-wider">
                  Pending Directives ({pendingTasks.length})
                </div>
                {pendingTasks.length === 0 ? (
                  <div className="text-center py-6 border border-dashed border-cyan-500/20 rounded-xl text-cyan-500/60 font-mono-tech text-xs">
                    All tasks completed. Standing by for new directives, Sir.
                  </div>
                ) : (
                  pendingTasks.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between p-3 bg-cyan-950/30 border border-cyan-500/20 hover:border-cyan-500/40 rounded-xl transition-all"
                    >
                      <button
                        onClick={() => handleToggleTask(t.id)}
                        className="flex items-center space-x-3 text-left flex-1"
                      >
                        <Square className="w-4 h-4 text-cyan-400 shrink-0" />
                        <span className="text-xs font-mono-tech text-cyan-200">{t.text}</span>
                      </button>
                      <button
                        onClick={() => handleDeleteTask(t.id)}
                        className="text-cyan-600 hover:text-red-400 p-1 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* Completed Tasks */}
              {completedTasks.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-cyan-500/20">
                  <div className="text-[11px] font-orbitron text-cyan-600 uppercase tracking-wider">
                    Completed Directives ({completedTasks.length})
                  </div>
                  {completedTasks.slice(-5).map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between p-2.5 bg-black/40 border border-cyan-900/30 rounded-xl opacity-60"
                    >
                      <button
                        onClick={() => handleToggleTask(t.id)}
                        className="flex items-center space-x-3 text-left flex-1"
                      >
                        <CheckSquare className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="text-xs font-mono-tech line-through text-cyan-500">{t.text}</span>
                      </button>
                      <button
                        onClick={() => handleDeleteTask(t.id)}
                        className="text-cyan-700 hover:text-red-400 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'notes' && (
            <div className="space-y-4">
              {/* Add Note Form */}
              <form onSubmit={handleAddNote} className="space-y-2 bg-black/40 border border-cyan-500/20 p-3 rounded-xl">
                <input
                  type="text"
                  value={newNoteTitle}
                  onChange={(e) => setNewNoteTitle(e.target.value)}
                  placeholder="Note Title / Reference (e.g. Bambu A1 Filament Retraction)..."
                  className="w-full bg-cyan-950/30 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs text-cyan-100 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
                />
                <textarea
                  value={newNoteContent}
                  onChange={(e) => setNewNoteContent(e.target.value)}
                  placeholder="Details, observations, parameters, or links..."
                  rows={3}
                  className="w-full bg-cyan-950/30 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs text-cyan-200 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
                />
                <div className="flex justify-end">
                  <button
                    type="submit"
                    className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-black font-orbitron font-bold text-xs rounded-lg transition-all"
                  >
                    SAVE NOTE
                  </button>
                </div>
              </form>

              {/* Notes List */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.notes.map((n) => (
                  <div key={n.id} className="p-3 bg-cyan-950/20 border border-cyan-500/30 rounded-xl space-y-1">
                    <div className="font-orbitron font-bold text-xs text-cyan-200 flex items-center justify-between">
                      <span className="truncate">{n.title}</span>
                      <StickyNote className="w-3.5 h-3.5 text-cyan-400 shrink-0 ml-1" />
                    </div>
                    <p className="font-mono-tech text-xs text-cyan-300/80 whitespace-pre-wrap">
                      {n.content}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'timers' && (
            <div className="space-y-6">
              <div>
                <h3 className="font-orbitron text-xs text-cyan-300 font-bold mb-2">QUICK J.A.R.V.I.S. TIMERS</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                  {[
                    { mins: 5, label: "Bed Adhesion Check" },
                    { mins: 15, label: "First Layer Inspection" },
                    { mins: 30, label: "Filament Level Alert" },
                    { mins: 45, label: "Deep Work Sprint" }
                  ].map((preset) => (
                    <button
                      key={preset.mins}
                      onClick={() => handleStartTimer(preset.mins, preset.label)}
                      className="p-3 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400 rounded-xl text-left transition-all group"
                    >
                      <div className="flex items-center justify-between text-cyan-400 mb-1">
                        <Clock className="w-4 h-4 group-hover:animate-spin" />
                        <span className="font-orbitron font-bold text-sm text-cyan-100">{preset.mins}m</span>
                      </div>
                      <div className="text-[11px] font-mono-tech text-cyan-300/80 truncate">
                        {preset.label}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-4 bg-black/40 border border-cyan-500/20 rounded-xl space-y-3">
                <h3 className="font-orbitron text-xs text-cyan-300 font-bold">CUSTOM COUNTDOWN</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-mono-tech text-cyan-400 block mb-1">DURATION (MINUTES)</label>
                    <input
                      type="number"
                      min={1}
                      max={180}
                      value={customTimerMins}
                      onChange={(e) => setCustomTimerMins(Number(e.target.value))}
                      className="w-full bg-cyan-950/40 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs text-cyan-100 font-mono-tech focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-mono-tech text-cyan-400 block mb-1">LABEL / DIRECTIVE</label>
                    <input
                      type="text"
                      value={timerLabel}
                      onChange={(e) => setTimerLabel(e.target.value)}
                      placeholder="e.g. Jet Engine Slicing"
                      className="w-full bg-cyan-950/40 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs text-cyan-100 font-mono-tech focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </div>
                <button
                  onClick={() => handleStartTimer(customTimerMins, timerLabel)}
                  className="w-full py-2 bg-gradient-to-r from-cyan-600 to-teal-500 hover:from-cyan-500 hover:to-teal-400 text-black font-orbitron font-bold text-xs rounded-xl transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)]"
                >
                  START COUNTDOWN
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

