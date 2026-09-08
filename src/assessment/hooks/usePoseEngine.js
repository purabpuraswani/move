/**
 * React binding for the single shared pose engine.
 *
 * The engine, the camera, and the model are created once for the whole
 * assessment and shared by all three checks. Frames are delivered to any number
 * of subscribers, so the preview overlay and the active measurement can both
 * read the same frame without the camera being opened twice.
 *
 * The camera is not requested until connect() is called, which happens only
 * after the user has read the safety and privacy notice.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ENGINE_STATE,
  PoseEngine,
  describePoseError,
  disposeSharedDetector,
} from "../pose/poseEngine.js";

export function usePoseEngine() {
  const videoRef = useRef(null);
  const engineRef = useRef(null);
  const subscribersRef = useRef(new Set());

  const [requested, setRequested] = useState(false);
  const [generation, setGeneration] = useState(0);
  const [state, setState] = useState(ENGINE_STATE.IDLE);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!requested) return undefined;

    const video = videoRef.current;

    if (!video) return undefined;

    setError(null);

    const engine = new PoseEngine({
      onFrame: (frame) => {
        subscribersRef.current.forEach((subscriber) => {
          try {
            subscriber(frame);
          } catch (subscriberError) {
            // One misbehaving subscriber must not take the camera down with it.
            console.error("Pose frame subscriber failed", subscriberError);
          }
        });
      },
      onState: setState,
      onError: (engineError) => {
        setError({ code: engineError.code, message: describePoseError(engineError.code) });
      },
    });

    engineRef.current = engine;

    engine.prepare(video).catch(() => {
      // Already surfaced through onError; nothing further to do here.
    });

    return () => {
      engine.dispose();

      if (engineRef.current === engine) engineRef.current = null;
    };
  }, [requested, generation]);

  // Free the model when the assessment is left entirely.
  useEffect(() => disposeSharedDetector, []);

  const connect = useCallback(() => setRequested(true), []);

  const retry = useCallback(() => {
    setRequested(true);
    setGeneration((value) => value + 1);
  }, []);

  /**
   * Give the camera back as soon as the last measurement is done, without
   * waiting for the page to unmount. The effect cleanup disposes the engine,
   * which stops every track, so the camera indicator light goes out while the
   * user is still reading their results.
   */
  const release = useCallback(() => {
    setRequested(false);
    setState(ENGINE_STATE.IDLE);
  }, []);

  const subscribe = useCallback((subscriber) => {
    subscribersRef.current.add(subscriber);

    return () => {
      subscribersRef.current.delete(subscriber);
    };
  }, []);

  const startLoop = useCallback(() => {
    engineRef.current?.start();
  }, []);

  const stopLoop = useCallback(() => {
    engineRef.current?.stop();
  }, []);

  const getFps = useCallback(() => engineRef.current?.fps() ?? null, []);

  const getVideoSize = useCallback(
    () => engineRef.current?.videoSize() ?? { width: 0, height: 0 },
    []
  );

  return {
    videoRef,
    connect,
    retry,
    release,
    subscribe,
    startLoop,
    stopLoop,
    getFps,
    getVideoSize,
    state,
    error,
    isConnecting:
      state === ENGINE_STATE.LOADING_MODEL || state === ENGINE_STATE.STARTING_CAMERA,
    isLive: state === ENGINE_STATE.READY || state === ENGINE_STATE.RUNNING || state === ENGINE_STATE.STOPPED,
    hasFailed: state === ENGINE_STATE.FAILED,
  };
}
