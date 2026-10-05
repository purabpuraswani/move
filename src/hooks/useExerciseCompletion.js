/**
 * Today's exercise completions, and the two ways to change them.
 *
 * Extracted from SpecialistPanel so the plan's specialist card can show
 * the same ticks without a second progress store. There is one source of
 * truth — the exercise-results API — and both screens read and write it
 * through this hook.
 *
 * The camera/manual distinction is preserved exactly as the API defines
 * it: ticking a box records `source: "manual_confirmation"` with no
 * measurements, and only such a result can be un-ticked. A camera
 * session is a measurement and cannot be removed from here.
 */

import { useCallback, useEffect, useState } from "react";

import {
  confirmExerciseManually,
  deleteManualExerciseResult,
  fetchExerciseResults,
} from "../services/exerciseResults";

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function isToday(result) {
  const stamp = result?.completedAt || result?.recordedAt;

  return typeof stamp === "string" && stamp.startsWith(todayKey());
}

export default function useExerciseCompletion({ enabled = true } = {}) {
  const [results, setResults] = useState([]);
  const [completedIds, setCompletedIds] = useState(() => new Set());

  useEffect(() => {
    if (!enabled) return undefined;

    let active = true;

    fetchExerciseResults({ limit: 50 })
      .then((response) => {
        if (!active || !response?.results) return;

        const todays = response.results.filter(isToday);

        setResults(todays);
        setCompletedIds(
          new Set(
            todays
              .filter(
                (result) =>
                  result.status === "completed" || result.status === "incomplete",
              )
              .map((result) => result.exerciseId),
          ),
        );
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [enabled]);

  /** The result behind today's tick for one exercise, if there is one. */
  const resultFor = useCallback(
    (exerciseId) => results.find((result) => result.exerciseId === exerciseId) || null,
    [results],
  );

  /**
   * Record "I did this" by hand.
   *
   * `planId`/`itemId` are optional and, when known, are what link the record
   * back to the plan item that asked for it — the same link the camera flow
   * sends. Without them the record is still real; it simply is not attached to
   * a plan item, and nothing is invented to attach it to.
   */
  const markCompleted = useCallback(async (exerciseId, { planId = null, itemId = null } = {}) => {
    const response = await confirmExerciseManually({ exerciseId, planId, itemId });
    const saved = response?.result;

    setCompletedIds((previous) => new Set(previous).add(exerciseId));

    if (saved) {
      setResults((previous) => [
        ...previous.filter((result) => result.exerciseId !== exerciseId),
        saved,
      ]);
    }
  }, []);

  const undoCompletion = useCallback(async (resultId) => {
    await deleteManualExerciseResult(resultId);

    setResults((previous) => {
      const removed = previous.find((result) => result.id === resultId);

      if (removed?.exerciseId) {
        setCompletedIds((ids) => {
          const next = new Set(ids);
          next.delete(removed.exerciseId);
          return next;
        });
      }

      return previous.filter((result) => result.id !== resultId);
    });
  }, []);

  return {
    completedIds,
    results,
    resultFor,
    markCompleted,
    undoCompletion,
    /** Lets a test or a parent screen seed the state. */
    setCompletedIds,
    setResults,
  };
}
