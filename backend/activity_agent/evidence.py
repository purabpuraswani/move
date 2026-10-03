"""The Exercise & Physical Activity domain view of the User State.

This is the input filter, in code: the agent is handed this view and
never the whole User State, so it cannot read a medical report, a sleep
answer or a balance measurement even by accident. Everything it is given
is something a physical-activity specialist would legitimately ask about.

What is deliberately NOT in this view:
  * medical_context  -- safety's evidence, not activity's;
  * sleep / fatigue  -- recovery's domain;
  * nutrition        -- nutrition's domain;
  * per-test movement measurements -- physiotherapy's domain. Only the
    *levels* the Need Assessment already derived are passed, and only so
    activity progression can be paced against them; the raw angles and
    hold times are not needed to decide how far someone should walk.
"""

from orchestration.evidence import KNOWN, MISSING, signal

# The physical need dimensions activity pacing is allowed to look at --
# as levels only, never as raw measurements.
PACING_NEED_DIMENSIONS = ("functional_movement_need", "stability_need")


def _questionnaire(user_state: dict) -> dict:
    section = user_state.get("questionnaire") or {}

    return (section.get("data") or {}) if section.get("available") else {}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def build_activity_view(
    user_state: dict,
    *,
    exercise_results: list = None,
    recovery_constraint: dict = None,
) -> dict:
    """Build the activity domain view.

    `recovery_constraint` is the Recovery specialist's own output for this
    cycle, passed in by the Orchestrator when Recovery ran first. It is the
    one piece of another domain's reasoning this agent sees, and it can
    only ever slow progression down -- never speed it up, and never add a
    recommendation of its own. Coordination, not delegation.
    """

    answers = _questionnaire(user_state)

    steps = _number(answers.get("daily_steps"))
    days = _number(answers.get("exercise_days"))
    minutes = _number(answers.get("exercise_minutes"))
    sitting = _number(answers.get("daily_sitting_hours"))
    work_type = answers.get("work_type") or None

    weekly_minutes = days * minutes if days is not None and minutes is not None else None

    signals = {
        "daily_steps": signal("daily_steps", steps, label="Daily steps", unit="steps/day"),
        "exercise_days": signal("exercise_days", days, label="Exercise frequency", unit="days/week"),
        "exercise_minutes": signal(
            "exercise_minutes", minutes, label="Typical session length", unit="minutes"
        ),
        "weekly_exercise_minutes": signal(
            "weekly_exercise_minutes", weekly_minutes, label="Weekly exercise volume", unit="minutes/week"
        ),
        "daily_sitting_hours": signal(
            "daily_sitting_hours", sitting, label="Daily sitting time", unit="hours/day"
        ),
        "work_type": signal("work_type", work_type, label="Work pattern"),
    }

    # Recorded sessions are volume evidence, not performance evidence: how
    # many sessions were logged, never how well they went (that reading
    # belongs to behaviour adherence and to physio's own result history).
    if exercise_results is None:
        signals["recorded_sessions"] = signal(
            "recorded_sessions", None, label="Logged exercise sessions", state=MISSING
        )
    else:
        completed = sum(
            1
            for entry in exercise_results
            if isinstance(entry, dict) and entry.get("status") == "completed"
        )
        signals["recorded_sessions"] = signal(
            "recorded_sessions", completed, label="Logged exercise sessions", unit="sessions", state=KNOWN
        )

    needs = user_state.get("current_needs") or {}
    need_data = (needs.get("data") or {}) if needs.get("available") else {}

    pacing_levels = {
        dimension: (need_data.get(dimension) or {}).get("level")
        for dimension in PACING_NEED_DIMENSIONS
        if (need_data.get(dimension) or {}).get("level")
    }

    return {
        "signals": signals,
        "pacing_need_levels": pacing_levels,
        "recovery_constraint": recovery_constraint or None,
    }
