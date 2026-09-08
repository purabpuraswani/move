"""The Habit Plan shape: what the Behaviour Agent actually produces.

A habit/behaviour-change suggestion, never a psychological intervention or
a mental-health treatment claim. Mirrors physio_agent/plan_schema.py and
nutrition_agent/plan_schema.py's discipline exactly.
"""

from datetime import datetime, timezone
from uuid import uuid4

PLAN_REQUIRED_FIELDS = ("plan_id", "created_at", "goal", "habit_goals")

GOAL_ENTRY_REQUIRED_FIELDS = (
    "topic_id",
    "practical_goal",
    "rationale",
    "safety_notes",
)

# The structured decision fields a Behaviour Agent decision carries. Optional
# rather than required, so every existing caller and test that builds an
# entry without them still produces a valid entry -- and validated strictly
# whenever they ARE present, so a decision can never claim an adherence
# status or a decision type this system does not actually produce.
#
#   target_signal     which self-reported signal this goal was chosen for.
#   decision_type     what the agent did with this goal this cycle.
#   evidence_used     what the decision was actually made from.
#   evidence_needed   what would let the agent decide better next time.
#   adherence_status  what the recorded evidence says about following it --
#                     including, explicitly, that nothing is known.
GOAL_ENTRY_OPTIONAL_FIELDS = (
    "target_signal",
    "decision_type",
    "evidence_used",
    "evidence_needed",
    "adherence_status",
)

# ADD on a first plan; MAINTAIN / MODIFY / REMOVE once there is a plan to
# adapt. Deliberately not the six physio types: a nutrition or habit goal
# has no harder or easier version to move between, so PROGRESS and REGRESS
# would be decision types nothing could ever produce.
DECISION_TYPES = ("ADD", "MAINTAIN", "MODIFY", "REMOVE")

# What is actually known about following this goal. KNOWN means real
# recorded evidence exists and was used. NOT_LOGGED means the user recorded
# nothing -- which is a fact about logging, never a claim that they did not
# follow the goal. UNKNOWN means there is not enough evidence to say either
# way. There is deliberately no value meaning "assumed".
ADHERENCE_STATUSES = ("KNOWN", "NOT_LOGGED", "UNKNOWN")

DIAGNOSTIC_LANGUAGE_DENYLIST = (
    "diagnos",
    "treats your",
    "cures",
    "disorder",
    "disease",
    "syndrome",
    "prescri",
    "medical condition",
    "mental illness",
    "therapy",
    "treatment for",
)


class HabitPlanValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Habit Plan."""


def _fail(message: str):
    raise HabitPlanValidationError(message)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_plan_id() -> str:
    return f"habit_plan_{uuid4().hex}"


def build_habit_goal_entry(
    *,
    topic_id: str,
    practical_goal: str,
    rationale: str,
    safety_notes: list = None,
    target_signal: str = None,
    decision_type: str = None,
    evidence_used: list = None,
    evidence_needed: list = None,
    adherence_status: str = None,
) -> dict:
    entry = {
        "topic_id": topic_id,
        "practical_goal": practical_goal,
        "rationale": rationale,
        "safety_notes": safety_notes if safety_notes is not None else [],
    }

    # Only added when actually supplied, so an entry built by a caller that
    # makes no structured decision stays byte-identical to before.
    for key, value in (
        ("target_signal", target_signal),
        ("decision_type", decision_type),
        ("evidence_used", evidence_used),
        ("evidence_needed", evidence_needed),
        ("adherence_status", adherence_status),
    ):
        if value is not None:
            entry[key] = value

    validate_habit_goal_entry(entry)

    return entry


def build_habit_plan(*, goal: str, habit_goals: list, created_at: str = None) -> dict:
    plan = {
        "plan_id": new_plan_id(),
        "created_at": created_at or _now_iso(),
        "goal": goal,
        "habit_goals": habit_goals,
    }

    validate_habit_plan(plan)

    return plan


def validate_habit_goal_entry(entry) -> None:
    if not isinstance(entry, dict):
        _fail("a habit goal entry must be an object")

    missing = [f for f in GOAL_ENTRY_REQUIRED_FIELDS if f not in entry]

    if missing:
        _fail(f"habit goal entry missing field(s): {', '.join(missing)}")

    unexpected = set(entry) - set(GOAL_ENTRY_REQUIRED_FIELDS) - set(
        GOAL_ENTRY_OPTIONAL_FIELDS
    )

    if unexpected:
        _fail(f"habit goal entry has unexpected field(s): {', '.join(sorted(unexpected))}")

    if "decision_type" in entry and entry["decision_type"] not in DECISION_TYPES:
        _fail(f"decision_type must be one of {', '.join(DECISION_TYPES)}")

    if "adherence_status" in entry and entry["adherence_status"] not in (
        ADHERENCE_STATUSES
    ):
        _fail(f"adherence_status must be one of {', '.join(ADHERENCE_STATUSES)}")

    for field in ("evidence_used", "evidence_needed"):
        if field in entry and (
            not isinstance(entry[field], list)
            or any(not isinstance(item, str) or not item for item in entry[field])
        ):
            _fail(f"{field} must be a list of non-empty strings when present")

    if not isinstance(entry["topic_id"], str) or not entry["topic_id"]:
        _fail("topic_id must be a non-empty string")

    if not isinstance(entry["practical_goal"], str) or not entry["practical_goal"].strip():
        _fail("practical_goal must be a non-empty string")

    if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
        _fail("rationale must be a non-empty string")

    _check_no_diagnostic_language(entry["rationale"])
    _check_no_diagnostic_language(entry["practical_goal"])

    if not isinstance(entry["safety_notes"], list) or any(
        not isinstance(item, str) for item in entry["safety_notes"]
    ):
        _fail("safety_notes must be a list of strings")


def validate_habit_plan(plan) -> None:
    if not isinstance(plan, dict):
        _fail("a habit plan must be an object")

    missing = [f for f in PLAN_REQUIRED_FIELDS if f not in plan]

    if missing:
        _fail(f"habit plan missing field(s): {', '.join(missing)}")

    unexpected = set(plan) - set(PLAN_REQUIRED_FIELDS)

    if unexpected:
        _fail(f"habit plan has unexpected field(s): {', '.join(sorted(unexpected))}")

    if not isinstance(plan["plan_id"], str) or not plan["plan_id"]:
        _fail("plan_id must be a non-empty string")

    if not isinstance(plan["created_at"], str) or not plan["created_at"]:
        _fail("created_at must be a non-empty ISO timestamp string")

    if not isinstance(plan["goal"], str) or not plan["goal"].strip():
        _fail("goal must be a non-empty string")

    if not isinstance(plan["habit_goals"], list):
        _fail("habit_goals must be a list")

    for entry in plan["habit_goals"]:
        validate_habit_goal_entry(entry)


def _check_no_diagnostic_language(text: str) -> None:
    lowered = text.lower()

    for phrase in DIAGNOSTIC_LANGUAGE_DENYLIST:
        if phrase in lowered:
            _fail(
                f"text contains diagnostic/clinical/therapeutic language "
                f"({phrase!r}) — describe a general habit-formation goal, "
                "never a claim about diagnosing or treating a condition"
            )
