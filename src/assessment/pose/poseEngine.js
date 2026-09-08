/**
 * The single shared pose engine.
 *
 * One MoveNet model instance is loaded for the whole assessment and reused by
 * all three tests. Loading a separate model per test would multiply the download
 * and the memory cost for no benefit.
 *
 * PRIVACY, enforced by this file:
 *   - Pose estimation runs entirely in the browser.
 *   - No frame, no image, and no video is ever uploaded anywhere.
 *   - Nothing is recorded. Each frame is handed to the callback and dropped; the
 *     engine keeps no history of frames or keypoints.
 *
 * The engine's only job is: camera in, named keypoints out. It knows nothing
 * about shoulders, chairs, or balance, and it produces no measurements.
 */

import { toFrame } from "../utils/keypoints.js";

/** Error codes, so the UI can explain the problem instead of showing a stack. */
export const POSE_ERROR = {
  UNSUPPORTED_BROWSER: "unsupported_browser",
  INSECURE_CONTEXT: "insecure_context",
  MODEL_UNAVAILABLE: "model_unavailable",
  MODEL_LOAD_FAILED: "model_load_failed",
  CAMERA_PERMISSION_DENIED: "camera_permission_denied",
  CAMERA_NOT_FOUND: "camera_not_found",
  CAMERA_IN_USE: "camera_in_use",
  CAMERA_FAILED: "camera_failed",
  VIDEO_NOT_READY: "video_not_ready",
  ESTIMATION_FAILED: "estimation_failed",
};

/** Engine lifecycle, surfaced to the UI. */
export const ENGINE_STATE = {
  IDLE: "idle",
  LOADING_MODEL: "loading_model",
  STARTING_CAMERA: "starting_camera",
  READY: "ready",
  RUNNING: "running",
  STOPPED: "stopped",
  FAILED: "failed",
};

export class PoseEngineError extends Error {
  constructor(code, message, cause) {
    super(message);

    this.name = "PoseEngineError";
    this.code = code;
    this.cause = cause;
  }
}

/** User-facing text for each error code. No stack traces reach the user. */
export function describePoseError(code) {
  switch (code) {
    case POSE_ERROR.UNSUPPORTED_BROWSER:
      return "This browser does not provide camera access. Try a recent version of Chrome, Edge, Firefox, or Safari.";
    case POSE_ERROR.INSECURE_CONTEXT:
      return "Camera access needs a secure connection. Open the app over HTTPS, or on localhost during development.";
    case POSE_ERROR.MODEL_UNAVAILABLE:
      return "The pose estimation library is not installed. Run npm install, then reload the page.";
    case POSE_ERROR.MODEL_LOAD_FAILED:
      return "The pose model could not be loaded. Check your connection and try again.";
    case POSE_ERROR.CAMERA_PERMISSION_DENIED:
      return "Camera permission was declined. The movement checks cannot run without it, and you can still use the rest of the app.";
    case POSE_ERROR.CAMERA_NOT_FOUND:
      return "No camera was found on this device.";
    case POSE_ERROR.CAMERA_IN_USE:
      return "The camera is already in use by another application. Close it and try again.";
    case POSE_ERROR.VIDEO_NOT_READY:
      return "The camera preview did not start. Try again, or reload the page.";
    case POSE_ERROR.ESTIMATION_FAILED:
      return "Pose estimation stopped unexpectedly. You can retry this check.";
    default:
      return "The camera could not be started.";
  }
}

/**
 * One model for the whole session.
 *
 * Held at module scope on purpose: navigating between the three tests must not
 * trigger another model download.
 */
let sharedDetector = null;
let detectorPromise = null;

export function isDetectorLoaded() {
  return sharedDetector !== null;
}

/**
 * Load (or reuse) the shared MoveNet detector.
 *
 * MoveNet is used as a PRETRAINED keypoint detector and nothing else. No
 * training, fine-tuning, or classification happens here or anywhere else in the
 * application; every measurement is derived from the keypoints by explicit
 * geometry in the test logic modules.
 */
export async function loadPoseDetector() {
  if (sharedDetector) return sharedDetector;
  if (detectorPromise) return detectorPromise;

  detectorPromise = (async () => {
    let tf;
    let poseDetection;

    try {
      // Imported dynamically so the large model bundle is only fetched when a
      // user actually starts an assessment, and so a missing install produces a
      // clear message rather than breaking the whole app.
      tf = await import("@tensorflow/tfjs");
      await import("@tensorflow/tfjs-backend-webgl");
      poseDetection = await import("@tensorflow-models/pose-detection");
    } catch (error) {
      detectorPromise = null;

      throw new PoseEngineError(
        POSE_ERROR.MODEL_UNAVAILABLE,
        "Pose estimation packages are not available",
        error
      );
    }

    try {
      await tf.ready();

      const detector = await poseDetection.createDetector(
        poseDetection.SupportedModels.MoveNet,
        {
          modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING,
          // The library's own smoothing is off because this application does its
          // own median filtering. Two undocumented smoothing stages would make
          // the reported numbers impossible to reason about.
          enableSmoothing: false,
        }
      );

      sharedDetector = detector;

      return detector;
    } catch (error) {
      detectorPromise = null;

      throw new PoseEngineError(
        POSE_ERROR.MODEL_LOAD_FAILED,
        "MoveNet could not be initialised",
        error
      );
    }
  })();

  return detectorPromise;
}

