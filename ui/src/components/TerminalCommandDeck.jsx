import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Mic, MicOff, Volume2, VolumeX, Terminal, 
  Cpu, Disc
} from 'lucide-react';

export default function TerminalCommandDeck({
  messages = [],
  onSendMessage,
  isListening,
  onToggleListening,
  interimTranscript = "",
  voiceEnabled,
  onToggleVoice,
  isProcessing,
  isHexorSpeaking = false,
  conversationMode = false,
  convoSecondsLeft = 0
}) {
  const [inputText, setInputText] = useState('');
  const chatScrollContainerRef = useRef(null);

  useEffect(() => {
    if (chatScrollContainerRef.current) {
      chatScrollContainerRef.current.scrollTop = chatScrollContainerRef.current.scrollHeight;
    }
  }, [messages, isProcessing, interimTranscript]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputText.trim() && !isProcessing) {
      onSendMessage(inputText);
      setInputText('');
    }
  };

  const quickPrompts = [
    "Play Starboy on Spotify",
    "Find a phone stand for my Bambu A1",
    "List files in current directory",
    "Run system diagnostics",
    "Explain how my code works"
  ];

  return (
    <div className="relative flex flex-col h-full bg-black/70 border border-cyan-500/30 rounded-xl p-4 backdrop-blur-md glow-cyan overflow-hidden">
      <div className="shrink-0 relative z-10 flex items-center justify-between pb-3 border-b border-cyan-500/20">
        <div className="flex items-center space-x-2">
          <Terminal className="w-5 h-5 text-cyan-400" />
          <span className="font-orbitron font-bold text-sm tracking-wider text-cyan-200">
            HEXOR COMMAND DECK
          </span>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onToggleVoice}
            className={`p-1.5 rounded-lg border transition-all ${
              voiceEnabled 
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300' 
                : 'bg-black/40 border-cyan-500/20 text-cyan-600'
            }`}
            title={voiceEnabled ? "Voice Output Active" : "Voice Output Muted"}
          >
            {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          <button
            onClick={onToggleListening}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border transition-all ${
              isHexorSpeaking
                ? 'bg-amber-950/60 border-amber-400/80 text-amber-200'
                : conversationMode
                ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200 shadow-[0_0_12px_rgba(16,185,129,0.5)] animate-pulse'
                : isListening
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 shadow-[0_0_8px_rgba(0,240,255,0.3)]'
                : 'bg-black/40 border-cyan-500/30 text-cyan-400 hover:text-cyan-200'
            }`}
            title={
              isHexorSpeaking
                ? "Microphone muted while Hexor speaks"
                : conversationMode
                ? `Hands-free conversation active (${convoSecondsLeft}s remaining)`
                : isListening
                ? "Standing by for 'Hey Hexor' or 'Hexor'"
                : "Start voice wake listener"
            }
          >
            {isHexorSpeaking ? (
              <Volume2 className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            ) : conversationMode ? (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
            ) : isListening ? (
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-pulse absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
              </span>
            ) : (
              <MicOff className="w-3.5 h-3.5" />
            )}
            <span className="font-orbitron text-[11px] font-semibold">
              {isHexorSpeaking
                ? "HEXOR SPEAKING"
                : conversationMode
                ? `CONVERSATION (${convoSecondsLeft}s)`
                : isListening
                ? "STANDBY (HEY HEXOR)"
                : "START WAKE"}
            </span>
          </button>
        </div>
      </div>

      <div ref={chatScrollContainerRef} className="flex-1 overflow-y-auto space-y-3 py-3 pr-2 font-mono-tech text-xs">
        {messages.map((msg, index) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={index}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center space-x-1.5 mb-0.5 text-[10px] text-cyan-500 font-orbitron">
                <span>{isUser ? "OPERATOR" : "HEXOR"}</span>
                {msg.latency && (
                  <span className="px-1.5 py-0.2 bg-cyan-950/60 rounded border border-cyan-500/20 text-[9px] text-cyan-400">
                    {msg.latency}s
                  </span>
                )}
              </div>

              <div
                className={`max-w-[88%] px-3.5 py-2.5 rounded-xl border leading-relaxed ${
                  isUser
                    ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-100 rounded-tr-none'
                    : 'bg-black/70 border-cyan-500/30 text-cyan-200 rounded-tl-none shadow-[0_0_10px_rgba(0,240,255,0.08)]'
                }`}
              >
                {msg.tool_name && (
                  <div className="flex items-center space-x-1 text-[10px] text-amber-400 mb-1 pb-1 border-b border-cyan-500/20 font-orbitron">
                    <Cpu className="w-3 h-3" />
                    <span>TOOL: [{msg.tool_name}]</span>
                  </div>
                )}
                
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {msg.web_results && (
                  <div className="mt-2 space-y-1.5 border-t border-cyan-500/20 pt-1.5">
                    {msg.web_results.map((r, i) => (
                      <a
                        key={i}
                        href={r.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block p-1.5 bg-cyan-950/30 hover:bg-cyan-900/40 border border-cyan-500/20 rounded transition-all text-cyan-300"
                      >
                        <div className="font-semibold text-[11px] truncate">{r.title}</div>
                        <div className="text-[10px] text-cyan-400/70 line-clamp-1">{r.snippet}</div>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isHexorSpeaking && (
          <div className="flex items-center space-x-2 p-2 bg-amber-950/40 border border-amber-500/40 rounded-lg text-amber-200 text-xs font-mono-tech">
            <Volume2 className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>[Audio Active] Hexor speaking — microphone feedback suppressed.</span>
          </div>
        )}

        {isListening && !isHexorSpeaking && interimTranscript && (
          <div className={`flex items-center space-x-2 p-2 rounded-lg text-xs font-mono-tech animate-pulse ${
            conversationMode
              ? 'bg-emerald-950/40 border border-emerald-500/50 text-emerald-200'
              : 'bg-cyan-950/40 border border-cyan-500/50 text-cyan-200'
          }`}>
            <span className={`w-2 h-2 rounded-full animate-ping ${conversationMode ? 'bg-emerald-400' : 'bg-cyan-400'}`} />
            <span>{conversationMode ? '[Live Conversation] ' : '[Standby] '}Hearing: "{interimTranscript}"</span>
          </div>
        )}

        {isProcessing && (
          <div className="flex items-center space-x-2 text-cyan-400 py-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span className="font-orbitron text-xs animate-pulse">HEXOR COGNITIVE CORES PROCESSING...</span>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-1.5 overflow-x-auto py-1.5 no-scrollbar">
        {quickPrompts.map((q, i) => (
          <button
            key={i}
            onClick={() => onSendMessage(q)}
            className="whitespace-nowrap px-2 py-1 bg-cyan-950/30 border border-cyan-500/20 hover:border-cyan-400/50 hover:bg-cyan-900/30 rounded text-[10px] text-cyan-400 transition-all font-mono-tech"
          >
            + {q}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="relative mt-2 flex items-center">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Speak or type a command for Hexor..."
          className="w-full bg-cyan-950/40 border border-cyan-500/30 rounded-xl px-4 py-2.5 pr-12 text-sm text-cyan-100 placeholder-cyan-600/70 focus:outline-none focus:border-cyan-400 font-mono-tech"
        />
        <button
          type="submit"
          disabled={!inputText.trim() || isProcessing}
          className="absolute right-2 p-1.5 rounded-lg bg-cyan-500 text-black hover:bg-cyan-400 disabled:opacity-40 transition-all"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
