"""The one sanctioned way a Physio Agent Result changes the User State.

Mirrors need_assessment.assessment.apply_need_profile()'s discipline
exactly: a pure function, never mutates its input, and is the only place
`exercise_history` is ever populated. No other code writes to this section
directly — the Orchestrator calls this function with a completed Physio
Agent Result, and nothing else.

Phase 5 addition: each apply_*_plan function accepts optional
`adaptation_reason` / `triggered_by` keyword arguments so a plan
version created because the Progress Agent recommended an adaptation
(rather than an initial need-based selection) carries a structured,
non-vague reason and its origin. Both default to None, so a normal,
non-adaptation plan creation is unaffected.

Only information actually known at plan-creation time is recorded: which
plan, which exercises, when. This module never claims a user performed,
completed, or benefited from an exercise before they actually did — that is
what backend/exercise_assessment/schema.py's `record_exercise_result` is
for, once real performance data exists, in a later phase.
"""

from datetime import datetime, timezone

from user_state.schema import validate_user_state

EXERCISE_HISTORY_SCHEMA_VERSION = "0.1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_physio_plan(
    user_state: dict,
    physio_agent_result: dict,
    *,
    adaptation_reason: str = None,
    triggered_by: str = None,
) -> dict:
    """Return a new User State with `exercise_history` recording a created plan.

    Raises ValueError if `physio_agent_result` did not actually produce a
    plan (status != "completed", or no plan in its findings) — this
    function only ever records a plan that was genuinely built, never an
    empty or failed run.
    """

    if physio_agent_result.get("status") != "completed":
        raise ValueError(
            "apply_physio_plan requires a completed Physio Agent Result "
            f"(got status={physio_agent_result.get('status')!r})"
        )

    plan = (physio_agent_result.get("findings") or {}).get("plan")

    if not plan or not plan.get("exercises"):
        raise ValueError(
            "apply_physio_plan requires a Physio Agent Result whose "
            "findings.plan has at least one exercise"
        )

    existing_history_section = user_state.get("exercise_history") or {}
    existing_data = (
        existing_history_section.get("data")
        if existing_history_section.get("available")
        else None
    )
    previous_plans = list((existing_data or {}).get("plans", []))

    findings = physio_agent_result.get("findings") or {}

    record = {
        "plan_id": plan["plan_id"],
        "plan_version": len(previous_plans) + 1,
        "created_at": plan["created_at"],
        "goal": plan["goal"],
        "exercise_ids": [entry["exercise_id"] for entry in plan["exercises"]],
        # The full prescription for each exercise, and the structured
        # decision behind it. Recorded because the exercise ids alone
        # cannot answer "why is this in my programme" or "what changed" —
        # before this, the Movement screen had names and set counts and
        # nothing else, so any explanation shown there would have had to be
        # written in the UI rather than read from the agent.
        "exercises": [dict(entry) for entry in plan["exercises"]],
        "decisions": [dict(entry) for entry in (findings.get("decisions") or [])],
        "selection_mode": findings.get("selection_mode"),
        "need_levels": dict(findings.get("need_levels") or {}),
        "capabilities_targeted": list(findings.get("capabilities_targeted") or []),
        "unassessed_dimensions": list(findings.get("unassessed_dimensions") or []),
        "adapted_from_plan_id": findings.get("adapted_from_plan_id"),
        "source": "physio_agent",
        "agent_run_id": physio_agent_result["metadata"]["agent_run_id"],
        "recorded_at": _now_iso(),
        # The Orchestrator's reason when it has one (a Progress-driven
        # dispatch), otherwise the agent's own summary of what it changed.
        # Never a vague "plan updated": if nothing changed, this stays None.
        "adaptation_reason": adaptation_reason or findings.get("adaptation_summary"),
        "triggered_by": triggered_by,
    }

    updated = dict(user_state)
    updated["exercise_history"] = {
        "available": True,
        "reason": None,
        "data": {
            "schemaVersion": EXERCISE_HISTORY_SCHEMA_VERSION,
            "plans": previous_plans + [record],
        },
    }

    validate_user_state(updated)

    return updated


