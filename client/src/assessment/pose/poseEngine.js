import * as tf from '@tensorflow/tfjs';
import * as poseDetection from '@tensorflow-models/pose-detection';

let cachedDetector = null;

/**
 * Initializes TensorFlow.js and loads MoveNet SinglePose Lightning model.
 */
export async function initMoveNet() {
  if (cachedDetector) return cachedDetector;
  
  try {
    await tf.ready();
    cachedDetector = await poseDetection.createDetector(
      poseDetection.SupportedModels.MoveNet,
      {
        modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING,
        enableSmoothing: true
      }
    );
    return cachedDetector;
  } catch (error) {
    console.error('Failed to initialize MoveNet pose detector:', error);
    throw new Error('Could not load MoveNet pose detection model. Please check network or try again.');
  }
}

/**
 * Starts webcam and binds to an HTML5 video element.
 * Resolves once metadata is loaded and video is playing.
 */
export async function startCameraStream(videoElement) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error('Camera access is not supported by your browser.');
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      width: { ideal: 640 },
      height: { ideal: 480 },
      facingMode: 'user'
    },
    audio: false
  });

  if (!videoElement) {
    return { stream };
  }

  videoElement.srcObject = stream;
  videoElement.muted = true;
  videoElement.setAttribute('playsinline', 'true');

  if (videoElement.readyState >= 2) {
    try {
      await videoElement.play();
    } catch (e) {
      console.warn('Direct video play error:', e);
    }
    return { stream };
  }

  await new Promise((resolve) => {
    let resolved = false;
    const finish = () => {
      if (!resolved) {
        resolved = true;
        try {
          videoElement.play().catch(() => {});
        } catch { /* ignore */ }
        resolve();
      }
    };

    // 2.5s maximum timeout safeguard so it never hangs indefinitely
    const timer = setTimeout(finish, 2500);

    videoElement.onloadedmetadata = () => {
      clearTimeout(timer);
      finish();
    };

    videoElement.onloadeddata = () => {
      clearTimeout(timer);
      finish();
    };

    videoElement.onerror = () => {
      clearTimeout(timer);
      finish();
    };
  });

  return { stream };
}

/**
 * Stops all media stream tracks.
 */
export function stopCameraStream(stream, animFrameId) {
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
  }
  if (stream) {
    stream.getTracks().forEach(track => {
      try {
        track.stop();
      } catch (e) {
        // Ignore stop error
      }
    });
  }
}

/**
 * Computes 2D angle (in degrees) between three points: A -> B (vertex) -> C.
 */
export function calculateAngle(pointA, pointB, pointC, minScore = 0.25) {
  if (!pointA || !pointB || !pointC) return null;
  if ((pointA.score !== undefined && pointA.score < minScore) ||
      (pointB.score !== undefined && pointB.score < minScore) ||
      (pointC.score !== undefined && pointC.score < minScore)) {
    return null;
  }

  const radians = Math.atan2(pointC.y - pointB.y, pointC.x - pointB.x) -
                  Math.atan2(pointA.y - pointB.y, pointA.x - pointB.x);
  let angle = Math.abs((radians * 180.0) / Math.PI);
  if (angle > 180.0) angle = 360.0 - angle;
  return Math.round(angle);
}

/**
 * Draws MoveNet skeleton bones and keypoint joints onto a 2D canvas.
 */
export function drawSkeleton(ctx, keypoints, width, height, minScore = 0.3) {
  if (!ctx || !keypoints || keypoints.length === 0) return;

  const kpMap = {};
  keypoints.forEach(k => { kpMap[k.name] = k; });

  const boneConnections = [
    ['left_shoulder', 'right_shoulder'],
    ['left_shoulder', 'left_elbow'],
    ['left_elbow', 'left_wrist'],
    ['right_shoulder', 'right_elbow'],
    ['right_elbow', 'right_wrist'],
    ['left_shoulder', 'left_hip'],
    ['right_shoulder', 'right_hip'],
    ['left_hip', 'right_hip'],
    ['left_hip', 'left_knee'],
    ['left_knee', 'left_ankle'],
    ['right_hip', 'right_knee'],
    ['right_knee', 'right_ankle']
  ];

  ctx.clearRect(0, 0, width, height);

  // Draw connecting bones
  ctx.lineWidth = 3;
  ctx.strokeStyle = '#10b981'; // Emerald-500
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  boneConnections.forEach(([fromName, toName]) => {
    const p1 = kpMap[fromName];
    const p2 = kpMap[toName];
    if (p1 && p2 && p1.score >= minScore && p2.score >= minScore) {
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }
  });

  // Draw joint keypoints
  keypoints.forEach(kp => {
    if (kp.score >= minScore) {
      // Glow outer circle
      ctx.beginPath();
      ctx.arc(kp.x, kp.y, 6, 0, 2 * Math.PI);
      ctx.fillStyle = '#34d399'; // Emerald-400
      ctx.fill();

      // Core white dot
      ctx.beginPath();
      ctx.arc(kp.x, kp.y, 2.5, 0, 2 * Math.PI);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
    }
  });
}

