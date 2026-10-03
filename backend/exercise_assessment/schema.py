"""Validating a submitted Exercise Result.

Mirrors backend/assessments/schema.py's discipline deliberately: structural
ceilings generous for what a real result looks like and far too small for a
frame or a keypoint sequence, plus a name-based rejection of anything that
even *looks* like pose data, as a second line of defence behind "the browser
was never going to send that in the first place."

What this module does NOT do: judge whether the reported performance is
good, whether the user should progress or regress, or anything else that
requires reasoning about the exercise. That is Physio Agent work (Phase 3).
This module only accepts or refuses a result — never scores or interprets one.
"""

from datetime import datetime

from exercise_library.catalog import ExerciseNotFoundError, get_exercise_details

STATUS_VALUES = ("completed", "incomplete", "invalid")

MAX_ARRAY_LENGTH = 16
MAX_STRING_LENGTH = 200
MAX_ERROR_CODES = 12

# Same two-tier privacy filter as assessments/schema.py: a name containing
# one of these is refused outright (no legitimate scalar meaning), and a
# name containing one of the broader POSE_RELATED terms may hold a number or
# short string but never a list or object.
FORBIDDEN_KEY_SUBSTRINGS = (
    "video",
    "framedata",
    "rawframe",
    "image",
    "pixel",
    "dataurl",
    "base64",
    "blob",
    "thumbnail",
    "snapshot",
)

POSE_RELATED_KEY_SUBSTRINGS = ("keypoint", "landmark", "pose", "skeleton", "frame")

# The only metric names this module knows about. An exercise's own
# measurable_metrics (exercise_library data) must be a subset of this list —
# enforced indirectly, since a result can never report a metric the exercise
# doesn't declare, and every metric the library declares is drawn from here.
# How this result was produced. A camera session is a measurement; a
# manual confirmation is the user saying they did the exercise. Both are
# real evidence that it happened, and they are NOT the same evidence --
# keeping them apart is what stops a ticked box from being read later as a
# measured performance (see physio_agent/adaptation.py). Results stored
# before this field existed have no `source` and are read as camera
# results, which is what they were.
SOURCE_CAMERA = "camera"
SOURCE_MANUAL = "manual_confirmation"
SOURCE_VALUES = (SOURCE_CAMERA, SOURCE_MANUAL)

KNOWN_METRICS = (
    "repetitions",
    "durationSeconds",
    "rangeOfMotion",
    "stability",
    "movementQuality",
    "symmetry",
    "completion",
)


class ExerciseResultValidationError(ValueError):
    """Raised when a submitted exercise result cannot be accepted."""


def _fail(message: str):
    raise ExerciseResultValidationError(message)


def _check_key_privacy(key: str) -> None:
    lowered = key.lower()

    for term in FORBIDDEN_KEY_SUBSTRINGS:
        if term in lowered:
            _fail(
                f"the field {key!r} is not accepted: video, images, and "
                "encoded media are never stored"
            )


def _check_value_privacy(key: str, value) -> None:
    if not isinstance(value, (list, dict)):
        return

    lowered = key.lower()

    for term in POSE_RELATED_KEY_SUBSTRINGS:
        if term in lowered:
            _fail(
                f"the field {key!r} is not accepted: a field naming pose "
                "data may hold a single summary value, not a list or object"
            )


def _validate_measurements(measurements, exercise: dict) -> dict:
    if not isinstance(measurements, dict):
        _fail("measurements must be an object")

    allowed_metrics = set(exercise["measurable_metrics"])
    cleaned = {}

    for key, value in measurements.items():
        if not isinstance(key, str) or not key:
            _fail("measurement keys must be non-empty strings")

        _check_key_privacy(key)
        _check_value_privacy(key, value)

        if key not in KNOWN_METRICS:
            _fail(
                f"{key!r} is not a recognised metric name (known: "
                f"{', '.join(KNOWN_METRICS)})"
            )

        if key not in allowed_metrics:
            _fail(
                f"exercise {exercise['exercise_id']!r} does not declare "
                f"{key!r} in its measurable_metrics — a result cannot report "
                "a metric the library doesn't say this exercise produces"
            )

        cleaned[key] = _validate_metric_value(key, value)

    return cleaned


