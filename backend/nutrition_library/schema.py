"""The Nutrition Guidance data shape, and validation for it.

Same discipline as exercise_library/schema.py: a plain dict schema over
static, developer-authored content (see data.py), validated by a function
rather than an ORM/pydantic model, because there is no user input being
parsed here — only a closed set of general wellness guidance topics.

`topic_id` names a nutrition GOAL AREA this project can give general
guidance on (e.g. "increase_fruit_vegetable_intake"), never a nutrient
deficiency, a disease, or a diagnosis. `target_signal` names which of the
four self-reported Phase 4 nutrition questions
(user_state/schema.py's `nutrition` section) a topic is relevant to, so the
catalog can be searched the same way exercise_library is searched by
target_capability.
"""

TARGET_SIGNALS = (
    "meal_pattern",
    "fruit_vegetable_servings",
    "water_glasses_per_day",
    "processed_food_frequency",
)

CATEGORIES = (
    "meal_regularity",
    "fruit_vegetable_intake",
    "hydration",
    "processed_food_reduction",
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


class NutritionGuidanceValidationError(ValueError):
    """Raised when a nutrition guidance document does not have a valid shape."""


def _fail(message: str):
    raise NutritionGuidanceValidationError(message)


def _non_empty_string_list(value, label: str) -> None:
    if not isinstance(value, list) or not value:
        _fail(f"{label} must be a non-empty list")

    if any(not isinstance(item, str) or not item.strip() for item in value):
        _fail(f"{label} must contain only non-empty strings")


def validate_nutrition_topic(topic) -> None:
    """Raise NutritionGuidanceValidationError if `topic` is not well-formed.

    Checks structure and closed vocabularies only — it cannot and does not
    verify clinical correctness. A healthcare/nutrition reviewer should
    treat every entry in data.py as a draft to correct, exactly as
    exercise_library/schema.py says of its own content.
    """

    if not isinstance(topic, dict):
        _fail("a nutrition guidance topic must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in topic]

    if missing:
        _fail(f"nutrition topic is missing field(s): {', '.join(missing)}")

    unexpected = set(topic) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"nutrition topic has unexpected field(s): {', '.join(sorted(unexpected))}")

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
