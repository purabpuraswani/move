"""The Exercise Plan shape: what the Physio Agent actually produces.

A wellness/exercise-guidance plan, not a clinical prescription — the same
distinction backend/exercise_library data already draws (progression/
regression text, never a prescribed dosage). Each entry's `rationale` is
required and is checked (weakly, by a denylist of clinical-sounding verbs)
against drifting into diagnostic language, mirroring the discipline
need_assessment/rules.py's own docstring calls out as still just a writing
convention there — here it is at least a runtime check, closing exactly the
gap Phase 1's "known limitations" flagged for that convention.
"""

from datetime import datetime, timezone
from uuid import uuid4

PLAN_REQUIRED_FIELDS = ("plan_id", "created_at", "goal", "exercises")

EXERCISE_ENTRY_REQUIRED_FIELDS = (
    "exercise_id",
    "sets",
    "repetitions",
    "duration_seconds",
    "difficulty",
    "progression",
    "regression",
    "rationale",
    "safety_notes",
)

# The structured decision fields a Physio Agent decision carries. Optional
# rather than required so that every existing caller and test that builds an
# entry without them still produces a valid entry -- but validated strictly
# whenever they ARE present, so a decision can never carry a decision_type
# this system does not actually implement.
#
#   target_need         which need dimension this exercise was chosen for
#                       (a need_assessment dimension name), or None when the
#                       choice was not driven by one.
#   decision_type       what the agent did with this exercise this cycle.
#   measurement_method  how performance on it is actually measured, taken
#                       from the exercise library's own movenet_support --
#                       never a claim that something is measured when the
#                       library says it is not.
EXERCISE_ENTRY_OPTIONAL_FIELDS = (
    "target_need",
    "decision_type",
    "measurement_method",
)

# ADD/REMOVE/REPLACE/MAINTAIN/PROGRESS/REGRESS. An initial plan uses ADD;
# the rest become reachable when the Progress Agent's evidence drives an
# adaptation. Listed here (rather than only where they are produced) so
# there is one definition of what a decision may be.
DECISION_TYPES = (
    "ADD",
    "REMOVE",
    "REPLACE",
    "MAINTAIN",
    "PROGRESS",
    "REGRESS",
)

# How this system can actually observe an exercise being performed.
MEASUREMENT_METHODS = (
    # Browser-side MoveNet produces real, derived measurements for it.
    "movenet_derived_metrics",
    # The library says MoveNet cannot observe this movement, so the only
    # honest record is the user saying they did it.
    "manual_completion",
)

# Words that would turn a rationale into a diagnostic or prescriptive claim.
# Not exhaustive — a genuine content-safety system is later, separate work —
# but enough to catch the clearest violations of rule 11's good/bad example
# ("supports balance training" vs. "treats your balance disorder").
DIAGNOSTIC_LANGUAGE_DENYLIST = (
    "diagnos",
    "treats your",
    "cures",
    "disorder",
    "disease",
    "syndrome",
    "prescri",
    "medical condition",
)


class ExercisePlanValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Exercise Plan."""


def _fail(message: str):
    raise ExercisePlanValidationError(message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_plan_id() -> str:
    return f"plan_{uuid4().hex}"


def build_exercise_plan_entry(
    *,
    exercise_id: str,
    sets,
    repetitions,
    duration_seconds,
    difficulty: str,
    progression,
    regression,
    rationale: str,
    safety_notes: list = None,
    target_need: str = None,
    decision_type: str = None,
    measurement_method: str = None,
) -> dict:
    entry = {
        "exercise_id": exercise_id,
        "sets": sets,
        "repetitions": repetitions,
        "duration_seconds": duration_seconds,
        "difficulty": difficulty,
        "progression": progression,
        "regression": regression,
        "rationale": rationale,
        "safety_notes": safety_notes if safety_notes is not None else [],
    }

    # Only added when actually supplied, so an entry built by a caller that
    # does not make structured decisions stays byte-identical to before.
    for key, value in (
        ("target_need", target_need),
        ("decision_type", decision_type),
        ("measurement_method", measurement_method),
    ):
        if value is not None:
            entry[key] = value

    validate_exercise_plan_entry(entry)

    return entry


def build_exercise_plan(*, goal: str, exercises: list, created_at: str = None) -> dict:
    plan = {
        "plan_id": new_plan_id(),
        "created_at": created_at or _now_iso(),
        "goal": goal,
        "exercises": exercises,
    }

    validate_exercise_plan(plan)

    return plan


def validate_exercise_plan_entry(entry) -> None:
    if not isinstance(entry, dict):
        _fail("an exercise plan entry must be an object")

    missing = [f for f in EXERCISE_ENTRY_REQUIRED_FIELDS if f not in entry]

    if missing:
        _fail(f"exercise plan entry missing field(s): {', '.join(missing)}")

    unexpected = set(entry) - set(EXERCISE_ENTRY_REQUIRED_FIELDS) - set(
        EXERCISE_ENTRY_OPTIONAL_FIELDS
    )

    if unexpected:
        _fail(f"exercise plan entry has unexpected field(s): {', '.join(sorted(unexpected))}")

    if "decision_type" in entry and entry["decision_type"] not in DECISION_TYPES:
        _fail(f"decision_type must be one of {', '.join(DECISION_TYPES)}")

    if "measurement_method" in entry and entry["measurement_method"] not in (
        MEASUREMENT_METHODS
    ):
        _fail(f"measurement_method must be one of {', '.join(MEASUREMENT_METHODS)}")

    if "target_need" in entry and (
        not isinstance(entry["target_need"], str) or not entry["target_need"]
    ):
        _fail("target_need must be a non-empty string when present")

    if not isinstance(entry["exercise_id"], str) or not entry["exercise_id"]:
        _fail("exercise_id must be a non-empty string")

    for field in ("sets", "repetitions"):
        value = entry[field]

        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            _fail(f"{field} must be null or a positive integer")

    duration = entry["duration_seconds"]

    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0
    ):
        _fail("duration_seconds must be null or a positive number")

    if not isinstance(entry["difficulty"], str) or not entry["difficulty"]:
        _fail("difficulty must be a non-empty string")

    for field in ("progression", "regression"):
        value = entry[field]

        if value is not None and (not isinstance(value, str) or not value.strip()):
            _fail(f"{field} must be null or a non-empty string")

    if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
        _fail("rationale must be a non-empty string")

    _check_no_diagnostic_language(entry["rationale"])

    if not isinstance(entry["safety_notes"], list) or any(
        not isinstance(item, str) for item in entry["safety_notes"]
    ):
        _fail("safety_notes must be a list of strings")


def validate_exercise_plan(plan) -> None:
    if not isinstance(plan, dict):
        _fail("an exercise plan must be an object")

    missing = [f for f in PLAN_REQUIRED_FIELDS if f not in plan]

    if missing:
        _fail(f"exercise plan missing field(s): {', '.join(missing)}")

    unexpected = set(plan) - set(PLAN_REQUIRED_FIELDS)

    if unexpected:
        _fail(f"exercise plan has unexpected field(s): {', '.join(sorted(unexpected))}")

    if not isinstance(plan["plan_id"], str) or not plan["plan_id"]:
        _fail("plan_id must be a non-empty string")

    if not isinstance(plan["created_at"], str) or not plan["created_at"]:
        _fail("created_at must be a non-empty ISO timestamp string")

    if not isinstance(plan["goal"], str) or not plan["goal"].strip():
        _fail("goal must be a non-empty string")

    if not isinstance(plan["exercises"], list):
        _fail("exercises must be a list")

    for entry in plan["exercises"]:
        validate_exercise_plan_entry(entry)


def _check_no_diagnostic_language(rationale: str) -> None:
    lowered = rationale.lower()

    for phrase in DIAGNOSTIC_LANGUAGE_DENYLIST:
        if phrase in lowered:
            _fail(
                f"rationale contains diagnostic/clinical-sounding language "
                f"({phrase!r}) — describe support for a movement capability, "
                "never a claim about treating or diagnosing a condition"
            )
