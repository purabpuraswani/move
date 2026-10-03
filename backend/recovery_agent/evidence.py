"""The Recovery & Care domain view of the User State.

The input filter for this specialist, in code. Recovery reasons about
rest, sleep and how much work the user has recently asked of themselves
-- nothing else. It is not given medical context (safety's evidence),
nutrition answers, or raw movement measurements, and it cannot select or
modify an exercise.

Workload is read as *volume only*: how many sessions the current
programme asks for and how many were recorded. How well a session went
is not recovery's evidence, and an unmeasurable session is never read
here as fatigue.
"""

from orchestration.evidence import KNOWN, MISSING, signal

# Self-reported sleep quality values this project recognises as a reason
# to look at rest. Any other string is treated as an unrecognised answer
# (MISSING), never guessed at.
SLEEP_QUALITY_CONCERN_VALUES = frozenset({"poor", "fair", "restless"})
SLEEP_QUALITY_KNOWN_VALUES = frozenset({"good", "excellent"}) | SLEEP_QUALITY_CONCERN_VALUES


def _questionnaire(user_state: dict) -> dict:
    section = user_state.get("questionnaire") or {}

    return (section.get("data") or {}) if section.get("available") else {}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _active_plan(user_state: dict) -> dict:
    section = user_state.get("exercise_history") or {}

    if not section.get("available"):
        return {}

    plans = (section.get("data") or {}).get("plans") or []

    return plans[-1] if plans else {}


def build_recovery_view(user_state: dict, *, exercise_results: list = None) -> dict:
    """Build the recovery domain view from sleep answers and workload."""

    answers = _questionnaire(user_state)

    sleep_hours = _number(answers.get("sleep_hours"))
    raw_quality = answers.get("sleep_quality")
    quality = (
        str(raw_quality).lower()
        if isinstance(raw_quality, str) and str(raw_quality).lower() in SLEEP_QUALITY_KNOWN_VALUES
        else None
    )

    plan = _active_plan(user_state)
    planned = len(plan.get("exercise_ids") or []) if plan else None

    signals = {
        "sleep_hours": signal("sleep_hours", sleep_hours, label="Sleep duration", unit="hours/night"),
        "sleep_quality": signal("sleep_quality", quality, label="Self-reported sleep quality"),
        "planned_exercises": signal(
            "planned_exercises", planned, label="Exercises in the current programme", unit="exercises"
        ),
    }

    if exercise_results is None:
        signals["completed_sessions"] = signal(
            "completed_sessions", None, label="Recorded sessions", state=MISSING
        )
    else:
        completed = sum(
            1
            for entry in exercise_results
            if isinstance(entry, dict) and entry.get("status") == "completed"
        )
        signals["completed_sessions"] = signal(
            "completed_sessions", completed, label="Recorded sessions", unit="sessions", state=KNOWN
        )

    return {"signals": signals}