def _validate_metric_value(key: str, value):
    if key in ("repetitions",):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _fail(f"{key} must be a non-negative integer")

        return value

    if key in ("durationSeconds", "rangeOfMotion", "stability"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            _fail(f"{key} must be a non-negative number")

        return value

    if key == "completion":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            _fail(f"{key} must be a number between 0 and 1")

        return value

    if key in ("movementQuality", "symmetry"):
        if isinstance(value, str):
            if len(value) > MAX_STRING_LENGTH:
                _fail(f"{key} must be at most {MAX_STRING_LENGTH} characters")

            return value

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(f"{key} must be a number or a short string")

        return value

    _fail(f"no validator defined for metric {key!r}")  # pragma: no cover


def _validate_errors(value) -> list:
    if value is None:
        return []

    if not isinstance(value, list) or len(value) > MAX_ERROR_CODES:
        _fail(f"errors must be a list of at most {MAX_ERROR_CODES} entries")

    for item in value:
        if not isinstance(item, str) or not item or len(item) > 64:
            _fail("each error must be a short reason-code string")

    return value


def validate_exercise_result(raw) -> dict:
    """Validate a submitted Exercise Result and return the cleaned document.

    Raises ExerciseResultValidationError for a structurally bad submission,
    or ExerciseNotFoundError if `exerciseId` does not name a real exercise —
    both are refusals, never a silently accepted best guess.
    """

    if not isinstance(raw, dict):
        _fail("an exercise result must be an object")

    unknown = set(raw) - {
        "exerciseId",
        "status",
        "startedAt",
        "completedAt",
        "measurements",
        "errors",
        "source",
    }

    if unknown:
        _fail(f"unexpected field(s): {', '.join(sorted(unknown))}")

    exercise_id = raw.get("exerciseId")

    if not isinstance(exercise_id, str) or not exercise_id:
        _fail("exerciseId is required and must be a string")

    exercise = get_exercise_details(exercise_id)  # raises ExerciseNotFoundError

    status = raw.get("status")

    if status not in STATUS_VALUES:
        _fail(f"status must be one of {', '.join(STATUS_VALUES)}")

    source = raw.get("source") or SOURCE_CAMERA

    if source not in SOURCE_VALUES:
        _fail(f"source must be one of {', '.join(SOURCE_VALUES)}")

    if source == SOURCE_MANUAL and status != "completed":
        _fail(
            "a manually confirmed result can only be 'completed' — ticking a box "
            "says the exercise was done, and it cannot report anything else"
        )

    measurements = raw.get("measurements")

    if source == SOURCE_MANUAL:
        # A tick measures nothing. Storing a manual confirmation with
        # measurements would make a self-report indistinguishable from a
        # camera reading in every consumer downstream.
        if measurements not in (None, {}):
            _fail("a manually confirmed result must not carry measurements")

        measurements = {}

    elif status == "invalid":
        if measurements not in (None, {}):
            _fail("an invalid result must not carry measurements")

        measurements = {}

    else:
        if not exercise.get("measurable_metrics"):
            if measurements not in (None, {}):
                _fail(f"{exercise['name']} is not measured by camera and must not carry metrics")
            measurements = {}
        else:
            if not isinstance(measurements, dict) or not measurements:
                _fail(f"a {status} result must carry at least one measurement")
            measurements = _validate_measurements(measurements, exercise)

    for label in ("startedAt", "completedAt"):
        value = raw.get(label)

        if value is not None and (not isinstance(value, str) or len(value) > 64):
            _fail(f"{label} must be null or an ISO 8601 timestamp string")

        if value is not None:
            text = value[:-1] + "+00:00" if value.endswith("Z") else value

            try:
                datetime.fromisoformat(text)

            except ValueError:
                _fail(f"{label} must be a valid ISO 8601 timestamp, got {value!r}")

    return {
        "exerciseId": exercise_id,
        "status": status,
        "source": source,
        "startedAt": raw.get("startedAt"),
        "completedAt": raw.get("completedAt"),
        "measurements": measurements,
        "errors": _validate_errors(raw.get("errors")),
    }


def record_exercise_result(raw) -> dict:
    """Validate a submitted result and return it in the form record_exercise_result
    (the MCP tool) returns to a caller. A thin, explicit wrapper — kept
    separate from validate_exercise_result so a future change that actually
    persists a result (there is no database write here in Phase 2) has one
    obvious place to add it, without changing what validation means.
    """

    return validate_exercise_result(raw)