/** Release the shared model. Called when leaving the assessment entirely. */
export function disposeSharedDetector() {
  if (sharedDetector && typeof sharedDetector.dispose === "function") {
    try {
      sharedDetector.dispose();
    } catch {
      // A failed dispose must not prevent the page from unmounting.
    }
  }

  sharedDetector = null;
  detectorPromise = null;
}

function mapCameraError(error) {
  const name = error && error.name ? error.name : "";

  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return POSE_ERROR.CAMERA_PERMISSION_DENIED;
  }

  if (name === "NotFoundError" || name === "DevicesNotFoundError" || name === "OverconstrainedError") {
    return POSE_ERROR.CAMERA_NOT_FOUND;
  }

  if (name === "NotReadableError" || name === "TrackStartError") {
    return POSE_ERROR.CAMERA_IN_USE;
  }

  if (name === "SecurityError") {
    return POSE_ERROR.INSECURE_CONTEXT;
  }

  return POSE_ERROR.CAMERA_FAILED;
}

/** Wait for the video element to report real dimensions. */
function waitForVideo(video, timeoutMs = 10000) {
  if (video.readyState >= 2 && video.videoWidth > 0) return Promise.resolve();

  return new Promise((resolve, reject) => {
    let settled = false;

    const cleanup = () => {
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("error", onError);
      clearTimeout(timer);
    };

    const onReady = () => {
      if (settled) return;

      settled = true;
      cleanup();
      resolve();
    };

    const onError = () => {
      if (settled) return;

      settled = true;
      cleanup();
      reject(new PoseEngineError(POSE_ERROR.VIDEO_NOT_READY, "Video element reported an error"));
    };

    const timer = setTimeout(onError, timeoutMs);

    video.addEventListener("loadeddata", onReady);
    video.addEventListener("error", onError);
  });
}

export class PoseEngine {
  /**
   * @param {object} options
   * @param {(frame: {timestamp: number, keypoints: object}) => void} [options.onFrame]
   * @param {(error: PoseEngineError) => void} [options.onError]
   * @param {(state: string) => void} [options.onState]
   * @param {number} [options.fpsWindow] frames used for the rolling frame rate
   */
  constructor({ onFrame, onError, onState, fpsWindow = 30 } = {}) {
    this.onFrame = onFrame || null;
    this.onError = onError || null;
    this.onState = onState || null;
    this.fpsWindow = fpsWindow;

    this.state = ENGINE_STATE.IDLE;
    this.video = null;
    this.stream = null;
    this.frameTimes = [];
    this.framesProcessed = 0;
    this.lastError = null;

    this.disposed = false;
    this.running = false;

    this.rafId = null;
    this.inFlight = false;
  }

  #setState(state) {
    this.state = state;

