/**
 * Runs one measurement test against the shared pose engine.
 *
 * Every frame is pushed into the test logic, but the UI is only re-rendered a
 * few times a second. Measurement accuracy and render frequency are deliberately
 * decoupled: dropping a UI update is harmless, dropping a frame is not.
 *
 * The runner knows nothing about what is being measured. It starts a test, feeds
 * it, asks it whether it has finished, and hands the finished result back.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * @param {object} options
 * @param {object} options.engine the value returned by usePoseEngine
 * @param {() => object} options.createTest builds a fresh test instance
 * @param {(test: object, status: object) => boolean} options.isFinished
 * @param {(test: object, timestamp: number) => void} [options.onAbort]
 * @param {(context: {aborted: boolean, attempts: number}) => object} [options.finishArgs]
 * @param {number} [options.uiIntervalMs] minimum gap between UI updates
 */
export function useTestRunner({
  engine,
  createTest,
  isFinished,
  onAbort,
  finishArgs,
  uiIntervalMs = 120,
}) {
  const { subscribe, startLoop } = engine;

  const callbacksRef = useRef({ createTest, isFinished, onAbort, finishArgs });

  useEffect(() => {
    callbacksRef.current = { createTest, isFinished, onAbort, finishArgs };
  });

  const testRef = useRef(null);
  const lastTimestampRef = useRef(null);
  const lastUiUpdateRef = useRef(0);
  const attemptsRef = useRef(0);
  const settledRef = useRef(false);

  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [attempts, setAttempts] = useState(0);

  const settle = useCallback((aborted) => {
    const test = testRef.current;

    if (!test || settledRef.current) return;

    settledRef.current = true;

    const { onAbort: abortHandler, finishArgs: buildArgs } = callbacksRef.current;

    if (aborted && abortHandler) {
      abortHandler(test, lastTimestampRef.current ?? 0);
    }

    const args = buildArgs
      ? buildArgs({ aborted, attempts: attemptsRef.current })
      : { aborted, attempts: attemptsRef.current };

    // finish() never throws and never guesses: an incomplete run comes back
    // marked invalid with its reasons attached.
    setResult(test.finish(args));
    setRunning(false);
  }, []);

  useEffect(() => {
    if (!running) return undefined;

    const handleFrame = (frame) => {
      const test = testRef.current;

      if (!test || settledRef.current) return;

      lastTimestampRef.current = frame.timestamp;

      const nextStatus = test.push(frame);

      if (callbacksRef.current.isFinished(test, nextStatus)) {
        setStatus(nextStatus);
        settle(false);

        return;
      }

      if (frame.timestamp - lastUiUpdateRef.current >= uiIntervalMs) {
        lastUiUpdateRef.current = frame.timestamp;
        setStatus(nextStatus);
      }
    };

    const unsubscribe = subscribe(handleFrame);

    // The frame loop is shared, so it is started but never stopped here.
    startLoop();

    return unsubscribe;
  }, [running, subscribe, startLoop, settle, uiIntervalMs]);

  const start = useCallback(() => {
    attemptsRef.current += 1;
    settledRef.current = false;
    lastUiUpdateRef.current = 0;
    lastTimestampRef.current = null;
    testRef.current = callbacksRef.current.createTest();

    setAttempts(attemptsRef.current);
    setStatus(null);
    setResult(null);
    setRunning(true);
  }, []);

  /** User-initiated stop. The attempt is finished honestly, not discarded. */
  const stop = useCallback(() => settle(true), [settle]);

  /** Clear the finished attempt so the panel returns to its ready state. */
  const clear = useCallback(() => {
    settledRef.current = false;
    testRef.current = null;

    setStatus(null);
    setResult(null);
    setRunning(false);
  }, []);

  const guidance = useCallback(() => {
    const test = testRef.current;

    if (!test || typeof test.currentGuidance !== "function") return null;

    return test.currentGuidance();
  }, []);

  return { running, status, result, attempts, start, stop, clear, guidance };
}
