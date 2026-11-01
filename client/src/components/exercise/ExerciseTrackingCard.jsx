import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Play, Pause, Square, CheckCircle, AlertCircle, ChevronDown, ChevronUp,
  Camera, Dumbbell, ShieldCheck, Clock, Award, Activity, RefreshCw
} from 'lucide-react';
import { initMoveNet, startCameraStream, stopCameraStream, drawSkeleton } from '../../assessment/pose/poseEngine';
import { createExerciseTracker } from '../../assessment/exercises/exerciseTrackers';
import { exerciseService } from '../../services/api';

export default function ExerciseTrackingCard({
  exercise,
  index,
  isCompleted,
  onSessionCompleted
}) {
  const [expanded, setExpanded] = useState(false);
  const [trackingActive, setTrackingActive] = useState(false);
  const [paused, setPaused] = useState(false);
  const [loadingModel, setLoadingModel] = useState(false);
  const [cameraError, setCameraError] = useState('');

  // Live session metrics
  const [reps, setReps] = useState(0);
  const [feedback, setFeedback] = useState('Position yourself in front of the camera');
  const [qualityScore, setQualityScore] = useState(100);
  const [sessionSeconds, setSessionSeconds] = useState(0);
  const [sessionFinished, setSessionFinished] = useState(false);
  const [savingSession, setSavingSession] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState('');

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const trackerRef = useRef(null);
  const animFrameRef = useRef(null);
  const timerRef = useRef(null);
  const pausedRef = useRef(false);

  // Keep pausedRef synced
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // Clean up camera on unmount or when drawer collapses
  useEffect(() => {
    return () => {
      stopTracking();
    };
  }, []);

  const startTracking = async () => {
    setCameraError('');
    setLoadingModel(true);
    setSessionFinished(false);
    setReps(0);
    setSessionSeconds(0);
    setPaused(false);

    try {
      // 1. Acquire camera stream first
      const { stream } = await startCameraStream(videoRef.current);
      streamRef.current = stream;

      // 2. Initialize exercise-specific tracker
      trackerRef.current = createExerciseTracker(exercise.name);

      // 3. Initialize MoveNet SinglePose Lightning
      const detector = await initMoveNet();
      detectorRef.current = detector;

      setLoadingModel(false);
      setTrackingActive(true);

      // Start duration ticker
      timerRef.current = setInterval(() => {
        if (!pausedRef.current) {
          setSessionSeconds(s => s + 1);
        }
      }, 1000);

      // 4. Start detection loop
      runTrackingLoop();
    } catch (err) {
      console.error('Exercise tracking start error:', err);
      setLoadingModel(false);
      setTrackingActive(false);
      setCameraError(err.message || 'Could not access camera or load MoveNet model. Please check camera permissions.');
    }
  };

  const stopTracking = () => {
    stopCameraStream(streamRef.current, animFrameRef.current);
    streamRef.current = null;
    animFrameRef.current = null;

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    setTrackingActive(false);
    setSessionFinished(true);
  };

  const runTrackingLoop = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const detector = detectorRef.current;
    const tracker = trackerRef.current;

    if (!video || !canvas || !detector || video.readyState < 2) {
      animFrameRef.current = requestAnimationFrame(runTrackingLoop);
      return;
    }

    if (!pausedRef.current) {
      try {
        const poses = await detector.estimatePoses(video);
        const ctx = canvas.getContext('2d');

        if (poses && poses.length > 0 && poses[0].keypoints) {
          const keypoints = poses[0].keypoints;

          // Draw emerald MoveNet skeleton
          drawSkeleton(ctx, keypoints, canvas.width, canvas.height, 0.3);

          // Process exercise state machine
          if (tracker) {
            const stats = tracker.processFrame(keypoints);
            setReps(stats.reps);
            setFeedback(stats.feedback);
            setQualityScore(stats.qualityScore);
          }
        } else {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          setFeedback('Searching for body in frame...');
        }
      } catch (e) {
        console.warn('Frame estimation notice:', e);
      }
    }

    animFrameRef.current = requestAnimationFrame(runTrackingLoop);
  };

  const handleSaveValidatedSession = async () => {
    if (reps === 0) return;
    setSavingSession(true);
    setSaveError('');

    try {
      await exerciseService.complete(exercise.id, {
        repetitions: reps,
        sets: 1,
        duration_seconds: sessionSeconds,
        tracking_quality: 'MoveNet SinglePose Lightning Validated',
        notes: `Completed ${reps} MoveNet verified repetitions of ${exercise.name}`
      });

      setSaveSuccess(true);
      if (onSessionCompleted) {
        await onSessionCompleted(exercise.id);
      }
      setTimeout(() => {
        setSessionFinished(false);
        setExpanded(false);
        setSaveSuccess(false);
      }, 1500);
    } catch (err) {
      console.error('Failed to save exercise session:', err);
      setSaveError(err.response?.data?.error || err.message || 'Failed to save exercise record to database.');
    } finally {
      setSavingSession(false);
    }
  };

  // Parse structured arrays if needed
  const instructionsList = Array.isArray(exercise.instructions)
    ? exercise.instructions
    : (typeof exercise.instructions === 'string' ? JSON.parse(exercise.instructions || '[]') : []);

  const commonMistakesList = Array.isArray(exercise.common_mistakes)
    ? exercise.common_mistakes
    : (typeof exercise.common_mistakes === 'string' ? JSON.parse(exercise.common_mistakes || '[]') : []);

  const targetRepsNum = parseInt(exercise.reps) || 10;

  return (
    <div
      className={`border rounded-xl transition-all shadow-md overflow-hidden ${
        isCompleted
          ? 'bg-[#0a120a] border-emerald-500/40'
          : 'bg-[#0f1a0f] border-emerald-900/40 hover:border-emerald-500/30'
      }`}
    >
      {/* Exercise Card Header / Summary Row */}
      <div className="p-5 flex flex-col md:flex-row items-start gap-6">
        {/* Preview image */}
        <div className="w-full md:w-52 h-36 bg-[#0a0f0a] border border-emerald-900/40 rounded-lg flex items-center justify-center p-2 relative overflow-hidden flex-shrink-0">
          {exercise.image_url ? (
            <img src={exercise.image_url} alt={exercise.name} className="w-full h-full object-contain" />
          ) : (
            <Dumbbell size={36} className="text-emerald-600" />
          )}
          <span className="absolute bottom-2 left-2 bg-black/85 text-[10px] text-emerald-400 font-mono px-2 py-0.5 rounded border border-emerald-900/60">
            MoveNet AI Ready
          </span>
        </div>

        {/* Content Details */}
        <div className="flex-1 space-y-3 w-full">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-emerald-500 font-mono text-xs font-bold">0{index + 1}</span>
                <h3 className="text-base font-bold text-white hover:text-emerald-400 transition-colors">
                  <Link to={`/exercises/${exercise.id}`}>{exercise.name}</Link>
                </h3>
                {isCompleted && (
                  <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30 font-mono font-bold">
                    ✓ Completed in SQLite
                  </span>
                )}
              </div>
              <p className="text-xs text-emerald-400/90 font-medium mt-0.5">
                Target: {exercise.target_area}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1.5 text-xs bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 px-3 py-1.5 rounded-lg border border-emerald-900/50 transition-colors font-medium"
              >
                <span>{expanded ? 'Close AI Tracking' : 'Track with MoveNet'}</span>
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>
          </div>

          <p className="text-xs text-emerald-100/70 leading-relaxed">
            <strong className="text-emerald-300">Why it is included:</strong> {exercise.purpose}
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-emerald-900/30 text-xs font-mono">
            <div>
              <span className="text-emerald-700 block text-[10px]">Protocol</span>
              <span className="text-white font-semibold">{exercise.sets} sets × {exercise.reps}</span>
            </div>
            <div>
              <span className="text-emerald-700 block text-[10px]">Rest Interval</span>
              <span className="text-white font-semibold">{exercise.rest_period || '45s rest'}</span>
            </div>
            <div>
              <span className="text-emerald-700 block text-[10px]">Equipment</span>
              <span className="text-white font-semibold">{exercise.equipment}</span>
            </div>
            <div>
              <span className="text-emerald-700 block text-[10px]">Difficulty</span>
              <span className="text-emerald-400 font-semibold capitalize">{exercise.difficulty}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Expandable MoveNet Interactive Tracking Arena */}
      {expanded && (
        <div className="border-t border-emerald-900/40 bg-[#091009] p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-emerald-900/30">
            <div className="flex items-center gap-2">
              <Camera size={16} className="text-emerald-400" />
              <h4 className="text-sm font-bold text-white">MoveNet Computer Vision Repetition Tracker</h4>
            </div>
            <span className="text-xs font-mono text-emerald-400">
              Target: {exercise.sets} Sets × {exercise.reps} Reps
            </span>
          </div>

          {/* Video / Canvas Arena */}
          <div className="relative w-full aspect-video max-w-2xl mx-auto bg-[#050805] rounded-xl overflow-hidden border border-emerald-900/60 flex items-center justify-center">
            {/* Permanently mounted HTML5 video */}
            <video
              ref={videoRef}
              width={640}
              height={480}
              className={trackingActive ? "w-full h-full object-cover mirror" : "absolute opacity-0 pointer-events-none w-1 h-1"}
              playsInline
              muted
            />

            {/* Permanently mounted canvas */}
            <canvas
              ref={canvasRef}
              width={640}
              height={480}
              className={trackingActive ? "absolute inset-0 w-full h-full pointer-events-none" : "absolute opacity-0 pointer-events-none w-1 h-1"}
            />

            {/* Standby screen before tracking starts */}
            {!trackingActive && !sessionFinished && (
              <div className="text-center p-6 space-y-3">
                <Camera size={40} className="text-emerald-700 mx-auto" />
                <h4 className="text-sm font-bold text-white">{exercise.name} AI Form Mirror</h4>
                <p className="text-xs text-emerald-100/60 max-w-md mx-auto">
                  {exercise.starting_position}
                </p>

                {cameraError ? (
                  <div className="space-y-2">
                    <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2.5 max-w-sm mx-auto">
                      {cameraError}
                    </div>
                    <button
                      onClick={startTracking}
                      className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-5 py-2.5 rounded-lg text-xs transition-colors shadow-lg inline-flex items-center gap-2"
                    >
                      <RefreshCw size={14} />
                      <span>Retry Camera Start</span>
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={startTracking}
                    disabled={loadingModel}
                    className="bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-bold px-5 py-2.5 rounded-lg text-xs transition-colors shadow-lg inline-flex items-center gap-2"
                  >
                    {loadingModel ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                    <span>{loadingModel ? 'Starting Camera & MoveNet...' : 'Start MoveNet Tracking'}</span>
                  </button>
                )}
              </div>
            )}

            {/* Active tracking real-time HUD */}
            {trackingActive && (
              <div className="absolute top-3 left-3 right-3 flex items-start justify-between pointer-events-none">
                {/* Rep Counter Badge */}
                <div className="bg-black/85 border border-emerald-500/40 p-2.5 rounded-xl text-left font-mono">
                  <span className="text-emerald-500 text-[10px] block font-bold">REPETITIONS</span>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-white">{reps}</span>
                    <span className="text-xs text-emerald-400">/ {targetRepsNum}</span>
                  </div>
                </div>

                {/* Duration & Quality */}
                <div className="bg-black/85 border border-emerald-500/40 p-2.5 rounded-xl text-right font-mono">
                  <span className="text-emerald-500 text-[10px] block font-bold">TIME</span>
                  <span className="text-base font-bold text-white">{sessionSeconds}s</span>
                </div>
              </div>
            )}

            {/* Active Live Feedback Pill */}
            {trackingActive && (
              <div className="absolute bottom-3 left-3 right-3 text-center pointer-events-none">
                <div className="bg-black/90 border border-emerald-500/60 px-4 py-2 rounded-xl inline-block shadow-lg">
                  <p className="text-xs text-emerald-300 font-semibold">{feedback}</p>
                </div>
              </div>
            )}

            {/* Session Result Screen */}
            {sessionFinished && (
              <div className="text-center p-6 space-y-3 bg-[#0a120a] w-full h-full flex flex-col items-center justify-center">
                {reps > 0 && sessionSeconds >= 2 ? (
                  <>
                    <CheckCircle size={44} className="text-emerald-400" />
                    <h4 className="text-base font-bold text-white">Movement Session Completed!</h4>
                    <p className="text-xs text-emerald-300">
                      {reps} valid repetition{reps > 1 ? 's' : ''} observed and validated by MoveNet.
                    </p>
                    <div className="flex items-center gap-6 font-mono text-xs pt-1">
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Reps Counted</span>
                        <span className="text-xl font-bold text-white">{reps}</span>
                      </div>
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Session Time</span>
                        <span className="text-xl font-bold text-emerald-400">{sessionSeconds}s</span>
                      </div>
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Tracking Quality</span>
                        <span className="text-sm font-bold text-emerald-300">MoveNet Validated</span>
                      </div>
                    </div>

                    {saveSuccess && (
                      <div className="text-xs text-emerald-300 bg-emerald-500/20 border border-emerald-500/40 rounded-lg px-4 py-2 mt-2">
                        ✓ Saved to database! Adherence updated.
                      </div>
                    )}

                    {saveError && (
                      <div className="text-xs text-red-400 bg-red-500/20 border border-red-500/40 rounded-lg px-4 py-2 mt-2">
                        {saveError}
                      </div>
                    )}

                    <div className="pt-3 flex gap-2">
                      <button
                        onClick={startTracking}
                        className="text-xs bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 px-4 py-2 rounded-lg border border-emerald-900 font-medium"
                      >
                        Repeat Session
                      </button>
                      <button
                        onClick={handleSaveValidatedSession}
                        disabled={savingSession || saveSuccess}
                        className="text-xs bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-white font-bold px-5 py-2 rounded-lg shadow-lg"
                      >
                        {savingSession ? 'Saving to Database...' : saveSuccess ? 'Saved!' : 'Save Validated Exercise to DB'}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <AlertCircle size={44} className="text-amber-400" />
                    <h4 className="text-base font-bold text-white">Movement Not Detected</h4>
                    <p className="text-xs text-amber-200/90 max-w-sm">
                      Your movement was not detected clearly. Please adjust your position and try again.
                    </p>
                    <div className="flex items-center gap-6 font-mono text-xs pt-1">
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Reps Counted</span>
                        <span className="text-xl font-bold text-neutral-400">0</span>
                      </div>
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Duration</span>
                        <span className="text-xl font-bold text-neutral-400">{sessionSeconds}s</span>
                      </div>
                      <div>
                        <span className="text-emerald-600 block text-[10px]">Tracking Quality</span>
                        <span className="text-sm font-bold text-amber-400">Unvalidated</span>
                      </div>
                    </div>
                    <div className="pt-3">
                      <button
                        onClick={startTracking}
                        className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-6 py-2.5 rounded-lg shadow-lg flex items-center gap-2"
                      >
                        <RefreshCw size={13} />
                        <span>Adjust Position &amp; Try Again</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Active Controls & Feedback */}
          {trackingActive && (
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPaused(!paused)}
                  className="text-xs bg-[#111a11] hover:bg-emerald-500/20 text-emerald-300 border border-emerald-900/60 px-3.5 py-1.5 rounded-lg flex items-center gap-1.5"
                >
                  {paused ? <Play size={13} /> : <Pause size={13} />}
                  <span>{paused ? 'Resume' : 'Pause'}</span>
                </button>
                <button
                  onClick={stopTracking}
                  className="text-xs text-red-400 hover:bg-red-500/10 border border-red-900/40 px-3.5 py-1.5 rounded-lg flex items-center gap-1.5"
                >
                  <Square size={13} />
                  <span>Finish Tracking</span>
                </button>
              </div>

              <span className="text-xs text-emerald-400/80 font-mono">
                {paused ? 'Session Paused' : 'Live MoveNet Sensor Active'}
              </span>
            </div>
          )}

          {cameraError && (
            <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
              {cameraError}
            </div>
          )}

          {/* Instructions and common mistakes */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-emerald-900/30 text-xs">
            <div>
              <span className="text-emerald-400 font-bold block mb-1">Step-by-Step Instructions</span>
              <ul className="space-y-1 text-emerald-100/70 list-disc list-inside">
                {instructionsList.slice(0, 4).map((inst, i) => (
                  <li key={i}>{inst}</li>
                ))}
              </ul>
            </div>
            <div>
              <span className="text-amber-400 font-bold block mb-1">Common Mistakes to Avoid</span>
              <ul className="space-y-1 text-emerald-100/70 list-disc list-inside">
                {commonMistakesList.slice(0, 3).map((mistake, i) => (
                  <li key={i}>{mistake}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