# ---------------------------------------------------------------------------
# apply_nutrition_plan / apply_behaviour_plan — Phase 4. Same discipline as
# apply_physio_plan above, applied to the two new sections
# user_state/schema.py added for them (`nutrition_plan`, `behaviour`).
# Neither ever claims a user followed, completed, or benefited from a
# goal — only that a plan containing it was created.
# ---------------------------------------------------------------------------

NUTRITION_PLAN_HISTORY_SCHEMA_VERSION = "0.1.0"
BEHAVIOUR_PLAN_HISTORY_SCHEMA_VERSION = "0.1.0"


def apply_nutrition_plan(
    user_state: dict,
    nutrition_agent_result: dict,
    *,
    adaptation_reason: str = None,
    triggered_by: str = None,
) -> dict:
    """Return a new User State with `nutrition_plan` recording a created plan.

    Raises ValueError if `nutrition_agent_result` did not actually produce
    a plan with at least one goal.
    """

    if nutrition_agent_result.get("status") != "completed":
        raise ValueError(
            "apply_nutrition_plan requires a completed Nutrition Agent "
            f"Result (got status={nutrition_agent_result.get('status')!r})"
        )

    plan = (nutrition_agent_result.get("findings") or {}).get("plan")

    if not plan or not plan.get("nutrition_goals"):
        raise ValueError(
            "apply_nutrition_plan requires a Nutrition Agent Result whose "
            "findings.plan has at least one nutrition goal"
        )

    existing_section = user_state.get("nutrition_plan") or {}
    existing_data = (
        existing_section.get("data") if existing_section.get("available") else None
    )
    previous_plans = list((existing_data or {}).get("plans", []))

    findings = nutrition_agent_result.get("findings") or {}

    record = {
        "plan_id": plan["plan_id"],
        "plan_version": len(previous_plans) + 1,
        "created_at": plan["created_at"],
        "goal": plan["goal"],
        "topic_ids": [entry["topic_id"] for entry in plan["nutrition_goals"]],
        # The goals in full, and the structured decision behind each one.
        # The topic ids alone cannot answer "why is this my focus" or "what
        # changed", so any explanation shown to the user would otherwise
        # have had to be written in the UI rather than read from the agent.
        "goals": [dict(entry) for entry in plan["nutrition_goals"]],
        "decisions": [dict(entry) for entry in (findings.get("decisions") or [])],
        "triggered_signals": list(findings.get("triggered_signals") or []),
        "adapted_from_plan_id": findings.get("adapted_from_plan_id"),
        "source": "nutrition_agent",
        "agent_run_id": nutrition_agent_result["metadata"]["agent_run_id"],
        "recorded_at": _now_iso(),
        "adaptation_reason": adaptation_reason or findings.get("adaptation_summary"),
        "triggered_by": triggered_by,
    }

    updated = dict(user_state)
    updated["nutrition_plan"] = {
        "available": True,
        "reason": None,
        "data": {
            "schemaVersion": NUTRITION_PLAN_HISTORY_SCHEMA_VERSION,
            "plans": previous_plans + [record],
        },
    }

    validate_user_state(updated)

    return updated


