/**
 * The MoveWell journey, as a derivation from real state.
 *
 * This module answers one question: given what the user has actually done so
 * far, what is the next thing that makes sense? It is deliberately a pure
 * function of already-fetched data, not a stored "current_step" counter,
 * because a counter drifts from reality the moment anything is added outside
 * the wizard (a report confirmed on the reports page, an assessment redone
 * later) and then sends the user somewhere they have already been.
 *
 * Only steps whose completion can be observed are represented. Nothing here
 * marks a step done because the user visited a screen.
 *
 * The internal architecture is not visible in any of this. There is no
 * orchestrator step, no agent step, no MCP step -- those are how the plan is
 * produced, not things the user does.
 */

export const STAGE = Object.freeze({
  ABOUT_YOU: "about_you",
  LIFESTYLE: "lifestyle",
  HEALTH_INFO: "health_info",
  ASSESSMENT: "assessment",
  PLAN: "plan",
  FOLLOW: "follow",
  PROGRESS: "progress",
});

/**
 * The steps as the user sees them, in order.
 *
 * `optional: true` means the journey does not stall here -- the user can move
 * past it without doing it, and skipping it is a legitimate end state, not an
 * incomplete one.
 */
export const STAGE_STEPS = Object.freeze([
  {
    id: STAGE.ABOUT_YOU,
    title: "About you",
    description: "A few basics so guidance fits your situation.",
    path: "/onboarding",
  },
  {
    id: STAGE.LIFESTYLE,
    title: "Your lifestyle",
    description: "How you currently move through a typical day.",
    path: "/onboarding",
  },
  {
    id: STAGE.HEALTH_INFO,
    title: "Health information",
    description: "Optional. Add a report if you have one to hand.",
    path: "/reports",
    optional: true,
  },
  {
    id: STAGE.ASSESSMENT,
    title: "Movement assessment",
    description: "Three short movement checks, using your camera.",
    path: "/assessment",
  },
  {
    id: STAGE.PLAN,
    title: "Your personalised plan",
    description: "Prepared from your assessment and anything you confirmed.",
    path: "/plan",
  },
  {
    id: STAGE.FOLLOW,
    title: "Follow your plan",
    description: "Record what you actually do, when you do it.",
    path: "/plan",
  },
  {
    id: STAGE.PROGRESS,
    // Not a step that finishes. Progress is the loop the user stays in --
    // follow the plan, see what changed, get an updated plan -- so it has no
    // completion condition and is never returned as "the next thing to do".
    // Marking it terminal is what lets the journey report that setup is done
    // instead of prompting forever.
    ongoing: true,
    title: "Track progress",
    description: "What changed, and what that means for your plan.",
    path: "/progress",
  },
]);

function profileComplete(profile) {
  // profile/summary reports its own completeness; this never re-derives it
  // from individual fields, which would disagree with the server the moment
  // the questionnaire changes.
  if (!profile) {
    return false;
  }

  return Boolean(profile.profile_complete ?? profile.complete ?? false);
}

function assessmentComplete(assessment) {
  if (!assessment) {
    return false;
  }

  // A session exists. Whether all three checks produced a usable measurement
  // is a separate question the assessment screen already reports -- an
  // attempted session is enough to have moved past this step, because
  // requiring three usable results would trap a user whose camera conditions
  // are poor in a step they cannot leave.
  return true;
}

/**
 * Where the user is in the journey, and what is next.
 *
 * Every input is optional and may be null while still loading; an unknown
 * input is treated as "not done yet" rather than assumed complete, so the
 * journey never skips a step because data had not arrived.
 */
export function deriveJourney({
  profile = null,
  assessment = null,
  workflow = null,
  hasPlan = false,
  hasActivity = false,
} = {}) {
  const completed = new Set();

  if (profileComplete(profile)) {
    completed.add(STAGE.ABOUT_YOU);
    completed.add(STAGE.LIFESTYLE);
  }

  // Health information is optional, and "skipped" is a completed state for
  // it. It counts as addressed once the user has any confirmed report, or
  // once they have moved past it by completing an assessment.
  if (workflow?.medical_context_confirmed || assessmentComplete(assessment)) {
    completed.add(STAGE.HEALTH_INFO);
  }

  if (assessmentComplete(assessment)) {
    completed.add(STAGE.ASSESSMENT);
  }

  if (hasPlan) {
    completed.add(STAGE.PLAN);
  }

  if (hasActivity) {
    completed.add(STAGE.FOLLOW);
  }

  const steps = STAGE_STEPS.map((step) => ({
    ...step,
    complete: completed.has(step.id),
  }));

  // The next step is the first incomplete one that is neither optional nor
  // ongoing. An optional step is offered, never demanded, so it cannot block
  // the journey; an ongoing step has no end, so demanding it would prompt a
  // user who has already arrived there forever.
  const demanded = steps.filter((step) => !step.optional && !step.ongoing);

  const next = demanded.find((step) => !step.complete) ?? null;

  return {
    steps,
    next,
    currentStageId: next ? next.id : STAGE.PROGRESS,
    complete: next === null,
  };
}
