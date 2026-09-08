"""Deterministic reassessment-required check.

A system-decision configuration value, not a clinical timing
recommendation — see module docstring discipline shared with
need_assessment/rules.py. This project has no scheduling mechanism (Phase
4's mcp_servers/behaviour_server.py docstring already establishes this),
so this check only ever answers "is the most recent physical assessment
too old, or missing, to trust for a progress comparison right now" — it
never invents a recurring schedule ("every 2 weeks") the application does
not enforce anywhere.
"""

from datetime import datetime, timezone

# System decision, not a clinical guideline. A configurable project-level
# constant, per the Phase 5 brief's explicit instruction not to invent a
# clinical timing recommendation.
REASSESSMENT_STALE_AFTER_DAYS = 30


def _parse_timestamp(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value

        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        except ValueError:
            return None

    return None


def check_reassessment_required(current_assessment_completed_at, *, now: datetime = None) -> dict:
    """Return {"required": bool, "reason": str}.

    `current_assessment_completed_at` is the `completed_at` field of the
    most recent physical assessment document, or None if the user has
    never completed one. `now` is injectable for deterministic testing;
    defaults to the real current time.
    """

    now = now or datetime.now(timezone.utc)

    if current_assessment_completed_at is None:
        return {
            "required": True,
            "reason": (
                "No physical assessment has been completed yet, so progress "
                "cannot be evaluated against a baseline at all."
            ),
        }

    completed_at = _parse_timestamp(current_assessment_completed_at)

    if completed_at is None:
        return {
            "required": True,
            "reason": (
                "The most recent physical assessment's completion timestamp "
                "could not be read, so its age cannot be confirmed."
            ),
        }

    age_days = (now - completed_at).total_seconds() / 86400

    if age_days > REASSESSMENT_STALE_AFTER_DAYS:
        return {
            "required": True,
            "reason": (
                f"The most recent physical assessment is {age_days:.0f} days "
                f"old, past this project's {REASSESSMENT_STALE_AFTER_DAYS}-day "
                "threshold for a current physical comparison."
            ),
        }

    return {
        "required": False,
        "reason": (
            f"The most recent physical assessment is {age_days:.0f} days old, "
            f"within this project's {REASSESSMENT_STALE_AFTER_DAYS}-day "
            "threshold."
        ),
    }
