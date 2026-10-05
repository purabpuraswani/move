"""What a user may change about their own profile, and what values are allowed.

One definition, used by the endpoint that serves the profile to the browser and
by the endpoint that validates a change to it, so the editor can only offer
fields this module recognises and the server never stores a value the editor
could not have produced.

Deliberately NOT here: the self-reported health answers (diabetes, joint pain,
previous injury, and so on). They are collected at onboarding and they are
safety input — the Safety specialist reads them, and no screen in this
application needs to edit them. Adding a medical-history editor is a decision
about consent and review that a profile form should not make on its own, so
this module leaves them alone.

Every field below already exists on the stored profile document
(`backend/routes/profile.py`'s "complete profile" write) or is part of the
Nutrition & Lifestyle check-in (`nutrition_library/check_in.py`). No new
profile field is invented here.
"""

from nutrition_library.check_in import (
    NUTRITION_GOAL,
)

# Select vocabularies, taken from the onboarding form's own options
# (src/pages/OnboardingPage.jsx) so a value chosen in one place is valid in the
# other. Each option carries the stored value and the words shown for it.
SEX_OPTIONS = (
    {"value": "female", "label": "Female"},
    {"value": "male", "label": "Male"},
    {"value": "other", "label": "Other"},
    {"value": "prefer_not_to_say", "label": "Prefer not to say"},
)

SLEEP_QUALITY_OPTIONS = (
    {"value": "poor", "label": "Poor"},
    {"value": "average", "label": "Average"},
    {"value": "good", "label": "Good"},
)

WORK_TYPE_OPTIONS = (
    {"value": "mostly_sitting", "label": "Mostly sitting"},
    {"value": "mixed", "label": "A mix of sitting and standing"},
    {"value": "mostly_standing", "label": "Mostly standing or walking"},
    {"value": "physically_demanding", "label": "Physically demanding"},
)

NUTRITION_GOAL_OPTIONS = tuple(
    {
        "value": value,
        "label": value.replace("_", " ").capitalize(),
    }
    for value in (
        "balanced_eating",
        "hydration",
        "healthy_lifestyle",
        "weight_management",
    )
)

# Field descriptors. `kind` decides how the editor renders it and how a value is
# validated: "number" (with a range), "select" (with options), "text".
_BASIC_FIELDS = (
    {
        "key": "name",
        "label": "Name",
        "kind": "text",
        "max_length": 80,
        "help": "The name shown in your account.",
    },
    {
        "key": "age",
        "label": "Age",
        "kind": "number",
        "integer": True,
        "min": 10,
        "max": 120,
        "unit": "years",
    },
    {
        "key": "sex",
        "label": "Sex",
        "kind": "select",
        "options": SEX_OPTIONS,
    },
)

_BODY_FIELDS = (
    {
        "key": "height_cm",
        "label": "Height",
        "kind": "number",
        "min": 90,
        "max": 250,
        "step": 0.5,
        "unit": "cm",
    },
    {
        "key": "weight_kg",
        "label": "Weight",
        "kind": "number",
        "min": 25,
        "max": 350,
        "step": 0.1,
        "unit": "kg",
        "help": "Your BMI is worked out from these two values.",
    },
)

_LIFESTYLE_FIELDS = (
    {
        "key": "work_type",
        "label": "Work type",
        "kind": "select",
        "options": WORK_TYPE_OPTIONS,
    },
    {
        "key": "daily_sitting_hours",
        "label": "Sitting time",
        "kind": "number",
        "min": 0,
        "max": 24,
        "step": 0.5,
        "unit": "hours a day",
    },
    {
        "key": "daily_screen_hours",
        "label": "Screen time",
        "kind": "number",
        "min": 0,
        "max": 24,
        "step": 0.5,
        "unit": "hours a day",
    },
    {
        "key": "sleep_hours",
        "label": "Sleep",
        "kind": "number",
        "min": 0,
        "max": 16,
        "step": 0.5,
        "unit": "hours a night",
    },
    {
        "key": "sleep_quality",
        "label": "How your sleep feels",
        "kind": "select",
        "options": SLEEP_QUALITY_OPTIONS,
    },
    {
        "key": "daily_steps",
        "label": "Daily steps",
        "kind": "number",
        "integer": True,
        "min": 0,
        "max": 100000,
        "unit": "steps a day",
    },
    {
        "key": "exercise_days",
        "label": "Exercise frequency",
        "kind": "number",
        "integer": True,
        "min": 0,
        "max": 7,
        "unit": "days a week",
    },
    {
        "key": "exercise_minutes",
        "label": "Typical session",
        "kind": "number",
        "integer": True,
        "min": 0,
        "max": 600,
        "unit": "minutes",
    },
)

