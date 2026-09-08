"""The Behaviour Guidance data shape, and validation for it.

Same discipline as exercise_library/schema.py and
nutrition_library/schema.py. `target_signal` names which real, already-
collected questionnaire field (user_state/schema.py's `questionnaire`
section — the same fields need_assessment.rules.assess_behaviour_need()
already reads) a topic is relevant to.
"""

TARGET_SIGNALS = (
    "daily_sitting_hours",
    "daily_screen_hours",
    "exercise_days",
    "weekly_exercise_minutes",
)

CATEGORIES = (
    "movement_breaks",
    "screen_time",
    "exercise_frequency",
    "routine_building",
)

REQUIRED_FIELDS = (
    "topic_id",
    "name",
    "category",
    "target_signal",
    "guidance",
    "practical_goal_examples",
    "common_barriers",
    "safety_notes",
    "reference",
)


class BehaviourGuidanceValidationError(ValueError):
    """Raised when a behaviour guidance document does not have a valid shape."""


def _fail(message: str):
    raise BehaviourGuidanceValidationError(message)


def _non_empty_string_list(value, label: str) -> None:
    if not isinstance(value, list) or not value:
        _fail(f"{label} must be a non-empty list")

    if any(not isinstance(item, str) or not item.strip() for item in value):
        _fail(f"{label} must contain only non-empty strings")


def validate_behaviour_topic(topic) -> None:
    if not isinstance(topic, dict):
        _fail("a behaviour guidance topic must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in topic]

    if missing:
        _fail(f"behaviour topic is missing field(s): {', '.join(missing)}")

    unexpected = set(topic) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"behaviour topic has unexpected field(s): {', '.join(sorted(unexpected))}")

    if (
        not isinstance(topic["topic_id"], str)
        or not topic["topic_id"]
        or not all(ch.islower() or ch.isdigit() or ch == "_" for ch in topic["topic_id"])
    ):
        _fail("topic_id must be a non-empty snake_case string")

    if not isinstance(topic["name"], str) or not topic["name"].strip():
        _fail("name must be a non-empty string")

    if topic["category"] not in CATEGORIES:
        _fail(f"category must be one of {', '.join(CATEGORIES)}")

    if topic["target_signal"] not in TARGET_SIGNALS:
        _fail(f"target_signal must be one of {', '.join(TARGET_SIGNALS)}")

    _non_empty_string_list(topic["guidance"], "guidance")
    _non_empty_string_list(topic["practical_goal_examples"], "practical_goal_examples")
    _non_empty_string_list(topic["common_barriers"], "common_barriers")
    _non_empty_string_list(topic["safety_notes"], "safety_notes")

    if topic["reference"] is not None and not isinstance(topic["reference"], str):
        _fail("reference must be null or a string")
