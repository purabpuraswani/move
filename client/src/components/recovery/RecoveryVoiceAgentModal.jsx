import React, { useState, useEffect, useRef } from 'react';
import {
  Mic, MicOff, Volume2, VolumeX, Send, X, Sparkles, Moon,
  Wind, CheckCircle2, AlertCircle, Loader2
} from 'lucide-react';
import { recoveryService } from '../../services/api';

export default function RecoveryVoiceAgentModal({ isOpen, onClose, onRecordLogged }) {
  const [messages, setMessages] = useState([
    {
      role: 'model',
      content: "Hello! I'm your MoveWell Recovery & Sleep Specialist. You can talk to me naturally about how you slept, how stressed or tired you feel, or ask for guidance. I can also log your sleep automatically as we chat!",
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [voiceOutput, setVoiceOutput] = useState(true);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [recentLoggedRecord, setRecentLoggedRecord] = useState(null);

  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isSending]);

  // Setup Web Speech API for voice input
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript.trim()) {
        sendMessage(transcript);
      }
      setIsListening(false);
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition event:', event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch { /* ignore */ }
      }
      window.speechSynthesis?.cancel();
    };
  }, []);

  // Text to speech helper
  const speakText = (text) => {
    if (!voiceOutput || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      // Remove markdown asterisks or code formatting for cleaner speech
      const cleanText = text.replace(/[*_#`]/g, '');
      const utterance = new SpeechSynthesisUtterance(cleanText);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis error:', e);
    }
  };

  const toggleListening = () => {
    if (!speechSupported) {
      alert('Speech recognition is not supported in this browser. You can type your messages below!');
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      window.speechSynthesis?.cancel();
      try {
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (err) {
        console.warn('Failed to start speech recognition:', err);
        setIsListening(false);
      }
    }
  };

  const sendMessage = async (textToSend) => {
    const content = (textToSend || inputText).trim();
    if (!content || isSending) return;

    setInputText('');
    const userMessage = { role: 'user', content, timestamp: new Date() };
    const updatedHistory = [...messages, userMessage];
    setMessages(updatedHistory);
    setIsSending(true);

    try {
      // Map history for Gemini API
      const conversationHistory = updatedHistory
        .slice(-8)
        .map(m => ({ role: m.role, content: m.content }));

      const res = await recoveryService.chat({
        message: content,
        conversationHistory
      });

      const replyText = res.data?.reply || "I didn't quite catch that. Could you repeat?";
      const logged = res.data?.loggedRecord;

      setMessages(prev => [
        ...prev,
        {
          role: 'model',
          content: replyText,
          timestamp: new Date(),
          loggedRecord: logged
        }
      ]);

      if (logged) {
        setRecentLoggedRecord(logged);
        if (onRecordLogged) {
          onRecordLogged(logged);
        }
      }

      // Voice output
      speakText(replyText);
    } catch (err) {
      console.error('Chat error:', err);
      const errorMsg = err.response?.data?.error || err.message || 'Error communicating with OpenRouter recovery agent.';
      setMessages(prev => [
        ...prev,
        {
          role: 'model',
          content: `⚠️ ${errorMsg}`,
          timestamp: new Date(),
          isError: true
        }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  if (!isOpen) return null;

  const quickPrompts = [
    "Good morning! I slept 7.5 hours, felt great, stress is low around 2.",
    "Only got 5 hours of sleep last night and feeling stressed about work.",
    "Can you guide me through a 4-4-6 breathing exercise to relax?",
    "Why is restorative sleep so critical for muscle recovery?"
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#0b140b] border border-emerald-500/40 rounded-2xl w-full max-w-2xl h-[650px] flex flex-col shadow-2xl overflow-hidden ring-1 ring-emerald-500/20">
        
        {/* Header */}
        <div className="p-4 border-b border-emerald-900/60 bg-[#0f1b0f] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-900/30">
              <Sparkles className="text-white" size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">Wellness &amp; Recovery Voice Coach</h3>
                <span className="text-[10px] bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-mono px-2 py-0.5 rounded-full">
                  GPT-4o Mini
                </span>
              </div>
              <p className="text-xs text-emerald-400/80">Talk freely • Ask questions • Auto-logs your sleep</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const nextState = !voiceOutput;
                setVoiceOutput(nextState);
                if (!nextState) window.speechSynthesis?.cancel();
              }}
              title={voiceOutput ? "Voice output enabled (click to mute)" : "Voice output muted (click to enable)"}
              className={`p-2 rounded-lg border transition-colors ${
                voiceOutput
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                  : 'border-zinc-800 bg-zinc-900/60 text-zinc-500 hover:text-zinc-400'
              }`}
            >
              {voiceOutput ? <Volume2 size={16} /> : <VolumeX size={16} />}
            </button>

            <button
              onClick={() => {
                window.speechSynthesis?.cancel();
                onClose();
              }}
              className="p-2 rounded-lg border border-emerald-900/40 text-zinc-400 hover:text-white hover:bg-emerald-900/30 transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Recent Auto-Log Banner */}
        {recentLoggedRecord && (
          <div className="px-4 py-2 bg-emerald-950/70 border-b border-emerald-700/40 flex items-center justify-between text-xs text-emerald-300 animate-in slide-in-from-top-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={14} className="text-emerald-400" />
              <span>
                <strong>Saved to Database:</strong> {recentLoggedRecord.sleep_duration}h • {recentLoggedRecord.sleep_quality} Quality • Stress {recentLoggedRecord.stress_level || 'N/A'}/10
              </span>
            </div>
            <span className="text-[10px] text-emerald-400 font-mono">SQLite Synced</span>
          </div>
        )}

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md ${
                  msg.role === 'user'
                    ? 'bg-emerald-600 text-white rounded-br-none'
                    : msg.isError
                    ? 'bg-rose-950/60 border border-rose-500/40 text-rose-200 rounded-bl-none'
                    : 'bg-[#132213] border border-emerald-900/60 text-emerald-50 rounded-bl-none'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>

                {/* If this turn auto-logged a record */}
                {msg.loggedRecord && (
                  <div className="mt-3 p-2.5 bg-emerald-900/40 border border-emerald-500/40 rounded-xl text-xs text-emerald-200 flex items-start gap-2">
                    <CheckCircle2 size={15} className="text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-emerald-300">SQLite Record Created Automatically</p>
                      <p className="text-[11px] text-emerald-400/90 mt-0.5">
                        Duration: {msg.loggedRecord.sleep_duration} hrs | Quality: {msg.loggedRecord.sleep_quality} | Stress: {msg.loggedRecord.stress_level}/10
                      </p>
                    </div>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-emerald-100/40 px-1 mt-1">
                {msg.role === 'user' ? 'You' : 'Recovery Coach'} • {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {isSending && (
            <div className="flex items-center gap-2 text-emerald-400 text-xs py-2">
              <Loader2 size={14} className="animate-spin" />
              <span>Recovery coach is thinking &amp; reviewing your profile...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Prompts Bar */}
        <div className="px-4 py-2 border-t border-emerald-950 bg-[#0d160d] overflow-x-auto flex items-center gap-2 scrollbar-none">
          <span className="text-[10px] uppercase tracking-wider text-emerald-500 font-bold shrink-0">Try Asking:</span>
          {quickPrompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => sendMessage(prompt)}
              disabled={isSending}
              className="text-xs text-emerald-200/90 bg-[#162716] hover:bg-emerald-900/50 border border-emerald-800/50 px-2.5 py-1 rounded-full whitespace-nowrap transition-colors disabled:opacity-50"
            >
              {prompt.length > 40 ? prompt.substring(0, 40) + '...' : prompt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-emerald-900/60 bg-[#0f1b0f]">
          {isListening && (
            <div className="mb-3 px-3 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center justify-between animate-pulse">
              <div className="flex items-center gap-2 text-xs text-emerald-300">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                <span>Listening... speak now. I'll automatically send when you finish speaking.</span>
              </div>
              <button
                onClick={toggleListening}
                className="text-xs text-emerald-400 hover:text-white font-semibold underline"
              >
                Stop
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="flex items-center gap-2"
          >
            {/* Mic Toggle Button */}
            <button
              type="button"
              onClick={toggleListening}
              title={isListening ? "Stop listening" : "Start speaking"}
              className={`p-3 rounded-xl border transition-all flex items-center justify-center ${
                isListening
                  ? 'bg-rose-500 border-rose-400 text-white shadow-lg shadow-rose-500/30 animate-pulse'
                  : 'bg-emerald-600/30 border-emerald-500/50 text-emerald-200 hover:bg-emerald-500 hover:text-white'
              }`}
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
            </button>

            {/* Text Input */}
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={isListening ? "Listening to your voice..." : "Type or speak to chat / log your sleep..."}
              disabled={isSending}
              className="flex-1 bg-[#070d07] border border-emerald-900 rounded-xl px-4 py-2.5 text-sm text-white placeholder-emerald-700 focus:outline-none focus:border-emerald-500 transition-colors"
            />

            {/* Send Button */}
            <button
              type="submit"
              disabled={!inputText.trim() || isSending}
              className="p-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-lg shadow-emerald-950"
            >
              <Send size={18} />
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}