    if (this.onState) this.onState(state);
  }

  #fail(error) {
    const wrapped =
      error instanceof PoseEngineError
        ? error
        : new PoseEngineError(POSE_ERROR.CAMERA_FAILED, "Pose engine failed", error);

    this.lastError = wrapped;
    this.#setState(ENGINE_STATE.FAILED);

    if (this.onError) this.onError(wrapped);

    return wrapped;
  }

  /**
   * Load the model and open the camera.
   *
   * @param {HTMLVideoElement} video the preview element to attach the stream to
   * @param {object} [constraints] overrides for the video constraints
   */
  async prepare(video, constraints = {}) {
    if (this.disposed) throw new PoseEngineError(POSE_ERROR.CAMERA_FAILED, "Engine disposed");

    this.video = video;

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw this.#fail(
        new PoseEngineError(POSE_ERROR.UNSUPPORTED_BROWSER, "getUserMedia is unavailable")
      );
    }

    if (typeof window !== "undefined" && window.isSecureContext === false) {
      throw this.#fail(
        new PoseEngineError(POSE_ERROR.INSECURE_CONTEXT, "A secure context is required")
      );
    }

    try {
      this.#setState(ENGINE_STATE.LOADING_MODEL);
      await loadPoseDetector();
    } catch (error) {
      throw this.#fail(error);
    }

    if (this.disposed) return;

    try {
      this.#setState(ENGINE_STATE.STARTING_CAMERA);

      // audio: false is explicit. Nothing but video frames is ever requested,
      // and those frames never leave the browser.
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: "user",
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30 },
          ...constraints,
        },
      });
    } catch (error) {
      throw this.#fail(
        new PoseEngineError(mapCameraError(error), "The camera could not be opened", error)
      );
    }

    // A dispose() that arrived while the permission prompt was open must not
    // leave a live camera behind.
    if (this.disposed) {
      this.#releaseStream();

      return;
    }

    try {
      video.srcObject = this.stream;
      video.muted = true;
      video.playsInline = true;

      await video.play().catch(() => {
        // Autoplay rejection is not fatal; the frame loop reads the element
        // regardless once it has data.
      });

      await waitForVideo(video);
    } catch (error) {
      this.#releaseStream();

      throw this.#fail(error);
    }

    if (this.disposed) {
      this.#releaseStream();

      return;
    }

    this.#setState(ENGINE_STATE.READY);
  }

  /** Begin delivering frames to onFrame. */
  start() {
    if (this.disposed || this.running) return;
    if (this.state !== ENGINE_STATE.READY && this.state !== ENGINE_STATE.STOPPED) return;

    this.running = true;
    this.frameTimes = [];
    this.#setState(ENGINE_STATE.RUNNING);
    this.#scheduleFrame();
  }

  /** Stop delivering frames. The camera stays open so a retry is instant. */
  stop() {
    this.running = false;

    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }

    if (this.state === ENGINE_STATE.RUNNING) this.#setState(ENGINE_STATE.STOPPED);
  }

  #scheduleFrame() {
    if (!this.running || this.disposed) return;

    this.rafId = requestAnimationFrame(() => {
      this.rafId = null;
      void this.#processFrame();
    });
  }

  async #processFrame() {
    if (!this.running || this.disposed) return;

    // Skip rather than queue: a slow device should drop frames, not build a
    // backlog that would make timestamps meaningless.
    if (this.inFlight) {
      this.#scheduleFrame();

      return;
    }

    const video = this.video;

    if (!video || video.readyState < 2 || !video.videoWidth) {
      this.#scheduleFrame();

      return;
    }

    this.inFlight = true;

    let poses;

    try {
      poses = await sharedDetector.estimatePoses(video, {
        // The preview is mirrored with CSS for comfort; the pixels handed to the
        // detector are not, so its left/right labelling stays correct.
        flipHorizontal: false,
        maxPoses: 1,
      });
    } catch (error) {
      this.inFlight = false;
      this.running = false;
      this.#fail(
        new PoseEngineError(POSE_ERROR.ESTIMATION_FAILED, "estimatePoses failed", error)
      );

      return;
    }

    this.inFlight = false;

    if (!this.running || this.disposed) return;

    const timestamp = typeof performance !== "undefined" ? performance.now() : Date.now();

    this.#recordFrameTime(timestamp);
    this.framesProcessed += 1;

    // toFrame(null, ...) yields an empty keypoint map, which the test logic
    // treats as pose loss. An undetected person must never look like a still one.
    const frame = toFrame(poses && poses.length ? poses[0] : null, timestamp);

    if (this.onFrame) {
      try {
        this.onFrame(frame);
      } catch (error) {
        this.running = false;
        this.#fail(error);

        return;
      }
    }

    // Nothing is retained: `frame` and `poses` go out of scope here.
    this.#scheduleFrame();
  }

  #recordFrameTime(timestamp) {
    this.frameTimes.push(timestamp);

    if (this.frameTimes.length > this.fpsWindow) this.frameTimes.shift();
  }

  /** Rolling frame rate, or null before enough frames have been seen. */
  fps() {
    if (this.frameTimes.length < 2) return null;

    const first = this.frameTimes[0];
    const last = this.frameTimes[this.frameTimes.length - 1];
    const span = last - first;

    if (span <= 0) return null;

    return ((this.frameTimes.length - 1) / span) * 1000;
  }

  /** Intrinsic video size, needed to size an overlay canvas. */
  videoSize() {
    if (!this.video) return { width: 0, height: 0 };

    return { width: this.video.videoWidth || 0, height: this.video.videoHeight || 0 };
  }

  #releaseStream() {
    if (this.stream) {
      // Every track must be stopped, or the camera indicator light stays on.
      this.stream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // Ignore: the track may already have ended.
        }
      });

      this.stream = null;
    }

    if (this.video) {
      try {
        this.video.pause();
      } catch {
        // Ignore: the element may already be detached.
      }

      this.video.srcObject = null;
    }
  }

  /**
   * Full teardown: stop the loop and release the camera.
   * Safe to call more than once, and safe to call mid-start.
   */
  dispose() {
    this.disposed = true;
    this.stop();
    this.#releaseStream();
    this.video = null;
    this.#setState(ENGINE_STATE.IDLE);
  }
}
