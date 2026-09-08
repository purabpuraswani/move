"""The Exercise data shape, and validation for it.

Deliberately a plain dict schema, validated by a function, in the same style
as assessments/schema.py and reports/schema.py rather than introducing an
ORM/pydantic model for what is, in Phase 2, static developer-authored data
(see data.py) — there is no user input to parse here yet. If exercises move
to a database in a later phase, this validator is what a write path would
run a candidate document through before accepting it.
"""

# Deliberately aligned with need_assessment.schema.NEED_DIMENSIONS' naming
# (mobility_need, stability_need, functional_movement_need) plus "strength",
# which the Need Profile does not track as its own dimension but which the
# exercise library still needs to describe what an exercise trains. Using
# "stability" here (not "balance") is intentional, so a future Physio Agent
# can match an exercise's target_capability directly against a Need Profile
# dimension name without a translation table.
TARGET_CAPABILITIES = (
    "mobility",
    "stability",
    "strength",
    "functional_movement",
)

TARGET_BODY_AREAS = (
    "shoulders",
    "arms",
    "legs",
    "hips",
    "ankles",
    "calves",
    "core",
    "knees",
)

DIFFICULTY_LEVELS = ("beginner", "intermediate", "advanced")

CATEGORIES = (
    "lower_body_strength",
    "upper_body_strength",
    "balance_training",
    "mobility_training",
)

REQUIRED_FIELDS = (
    "exercise_id",
    "name",
    "category",
    "target_capability",
    "target_body_area",
    "difficulty",
    "equipment",
    "instructions",
    "sets",
    "repetitions",
    "duration_seconds",
    "progression",
    "regression",
    "common_mistakes",
    "safety_constraints",
    "movenet_support",
    "measurable_metrics",
    "demonstration_id",
    "reference",
)


class ExerciseValidationError(ValueError):
    """Raised when an exercise document does not have a valid shape."""


def _fail(message: str):
    raise ExerciseValidationError(message)


def _non_empty_string_list(value, label: str) -> None:
    if not isinstance(value, list) or not value:
        _fail(f"{label} must be a non-empty list")

    if any(not isinstance(item, str) or not item.strip() for item in value):
        _fail(f"{label} must contain only non-empty strings")


def _closed_list(value, label: str, allowed) -> None:
    if not isinstance(value, list) or not value:
        _fail(f"{label} must be a non-empty list")

    unknown = [item for item in value if item not in allowed]

    if unknown:
        _fail(f"{label} contains unrecognised value(s): {', '.join(map(str, unknown))}")


def _validate_movenet_support(value, label: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")

    if set(value) != {"supported", "implemented", "metrics", "notes"}:
        _fail(f"{label} must have exactly supported/implemented/metrics/notes")

    if not isinstance(value["supported"], bool):
        _fail(f"{label}.supported must be a boolean")

    if not isinstance(value["implemented"], bool):
        _fail(f"{label}.implemented must be a boolean")

    if value["implemented"] and not value["supported"]:
        _fail(f"{label}.implemented cannot be true when supported is false")

    if not isinstance(value["metrics"], list) or any(
        not isinstance(item, str) for item in value["metrics"]
    ):
        _fail(f"{label}.metrics must be a list of strings")

    if value["implemented"] and not value["metrics"]:
        _fail(
            f"{label} claims an implemented movement assessment but names no "
            "metrics it produces"
        )

    if not value["supported"] and value["metrics"]:
        _fail(
            f"{label} names metrics for an exercise marked as not "
            "MoveNet-supported"
        )

    if value["notes"] is not None and not isinstance(value["notes"], str):
        _fail(f"{label}.notes must be null or a string")


def validate_exercise(exercise) -> None:
    """Raise ExerciseValidationError if `exercise` is not a well-formed
    library entry. Checks structure and closed vocabularies; does not (and
    cannot) verify that the exercise is clinically appropriate — that is a
    human physiotherapist review, not a runtime check.
    """

    if not isinstance(exercise, dict):
        _fail("an exercise must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in exercise]

    if missing:
        _fail(f"exercise is missing field(s): {', '.join(missing)}")

    unexpected = set(exercise) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"exercise has unexpected field(s): {', '.join(sorted(unexpected))}")

    if (
        not isinstance(exercise["exercise_id"], str)
        or not exercise["exercise_id"]
        or not all(ch.islower() or ch.isdigit() or ch == "-" for ch in exercise["exercise_id"])
    ):
        _fail("exercise_id must be a non-empty kebab-case string")

    if not isinstance(exercise["name"], str) or not exercise["name"].strip():
        _fail("name must be a non-empty string")

    if exercise["category"] not in CATEGORIES:
        _fail(f"category must be one of {', '.join(CATEGORIES)}")

    _closed_list(exercise["target_capability"], "target_capability", TARGET_CAPABILITIES)
    _closed_list(exercise["target_body_area"], "target_body_area", TARGET_BODY_AREAS)

    if exercise["difficulty"] not in DIFFICULTY_LEVELS:
        _fail(f"difficulty must be one of {', '.join(DIFFICULTY_LEVELS)}")

    if not isinstance(exercise["equipment"], list) or any(
        not isinstance(item, str) for item in exercise["equipment"]
    ):
        _fail("equipment must be a list of strings (empty list means none needed)")

    _non_empty_string_list(exercise["instructions"], "instructions")
    _non_empty_string_list(exercise["common_mistakes"], "common_mistakes")
    _non_empty_string_list(exercise["safety_constraints"], "safety_constraints")

    for field in ("sets", "repetitions"):
        value = exercise[field]

        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
            _fail(f"{field} must be null or a positive integer")

    duration = exercise["duration_seconds"]

    if duration is not None and (
        isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0
    ):
        _fail("duration_seconds must be null or a positive number")

    if exercise["repetitions"] is None and exercise["duration_seconds"] is None:
        _fail(
            "an exercise must specify either repetitions or duration_seconds "
            "(how is 'one set' of it measured otherwise?)"
        )

    for field in ("progression", "regression"):
        value = exercise[field]

        if value is not None and (not isinstance(value, str) or not value.strip()):
            _fail(f"{field} must be null or a non-empty description string")

    _validate_movenet_support(exercise["movenet_support"], "movenet_support")

    if not isinstance(exercise["measurable_metrics"], list) or any(
        not isinstance(item, str) for item in exercise["measurable_metrics"]
    ):
        _fail("measurable_metrics must be a list of strings")

    if set(exercise["measurable_metrics"]) != set(exercise["movenet_support"]["metrics"]):
        _fail(
            "measurable_metrics must match movenet_support.metrics exactly — "
            "one is not a separate claim from the other"
        )

    if (
        not isinstance(exercise["demonstration_id"], str)
        or not exercise["demonstration_id"]
    ):
        _fail("demonstration_id must be a non-empty string")

    if exercise["reference"] is not None and not isinstance(exercise["reference"], str):
        _fail("reference must be null or a string")
