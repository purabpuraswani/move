"""How much programme this user should be given, and in what order.

The Physio Agent already chose exercises from measured movement needs.
What it did not do was vary the *shape* of the plan: a MEDIUM need and a
HIGH need triggered identically, and the lifestyle evidence the input
contract has carried since Phase 3 (`relevant_lifestyle_constraints`,
`relevant_user_profile`) was passed in and then ignored. Two users with
the same three need levels therefore received the same six exercises
whatever else was known about them.

This module is that missing step, and only that step. It never selects
an exercise, never invents a need, and never raises difficulty:

  * capability order and slot allocation follow measured SEVERITY, so a
    HIGH need gets more of the plan than a MEDIUM one;
  * a plan is made SMALLER and EASIER when the user's own activity
    answers say they are starting from very little, because six
    exercises for someone exercising once a week is a plan that will not
    be done;
  * every decision records the evidence it came from, so the plan can be
    explained from the user's data rather than asserted.

Thresholds reused from need_assessment/rules.py rather than restated, so
"low activity" means here exactly what it means there. Nothing in this
module reads medical context: that is the Safety Gate's evidence.
"""

from need_assessment.rules import (
    EXERCISE_DAYS_LOW_THRESHOLD,
    SITTING_HOURS_HIGH_THRESHOLD,
)

# Plan sizes. The default is the agent's existing cap; the reduced size is
# for a user whose own answers show a very low starting point. A system
# decision about how much change is realistic to ask for at once, not a
# clinical dose.
DEFAULT_MAX_EXERCISES = 6
REDUCED_MAX_EXERCISES = 4

# A HIGH need may take this many slots; a MEDIUM need fewer, so the
# capability the evidence is loudest about actually dominates the plan.
SLOTS_FOR_HIGH = 3
SLOTS_FOR_MEDIUM = 2

LEVEL_RANK = {"HIGH": 0, "MEDIUM": 1}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def activity_context(lifestyle_constraints, questionnaire_signals=None) -> dict:
    """What the user's own answers say about their starting point.

    Returns `{"low_activity": bool, "evidence": [...]}`. Absent answers
    produce no evidence and no conclusion -- a missing exercise-frequency
    answer is not a sedentary user, so the plan is not reduced for it.
    """

    constraints = lifestyle_constraints or {}
    signals = questionnaire_signals or {}

    sitting = _number(constraints.get("daily_sitting_hours"))
    exercise_days = _number(signals.get("exercise_days"))

    evidence = []

    if sitting is not None and sitting >= SITTING_HOURS_HIGH_THRESHOLD:
        evidence.append(
            f"self-reported sitting time is {sitting:g} hours a day"
        )

    if exercise_days is not None and exercise_days < EXERCISE_DAYS_LOW_THRESHOLD:
        evidence.append(
            f"self-reported exercise frequency is {exercise_days:g} day(s) a week"
        )

    return {"low_activity": bool(evidence), "evidence": evidence}


def plan_shape(triggers_by_capability: dict, context: dict) -> dict:
    """The size, ordering and per-capability limits for this plan.

    `triggers_by_capability` is the agent's own
    `{capability: [{dimension, level, evidence}, ...]}`. Ordering is by
    the strongest level behind each capability, so the most strongly
    evidenced capability is filled first and keeps its slots when the
    plan runs out of room.
    """

    def strongest(capability):
        levels = [trigger.get("level") for trigger in triggers_by_capability[capability]]

        return min((LEVEL_RANK.get(level, 9) for level in levels), default=9)

    # Ties keep the caller's own order, so the result stays deterministic
    # for identical evidence.
    ordered = sorted(triggers_by_capability, key=lambda name: (strongest(name), ))

    slots = {}

    for capability in ordered:
        slots[capability] = (
            SLOTS_FOR_HIGH if strongest(capability) == LEVEL_RANK["HIGH"] else SLOTS_FOR_MEDIUM
        )

    low_activity = bool(context.get("low_activity"))
    max_exercises = REDUCED_MAX_EXERCISES if low_activity else DEFAULT_MAX_EXERCISES

    notes = []

    if low_activity:
        notes.append(
            "Programme kept to "
            f"{REDUCED_MAX_EXERCISES} exercises because "
            + " and ".join(context.get("evidence") or ["activity is low"])
            + ". This is about what is realistic to repeat, not a finding "
            "about capability."
        )

    return {
        "ordered_capabilities": ordered,
        "slots": slots,
        "max_exercises": max_exercises,
        "low_activity": low_activity,
        "notes": notes,
    }


def measured_evidence(triggers) -> str:
    """The measurement behind a capability, as one phrase for a rationale.

    Uses the Need Assessment's own evidence strings -- the sentences that
    already state what was measured and in what units -- rather than
    writing a new claim about the user.
    """

    for trigger in triggers or []:
        for line in trigger.get("evidence") or []:
            if isinstance(line, str) and line.strip():
                return line.strip()

    return None
