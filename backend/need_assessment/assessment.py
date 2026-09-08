"""Assembling a Need Profile from a User State, and writing it back.

    assemble_need_profile(user_state)   -> a validated Need Profile
    apply_need_profile(user_state, ...) -> a new User State with
                                            current_needs populated

Both functions are pure: they read their arguments and return a new value,
never mutate the User State dict they were given in place. That keeps the
User State the single source of truth described in Phase 0 — the only way
`current_needs` changes is by calling apply_need_profile() and using its
return value, never by reaching into a state dict and setting a key.
"""

from datetime import datetime, timezone

from need_assessment.rules import (
    assess_behaviour_need,
    assess_exercise_need,
    assess_functional_movement_need,
    assess_mobility_need,
    assess_nutrition_need,
    assess_safety_status,
    assess_stability_need,
)
from need_assessment.schema import NEED_PROFILE_SCHEMA_VERSION, validate_need_profile
from orchestration.ids import start_workflow
from user_state.schema import validate_user_state

NEED_LEVEL_PRIORITY = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NOT_ASSESSED": 0}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _overall_summary(dimension_entries: dict) -> dict:
    """A plain, non-clinical rollup of the dimension entries.

    Deliberately just counts and names dimensions — it does not compute a
    single blended "risk score" for the whole person, which would invite
    exactly the kind of unexplainable, over-precise output Phase 1 rules out.
    """

    assessed = {
        name: entry for name, entry in dimension_entries.items()
        if entry["level"] != "NOT_ASSESSED"
    }

    not_assessed = [
        name for name in dimension_entries if name not in assessed
    ]

    high = sorted(name for name, entry in assessed.items() if entry["level"] == "HIGH")
    medium = sorted(
        name for name, entry in assessed.items() if entry["level"] == "MEDIUM"
    )
    low = sorted(name for name, entry in assessed.items() if entry["level"] == "LOW")

    if high:
        headline = (
            "HIGH need identified in: " + ", ".join(high) + "."
        )
    elif medium:
        headline = "MEDIUM need identified in: " + ", ".join(medium) + "."
    elif low:
        headline = "No dimension exceeded a LOW need."
    else:
        headline = "No dimension could be assessed from the available data."

    return {
        "headline": headline,
        "dimensionsAtHigh": high,
        "dimensionsAtMedium": medium,
        "dimensionsAtLow": low,
        "dimensionsNotAssessed": sorted(not_assessed),
        "assessedCount": len(assessed),
        "notAssessedCount": len(not_assessed),
    }


def assemble_need_profile(
    user_state: dict, *, workflow_id: str = None, request_id: str = None
) -> dict:
    """Derive a validated Need Profile from a User State.

    `workflow_id`/`request_id` let a caller continue an existing workflow's
    tracing (see backend/orchestration/ids.py); if neither is given, a new
    workflow is started. This function never generates an agent_run_id or a
    tool_call_id — Need Assessment is not a specialist agent run in the sense
    orchestration.agent_result.py defines, so it does not claim to be one.
    """

    validate_user_state(user_state)

    if workflow_id is None and request_id is None:
        trace = start_workflow()
        workflow_id, request_id = trace.workflow_id, trace.request_id
    elif workflow_id is None or request_id is None:
        raise ValueError(
            "workflow_id and request_id must be given together, or both "
            "omitted to start a new workflow"
        )

    mobility = assess_mobility_need(user_state)
    stability = assess_stability_need(user_state)
    functional_movement = assess_functional_movement_need(user_state)
    behaviour = assess_behaviour_need(user_state)
    nutrition = assess_nutrition_need(user_state)
    exercise = assess_exercise_need(
        user_state,
        mobility=mobility,
        stability=stability,
        functional_movement=functional_movement,
        behaviour=behaviour,
    )
    safety_status = assess_safety_status(user_state)

    dimension_entries = {
        "mobility_need": mobility,
        "stability_need": stability,
        "functional_movement_need": functional_movement,
        "behaviour_need": behaviour,
        "nutrition_need": nutrition,
        "exercise_need": exercise,
    }

    profile = {
        "assessmentVersion": NEED_PROFILE_SCHEMA_VERSION,
        **dimension_entries,
        "safety_status": safety_status,
        "overallSummary": _overall_summary(dimension_entries),
        "metadata": {
            "assessmentVersion": NEED_PROFILE_SCHEMA_VERSION,
            "generatedAt": _now_iso(),
            "workflowId": workflow_id,
            "requestId": request_id,
        },
    }

    validate_need_profile(profile)

    return profile


def apply_need_profile(user_state: dict, need_profile: dict) -> dict:
    """Return a new User State with `current_needs` set from `need_profile`.

    Does not mutate `user_state`. This is the only sanctioned way
    `current_needs` is populated — a future Orchestrator or specialist agent
    reads it, and nothing (this module included) writes any other section of
    the User State from here. Per the Phase 0/1 design, agents will never be
    given free rein to poke arbitrary fields into the User State; this single
    function is the entire surface for this one, specific update.
    """

    validate_user_state(user_state)
    validate_need_profile(need_profile)

    updated = dict(user_state)
    updated["current_needs"] = {
        "available": True,
        "reason": None,
        "data": need_profile,
    }

    validate_user_state(updated)

    return updated


def run_need_assessment(
    user_state: dict, *, workflow_id: str = None, request_id: str = None
) -> dict:
    """Convenience wrapper: assemble a Need Profile and apply it in one call.

    Returns the updated User State (with current_needs populated), not the
    bare Need Profile — most callers want the state to persist, and can read
    `result["current_needs"]["data"]` for the profile itself.
    """

    profile = assemble_need_profile(
        user_state, workflow_id=workflow_id, request_id=request_id
    )

    return apply_need_profile(user_state, profile)
