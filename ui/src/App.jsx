import React, { useState, useEffect, useRef } from 'react';
import { Settings, Volume2, VolumeX, Power, AlertTriangle, CloudSun, MapPin } from 'lucide-react';

import HexCoreReactor from './components/HexCoreReactor';
import Bambu3DPanel from './components/Bambu3DPanel';
import SpotifyPlayerPanel from './components/SpotifyPlayerPanel';
import SystemDiagnostics from './components/SystemDiagnostics';
import SkillEvolutionVault from './components/SkillEvolutionVault';
import TerminalCommandDeck from './components/TerminalCommandDeck';
import SettingsModal from './components/SettingsModal';
import JarvisProtocolBar from './components/JarvisProtocolBar';
import ProductivityModal from './components/ProductivityModal';

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hexor Quantum Core online, Sir. 120B neural model engaged, live weather & geolocation synchronized, and Windows deep OS automation active.',
      latency: 0.05
    }
  ]);

  const [telemetry, setTelemetry] = useState({});
  const [bambuData, setBambuData] = useState({});
  const [pendingApproval, setPendingApproval] = useState(null);
  const [spotifyData, setSpotifyData] = useState({});
  const [isProductivityOpen, setIsProductivityOpen] = useState(false);
  const [weatherData, setWeatherData] = useState({
    location: "Detecting Location...",
    temperature_c: 22,
    condition: "Clear"
  });
  const [skills, setSkills] = useState([]);
  
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(true);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  
  const [selectedMicId, setSelectedMicId] = useState(localStorage.getItem('hexor_mic_id') || '');
  const [selectedSpeakerId, setSelectedSpeakerId] = useState(localStorage.getItem('hexor_speaker_id') || '');
  const [activeMicLabel, setActiveMicLabel] = useState('Redgear Shadow VoX');

  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isShutdownConfirmOpen, setIsShutdownConfirmOpen] = useState(false);
  const [isSystemShuttingDown, setIsSystemShuttingDown] = useState(false);
  const [systemTime, setSystemTime] = useState(new Date().toLocaleTimeString());

  // Conversational hands-free & anti-feedback state
  const [isHexorSpeaking, setIsHexorSpeaking] = useState(false);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [conversationMode, setConversationMode] = useState(false);
  const [convoSecondsLeft, setConvoSecondsLeft] = useState(0);
  const [ringingAlarm, setRingingAlarm] = useState(null);

  const audioRef = useRef(new Audio());
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const isListeningRef = useRef(true);
  const isSpeakingRef = useRef(false);
  const wasInConvoBeforeSpeakingRef = useRef(false);
  const userSpeakingTimeoutRef = useRef(null);
  const speechTimeoutRef = useRef(null);
  const conversationActiveUntilRef = useRef(0);
  const silenceTimerRef = useRef(null);
  const accumulatedTranscriptRef = useRef('');
  const wsRef = useRef(null);

  const triggerUserSpeaking = (active = true) => {
    // If wake listener / standby is turned off, do NOT trigger user speaking state!
    if (!isListeningRef.current) {
      setIsUserSpeaking(false);
      return;
    }
    if (active) {
      if (isSpeakingRef.current) return;
      setIsUserSpeaking(true);
      if (userSpeakingTimeoutRef.current) clearTimeout(userSpeakingTimeoutRef.current);
      userSpeakingTimeoutRef.current = setTimeout(() => {
        setIsUserSpeaking(false);
      }, 2500);
    } else {
      if (userSpeakingTimeoutRef.current) clearTimeout(userSpeakingTimeoutRef.current);
      setIsUserSpeaking(false);
    }
  };

  const resetSpeakingState = () => {
    if (speechTimeoutRef.current) {
      clearTimeout(speechTimeoutRef.current);
      speechTimeoutRef.current = null;
    }
    setIsSpeaking(false);
    isSpeakingRef.current = false;
    setIsHexorSpeaking(false);
    accumulatedTranscriptRef.current = '';
    setInterimTranscript('');
  };

  const playWakeChime = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const now = ctx.currentTime;
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();
      osc1.type = 'sine';
      osc2.type = 'triangle';
      osc1.frequency.setValueAtTime(523.25, now);
      osc1.frequency.exponentialRampToValueAtTime(1046.50, now + 0.12);
      osc2.frequency.setValueAtTime(659.25, now);
      osc2.frequency.exponentialRampToValueAtTime(1318.51, now + 0.12);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);
      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 0.22);
      osc2.stop(now + 0.22);
    } catch (e) {}
  };

  // Live Clock & Conversation timer
  useEffect(() => {
    const timer = setInterval(() => {
      setSystemTime(new Date().toLocaleTimeString());
      
      // While Hexor is actively speaking, do NOT decrement the user's listening timeout!
      if (isSpeakingRef.current) {
        return;
      }

      const left = Math.max(0, Math.ceil((conversationActiveUntilRef.current - Date.now()) / 1000));
      setConvoSecondsLeft(left);
      if (left <= 0 && conversationActiveUntilRef.current !== 0) {
        conversationActiveUntilRef.current = 0;
        setConversationMode(false);
        setIsUserSpeaking(false);
        // Synchronously notify backend wake listener to drop into standby
        fetch('/api/voice/standby', { method: 'POST' }).catch(() => {});
      }
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Speaker routing & acoustic feedback prevention
  useEffect(() => {
    const audio = audioRef.current;
    
    const onPlay = () => {
      wasInConvoBeforeSpeakingRef.current = isListeningRef.current && (conversationActiveUntilRef.current > Date.now());
      setIsSpeaking(true);
      isSpeakingRef.current = true;
      setIsHexorSpeaking(true);
      triggerUserSpeaking(false);
    };

    const onEnd = () => {
      const shouldResumeConvo = isListeningRef.current && wasInConvoBeforeSpeakingRef.current;
      resetSpeakingState();
      triggerUserSpeaking(false);
      if (shouldResumeConvo) {
        // The listening timeout starts ONLY AFTER Hexor finishes speaking, and only if conversation was active!
        conversationActiveUntilRef.current = Date.now() + 25000;
        setConversationMode(true);
        setConvoSecondsLeft(25);
      } else {
        conversationActiveUntilRef.current = 0;
        setConversationMode(false);
        setConvoSecondsLeft(0);
      }
    };

    const onError = () => {
      resetSpeakingState();
      triggerUserSpeaking(false);
    };

    audio.addEventListener('play', onPlay);
    audio.addEventListener('ended', onEnd);
    audio.addEventListener('pause', onEnd);
    audio.addEventListener('error', onError);

    if (selectedSpeakerId && audio.setSinkId) {
      audio.setSinkId(selectedSpeakerId).catch(() => {});
    }

    return () => {
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('ended', onEnd);
      audio.removeEventListener('pause', onEnd);
      audio.removeEventListener('error', onError);
    };
  }, [selectedSpeakerId]);

  // Audio Device Detection
  useEffect(() => {
    const detectDevices = async () => {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
        const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
        const inputs = devices.filter(d => d.kind === 'audioinput');
        const outputs = devices.filter(d => d.kind === 'audiooutput');

        if (!selectedMicId) {
          const redgear = inputs.find(d => 
            d.label && (
              d.label.toLowerCase().includes('redgear') || 
              d.label.toLowerCase().includes('shadow vox')
            )
          );
          const chosenMic = redgear || inputs[0];
          if (chosenMic && chosenMic.deviceId) {
            setSelectedMicId(chosenMic.deviceId);
            setActiveMicLabel(chosenMic.label || 'Default Microphone');
            localStorage.setItem('hexor_mic_id', chosenMic.deviceId);
          }
        } else {
          const curr = inputs.find(d => d.deviceId === selectedMicId);
          if (curr && curr.label) setActiveMicLabel(curr.label);
        }

        if (!selectedSpeakerId) {
          const dell = outputs.find(d => 
            d.label && (
              d.label.toLowerCase().includes('dell') || 
              d.label.toLowerCase().includes('s234')
            )
          );
          const chosenSpk = dell || outputs[0];
          if (chosenSpk && chosenSpk.deviceId) {
            setSelectedSpeakerId(chosenSpk.deviceId);
            localStorage.setItem('hexor_speaker_id', chosenSpk.deviceId);
          }
        }
      } catch (e) {}
    };

    detectDevices();
  }, []);

  // Browser Geolocation Access on Startup
  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const res = await fetch('/api/location', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude
              })
            });
            const data = await res.json();
            if (data.weather) setWeatherData(data.weather);
          } catch (e) {}
        },
        () => {},
        { timeout: 8000 }
      );
    }
  }, []);

  // WebSocket Connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    const connectWs = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "hud_telemetry") {
            if (data.system) setTelemetry(data.system);
            if (data.bambu) setBambuData(data.bambu);
            if (data.weather && data.weather.location) setWeatherData(data.weather);
            if (data.spotify) setSpotifyData(data.spotify);
            if (data.pending_approval !== undefined) setPendingApproval(data.pending_approval);
          } else if (data.type === "spotify_update" && data.data) {
            setSpotifyData(data.data);
          } else if (data.type === "alarm_triggered") {
            setRingingAlarm(data.alarm);
            if (data.greeting) {
              setMessages(prev => [...prev, { role: 'assistant', content: data.greeting }]);
            }
            if (data.audio?.audio_base64 && voiceEnabled) {
              playVoiceAudio(data.audio.audio_base64, data.audio.mime_type);
            }
          } else if (data.type === "alarm_stopped") {
            setRingingAlarm(null);
          } else if (data.type === "user_speaking") {
            if (isListeningRef.current) {
              triggerUserSpeaking(!!data.speaking);
              // Only extend conversation timeout if already actively in conversation!
              if (data.speaking && (conversationActiveUntilRef.current > Date.now())) {
                conversationActiveUntilRef.current = Date.now() + 25000;
              }
            }
          } else if (data.type === "system_shutdown") {
            setIsSystemShuttingDown(true);
            stopWebSpeech();
            setTimeout(() => {
              try { window.close(); } catch (e) {}
              window.location.href = "about:blank";
            }, 500);
          } else if (data.type === "standby_entered") {
            conversationActiveUntilRef.current = 0;
            setConversationMode(false);
            setIsUserSpeaking(false);
            setConvoSecondsLeft(0);
          } else if (data.type === "wake_detected") {
            if (isListeningRef.current) {
              playWakeChime();
              conversationActiveUntilRef.current = Date.now() + 25000;
              setConversationMode(true);
            }
          } else if (data.type === "chat_response" || data.type === "approval_response") {
            handleAssistantResponse(data.payload);
          }
        } catch (e) {
          console.error(e);
        }
      };

      ws.onclose = () => {
        setTimeout(connectWs, 3000);
      };
    };

    connectWs();
    fetchSkills();
    fetchSpotify();
    fetchWeather();
    fetchTelemetry();
    fetchBambu();

    const pollInterval = setInterval(() => {
      fetchSpotify();
      fetchTelemetry();
      fetchBambu();
    }, 2500);

    const weatherInterval = setInterval(fetchWeather, 30000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(weatherInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Speech Recognition (Web Speech API)
  const stopWebSpeech = () => {
    isListeningRef.current = false;
    setIsListening(false);
    setIsUserSpeaking(false);
    setConversationMode(false);
    conversationActiveUntilRef.current = 0;
    setConvoSecondsLeft(0);
    setInterimTranscript('');
    accumulatedTranscriptRef.current = '';
    wasInConvoBeforeSpeakingRef.current = false;
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onstart = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onresult = null;
        recognitionRef.current.onspeechstart = null;
        recognitionRef.current.onspeechend = null;
        recognitionRef.current.abort();
      } catch (e) {}
      recognitionRef.current = null;
    }
  };

  const startWebSpeech = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onstart = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.abort();
      } catch (e) {}
      recognitionRef.current = null;
    }

    isListeningRef.current = true;
    setIsListening(true);
    accumulatedTranscriptRef.current = '';
    setInterimTranscript('');

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      if (!isListeningRef.current) {
        try { recognition.abort(); } catch (e) {}
        return;
      }
      setIsListening(true);
    };

    let restartTimer = null;
    const safeRestart = () => {
      if (!isListeningRef.current) return;
      if (restartTimer) clearTimeout(restartTimer);
      restartTimer = setTimeout(() => {
        try {
          if (isListeningRef.current && recognitionRef.current) {
            recognitionRef.current.start();
          }
        } catch (err) {
          if (err.name !== 'InvalidStateError' && isListeningRef.current) {
            setTimeout(safeRestart, 400);
          }
        }
      }, 150);
    };

    recognition.onend = () => {
      if (!isListeningRef.current) return;
      safeRestart();
    };

    recognition.onerror = (e) => {
      if (e.error === 'not-allowed') {
        console.warn("Microphone access denied by browser.");
        stopWebSpeech();
        return;
      }
      if (e.error === 'aborted' || !isListeningRef.current) {
        return;
      }
      safeRestart();
    };

    recognition.onspeechstart = () => {
      if (isListeningRef.current && !isSpeakingRef.current && conversationActiveUntilRef.current > Date.now()) {
        triggerUserSpeaking(true);
      }
    };

    recognition.onspeechend = () => {
      triggerUserSpeaking(false);
    };

    recognition.onresult = (event) => {
      if (!isListeningRef.current) return;
      let currentInterim = '';
      let finalChunk = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalChunk += event.results[i][0].transcript;
        } else {
          currentInterim += event.results[i][0].transcript;
        }
      }

      const chunkText = (finalChunk || currentInterim).trim();
      if (!chunkText) return;

      // Barge-in: Only trigger if the user explicitly says an interrupt command, never on Hexor's own voice feedback
      if (isSpeakingRef.current) {
        if (/(?:stop|wait|pause|quiet|cancel|silence|hexor|jarvis)/i.test(chunkText)) {
          try {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
          } catch (e) {}
          if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
          }
          resetSpeakingState();
        }
        return;
      }

      if (finalChunk.trim()) {
        accumulatedTranscriptRef.current += ' ' + finalChunk.trim();
      }

      const candidateText = (accumulatedTranscriptRef.current + ' ' + currentInterim).trim();
      const isConversationActive = Date.now() < conversationActiveUntilRef.current;

      if (isConversationActive) {
        setInterimTranscript(currentInterim || finalChunk);
      }

      // Wake word regex
      const wakeRegex = /(?:(?:hey|ok|okay|hi|hello|yo)\s+)?(?:hex[\s_-]?(?:or|er|ar|ur|o|sir|are)?|heck[\s_-]?(?:sir|er|or|le)?|hack[\s_-]?(?:sir|er|saw)?|exor|exer|jarvis|javis|travis|charvis|hector|vector|axel)\b/i;
      const wakeMatch = candidateText.match(wakeRegex);

      if (wakeMatch) {
        playWakeChime();
        triggerUserSpeaking(false);
        conversationActiveUntilRef.current = Date.now() + 25000;
        setConversationMode(true);

        const command = candidateText.substring(wakeMatch.index + wakeMatch[0].length).replace(/^[,.\s]+/, '').trim();
        accumulatedTranscriptRef.current = '';
        setInterimTranscript('');

        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);

        if (command.length > 2) {
          silenceTimerRef.current = setTimeout(() => {
            sendMessage(command);
          }, 300);
        } else {
          const wakeReply = "Online, Sir.";
          setMessages(prev => [
            ...prev,
            { role: 'user', content: candidateText || "Hey Hexor" },
            { role: 'assistant', content: wakeReply }
          ]);
          speakText(wakeReply);
        }
        return;
      }

      // Active hands-free conversation mode
      if (isConversationActive) {
        triggerUserSpeaking(true);
        conversationActiveUntilRef.current = Date.now() + 25000;
        setConversationMode(true);

        if (/(?:stand\s*down|stop\s*listening|dismissed|hexor\s*stand\s*down|jarvis\s*stand\s*down|shut\s*up|stop\s*talking|exit\s*conversation)/i.test(candidateText)) {
          triggerUserSpeaking(false);
          conversationActiveUntilRef.current = 0;
          setConversationMode(false);
          setConvoSecondsLeft(0);
          accumulatedTranscriptRef.current = '';
          setInterimTranscript('');
          fetch('/api/voice/standby', { method: 'POST' }).catch(() => {});
          handleAssistantResponse({
            user_prompt: candidateText || "Stand down",
            response_text: "Standing by, Sir. Just call my name whenever you require assistance.",
            ui_action: "standby",
            latency_seconds: 0.1
          });
          return;
        }

        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = setTimeout(() => {
          triggerUserSpeaking(false);
          if (isSpeakingRef.current) return;
          const fullQuery = (accumulatedTranscriptRef.current + ' ' + currentInterim).trim();
          if (fullQuery.length > 1) {
            conversationActiveUntilRef.current = Date.now() + 25000;
            setConversationMode(true);
            sendMessage(fullQuery);
            accumulatedTranscriptRef.current = '';
            setInterimTranscript('');
          }
        }, 1200);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (e) {}
  };

  useEffect(() => {
    startWebSpeech();
    return () => {
      stopWebSpeech();
    };
  }, []);

  const toggleListening = async () => {
    const nextState = !isListening;
    setIsListening(nextState);
    isListeningRef.current = nextState;
    if (!nextState) {
      stopWebSpeech();
      try {
        await fetch('/api/voice/wake_listener', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: false })
        });
      } catch (e) {}
    } else {
      startWebSpeech();
      try {
        await fetch('/api/voice/wake_listener', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: true })
        });
      } catch (e) {}
    }
  };

  const fetchWeather = async () => {
    try {
      const res = await fetch('/api/weather');
      const data = await res.json();
      if (data.weather && data.weather.location) {
        setWeatherData(data.weather);
      } else if (data.location && data.location.city && data.location.city !== "Unknown") {
        setWeatherData(prev => ({
          ...prev,
          location: data.location.city
        }));
      }
    } catch (e) {}
  };

  const fetchTelemetry = async () => {
    try {
      const res = await fetch('/api/telemetry');
      const data = await res.json();
      if (data.data) setTelemetry(data.data);
    } catch (e) {}
  };

  const fetchBambu = async () => {
    try {
      const res = await fetch('/api/bambu/status');
      const data = await res.json();
      if (data.data) setBambuData(data.data);
      if (data.pending_approval !== undefined) setPendingApproval(data.pending_approval);
    } catch (e) {}
  };

  const fetchSkills = async () => {
    try {
      const res = await fetch('/api/skills');
      const data = await res.json();
      if (data.skills) setSkills(data.skills);
    } catch (e) {}
  };

  const fetchSpotify = async () => {
    try {
      const res = await fetch('/api/spotify/status');
      const data = await res.json();
      if (data.data) setSpotifyData(data.data);
    } catch (e) {}
  };

  const playVoiceAudio = async (audioBase64, mimeType = "audio/mp3") => {
    if (!voiceEnabled || !audioBase64) return;
    try {
      const audio = audioRef.current;
      if (!audio) return;
      if (selectedSpeakerId && audio.setSinkId) {
        await audio.setSinkId(selectedSpeakerId).catch(() => {});
      }

      try {
        audio.pause();
        audio.currentTime = 0;
      } catch (e) {}

      setIsSpeaking(true);
      isSpeakingRef.current = true;
      setIsHexorSpeaking(true);

      // Generous failsafe watchdog (2 minutes) — relying primarily on audio 'ended' event
      if (speechTimeoutRef.current) clearTimeout(speechTimeoutRef.current);
      speechTimeoutRef.current = setTimeout(() => {
        resetSpeakingState();
      }, 120000);

      audio.src = `data:${mimeType};base64,${audioBase64}`;
      await audio.play().catch((err) => {
        console.warn("Audio play rejected:", err);
        resetSpeakingState();
      });
    } catch (e) {
      resetSpeakingState();
    }
  };

  const speakText = async (text) => {
    if (!voiceEnabled || !text) return;
    try {
      const res = await fetch('/api/voice/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data && data.audio_base64) {
        await playVoiceAudio(data.audio_base64, data.mime_type || "audio/mp3");
        return;
      }
    } catch (e) {}

    // Fallback to Web Speech API SpeechSynthesis
    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
        window.speechSynthesis.resume();
        setIsSpeaking(true);
        isSpeakingRef.current = true;
        setIsHexorSpeaking(true);

        const clean = text.replace(/[*`#_]/g, '').trim();
        const utter = new SpeechSynthesisUtterance(clean);
        utter.rate = 1.05;
        window.__hexorCurrentUtterance = utter;

        const wordCount = clean.split(/\s+/).length;
        const expectedDurationMs = Math.min(180000, Math.max(15000, wordCount * 500));

        if (speechTimeoutRef.current) clearTimeout(speechTimeoutRef.current);
        speechTimeoutRef.current = setTimeout(() => {
          resetSpeakingState();
          window.__hexorCurrentUtterance = null;
        }, expectedDurationMs);

        if (window.__speechKeepAliveInterval) clearInterval(window.__speechKeepAliveInterval);
        window.__speechKeepAliveInterval = setInterval(() => {
          if (window.speechSynthesis && window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
            window.speechSynthesis.resume();
          } else {
            clearInterval(window.__speechKeepAliveInterval);
          }
        }, 10000);

        utter.onend = () => {
          if (window.__speechKeepAliveInterval) clearInterval(window.__speechKeepAliveInterval);
          resetSpeakingState();
          window.__hexorCurrentUtterance = null;
        };
        utter.onerror = () => {
          if (window.__speechKeepAliveInterval) clearInterval(window.__speechKeepAliveInterval);
          resetSpeakingState();
          window.__hexorCurrentUtterance = null;
        };
        window.speechSynthesis.speak(utter);
      } catch (e) {
        resetSpeakingState();
      }
    }
  };

  const handleAssistantResponse = (payload) => {
    setIsProcessing(false);
    if (!payload) return;

    // Handle explicit standby or shutdown from assistant
    if (payload.ui_action === "system_shutdown") {
      stopWebSpeech();
      setIsSystemShuttingDown(true);
      setTimeout(() => {
        try { window.close(); } catch (e) {}
        window.location.href = "about:blank";
      }, 1500);
    } else if (payload.ui_action === "standby") {
      conversationActiveUntilRef.current = 0;
      setConversationMode(false);
      setConvoSecondsLeft(0);
      setIsUserSpeaking(false);
      fetch('/api/voice/standby', { method: 'POST' }).catch(() => {});
    } else if (payload.ui_action === "alarm_stopped") {
      setRingingAlarm(null);
    } else if (isListeningRef.current && (conversationMode || conversationActiveUntilRef.current > Date.now())) {
      // Refresh hands-free conversation window so user can speak follow-ups naturally
      conversationActiveUntilRef.current = Date.now() + 25000;
      setConversationMode(true);
    }

    const prompt = (payload.user_prompt || '').trim();
    const newAssistantMsg = {
      role: 'assistant',
      content: payload.response_text,
      tool_name: payload.tool_name,
      latency: payload.latency_seconds,
      web_results: payload.tool_result?.data?.results
    };

    setMessages(prev => {
      if (prompt) {
        const lastMsg = prev[prev.length - 1];
        if (!lastMsg || lastMsg.role !== 'user' || lastMsg.content.toLowerCase().trim() !== prompt.toLowerCase()) {
          return [
            ...prev,
            { role: 'user', content: prompt },
            newAssistantMsg
          ];
        }
      }
      return [...prev, newAssistantMsg];
    });

    if (payload.ui_action === "show_3d_approval" || payload.requires_approval) {
      setPendingApproval(payload.tool_result?.data);
    }

    // Always deliver speech output when voice is enabled
    if (voiceEnabled && payload.response_text) {
      if (payload.audio?.audio_base64) {
        playVoiceAudio(payload.audio.audio_base64, payload.audio.mime_type);
      } else {
        speakText(payload.response_text);
      }
    }

    fetchSpotify();
    fetchSkills();
  };

  const sendMessage = async (text) => {
    if (!text.trim() || isProcessing) return;

    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setIsProcessing(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, voice_enabled: voiceEnabled })
      });
      const data = await res.json();
      handleAssistantResponse(data);
    } catch (err) {
      setIsProcessing(false);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Connection error: Backend unreachable (${err.message}).` 
      }]);
    }
  };

  const handleApprovePrint = async () => {
    try {
      const res = await fetch('/api/approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: true })
      });
      const data = await res.json();
      setPendingApproval(null);
      handleAssistantResponse(data);
    } catch (e) {}
  };

  const handleRejectPrint = async () => {
    try {
      const res = await fetch('/api/approval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: false })
      });
      const data = await res.json();
      setPendingApproval(null);
      handleAssistantResponse(data);
    } catch (e) {}
  };

  const handleBambuAction = async (action, params = {}) => {
    if (action === 'search_models') {
      sendMessage(`Find 3D model ${params.query || ''} to 3D print`);
      return;
    }
    try {
      const res = await fetch('/api/bambu/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          speed_level: params.speed_level || 'standard',
          query: params.query || ''
        })
      });
      const data = await res.json();
      if (data && data.data) {
        setBambuData(prev => ({ ...prev, ...data.data }));
      }
      if (data && data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message,
          tool_name: 'bambu_hub'
        }]);
      }
    } catch (e) {
      console.error("Bambu action failed:", e);
    }
  };

  const handleSpotifyAction = (action, params = {}) => {
    if (action === "play_song") {
      sendMessage(`Play ${params.query} on Spotify`);
    } else if (action === "play_playlist") {
      sendMessage(`Play ${params.query} playlist on Spotify`);
    } else if (action === "recommend_music") {
      sendMessage(`Play ${params.mood} playlist on Spotify`);
    } else {
      sendMessage(`Spotify ${action}`);
    }
  };

  const handleLearnSkill = async (skillReq) => {
    sendMessage(`Learn how to ${skillReq}`);
  };

  const handleSaveSettings = async (settingsPayload) => {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsPayload)
      });
      fetchSkills();
    } catch (e) {}
  };

  const handleShutdownConfirm = async () => {
    setIsSystemShuttingDown(true);
    setIsShutdownConfirmOpen(false);
    stopWebSpeech();
    try {
      await fetch('/api/system/shutdown', { method: 'POST' });
    } catch (e) {}
    setTimeout(() => {
      try {
        window.close();
      } catch (e) {}
      window.location.href = "about:blank";
    }, 400);
  };

  return (
    <div className="relative w-screen h-screen bg-[#030712] text-cyan-400 flex flex-col overflow-hidden cyber-grid">
      <div className="absolute inset-0 scanlines z-40 pointer-events-none" />

      {/* TOP STATUS BAR */}
      <header className="relative z-30 h-14 border-b border-cyan-500/30 bg-black/80 backdrop-blur-md px-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-400">
            <span className="font-orbitron font-black text-cyan-300 text-sm">HX</span>
          </div>
          <div>
            <div className="font-orbitron font-extrabold text-sm tracking-widest text-cyan-100 flex items-center space-x-2">
              <span>HEXOR</span>
              <span className="text-[10px] px-1.5 py-0.2 bg-cyan-500/20 border border-cyan-400/40 rounded text-cyan-300">
                120B NEURAL
              </span>
            </div>
            <div className="font-mono-tech text-[10px] text-cyan-500 tracking-wider">
              MIC: {activeMicLabel.substring(0, 22)}
            </div>
          </div>
        </div>

        {/* Live Weather & Location Pill + Indicators */}
        <div className="hidden md:flex items-center space-x-4 text-xs font-mono-tech">
          {/* Live Weather & Location */}
          <button
            onClick={() => sendMessage("What is the weather right now?")}
            className="flex items-center space-x-1.5 px-3 py-1 bg-cyan-950/50 hover:bg-cyan-900/60 border border-cyan-500/30 hover:border-cyan-400/60 rounded-full transition-all text-cyan-200"
            title="Click for full weather forecast"
          >
            <MapPin className="w-3 h-3 text-cyan-400" />
            <span className="font-semibold">{weatherData.location.split(',')[0]}</span>
            <span className="text-cyan-500">|</span>
            <CloudSun className="w-3.5 h-3.5 text-amber-400" />
            <span>{weatherData.temperature_c}°C {weatherData.condition}</span>
          </button>

          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-emerald-300">BAMBU A1</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <span className="text-purple-300">DELL S234</span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="font-orbitron text-xs font-bold text-cyan-200 tracking-wider bg-cyan-950/40 px-3 py-1 rounded border border-cyan-500/30">
            {systemTime}
          </div>

          <button
            onClick={() => setVoiceEnabled(!voiceEnabled)}
            className={`p-2 rounded-lg border transition-all ${
              voiceEnabled 
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-[0_0_10px_rgba(0,240,255,0.3)]' 
                : 'bg-black/40 border-cyan-500/20 text-cyan-600'
            }`}
            title={voiceEnabled ? "Mute Voice" : "Enable Voice"}
          >
            {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2 rounded-lg bg-black/40 border border-cyan-500/30 text-cyan-400 hover:text-cyan-100 hover:border-cyan-400 transition-all"
            title="Configure System, Audio Devices & Free Keys"
          >
            <Settings className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsShutdownConfirmOpen(true)}
            className="p-2 rounded-lg bg-red-950/50 border border-red-500/40 text-red-400 hover:bg-red-900/60 hover:text-red-200 hover:border-red-400 transition-all shadow-[0_0_10px_rgba(239,68,68,0.2)]"
            title="Shutdown Hexor System & Exit"
          >
            <Power className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ALARM RINGING HUD BANNER */}
      {ringingAlarm && (
        <div className="z-50 bg-gradient-to-r from-amber-600/90 via-red-600/90 to-amber-600/90 border-b border-amber-300 text-white px-6 py-2.5 flex items-center justify-between shadow-[0_0_25px_rgba(245,158,11,0.6)] animate-pulse">
          <div className="flex items-center space-x-3">
            <span className="text-xl">⏰</span>
            <div>
              <div className="font-orbitron font-bold text-sm tracking-wider uppercase text-amber-100">
                ALARM RINGING: {ringingAlarm.time_str || "WAKE UP"}
              </div>
              <div className="text-xs text-amber-200 font-mono-tech">
                Active Spotify Audio: {ringingAlarm.music || "Morning Chill"}
              </div>
            </div>
          </div>
          <button
            onClick={async () => {
              setRingingAlarm(null);
              try {
                await fetch('/api/alarms/stop', { method: 'POST' });
              } catch (e) {}
            }}
            className="px-4 py-1.5 bg-black/60 hover:bg-black/90 border border-white/50 rounded-lg text-xs font-orbitron font-bold tracking-wider uppercase text-amber-200 hover:text-white transition-all shadow-md"
          >
            DISMISS ALARM
          </button>
        </div>
      )}

      {/* JARVIS PROTOCOLS & ACTION BAR */}
      <JarvisProtocolBar 
        onExecuteCommand={sendMessage}
        onOpenProductivity={() => setIsProductivityOpen(true)}
      />

      {/* Shutdown confirmation dialog */}
      {isShutdownConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4">
          <div className="max-w-md w-full bg-gray-950 border border-red-500/60 rounded-2xl p-6 shadow-[0_0_30px_rgba(239,68,68,0.3)] text-center">
            <div className="w-12 h-12 rounded-full bg-red-950/70 border border-red-500 flex items-center justify-center mx-auto mb-3">
              <AlertTriangle className="w-6 h-6 text-red-400 animate-pulse" />
            </div>
            <h3 className="font-orbitron font-bold text-sm tracking-widest text-red-200 uppercase mb-2">
              TERMINATE HEXOR OS?
            </h3>
            <p className="font-mono-tech text-xs text-red-300/80 mb-6">
              This will safely terminate the backend server process, disconnect all hardware links, and close this interface.
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => setIsShutdownConfirmOpen(false)}
                className="flex-1 py-2 rounded-xl bg-black/60 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-950/50 font-orbitron text-xs transition-all"
              >
                CANCEL
              </button>
              <button
                onClick={handleShutdownConfirm}
                className="flex-1 py-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white font-orbitron font-bold text-xs transition-all shadow-[0_0_15px_rgba(239,68,68,0.5)]"
              >
                SHUTDOWN NOW
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Offline Standby Screen */}
      {isSystemShuttingDown && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black text-center p-6 select-none">
          <div className="w-16 h-16 rounded-full border border-cyan-500/30 flex items-center justify-center mb-4">
            <Power className="w-8 h-8 text-cyan-600" />
          </div>
          <h2 className="font-orbitron text-base font-bold text-cyan-400 tracking-widest uppercase mb-1">
            HEXOR OS OFFLINE
          </h2>
          <p className="font-mono-tech text-xs text-cyan-600 mb-4">
            System core and terminal safely deactivated.
          </p>
          <button
            onClick={() => {
              try { window.close(); } catch (e) {}
              window.location.href = "about:blank";
            }}
            className="px-4 py-2 rounded-lg border border-cyan-500/40 bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-200 font-orbitron text-xs tracking-wider transition-all"
          >
            CLOSE TAB
          </button>
        </div>
      )}

      <main className="relative z-10 flex-1 grid grid-cols-12 gap-3 p-3 overflow-hidden">
        <section className="col-span-12 lg:col-span-3 flex flex-col space-y-3 h-full overflow-hidden">
          <div className="flex-1 min-h-0">
            <Bambu3DPanel
              bambuData={bambuData}
              pendingApproval={pendingApproval}
              onApprove={handleApprovePrint}
              onReject={handleRejectPrint}
              onAction={handleBambuAction}
            />
          </div>
          <div className="h-[280px]">
            <SpotifyPlayerPanel
              spotifyData={spotifyData}
              onAction={handleSpotifyAction}
            />
          </div>
        </section>

        <section className="col-span-12 lg:col-span-5 flex flex-col space-y-3 h-full overflow-hidden">
          <div className="flex-1 min-h-0 bg-black/50 border border-cyan-500/30 rounded-xl overflow-hidden glow-cyan">
            <HexCoreReactor
              isSpeaking={isSpeaking}
              isListening={isListening}
              statusText={bambuData.state === "PRINTING" ? "BAMBU A1 PRINTING" : "HEXOR ONLINE"}
              telemetry={telemetry}
            />
          </div>
          <div className="h-[140px]">
            <SystemDiagnostics telemetry={telemetry} />
          </div>
        </section>

        <section className="col-span-12 lg:col-span-4 flex flex-col space-y-3 h-full overflow-hidden">
          <div className="flex-1 min-h-0">
            <TerminalCommandDeck
              messages={messages}
              onSendMessage={sendMessage}
              isListening={isListening}
              onToggleListening={toggleListening}
              interimTranscript={interimTranscript}
              voiceEnabled={voiceEnabled}
              onToggleVoice={() => setVoiceEnabled(!voiceEnabled)}
              isProcessing={isProcessing}
              isHexorSpeaking={isHexorSpeaking}
              isUserSpeaking={isUserSpeaking}
              conversationMode={conversationMode}
              convoSecondsLeft={convoSecondsLeft}
            />
          </div>
          <div className="h-[150px]">
            <SkillEvolutionVault
              skills={skills}
              onLearnSkill={handleLearnSkill}
            />
          </div>
        </section>
      </main>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveSettings}
        selectedMicId={selectedMicId}
        setSelectedMicId={setSelectedMicId}
        selectedSpeakerId={selectedSpeakerId}
        setSelectedSpeakerId={setSelectedSpeakerId}
      />

      <ProductivityModal
        isOpen={isProductivityOpen}
        onClose={() => setIsProductivityOpen(false)}
        onAction={sendMessage}
      />
    </div>
  );
}
