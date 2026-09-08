/**
 * The three states the plan screen can be in — and nothing else.
 *
 * This module exists because collapsing them is what made the product feel
 * broken. A user who finished a movement assessment, whose workflow ran and
 * returned 200, was shown the same screen as somebody who had just signed
 * up: "No plan yet — once you have completed your movement assessment, your
 * plan can be prepared." That sentence was false, and it was the only thing
 * the screen said.
 *
 *   NEVER_RUN                  Nothing has produced a usable measurement
 *                              yet. The only state in which "complete your
 *                              assessment first" is a true statement.
 *
 *   PLAN_AVAILABLE             A plan exists and can be followed.
 *
 *   NO_PLAN_SAFE_OR_SUPPORTED  The workflow ran against real evidence and
 *                              did not produce a plan. Carries what was
 *                              missing, why, and what to do next.
 *
 * The server decides which one applies (backend/workflow/response.py) and
 * sends it as `plan_state`; this module is the client's reader for it, kept
 * free of React and of any import with side effects so it can be unit
 * tested directly by `node --test`.
 *
 * The fallback below matters: an older server that does not send
 * `plan_state` must not make the screen throw or show nothing, so the state
 * is inferred from the plan flags — but only ever as PLAN_AVAILABLE or
 * NEVER_RUN, never as NO_PLAN_SAFE_OR_SUPPORTED, because that state's
 * substance (what was missing and why) can only come from the server. A
 * client that guessed it would be inventing the explanation.
 */

export const PLAN_STATES = Object.freeze({
  NEVER_RUN: "NEVER_RUN",
  PLAN_AVAILABLE: "PLAN_AVAILABLE",
  NO_PLAN_SAFE_OR_SUPPORTED: "NO_PLAN_SAFE_OR_SUPPORTED",
});

const KNOWN_STATES = new Set(Object.values(PLAN_STATES));

/**
 * Does this workflow response actually contain a plan the user can follow?
 *
 * A run can legitimately produce nothing — no need was detected, or every
 * recommendation was blocked by the Safety Gate. That is a real outcome to
 * show honestly, not an empty screen to hide.
 */
export function hasAnyPlan(workflow) {
  if (!workflow) {
    return false;
  }

  return Boolean(
    workflow.exercise_plan?.available ||
      workflow.nutrition_plan?.available ||
      workflow.behaviour_plan?.available,
  );
}

/**
 * The plan state for a workflow response, as `{ state, reason, missing,
 * nextAction }`.
 *
 * `missing` is a list of `{ capability, reason }` — the capabilities the
 * assessment could not measure, each with the reason Need Assessment itself
 * gave. Never a reason written on the client.
 */
export function planState(workflow) {
  const fromServer = workflow?.plan_state;

  if (fromServer && KNOWN_STATES.has(fromServer.state)) {
    return {
      state: fromServer.state,
      reason: fromServer.reason || null,
      missing: Array.isArray(fromServer.missing) ? fromServer.missing : [],
      nextAction: fromServer.next_action || null,
    };
  }

  // Fallback for a response with no (or an unrecognised) plan_state.
  return {
    state: hasAnyPlan(workflow)
      ? PLAN_STATES.PLAN_AVAILABLE
      : PLAN_STATES.NEVER_RUN,
    reason: null,
    missing: [],
    nextAction: null,
  };
}
