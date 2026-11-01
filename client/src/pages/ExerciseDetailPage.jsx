import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Dumbbell, PlayCircle, CheckCircle, ArrowLeft, AlertCircle,
  Clock, ShieldAlert, Sparkles, AlertTriangle, Video, Info
} from 'lucide-react';
import { exerciseService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

export default function ExerciseDetailPage() {
  const { id } = useParams();
  const [exercise, setExercise] = useState(null);
  const [loading, setLoading] = useState(true);
  const [completed, setCompleted] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const fetchExercise = async () => {
      try {
        setLoading(true);
        const res = await exerciseService.getById(id);
        setExercise(res.data);
      } catch (err) {
        console.error('Error fetching exercise:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchExercise();
  }, [id]);

  const handleMarkComplete = async () => {
    setCompleting(true);
    try {
      await exerciseService.complete(id);
      setCompleted(true);
    } catch (err) {
      console.error('Error completing exercise:', err);
    } finally {
      setCompleting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner message="Loading Exercise Guidance..." />
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-white text-base">Exercise not found.</p>
        <Link to="/specialists/physiotherapy" className="text-emerald-400 text-xs">
          ← Return to Physiotherapy
        </Link>
      </div>
    );
  }

  const instructions = Array.isArray(exercise.instructions) ? exercise.instructions : [];
  const mistakes = Array.isArray(exercise.common_mistakes) ? exercise.common_mistakes : [];
  const precautions = Array.isArray(exercise.safety_precautions) ? exercise.safety_precautions : [];

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Back button & category badge */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link
          to="/specialists/physiotherapy"
          className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          <ArrowLeft size={14} />
          <span>Back to Physiotherapy Plan</span>
        </Link>

        <div className="flex items-center gap-2">
          <span className="text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-mono font-bold">
            {exercise.category}
          </span>
          <span className="text-xs bg-black/60 text-emerald-500 border border-emerald-900 px-2.5 py-1 rounded-full font-mono">
            {exercise.difficulty}
          </span>
        </div>
      </div>

      {/* Header Info */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold text-white tracking-tight">{exercise.name}</h1>
        <p className="text-sm text-emerald-100/70">{exercise.purpose}</p>
      </div>

      {/* Video & Visual Stage */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Media Demonstration */}
        <div className="lg:col-span-2 bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-5 space-y-4 shadow-xl">
          <div className="relative aspect-video bg-[#0a0f0a] rounded-xl overflow-hidden border border-emerald-900/60 flex items-center justify-center">
            {exercise.video_url ? (
              <video
                src={exercise.video_url}
                controls
                poster={exercise.image_url}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full relative flex flex-col items-center justify-center p-6 text-center">
                {exercise.image_url && (
                  <img
                    src={exercise.image_url}
                    alt={exercise.name}
                    className="max-h-72 max-w-full object-contain mx-auto"
                  />
                )}
                <div className="absolute bottom-3 left-3 right-3 bg-black/85 backdrop-blur-sm border border-emerald-900/60 rounded-lg p-2.5 flex items-center gap-2 text-xs text-emerald-300">
                  <Info size={15} className="text-emerald-400 flex-shrink-0" />
                  <span>
                    <strong>Clinical Form Cue:</strong> Maintain deliberate cadence throughout both concentric elevation and eccentric lowering phases. Focus on muscle activation and joint alignment.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Specifications Pill Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono pt-2">
            <div className="bg-[#111a11] p-3 rounded-lg border border-emerald-900/30">
              <span className="text-emerald-700 block text-[10px]">Sets &amp; Reps</span>
              <span className="text-white font-bold">{exercise.sets} sets × {exercise.reps}</span>
            </div>
            <div className="bg-[#111a11] p-3 rounded-lg border border-emerald-900/30">
              <span className="text-emerald-700 block text-[10px]">Hold Duration</span>
              <span className="text-white font-bold">{exercise.hold_duration || 'Dynamic tempo'}</span>
            </div>
            <div className="bg-[#111a11] p-3 rounded-lg border border-emerald-900/30">
              <span className="text-emerald-700 block text-[10px]">Rest Interval</span>
              <span className="text-white font-bold">{exercise.rest_period || '45-60s'}</span>
            </div>
            <div className="bg-[#111a11] p-3 rounded-lg border border-emerald-900/30">
              <span className="text-emerald-700 block text-[10px]">Equipment</span>
              <span className="text-emerald-400 font-bold">{exercise.equipment}</span>
            </div>
          </div>
        </div>

        {/* Right Col: Action & Targets */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-xl space-y-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div>
              <span className="text-xs text-emerald-600 uppercase font-semibold">Primary Target</span>
              <h3 className="text-lg font-bold text-emerald-300">{exercise.target_area}</h3>
            </div>

            <div className="space-y-2 pt-2 border-t border-emerald-900/30">
              <span className="text-xs text-emerald-600 uppercase font-semibold">Starting Position</span>
              <p className="text-xs text-emerald-100/80 leading-relaxed bg-[#111a11] p-3 rounded-lg border border-emerald-900/40">
                {exercise.starting_position}
              </p>
            </div>

            <div className="space-y-2 pt-2 border-t border-emerald-900/30">
              <span className="text-xs text-emerald-600 uppercase font-semibold">Breathing Rhythm</span>
              <p className="text-xs text-emerald-300/90 leading-relaxed">
                {exercise.breathing || 'Exhale during concentric exertion; steady diaphragmatic breathing throughout.'}
              </p>
            </div>

            {exercise.easier_variation && (
              <div className="space-y-1.5 pt-2 border-t border-emerald-900/30">
                <span className="text-xs text-emerald-600 uppercase font-semibold">Easier Variation</span>
                <p className="text-xs text-emerald-100/70">
                  {exercise.easier_variation}
                </p>
              </div>
            )}
          </div>

          <div className="space-y-3 pt-4 border-t border-emerald-900/30">
            <button
              onClick={handleMarkComplete}
              disabled={completed || completing}
              className={`w-full py-3.5 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 shadow-lg ${
                completed
                  ? 'bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 cursor-default'
                  : 'bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20'
              }`}
            >
              <CheckCircle size={17} />
              <span>{completed ? 'Exercise Completed Today' : completing ? 'Recording...' : 'Mark Exercise Complete'}</span>
            </button>
            <p className="text-[10px] text-center text-emerald-600 font-mono">
              Persists to SQLite activity_completions &amp; updates adherence
            </p>
          </div>
        </div>
      </div>

      {/* Step-by-Step Instructions Sequence */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-xl space-y-4">
        <h2 className="text-lg font-bold text-white">Step-by-Step Execution Sequence</h2>

        <div className="space-y-3">
          {instructions.map((step, idx) => (
            <div
              key={idx}
              className="flex items-start gap-4 p-4 rounded-xl bg-[#111a11] border border-emerald-900/40 hover:border-emerald-500/30 transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-mono font-bold text-sm flex-shrink-0">
                0{idx + 1}
              </div>
              <p className="text-sm text-emerald-100/80 leading-relaxed pt-1">
                {step}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Common Mistakes & Safety Precautions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Common Mistakes */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-xl space-y-3">
          <div className="flex items-center gap-2 text-amber-400 font-bold text-sm">
            <AlertTriangle size={16} />
            <span>Common Form Errors to Avoid</span>
          </div>
          <ul className="space-y-2 text-xs text-emerald-100/70">
            {mistakes.map((m, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">•</span>
                <span>{m}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Safety Precautions */}
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-xl space-y-3">
          <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
            <ShieldAlert size={16} />
            <span>Clinical Safety Precautions</span>
          </div>
          <ul className="space-y-2 text-xs text-emerald-100/70">
            {precautions.map((p, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-emerald-400 mt-0.5">✓</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

