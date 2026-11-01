import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, Video, Camera, CheckCircle, AlertCircle, RefreshCw,
  Play, Square, ArrowRight, ShieldCheck, ChevronRight, Info, Eye
} from 'lucide-react';
import { initMoveNet, startCameraStream, stopCameraStream, calculateAngle, drawSkeleton } from '../assessment/pose/poseEngine';
import { assessmentService, workflowService } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

function formatDisplayDate(dateStr) {
  if (!dateStr) return 'Not recorded';
  try {
    const cleanStr = dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T');
    const d = new Date(cleanStr);
    if (isNaN(d.getTime())) return dateStr.substring(0, 16);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr.substring(0, 16);
  }
}

export default function AssessmentPage() {
  const [assessmentType, setAssessmentType] = useState('SHOULDER_RAISE');
  const [activeTab, setActiveTab] = useState('camera'); // 'camera' or 'manual'

  // Model & Camera states
  const [modelLoading, setModelLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [poseDetected, setPoseDetected] = useState(false);
  const [poseConfidence, setPoseConfidence] = useState(0);

  // Live real-time measurements
  const [liveLeftAngle, setLiveLeftAngle] = useState(null);
  const [liveRightAngle, setLiveRightAngle] = useState(null);
  const [peakLeftAngle, setPeakLeftAngle] = useState(0);
  const [peakRightAngle, setPeakRightAngle] = useState(0);

  // Balance hold timer
  const [testingSide, setTestingSide] = useState('LEFT'); // 'LEFT' or 'RIGHT' stance
  const [balanceHoldSeconds, setBalanceHoldSeconds] = useState(0);
  const [leftHoldTime, setLeftHoldTime] = useState(0);
  const [rightHoldTime, setRightHoldTime] = useState(0);
  const [isHoldingBalance, setIsHoldingBalance] = useState(false);

  // Manual fallback inputs
  const [manualLeft, setManualLeft] = useState('');
  const [manualRight, setManualRight] = useState('');

  // Assessment history
  const [history, setHistory] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const animFrameRef = useRef(null);
  const holdIntervalRef = useRef(null);

  const fetchHistory = async () => {
    try {
      const res = await assessmentService.getAll();
      setHistory(res.data || []);
    } catch (err) {
      console.error('History fetch error:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Clean up stream & timer on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  // Start MoveNet Camera Assessment
  const startCamera = async () => {
    setCameraError('');
    setSavedSuccess(false);
    setModelLoading(true);

    try {
      // 1. Ensure MoveNet detector is loaded
      const detector = await initMoveNet();
      detectorRef.current = detector;

      // 2. Obtain camera stream and attach to permanently mounted video element
      const { stream } = await startCameraStream(videoRef.current);
      streamRef.current = stream;

      setCameraActive(true);
      setModelLoading(false);

      // 3. Start real-time frame estimation loop
      runDetectionLoop();
    } catch (err) {
      console.error('Camera or MoveNet start failure:', err);
      setModelLoading(false);
      setCameraActive(false);
      setCameraError(
        err.message || 'Webcam access failed. Ensure camera permission is granted or switch to Manual Measurement mode.'
      );
    }
  };

  // Stop camera and tracking
  const stopCamera = () => {
    stopCameraStream(streamRef.current, animFrameRef.current);
    streamRef.current = null;
    animFrameRef.current = null;

    if (holdIntervalRef.current) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }

    setCameraActive(false);
    setPoseDetected(false);
    setIsHoldingBalance(false);
  };

  // MoveNet real-time pose estimation frame loop
  const runDetectionLoop = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const detector = detectorRef.current;

    if (!video || !canvas || !detector || video.readyState < 2) {
      animFrameRef.current = requestAnimationFrame(runDetectionLoop);
      return;
    }

    try {
      const poses = await detector.estimatePoses(video);
      const ctx = canvas.getContext('2d');

      if (poses && poses.length > 0 && poses[0].keypoints) {
        const keypoints = poses[0].keypoints;
        const validKps = keypoints.filter(k => k.score > 0.3);
        const avgScore = validKps.reduce((acc, k) => acc + k.score, 0) / (validKps.length || 1);

        setPoseDetected(validKps.length >= 6);
        setPoseConfidence(Math.round(avgScore * 100));

        // Draw skeleton connections
        drawSkeleton(ctx, keypoints, canvas.width, canvas.height, 0.3);

        // Keypoint dictionary
        const kp = {};
        keypoints.forEach(k => { kp[k.name] = k; });

        if (assessmentType === 'SHOULDER_RAISE') {
          // Angle between hip -> shoulder -> elbow
          const leftAngle = calculateAngle(kp.left_hip, kp.left_shoulder, kp.left_elbow);
          const rightAngle = calculateAngle(kp.right_hip, kp.right_shoulder, kp.right_elbow);

          if (leftAngle !== null) {
            setLiveLeftAngle(leftAngle);
            setPeakLeftAngle(prev => Math.max(prev, leftAngle));
          }
          if (rightAngle !== null) {
            setLiveRightAngle(rightAngle);
            setPeakRightAngle(prev => Math.max(prev, rightAngle));
          }
        } else if (assessmentType === 'ONE_LEG_STAND') {
          // Check ankle vertical difference to detect single-leg lift
          const leftAnkle = kp.left_ankle;
          const rightAnkle = kp.right_ankle;

          if (leftAnkle && rightAnkle && leftAnkle.score > 0.25 && rightAnkle.score > 0.25) {
            const ankleDelta = Math.abs(leftAnkle.y - rightAnkle.y);
            // If delta > 25 pixels, one foot is lifted off ground
            const lifted = ankleDelta > 25;
            setIsHoldingBalance(lifted);
          }
        }
      } else {
        setPoseDetected(false);
      }
    } catch (e) {
      console.warn('Pose estimation frame error:', e);
    }

    animFrameRef.current = requestAnimationFrame(runDetectionLoop);
  };

  // Balance hold timer ticker
  useEffect(() => {
    if (isHoldingBalance && cameraActive) {
      if (!holdIntervalRef.current) {
        holdIntervalRef.current = setInterval(() => {
          setBalanceHoldSeconds(s => s + 1);
        }, 1000);
      }
    } else {
      if (holdIntervalRef.current) {
        clearInterval(holdIntervalRef.current);
        holdIntervalRef.current = null;
      }
    }
    return () => {
      if (holdIntervalRef.current) {
        clearInterval(holdIntervalRef.current);
        holdIntervalRef.current = null;
      }
    };
  }, [isHoldingBalance, cameraActive]);

  // Record balance time when stopped
  const lockBalanceSide = (side) => {
    if (side === 'LEFT') {
      setLeftHoldTime(balanceHoldSeconds);
      setBalanceHoldSeconds(0);
      setTestingSide('RIGHT');
    } else {
      setRightHoldTime(balanceHoldSeconds);
      setBalanceHoldSeconds(0);
    }
  };

  // Save assessment (either camera-measured or manually entered)
  const handleSaveAssessment = async () => {
    setSubmitting(true);
    setSavedSuccess(false);

    const isCamera = activeTab === 'camera';
    let leftVal = 0;
    let rightVal = 0;

    if (isCamera) {
      if (assessmentType === 'SHOULDER_RAISE') {
        leftVal = peakLeftAngle || liveLeftAngle || 0;
        rightVal = peakRightAngle || liveRightAngle || 0;
      } else {
        leftVal = leftHoldTime || balanceHoldSeconds || 0;
        rightVal = rightHoldTime || 0;
      }
    } else {
      leftVal = parseFloat(manualLeft) || 0;
      rightVal = parseFloat(manualRight) || 0;
    }

    try {
      await assessmentService.create({
        assessment_type: assessmentType,
        left_measurement: leftVal,
        right_measurement: rightVal,
        unit: assessmentType === 'SHOULDER_RAISE' ? 'degrees' : 'seconds',
        source: isCamera ? 'camera' : 'manual',
        result_json: {
          tracking_source: isCamera ? 'movenet_lightning' : 'manual_user_entry',
          confidence: isCamera ? poseConfidence : null,
          timestamp: new Date().toISOString()
        }
      });

      // Recalibrate specialist plan with the new assessment
      await workflowService.run();
      setSavedSuccess(true);
      fetchHistory();
      if (isCamera) stopCamera();
    } catch (err) {
      console.error('Error saving assessment:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const hasValidMeasurements = assessmentType === 'SHOULDER_RAISE'
    ? (peakLeftAngle > 0 || peakRightAngle > 0)
    : (leftHoldTime > 0 || rightHoldTime > 0 || balanceHoldSeconds > 0);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Title & Mode Switcher */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-emerald-600 font-mono mb-1">
            <span>Assessment &gt; AI Kinematic Motion Screening</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Movement Assessment</h1>
          <p className="text-sm text-emerald-100/70 mt-1 max-w-3xl">
            Real-time computer vision pose tracking powered by TensorFlow.js and MoveNet SinglePose Lightning. Objectively measures shoulder range of motion and unilateral balance stability.
          </p>
        </div>

        {/* Assessment Type Selector */}
        <div className="flex items-center gap-2 bg-[#0f1a0f] border border-emerald-900/40 p-1 rounded-lg">
          <button
            onClick={() => { setAssessmentType('SHOULDER_RAISE'); }}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              assessmentType === 'SHOULDER_RAISE'
                ? 'bg-emerald-500 text-white font-bold'
                : 'text-emerald-400 hover:text-white'
            }`}
          >
            Shoulder Raise (ROM)
          </button>
          <button
            onClick={() => { setAssessmentType('ONE_LEG_STAND'); }}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              assessmentType === 'ONE_LEG_STAND'
                ? 'bg-emerald-500 text-white font-bold'
                : 'text-emerald-400 hover:text-white'
            }`}
          >
            One-Leg Stand (Balance)
          </button>
        </div>
      </div>

      {savedSuccess && (
        <div className="bg-emerald-500/20 border border-emerald-500/40 rounded-xl p-4 text-emerald-300 flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-2.5">
            <CheckCircle size={18} className="text-emerald-400" />
            <span className="text-sm font-semibold">
              Assessment recorded and saved to SQLite! Specialist workflow was executed and your MoveWell Plan has been re-synchronized.
            </span>
          </div>
          <Link to="/plan" className="text-xs bg-emerald-500 text-black font-bold px-3 py-1.5 rounded-lg hover:bg-emerald-400">
            View Updated Plan →
          </Link>
        </div>
      )}

      {/* Tabs: Camera Tracking vs Manual Entry Fallback */}
      <div className="flex gap-2 border-b border-emerald-900/40 pb-2">
        <button
          onClick={() => setActiveTab('camera')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'camera'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : 'text-emerald-100/60 hover:text-white'
          }`}
        >
          <Camera size={14} />
          <span>MoveNet Camera Assessment</span>
        </button>
        <button
          onClick={() => { setActiveTab('manual'); stopCamera(); }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
            activeTab === 'manual'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
              : 'text-emerald-100/60 hover:text-white'
          }`}
        >
          <Info size={14} />
          <span>Manual Measurement Fallback</span>
        </button>
      </div>

      {/* TAB 1: Real Camera MoveNet Assessment */}
      {activeTab === 'camera' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Video / Canvas Arena */}
          <div className="lg:col-span-2 bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <Camera size={16} className="text-emerald-400" />
                <span>MoveNet Pose Sensor Feed</span>
              </div>
              <div className="flex items-center gap-3 text-xs font-mono">
                {modelLoading && <span className="text-amber-400 animate-pulse">Initializing MoveNet...</span>}
                <span className={`w-2 h-2 rounded-full ${cameraActive ? 'bg-emerald-400 animate-ping' : 'bg-neutral-600'}`} />
                <span className={cameraActive ? 'text-emerald-400 font-bold' : 'text-neutral-500'}>
                  {cameraActive ? (poseDetected ? `TRACKING (${poseConfidence}%)` : 'DETECTING POSE...') : 'CAMERA STANDBY'}
                </span>
              </div>
            </div>

            {/* Video + Canvas Overlay Container (ALWAYS mounted so videoRef is ready) */}
            <div className="relative w-full aspect-video bg-[#0a0f0a] rounded-xl overflow-hidden border border-emerald-900/60 flex items-center justify-center">
              {/* Permanently mounted HTML5 video element */}
              <video
                ref={videoRef}
                width={640}
                height={480}
                className={cameraActive ? "w-full h-full object-cover mirror" : "absolute opacity-0 pointer-events-none w-1 h-1"}
                playsInline
                muted
              />

              {/* Permanently mounted canvas overlay */}
              <canvas
                ref={canvasRef}
                width={640}
                height={480}
                className={cameraActive ? "absolute inset-0 w-full h-full pointer-events-none" : "absolute opacity-0 pointer-events-none w-1 h-1"}
              />

              {/* Standby UI (visible only when camera is inactive) */}
              {!cameraActive && (
                <div className="text-center p-8 space-y-3">
                  <Video size={48} className="text-emerald-800 mx-auto" />
                  <h3 className="text-sm font-bold text-white">MoveNet AI Pose Tracking</h3>
                  <p className="text-xs text-emerald-100/60 max-w-md mx-auto">
                    {assessmentType === 'SHOULDER_RAISE'
                      ? 'Stand 2–3 meters back so upper body and both arms are visible. Raise both arms slowly to peak comfortable elevation.'
                      : 'Stand near a stable chair or support. Shift weight onto one leg and lift the other foot slightly off the floor.'}
                  </p>
                  <button
                    onClick={startCamera}
                    disabled={modelLoading}
                    className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-lg text-xs font-bold transition-colors inline-flex items-center gap-2 shadow-lg"
                  >
                    <Play size={14} />
                    <span>{modelLoading ? 'Initializing MoveNet...' : 'Start Camera Assessment'}</span>
                  </button>
                </div>
              )}

              {/* Real-time Angle Badges Overlay (When Camera Active) */}
              {cameraActive && assessmentType === 'SHOULDER_RAISE' && (
                <div className="absolute top-4 left-4 right-4 flex justify-between pointer-events-none">
                  <div className="bg-black/80 border border-emerald-500/40 px-3 py-1.5 rounded-lg text-xs font-mono">
                    <span className="text-emerald-600 block text-[10px]">Left Shoulder ROM</span>
                    <span className="text-lg font-bold text-emerald-300">
                      {liveLeftAngle !== null ? `${liveLeftAngle}°` : 'Tracking...'}
                    </span>
                    <span className="text-[10px] text-emerald-500 block">Peak: {peakLeftAngle > 0 ? `${peakLeftAngle}°` : '—'}</span>
                  </div>
                  <div className="bg-black/80 border border-emerald-500/40 px-3 py-1.5 rounded-lg text-xs font-mono text-right">
                    <span className="text-emerald-600 block text-[10px]">Right Shoulder ROM</span>
                    <span className="text-lg font-bold text-emerald-300">
                      {liveRightAngle !== null ? `${liveRightAngle}°` : 'Tracking...'}
                    </span>
                    <span className="text-[10px] text-emerald-500 block">Peak: {peakRightAngle > 0 ? `${peakRightAngle}°` : '—'}</span>
                  </div>
                </div>
              )}

              {/* Balance Hold Overlay (When Camera Active) */}
              {cameraActive && assessmentType === 'ONE_LEG_STAND' && (
                <div className="absolute top-4 left-4 right-4 flex justify-between pointer-events-none">
                  <div className="bg-black/80 border border-emerald-500/40 px-3 py-1.5 rounded-lg text-xs font-mono">
                    <span className="text-emerald-600 block text-[10px]">Active Stance</span>
                    <span className="text-base font-bold text-white">{testingSide} Leg</span>
                    <span className="text-[10px] text-emerald-400 block">
                      {isHoldingBalance ? 'Foot Lifted ✓ Holding...' : 'Lift one foot off ground'}
                    </span>
                  </div>
                  <div className="bg-black/80 border border-emerald-500/40 px-3 py-1.5 rounded-lg text-xs font-mono text-right">
                    <span className="text-emerald-600 block text-[10px]">Hold Duration</span>
                    <span className="text-2xl font-bold text-emerald-400">{balanceHoldSeconds} s</span>
                  </div>
                </div>
              )}
            </div>

            {/* Camera Error Message with retry */}
            {cameraError && (
              <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between">
                <span>{cameraError}</span>
                <button
                  onClick={startCamera}
                  className="text-xs bg-amber-500 text-black px-2.5 py-1 rounded font-bold hover:bg-amber-400 ml-3"
                >
                  Retry Camera
                </button>
              </div>
            )}

            {/* Camera Controls */}
            {cameraActive && (
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={stopCamera}
                  className="text-xs text-red-400 border border-red-900/40 hover:bg-red-500/10 px-3.5 py-1.5 rounded-lg font-medium transition-colors"
                >
                  Stop Camera
                </button>

                {assessmentType === 'ONE_LEG_STAND' && (
                  <button
                    onClick={() => lockBalanceSide(testingSide)}
                    className="text-xs bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-4 py-2 rounded-lg transition-colors shadow"
                  >
                    Lock {testingSide} Leg Time ({balanceHoldSeconds}s)
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Right Col: Captured Telemetry & Save to Database */}
          <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="pb-3 border-b border-emerald-900/30">
                <h3 className="text-base font-bold text-white">Target Form &amp; Telemetry</h3>
                <p className="text-xs text-emerald-100/60 font-mono">
                  MoveNet Kinematic Sensor Tracking
                </p>
              </div>

              {/* Real Male Exercise Demonstration Photo Alongside Camera Feed */}
              <div className="relative rounded-xl overflow-hidden border border-emerald-900/60 bg-[#050805] h-64 md:h-72 flex items-center justify-center p-1 group shadow-inner">
                <img
                  src={assessmentType === 'SHOULDER_RAISE' ? '/exercises/images/shoulder-raise-assessment.jpg' : '/exercises/images/one-leg-stand-assessment.jpg'}
                  alt={assessmentType === 'SHOULDER_RAISE' ? 'Adult male model demonstrating bilateral shoulder raise overhead form' : 'Adult male model demonstrating single-leg balance stance form'}
                  className="w-full h-full object-contain"
                />
                <div className="absolute top-2 left-2">
                  <span className="text-[10px] font-mono text-emerald-300 bg-black/85 px-2 py-0.5 rounded border border-emerald-500/40 font-bold">
                    {assessmentType === 'SHOULDER_RAISE' ? 'TARGET FORM • 180° OVERHEAD' : 'TARGET FORM • 15S+ BALANCE HOLD'}
                  </span>
                </div>
                <div className="absolute bottom-2 right-2">
                  <span className="text-[10px] font-mono text-emerald-400 bg-black/85 px-2 py-0.5 rounded border border-emerald-500/30">
                    Reference Model
                  </span>
                </div>
              </div>

              {assessmentType === 'SHOULDER_RAISE' ? (
                <div className="space-y-3">
                  <div className="p-3 bg-[#111a11] rounded-lg border border-emerald-900/40">
                    <span className="text-xs text-emerald-600 block">Peak Left Elevation</span>
                    <span className="text-2xl font-bold text-white font-mono">
                      {peakLeftAngle > 0 ? `${peakLeftAngle}°` : 'Not Measured'}
                    </span>
                    <span className="text-[10px] text-emerald-500 block">Functional threshold: 180°</span>
                  </div>
                  <div className="p-3 bg-[#111a11] rounded-lg border border-emerald-900/40">
                    <span className="text-xs text-emerald-600 block">Peak Right Elevation</span>
                    <span className="text-2xl font-bold text-white font-mono">
                      {peakRightAngle > 0 ? `${peakRightAngle}°` : 'Not Measured'}
                    </span>
                    <span className="text-[10px] text-emerald-500 block">Functional threshold: 180°</span>
                  </div>
                  <div className="p-3 bg-black/40 rounded-lg text-xs font-mono text-emerald-400 border border-emerald-900/30">
                    <span>Asymmetry Delta: </span>
                    <strong>{peakLeftAngle > 0 && peakRightAngle > 0 ? `${Math.abs(peakLeftAngle - peakRightAngle)}°` : '—'}</strong>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 bg-[#111a11] rounded-lg border border-emerald-900/40">
                    <span className="text-xs text-emerald-600 block">Left Stance Hold Time</span>
                    <span className="text-2xl font-bold text-white font-mono">
                      {leftHoldTime > 0 ? `${leftHoldTime} s` : (testingSide === 'LEFT' && balanceHoldSeconds > 0 ? `${balanceHoldSeconds} s` : 'Not Recorded')}
                    </span>
                  </div>
                  <div className="p-3 bg-[#111a11] rounded-lg border border-emerald-900/40">
                    <span className="text-xs text-emerald-600 block">Right Stance Hold Time</span>
                    <span className="text-2xl font-bold text-white font-mono">
                      {rightHoldTime > 0 ? `${rightHoldTime} s` : (testingSide === 'RIGHT' && balanceHoldSeconds > 0 ? `${balanceHoldSeconds} s` : 'Not Recorded')}
                    </span>
                  </div>
                  <div className="p-3 bg-black/40 rounded-lg text-xs font-mono text-emerald-400 border border-emerald-900/30">
                    <span>Imbalance Gap: </span>
                    <strong>{leftHoldTime > 0 && rightHoldTime > 0 ? `${Math.abs(leftHoldTime - rightHoldTime)} s` : '—'}</strong>
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-2 pt-4 border-t border-emerald-900/30">
              <button
                onClick={handleSaveAssessment}
                disabled={submitting || !hasValidMeasurements}
                className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-white py-3 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2 shadow-lg"
              >
                {submitting ? 'Analyzing & Saving to SQLite...' : hasValidMeasurements ? 'Save Assessment to SQLite' : 'Perform Test to Enable Save'}
                <ArrowRight size={15} />
              </button>
              <p className="text-[10px] text-center text-emerald-600 font-mono">
                Saves genuine measurements to SQLite &amp; recalculates all 6 specialists
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Real Male Exercise Demonstrations for Both Tests Side-by-Side */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Movement Assessment Exercise Reference Guides</h3>
            <p className="text-xs text-emerald-100/60">
              Photorealistic human demonstrations showing target alignment and posture for both assessment protocols
            </p>
          </div>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
            MoveNet AI Pose Calibrated
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-1">
          {/* Exercise 1: Shoulder Raise Card */}
          <div
            onClick={() => {
              setAssessmentType('SHOULDER_RAISE');
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            className={`rounded-xl border p-4 cursor-pointer transition-all ${
              assessmentType === 'SHOULDER_RAISE'
                ? 'bg-[#111c11] border-emerald-500/60 shadow-lg shadow-emerald-950/40'
                : 'bg-[#0a0f0a] border-emerald-900/30 hover:border-emerald-500/30'
            }`}
          >
            <div className="h-80 md:h-[420px] w-full rounded-lg overflow-hidden border border-emerald-900/40 relative mb-3.5 bg-[#050805] flex items-center justify-center p-2 group">
              <img
                src="/exercises/images/shoulder-raise-assessment.jpg"
                alt="Adult male model demonstrating standing bilateral shoulder raise"
                className="w-full h-full object-contain"
              />
              <span className="absolute top-2 left-2 bg-black/85 text-[10px] font-mono text-emerald-400 px-2.5 py-1 rounded border border-emerald-500/30">
                Exercise 1: Bilateral Shoulder Raise
              </span>
              <span className="absolute bottom-2 right-2 bg-emerald-500/90 text-white text-[10px] font-mono px-2.5 py-1 rounded font-bold">
                Target: 180° ROM
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-white">Shoulder Raise (Mobility &amp; Symmetry)</h4>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Upper Body
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                Stand tall with neutral spine. Raise both arms overhead toward full 180° vertical flexion. MoveNet measures bilateral peak angle and scapular rhythm delta.
              </p>
              <div className="pt-2 flex items-center justify-between text-xs font-mono text-emerald-400">
                <span>Sagittal &amp; Frontal Plane</span>
                <span className="text-emerald-300 font-bold underline">
                  {assessmentType === 'SHOULDER_RAISE' ? '✓ Currently Active Test' : 'Switch to this test →'}
                </span>
              </div>
            </div>
          </div>

          {/* Exercise 2: One-Leg Stand Card */}
          <div
            onClick={() => {
              setAssessmentType('ONE_LEG_STAND');
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            className={`rounded-xl border p-4 cursor-pointer transition-all ${
              assessmentType === 'ONE_LEG_STAND'
                ? 'bg-[#111c11] border-emerald-500/60 shadow-lg shadow-emerald-950/40'
                : 'bg-[#0a0f0a] border-emerald-900/30 hover:border-emerald-500/30'
            }`}
          >
            <div className="h-80 md:h-[420px] w-full rounded-lg overflow-hidden border border-emerald-900/40 relative mb-3.5 bg-[#050805] flex items-center justify-center p-2 group">
              <img
                src="/exercises/images/one-leg-stand-assessment.jpg"
                alt="Adult male model demonstrating single-leg stance balance hold"
                className="w-full h-full object-contain"
              />
              <span className="absolute top-2 left-2 bg-black/85 text-[10px] font-mono text-emerald-400 px-2.5 py-1 rounded border border-emerald-500/30">
                Exercise 2: One-Leg Stand Balance
              </span>
              <span className="absolute bottom-2 right-2 bg-emerald-500/90 text-white text-[10px] font-mono px-2.5 py-1 rounded font-bold">
                Target: 15s+ Hold
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-white">One-Leg Stand (Equilibrium &amp; Stability)</h4>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Lower Body
                </span>
              </div>
              <p className="text-xs text-emerald-100/70 leading-relaxed">
                Stand upright near a support. Lift one foot 6–8 inches off the ground with knee bent and hold equilibrium. MoveNet tracks hold duration and left/right balance gap.
              </p>
              <div className="pt-2 flex items-center justify-between text-xs font-mono text-emerald-400">
                <span>Vestibular &amp; Unilateral Stability</span>
                <span className="text-emerald-300 font-bold underline">
                  {assessmentType === 'ONE_LEG_STAND' ? '✓ Currently Active Test' : 'Switch to this test →'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* TAB 2: Clean Manual Measurement Fallback */}
      {activeTab === 'manual' && (
        <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg max-w-2xl mx-auto space-y-5">
          <div>
            <div className="flex items-center gap-2 text-amber-400 font-bold text-sm mb-1">
              <Info size={16} />
              <span>Manual Entry Fallback Mode</span>
            </div>
            <p className="text-xs text-emerald-100/70">
              Enter measured values directly if your webcam is unavailable. These records are explicitly saved with source <strong className="text-emerald-300 font-mono">"MANUAL"</strong> to preserve diagnostic provenance.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-emerald-400 block mb-1 font-semibold">
                Left Side ({assessmentType === 'SHOULDER_RAISE' ? 'Degrees °' : 'Hold Time in Seconds s'})
              </label>
              <input
                type="number"
                placeholder={assessmentType === 'SHOULDER_RAISE' ? 'e.g. 155' : 'e.g. 15'}
                value={manualLeft}
                onChange={e => setManualLeft(e.target.value)}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-3 text-white text-base font-mono focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="text-xs text-emerald-400 block mb-1 font-semibold">
                Right Side ({assessmentType === 'SHOULDER_RAISE' ? 'Degrees °' : 'Hold Time in Seconds s'})
              </label>
              <input
                type="number"
                placeholder={assessmentType === 'SHOULDER_RAISE' ? 'e.g. 148' : 'e.g. 20'}
                value={manualRight}
                onChange={e => setManualRight(e.target.value)}
                className="w-full bg-[#0a0f0a] border border-emerald-900 rounded-lg p-3 text-white text-base font-mono focus:border-emerald-500"
              />
            </div>
          </div>

          <button
            onClick={handleSaveAssessment}
            disabled={submitting || !manualLeft || !manualRight}
            className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:opacity-40 text-white py-3 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2"
          >
            {submitting ? 'Saving Manual Record...' : 'Save Manual Assessment'}
            <ArrowRight size={15} />
          </button>
        </div>
      )}

      {/* Historical Movement Assessment Sessions from SQLite */}
      <div className="bg-[#0f1a0f] border border-emerald-900/40 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-emerald-900/30">
          <div>
            <h3 className="text-base font-bold text-white">Your Assessment History</h3>
            <p className="text-xs text-emerald-100/60">Actual historical sessions retrieved from SQLite</p>
          </div>
          <span className="text-xs text-emerald-400 font-mono">{history.length} records found</span>
        </div>

        {history.length === 0 ? (
          <p className="text-xs text-emerald-400/60 py-4 text-center">
            No assessment sessions recorded yet. Complete your first test above!
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-emerald-700 border-b border-emerald-900/40">
                  <th className="pb-2">Date &amp; Time</th>
                  <th className="pb-2">Test Type</th>
                  <th className="pb-2">Left</th>
                  <th className="pb-2">Right</th>
                  <th className="pb-2">Imbalance</th>
                  <th className="pb-2">Source</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-emerald-900/20 text-emerald-100/80">
                {history.map((h) => {
                  const delta = Math.abs((h.left_measurement || 0) - (h.right_measurement || 0));
                  return (
                    <tr key={h.id} className="hover:bg-white/[0.02]">
                      <td className="py-3 text-white font-semibold">{formatDisplayDate(h.assessment_date)}</td>
                      <td className="py-3 text-emerald-300">{h.assessment_type}</td>
                      <td className="py-3">{h.left_measurement} {h.unit}</td>
                      <td className="py-3">{h.right_measurement} {h.unit}</td>
                      <td className="py-3 text-amber-400">{delta.toFixed(1)} {h.unit} delta</td>
                      <td className="py-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          h.source === 'camera' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-neutral-800 text-neutral-300'
                        }`}>
                          {h.source ? h.source.toUpperCase() : 'CAMERA'}
                        </span>
                      </td>
                      <td className="py-3 text-right text-emerald-400">COMPLETED</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
