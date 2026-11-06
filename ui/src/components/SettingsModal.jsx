import React, { useState, useEffect, useRef } from 'react';
import { 
  X, Settings, Key, Volume2, Box, Cpu, ExternalLink, 
  Save, Check, Mic, VolumeX, PlayCircle, Disc 
} from 'lucide-react';

export default function SettingsModal({ 
  isOpen, 
  onClose, 
  onSave, 
  selectedMicId, 
  setSelectedMicId, 
  selectedSpeakerId, 
  setSelectedSpeakerId 
}) {
  const [provider, setProvider] = useState('groq');
  const [groqKey, setGroqKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [voice, setVoice] = useState('en-GB-RyanNeural');
  const [bambuIp, setBambuIp] = useState('');
  const [bambuSerial, setBambuSerial] = useState('');
  const [bambuCode, setBambuCode] = useState('');
  const [spotifyClientId, setSpotifyClientId] = useState('');
  const [spotifyClientSecret, setSpotifyClientSecret] = useState('');
  const [spotifyAuthStatus, setSpotifyAuthStatus] = useState({ is_authenticated: false, auth_url: null });
  const [savedSuccess, setSavedSuccess] = useState(false);

  const [audioInputDevices, setAudioInputDevices] = useState([]);
  const [audioOutputDevices, setAudioOutputDevices] = useState([]);
  const [micLevel, setMicLevel] = useState(0);
  const [isTestingMic, setIsTestingMic] = useState(false);

  const audioContextRef = useRef(null);
  const micStreamRef = useRef(null);
  const animFrameRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      fetch('/api/settings')
        .then(res => res.json())
        .then(data => {
          if (data.llm) setProvider(data.llm.current_provider || 'groq');
          if (data.voice) setVoice(data.voice.name || 'en-GB-RyanNeural');
          if (data.bambu) {
            setBambuIp(data.bambu.ip || '');
            setBambuSerial(data.bambu.serial || '');
          }
          if (data.spotify) {
            setSpotifyClientId(data.spotify.client_id || '');
            setSpotifyAuthStatus({
              is_authenticated: data.spotify.is_authenticated,
              auth_url: data.spotify.auth_url
            });
          }
        })
        .catch(() => {});

      loadAudioDevices();
    } else {
      stopMicTest();
    }
    return () => stopMicTest();
  }, [isOpen]);

  const loadAudioDevices = async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
      
      const inputs = devices.filter(d => d.kind === 'audioinput');
      const outputs = devices.filter(d => d.kind === 'audiooutput');
      
      setAudioInputDevices(inputs);
      setAudioOutputDevices(outputs);

      if (!selectedMicId) {
        const redgear = inputs.find(d => d.label.toLowerCase().includes('redgear') || d.label.toLowerCase().includes('shadow vox'));
        if (redgear) {
          setSelectedMicId(redgear.deviceId);
          localStorage.setItem('hexor_mic_id', redgear.deviceId);
        } else if (inputs.length > 0) {
          setSelectedMicId(inputs[0].deviceId);
        }
      }

      if (!selectedSpeakerId) {
        const dell = outputs.find(d => d.label.toLowerCase().includes('dell') || d.label.toLowerCase().includes('s234'));
        if (dell) {
          setSelectedSpeakerId(dell.deviceId);
          localStorage.setItem('hexor_speaker_id', dell.deviceId);
        } else if (outputs.length > 0) {
          setSelectedSpeakerId(outputs[0].deviceId);
        }
      }
    } catch (e) {
      console.warn('Could not enumerate audio devices', e);
    }
  };

  const handleMicSelect = (id) => {
    setSelectedMicId(id);
    localStorage.setItem('hexor_mic_id', id);
    if (isTestingMic) {
      startMicTest(id);
    }
  };

  const handleSpeakerSelect = (id) => {
    setSelectedSpeakerId(id);
    localStorage.setItem('hexor_speaker_id', id);
  };

  const startMicTest = async (deviceId) => {
    stopMicTest();
    try {
      const constraints = deviceId ? { audio: { deviceId: { exact: deviceId } } } : { audio: true };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      micStreamRef.current = stream;
      setIsTestingMic(true);

      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const checkVolume = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        setMicLevel(Math.min(100, Math.round((avg / 128) * 100)));
        animFrameRef.current = requestAnimationFrame(checkVolume);
      };
      checkVolume();
    } catch (e) {
      console.error('Mic test error:', e);
      setIsTestingMic(false);
    }
  };

  const stopMicTest = () => {
    setIsTestingMic(false);
    setMicLevel(0);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(t => t.stop());
      micStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
  };

  const testSpeaker = async () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3); // A5
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.5);
    } catch (e) {}
  };

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      llm_provider: provider,
      groq_api_key: groqKey || undefined,
      gemini_api_key: geminiKey || undefined,
      voice_name: voice,
      bambu_ip: bambuIp || undefined,
      bambu_serial: bambuSerial || undefined,
      bambu_access_code: bambuCode || undefined,
      spotify_client_id: spotifyClientId || undefined,
      spotify_client_secret: spotifyClientSecret || undefined
    };

    if (onSave) {
      await onSave(payload);
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 1000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="relative w-full max-w-lg bg-gray-950 border border-cyan-500/40 rounded-2xl p-6 shadow-[0_0_30px_rgba(0,240,255,0.2)]">
        <div className="flex items-center justify-between pb-4 border-b border-cyan-500/20">
          <div className="flex items-center space-x-2">
            <Settings className="w-5 h-5 text-cyan-400" />
            <h2 className="font-orbitron font-bold text-sm tracking-wider text-cyan-100 uppercase">
              HEXOR QUANTUM SETTINGS
            </h2>
          </div>
          <button
            onClick={() => { stopMicTest(); onClose(); }}
            className="p-1 rounded text-cyan-400 hover:text-cyan-200 transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 text-xs font-mono-tech max-h-[75vh] overflow-y-auto pr-2">
          {/* HARDWARE AUDIO ROUTING (MIC & SPEAKER) */}
          <div className="p-3 bg-cyan-950/40 border border-cyan-500/30 rounded-xl space-y-3">
            <div className="flex items-center space-x-2 font-orbitron font-bold text-cyan-200 text-xs">
              <Mic className="w-4 h-4 text-cyan-400" />
              <span>AUDIO HARDWARE ROUTING</span>
            </div>

            {/* Microphone Selector */}
            <div>
              <label className="block text-cyan-400 text-[11px] mb-1">
                MICROPHONE INPUT DEVICE:
              </label>
              <select
                value={selectedMicId || ''}
                onChange={(e) => handleMicSelect(e.target.value)}
                className="w-full bg-black/70 border border-cyan-500/40 rounded px-3 py-2 text-cyan-100 focus:outline-none focus:border-cyan-400"
              >
                {audioInputDevices.map((d, i) => (
                  <option key={d.deviceId || i} value={d.deviceId}>
                    {d.label || `Microphone ${i + 1}`}
                  </option>
                ))}
              </select>
            </div>

            {/* Live Mic Test Meter */}
            <div className="bg-black/60 border border-cyan-500/20 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] text-cyan-400">INPUT SIGNAL LEVEL:</span>
                <button
                  type="button"
                  onClick={() => isTestingMic ? stopMicTest() : startMicTest(selectedMicId)}
                  className={`px-2 py-0.5 rounded text-[10px] font-orbitron uppercase border transition-all ${
                    isTestingMic 
                      ? 'bg-emerald-500/30 border-emerald-400 text-emerald-200' 
                      : 'bg-cyan-950/40 border-cyan-500/30 text-cyan-300'
                  }`}
                >
                  {isTestingMic ? 'TESTING (SPEAK NOW)' : 'TEST MIC'}
                </button>
              </div>
              <div className="w-full bg-gray-900 h-2 rounded-full overflow-hidden border border-cyan-500/30">
                <div 
                  className="bg-gradient-to-r from-emerald-500 to-cyan-400 h-full transition-all duration-100"
                  style={{ width: `${micLevel}%` }}
                />
              </div>
              <div className="text-[9px] text-cyan-500/80 mt-1">
                {isTestingMic ? `Level: ${micLevel}% ${micLevel > 10 ? '✓ Audio detected' : 'Waiting for voice...'}` : 'Click Test Mic to check signal'}
              </div>
            </div>

            {/* Speaker Selector */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-cyan-400 text-[11px]">
                  SPEAKER OUTPUT DEVICE:
                </label>
                <button
                  type="button"
                  onClick={testSpeaker}
                  className="flex items-center space-x-1 text-[10px] text-cyan-300 hover:text-cyan-100 underline"
                >
                  <PlayCircle className="w-3 h-3" />
                  <span>Test Chime</span>
                </button>
              </div>
              <select
                value={selectedSpeakerId || ''}
                onChange={(e) => handleSpeakerSelect(e.target.value)}
                className="w-full bg-black/70 border border-cyan-500/40 rounded px-3 py-2 text-cyan-100 focus:outline-none focus:border-cyan-400"
              >
                {audioOutputDevices.map((d, i) => (
                  <option key={d.deviceId || i} value={d.deviceId}>
                    {d.label || `Speaker ${i + 1}`}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* AI INFERENCE CORE */}
          <div>
            <label className="block text-cyan-400 font-orbitron text-[11px] mb-1">
              AI INFERENCE CORE
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-black/60 border border-cyan-500/30 rounded px-3 py-2 text-cyan-200 focus:outline-none focus:border-cyan-400"
            >
              <option value="groq">Groq Cloud (120B Flagship / Llama 3.3 - Free)</option>
              <option value="gemini">Google Gemini (Gemini 2.0 Flash - Free)</option>
              <option value="ollama">Ollama (Offline Local)</option>
            </select>
          </div>

          {/* Groq Key */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-cyan-400 font-orbitron text-[11px]">
                GROQ API KEY (FREE)
              </label>
              <a
                href="https://console.groq.com/keys"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-cyan-400 hover:text-cyan-200 flex items-center space-x-0.5 underline"
              >
                <span>Console Keys</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            </div>
            <input
              type="password"
              value={groqKey}
              onChange={(e) => setGroqKey(e.target.value)}
              placeholder="gsk_..."
              className="w-full bg-black/60 border border-cyan-500/30 rounded px-3 py-2 text-cyan-200 focus:outline-none focus:border-cyan-400"
            />
          </div>

          {/* Gemini Key */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-cyan-400 font-orbitron text-[11px]">
                GEMINI API KEY (FREE)
              </label>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-cyan-400 hover:text-cyan-200 flex items-center space-x-0.5 underline"
              >
                <span>AI Studio Key</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            </div>
            <input
              type="password"
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              placeholder="AIzaSy..."
              className="w-full bg-black/60 border border-cyan-500/30 rounded px-3 py-2 text-cyan-200 focus:outline-none focus:border-cyan-400"
            />
          </div>

          {/* Voice Personality */}
          <div>
            <label className="block text-cyan-400 font-orbitron text-[11px] mb-1">
              HEXOR VOICE & TIMBRE
            </label>
            <select
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="w-full bg-black/60 border border-cyan-500/30 rounded px-3 py-2 text-cyan-200 focus:outline-none focus:border-cyan-400"
            >
              <option value="en-GB-RyanNeural">Paul Bettany / JARVIS Refined British (Ryan Neural)</option>
              <option value="en-US-ChristopherNeural">Deep Authoritative Commander (Christopher Neural)</option>
              <option value="en-US-GuyNeural">Smooth Tactical American (Guy Neural)</option>
              <option value="en-US-AriaNeural">Cybernetic Female (Aria Neural)</option>
            </select>
          </div>

          {/* Bambu A1 LAN Settings */}
          <div className="pt-2 border-t border-cyan-500/20">
            <div className="flex items-center space-x-1.5 text-cyan-300 font-orbitron text-[11px] mb-2">
              <Box className="w-4 h-4 text-cyan-400" />
              <span>BAMBU LAB A1 LAN INTEGRATION</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-cyan-500 mb-0.5">PRINTER IP</label>
                <input
                  type="text"
                  value={bambuIp}
                  onChange={(e) => setBambuIp(e.target.value)}
                  placeholder="e.g. 192.168.1.120"
                  className="w-full bg-black/60 border border-cyan-500/30 rounded px-2.5 py-1.5 text-cyan-200 text-xs"
                />
              </div>
              <div>
                <label className="block text-[10px] text-cyan-500 mb-0.5">SERIAL NUMBER</label>
                <input
                  type="text"
                  value={bambuSerial}
                  onChange={(e) => setBambuSerial(e.target.value)}
                  placeholder="e.g. 01P00A..."
                  className="w-full bg-black/60 border border-cyan-500/30 rounded px-2.5 py-1.5 text-cyan-200 text-xs"
                />
              </div>
            </div>
            <div className="mt-2">
              <label className="block text-[10px] text-cyan-500 mb-0.5">ACCESS CODE</label>
              <input
                type="password"
                value={bambuCode}
                onChange={(e) => setBambuCode(e.target.value)}
                placeholder="From A1 Screen -> Settings -> LAN Mode"
                className="w-full bg-black/60 border border-cyan-500/30 rounded px-2.5 py-1.5 text-cyan-200 text-xs"
              />
            </div>
          </div>

          {/* Spotify Web API Integration */}
          <div className="pt-2 border-t border-cyan-500/20">
            <div className="flex items-center justify-between text-cyan-300 font-orbitron text-[11px] mb-2">
              <div className="flex items-center space-x-1.5">
                <Disc className="w-4 h-4 text-emerald-400" />
                <span>SPOTIFY WEB API (SILENT BACKGROUND CONTROL)</span>
              </div>
              {spotifyAuthStatus.is_authenticated ? (
                <span className="px-2 py-0.5 bg-emerald-500/20 border border-emerald-400/40 rounded text-[10px] text-emerald-300 flex items-center space-x-1">
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span>CONNECTED</span>
                </span>
              ) : (
                <span className="px-2 py-0.5 bg-amber-500/20 border border-amber-400/40 rounded text-[10px] text-amber-300">
                  NOT CONNECTED
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-cyan-500 mb-0.5">CLIENT ID</label>
                <input
                  type="text"
                  value={spotifyClientId}
                  onChange={(e) => setSpotifyClientId(e.target.value)}
                  placeholder="From developer.spotify.com"
                  className="w-full bg-black/60 border border-cyan-500/30 rounded px-2.5 py-1.5 text-cyan-200 text-xs"
                />
              </div>
              <div>
                <label className="block text-[10px] text-cyan-500 mb-0.5">CLIENT SECRET</label>
                <input
                  type="password"
                  value={spotifyClientSecret}
                  onChange={(e) => setSpotifyClientSecret(e.target.value)}
                  placeholder="From Spotify Dashboard"
                  className="w-full bg-black/60 border border-cyan-500/30 rounded px-2.5 py-1.5 text-cyan-200 text-xs"
                />
              </div>
            </div>
            {spotifyClientId && !spotifyAuthStatus.is_authenticated && (
              <div className="mt-2">
                <a
                  href="/api/spotify/login"
                  target="_blank"
                  rel="noreferrer"
                  className="block text-center py-1.5 bg-emerald-950/60 hover:bg-emerald-900/70 border border-emerald-400/50 rounded text-emerald-200 font-orbitron text-[10px] tracking-wider transition-all"
                >
                  AUTHORIZE SPOTIFY ACCOUNT (1-CLICK)
                </a>
              </div>
            )}
          </div>

          <button
            type="submit"
            className="w-full mt-4 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-orbitron font-bold text-xs rounded-xl flex items-center justify-center space-x-1.5 transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)]"
          >
            {savedSuccess ? (
              <>
                <Check className="w-4 h-4 text-emerald-950" />
                <span>SETTINGS SAVED</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>SAVE CONFIGURATION</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