_GOAL_FIELDS = (
    {
        "key": NUTRITION_GOAL,
        "label": "Main nutrition / lifestyle goal",
        "kind": "select",
        "options": NUTRITION_GOAL_OPTIONS,
    },
)

# The sections the profile screen shows, in order.
SECTIONS = (
    {
        "key": "basic",
        "title": "Basic information",
        "fields": _BASIC_FIELDS,
    },
    {
        "key": "body",
        "title": "Body",
        "fields": _BODY_FIELDS,
    },
    {
        "key": "lifestyle",
        "title": "Lifestyle",
        "fields": _LIFESTYLE_FIELDS,
    },
    {
        "key": "goals",
        "title": "Goals & preferences",
        "note": (
            "Saved separately from your nutrition check-in answers, and used "
            "the same way: the next time your plan is prepared."
        ),
        "fields": _GOAL_FIELDS,
    },
)

# `name` lives on the users document, not the profile document. Everything else
# is a `health_profiles` field.
USER_FIELD_KEYS = ("name",)

ALL_FIELDS = {
    field["key"]: field
    for section in SECTIONS
    for field in section["fields"]
}

EDITABLE_KEYS = tuple(ALL_FIELDS)


class ProfileValidationError(ValueError):
    """Raised when a profile change cannot be accepted."""


def _option_values(field):
    return tuple(option["value"] for option in field["options"])


def validate_value(key, value):
    """The stored form of one profile field, or raise ProfileValidationError.

    A value outside the field's own vocabulary or range is refused rather than
    clamped or coerced: silently turning "900 steps" into "0" would store
    something the user never said.
    """

    field = ALL_FIELDS.get(key)

    if field is None:
        raise ProfileValidationError(f"{key!r} is not an editable profile field")

    if value is None or value == "":
        # Clearing a field is allowed and stores NULL, which the User State
        # reports as "not answered" rather than as a value.
        return None

    if field["kind"] == "select":
        allowed = _option_values(field)

        if value not in allowed:
            raise ProfileValidationError(
                f"{key} must be one of: " + ", ".join(allowed)
            )

        return value

    if field["kind"] == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProfileValidationError(f"{key} must be a number")

        number = float(value)

        if field.get("integer"):
            if number != int(number):
                raise ProfileValidationError(f"{key} must be a whole number")

            number = int(number)

        if number < field["min"] or number > field["max"]:
            raise ProfileValidationError(
                f"{key} must be between {field['min']} and {field['max']}"
            )

        return number

    if field["kind"] == "text":
        if not isinstance(value, str):
            raise ProfileValidationError(f"{key} must be text")

        cleaned = value.strip()

        if not cleaned:
            return None

        if len(cleaned) > field["max_length"]:
            raise ProfileValidationError(
                f"{key} must be at most {field['max_length']} characters"
            )

        return cleaned

    raise ProfileValidationError(f"{key} has no validator")  # pragma: no cover


def validate_changes(changes) -> dict:
    """Validate a whole partial update: {key: value}. Raises on the first bad
    field, naming it, so the editor can point at the right input."""

    if not isinstance(changes, dict):
        raise ProfileValidationError("fields must be an object")

    cleaned = {}

    for key, value in changes.items():
        cleaned[key] = validate_value(key, value)

    return cleaned


def calculate_bmi(height_cm, weight_kg):
    """BMI from the two stored values, or None when either is missing."""

    if not height_cm or not weight_kg:
        return None

    height_m = float(height_cm) / 100

    if height_m <= 0:
        return None

    return round(float(weight_kg) / (height_m * height_m), 2)


def describe(profile_doc) -> list:
    """The sections with this user's current values, for the editor."""

    profile_doc = profile_doc or {}

    return [
        {
            "key": section["key"],
            "title": section["title"],
            "note": section.get("note"),
            "fields": [
                {**field, "value": profile_doc.get(field["key"])}
                for field in section["fields"]
            ],
        }
        for section in SECTIONS
    ]
