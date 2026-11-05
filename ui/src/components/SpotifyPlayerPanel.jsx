import React, { useState } from 'react';
import { 
  Music, Play, Pause, SkipForward, SkipBack, 
  Volume2, Radio, Disc3, Sparkles 
} from 'lucide-react';

export default function SpotifyPlayerPanel({ 
  spotifyData = {}, 
  onAction 
}) {
  const [songInput, setSongInput] = useState('');
  const currentTrack = spotifyData.current_track || {
    title: "Synthwave Transmissions",
    artist: "Cyberpunk Radio",
    status: "idle"
  };
  const isRunning = spotifyData.is_running ?? true;
  const isPlaying = currentTrack.status === "playing";

  const handlePlaySong = (e) => {
    e.preventDefault();
    if (songInput.trim() && onAction) {
      onAction('play_song', { query: songInput });
      setSongInput('');
    }
  };

  const handleMoodSelect = (mood) => {
    if (onAction) {
      onAction('recommend_music', { mood });
    }
  };

  return (
    <div className="relative flex flex-col h-full bg-black/60 border border-cyan-500/30 rounded-xl p-4 backdrop-blur-md overflow-hidden glow-cyan">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-cyan-500/20">
        <div className="flex items-center space-x-2">
          <Music className="w-5 h-5 text-emerald-400 animate-pulse" />
          <span className="font-orbitron font-bold text-sm tracking-wider text-cyan-200">
            SPOTIFY // AUDIO MATRIX
          </span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="font-mono-tech text-[11px] text-emerald-400 font-semibold">
            {isRunning ? "DESKTOP CONNECTED" : "WEB READY"}
          </span>
        </div>
      </div>

      {/* Track Details & Album Disc */}
      <div className="mt-3 flex items-center space-x-3 bg-black/40 border border-cyan-500/20 rounded-lg p-2.5">
        <div className="relative w-12 h-12 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center overflow-hidden">
          <Disc3 className={`w-8 h-8 text-cyan-400 ${isPlaying ? 'animate-spin-slow' : ''}`} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="font-orbitron text-xs font-bold text-cyan-100 truncate">
            {currentTrack.title || "Starboy"}
          </div>
          <div className="font-mono-tech text-[11px] text-cyan-400/80 truncate">
            {currentTrack.artist || "The Weeknd"}
          </div>
          <div className="flex items-center space-x-1 mt-1">
            {/* Equalizer animation */}
            <div className="flex items-end space-x-0.5 h-3">
              {[8, 14, 6, 12, 16, 9, 13, 5].map((h, i) => (
                <div
                  key={i}
                  className="w-1 bg-gradient-to-t from-cyan-500 to-emerald-400 rounded-sm animate-pulse"
                  style={{
                    height: isPlaying ? `${Math.sin(i * 1.5 + Date.now() / 300) * 6 + 8}px` : '3px',
                    transition: 'height 0.15s ease'
                  }}
                />
              ))}
            </div>
            <span className="text-[10px] font-mono-tech text-cyan-500 ml-1.5">
              {isPlaying ? "320 KBPS AUDIO" : "PAUSED"}
            </span>
          </div>
        </div>
      </div>

      {/* Quick Play Any Song or Playlist Input */}
      <form onSubmit={handlePlaySong} className="mt-2.5">
        <input
          type="text"
          value={songInput}
          onChange={(e) => setSongInput(e.target.value)}
          placeholder="Play any track, artist, or playlist..."
          className="w-full bg-cyan-950/40 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs text-cyan-200 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
        />
      </form>

      {/* Playback Controls */}
      <div className="mt-3 flex items-center justify-center space-x-4">
        <button
          onClick={() => onAction && onAction('previous')}
          className="p-2 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-400 hover:text-cyan-200 hover:border-cyan-400 transition-all"
          title="Previous Track"
        >
          <SkipBack className="w-4 h-4" />
        </button>

        <button
          onClick={() => onAction && onAction(isPlaying ? 'pause' : 'play')}
          className="p-3 rounded-full bg-cyan-500 text-black font-bold hover:bg-cyan-400 transition-all shadow-[0_0_15px_rgba(0,240,255,0.5)]"
          title={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
        </button>

        <button
          onClick={() => onAction && onAction('next')}
          className="p-2 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-400 hover:text-cyan-200 hover:border-cyan-400 transition-all"
          title="Next Track"
        >
          <SkipForward className="w-4 h-4" />
        </button>
      </div>

      {/* Smart Curated Playlists / Mood Presets */}
      <div className="mt-3 pt-2.5 border-t border-cyan-500/20">
        <div className="flex items-center space-x-1 text-[11px] font-orbitron text-cyan-400/80 mb-1.5">
          <Sparkles className="w-3 h-3 text-cyan-400" />
          <span>SMART TASTE PRESETS</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {[
            { label: "Focus Synth", mood: "focus" },
            { label: "Cyberpunk 2077", mood: "cyberpunk" },
            { label: "Lo-Fi Chill", mood: "lo-fi" },
            { label: "High Energy", mood: "energetic" }
          ].map((item) => (
            <button
              key={item.mood}
              onClick={() => handleMoodSelect(item.mood)}
              className="px-2 py-1 bg-black/40 border border-cyan-500/20 hover:border-cyan-400/60 hover:bg-cyan-950/40 rounded text-[10px] font-mono-tech text-cyan-300 text-left transition-all truncate"
            >
              # {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

