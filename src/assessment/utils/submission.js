import {
  assessmentCompletion,
  savedAssessmentMatches,
  toStoredPayload,
} from "./results.js";

/** Save first, verify the read-back, then run the workflow only for a complete session. */
export async function saveAssessmentForWorkflow(
  session,
  { save, runWorkflow, onSaved = () => {} },
) {
  const payload = toStoredPayload(session);
  const saved = await save(payload);

  if (!savedAssessmentMatches(payload, saved)) {
    throw new Error(
      "The server did not confirm both assessment results. Your plan has not been started; please retry saving.",
    );
  }

  onSaved(saved);

  if (!assessmentCompletion(saved).complete) {
    return { saved, workflow: null };
  }

  const workflow = await runWorkflow({
    idempotencyKey: `assessment-${saved.sessionId}`,
  });
  return { saved, workflow };
}
