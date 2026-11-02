import React, { useState, useEffect, useRef } from 'react';
import {
  Mic, MicOff, Volume2, VolumeX, Send, X, Sparkles, Utensils,
  CalendarCheck, CheckCircle2, AlertCircle, Loader2, Apple
} from 'lucide-react';
import { mealService } from '../../services/api';

export default function NutritionVoiceAgentModal({ isOpen, onClose, onPlanUpdated }) {
  const [messages, setMessages] = useState([
    {
      role: 'model',
      content: "Hello! I'm your MoveWell Nutrition & Metabolic Health Specialist. You can ask me to prepare your full-day meal schedule, tell me what you just ate to auto-log it, or ask about recipes and macronutrients. How can I help fuel your day?",
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [voiceOutput, setVoiceOutput] = useState(true);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [lastActionBadge, setLastActionBadge] = useState(null);

  const recognitionRef = useRef(null);
  const messagesEndRef = useRef(null);

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

    recognition.onerror = () => {
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

  const speakText = (text) => {
    if (!voiceOutput || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
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
      alert('Speech recognition is not supported in this browser. You can type below!');
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
      const conversationHistory = updatedHistory
        .slice(-8)
        .map(m => ({ role: m.role, content: m.content }));

      const res = await mealService.chat({
        message: content,
        conversationHistory
      });

      const replyText = res.data?.reply || "I didn't quite catch that. Could you repeat?";
      const logged = res.data?.loggedMeal;
      const scheduled = res.data?.scheduledPlan;
      const water = res.data?.loggedWater;

      let badge = null;
      if (logged) {
        badge = {
          type: 'MEAL_LOGGED',
          text: `Logged ${logged.meal_type}: ${logged.food_description}`
        };
      } else if (scheduled) {
        badge = {
          type: 'PLAN_SCHEDULED',
          text: `Prepared & Scheduled ${scheduled.meals.length} Meals into Daily Health Plan`
        };
      } else if (water) {
        badge = {
          type: 'WATER_LOGGED',
          text: `Updated Daily Water Target to ${water}L`
        };
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'model',
          content: replyText,
          timestamp: new Date(),
          loggedMeal: logged,
          scheduledPlan: scheduled,
          loggedWater: water
        }
      ]);

      if (badge) {
        setLastActionBadge(badge);
        if (onPlanUpdated) {
          onPlanUpdated({ loggedMeal: logged, scheduledPlan: scheduled, loggedWater: water });
        }
      }

      speakText(replyText);
    } catch (err) {
      console.error('Nutrition chat error:', err);
      const errorMsg = err.response?.data?.error || err.message || 'Error communicating with nutrition coach.';
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
    "Prepare my full day meal schedule for today",
    "I had oatmeal with blueberries and almond milk for breakfast",
    "I just ate a grilled chicken avocado bowl for lunch",
    "Suggest a high-protein anti-inflammatory dinner recipe"
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#0b140b] border border-emerald-500/40 rounded-2xl w-full max-w-2xl h-[650px] flex flex-col shadow-2xl overflow-hidden ring-1 ring-emerald-500/20">
        
        {/* Header */}
        <div className="p-4 border-b border-emerald-900/60 bg-[#0f1b0f] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-amber-600 flex items-center justify-center shadow-lg shadow-emerald-900/30">
              <Utensils className="text-white" size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">Nutrition &amp; Meal Planner Coach</h3>
                <span className="text-[10px] bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-mono px-2 py-0.5 rounded-full">
                  GPT-4o Mini
                </span>
              </div>
              <p className="text-xs text-emerald-400/80">Schedules full-day meals • Auto-logs food • Voice enabled</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                const nextState = !voiceOutput;
                setVoiceOutput(nextState);
                if (!nextState) window.speechSynthesis?.cancel();
              }}
              title={voiceOutput ? "Voice output enabled (click to mute)" : "Voice output muted"}
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

        {/* Live Action Banner */}
        {lastActionBadge && (
          <div className="px-4 py-2 bg-emerald-950/70 border-b border-emerald-700/40 flex items-center justify-between text-xs text-emerald-300 animate-in slide-in-from-top-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={14} className="text-emerald-400" />
              <span>
                <strong>{lastActionBadge.text}</strong>
              </span>
            </div>
            <span className="text-[10px] text-emerald-400 font-mono">SQLite Synced</span>
          </div>
        )}

        {/* Messages Stream */}
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

                {/* If a meal was logged */}
                {msg.loggedMeal && (
                  <div className="mt-3 p-2.5 bg-emerald-900/40 border border-emerald-500/40 rounded-xl text-xs text-emerald-200 flex items-start gap-2">
                    <CheckCircle2 size={15} className="text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-emerald-300">Saved to SQLite Meal Logs</p>
                      <p className="text-[11px] text-emerald-400/90 mt-0.5">
                        {msg.loggedMeal.meal_type}: {msg.loggedMeal.food_description} ({msg.loggedMeal.portion})
                      </p>
                    </div>
                  </div>
                )}

                {/* If a full meal schedule was created */}
                {msg.scheduledPlan && (
                  <div className="mt-3 p-3 bg-gradient-to-r from-emerald-950/90 to-teal-950/90 border border-emerald-500/50 rounded-xl text-xs space-y-2">
                    <div className="flex items-center gap-1.5 text-emerald-300 font-semibold">
                      <CalendarCheck size={14} className="text-emerald-400" />
                      <span>{msg.scheduledPlan.summary || 'Scheduled Meal Plan'}</span>
                    </div>
                    <div className="space-y-1.5 pt-1">
                      {msg.scheduledPlan.meals.map((m, i) => (
                        <div key={i} className="p-2 bg-[#0d170d] rounded-lg border border-emerald-800/40 flex items-start justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-mono text-emerald-400 uppercase font-bold">{m.time_block} • {m.meal_type}</span>
                            <p className="text-white font-medium text-xs mt-0.5">{m.title}</p>
                            {m.instructions && <p className="text-emerald-100/70 text-[11px] mt-0.5">{m.instructions}</p>}
                          </div>
                          {m.dosage && <span className="text-[10px] font-mono text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded shrink-0">{m.dosage}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <span className="text-[10px] text-emerald-100/40 px-1 mt-1">
                {msg.role === 'user' ? 'You' : 'Nutrition Coach'} • {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}

          {isSending && (
            <div className="flex items-center gap-2 text-emerald-400 text-xs py-2">
              <Loader2 size={14} className="animate-spin" />
              <span>Nutrition specialist is analyzing your dietary preferences...</span>
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
                <span>Listening... speak now. Mention what you ate or ask to schedule today's meals.</span>
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

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={isListening ? "Listening to your voice..." : "Type or speak (e.g. 'Plan my meals for today' or 'I ate oatmeal for breakfast')..."}
              disabled={isSending}
              className="flex-1 bg-[#070d07] border border-emerald-900 rounded-xl px-4 py-2.5 text-sm text-white placeholder-emerald-700 focus:outline-none focus:border-emerald-500 transition-colors"
            />

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