def apply_behaviour_plan(
    user_state: dict,
    behaviour_agent_result: dict,
    *,
    adaptation_reason: str = None,
    triggered_by: str = None,
) -> dict:
    """Return a new User State with `behaviour` recording a created habit plan.

    Raises ValueError if `behaviour_agent_result` did not actually produce
    a plan with at least one goal.
    """

    if behaviour_agent_result.get("status") != "completed":
        raise ValueError(
            "apply_behaviour_plan requires a completed Behaviour Agent "
            f"Result (got status={behaviour_agent_result.get('status')!r})"
        )

    plan = (behaviour_agent_result.get("findings") or {}).get("plan")

    if not plan or not plan.get("habit_goals"):
        raise ValueError(
            "apply_behaviour_plan requires a Behaviour Agent Result whose "
            "findings.plan has at least one habit goal"
        )

    existing_section = user_state.get("behaviour") or {}
    existing_data = (
        existing_section.get("data") if existing_section.get("available") else None
    )
    previous_plans = list((existing_data or {}).get("plans", []))

    findings = behaviour_agent_result.get("findings") or {}

    record = {
        "plan_id": plan["plan_id"],
        "plan_version": len(previous_plans) + 1,
        "created_at": plan["created_at"],
        "goal": plan["goal"],
        "topic_ids": [entry["topic_id"] for entry in plan["habit_goals"]],
        # The goals in full, and the structured decision behind each one.
        # The topic ids alone cannot answer "why is this my focus" or "what
        # changed", so any explanation shown to the user would otherwise
        # have had to be written in the UI rather than read from the agent.
        "goals": [dict(entry) for entry in plan["habit_goals"]],
        "decisions": [dict(entry) for entry in (findings.get("decisions") or [])],
        "triggered_signals": list(findings.get("triggered_signals") or []),
        "adapted_from_plan_id": findings.get("adapted_from_plan_id"),
        "source": "behaviour_agent",
        "agent_run_id": behaviour_agent_result["metadata"]["agent_run_id"],
        "recorded_at": _now_iso(),
        "adaptation_reason": adaptation_reason or findings.get("adaptation_summary"),
        "triggered_by": triggered_by,
    }

    updated = dict(user_state)
    updated["behaviour"] = {
        "available": True,
        "reason": None,
        "data": {
            "schemaVersion": BEHAVIOUR_PLAN_HISTORY_SCHEMA_VERSION,
            "plans": previous_plans + [record],
        },
    }

    validate_user_state(updated)

    return updated


# ---------------------------------------------------------------------------
# Refreshing evidence without minting a plan version
# ---------------------------------------------------------------------------
#
# A review that decides to change nothing is still a review, and it still
# produces evidence: "you logged food on 9 of 10 days" is worth showing even
# when the conclusion is "so keep going". Writing a new plan version for it
# would be wrong -- a version the user can see should mean the plan actually
# changed -- but discarding the evidence means the specialist screen can
# never show what it has learned.
#
# So the newest plan record is updated in place: its goals/decisions and the
# evidence attached to them are replaced with what this review found, while
# plan_id, plan_version, created_at and the whole preceding history are left
# exactly as they were. Nothing is appended, so the history stays
# append-only and version numbers stay monotonic.
# ---------------------------------------------------------------------------

_EVIDENCE_FIELDS = ("goals", "exercises", "decisions", "triggered_signals")


def refresh_plan_evidence(user_state: dict, *, section_name: str, agent_result: dict) -> dict:
    """Return a new User State whose newest plan record in `section_name`
    carries this run's evidence. No new version, no change to the plan's
    identity, and the input is not mutated.

    Returns `user_state` unchanged when there is no plan to refresh or the
    agent produced nothing to refresh it with.
    """

    section = user_state.get(section_name) or {}

    if not section.get("available"):
        return user_state

    plans = list((section.get("data") or {}).get("plans") or [])

    if not plans:
        return user_state

    findings = (agent_result or {}).get("findings") or {}
    plan = findings.get("plan") or {}

    latest = dict(plans[-1])
    changed = False

    for key, value in (
        ("goals", plan.get("nutrition_goals") or plan.get("habit_goals")),
        ("exercises", plan.get("exercises")),
        ("decisions", findings.get("decisions")),
        ("triggered_signals", findings.get("triggered_signals")),
    ):
        if value:
            latest[key] = [
                dict(item) if isinstance(item, dict) else item for item in value
            ]
            changed = True

    if not changed:
        return user_state

    latest["evidence_refreshed_at"] = _now_iso()

    plans[-1] = latest

    updated = dict(user_state)
    updated[section_name] = {
        **section,
        "data": {**(section.get("data") or {}), "plans": plans},
    }

    validate_user_state(updated)

    return updated
