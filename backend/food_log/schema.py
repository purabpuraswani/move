"""Validating one submitted Food Log entry.

Mirrors backend/exercise_assessment/schema.py's error-handling discipline:
a single ValueError subclass, a `_fail` helper, a closed set of accepted
fields, and a refusal rather than a silently corrected best guess.

What this module deliberately does NOT do: force structured nutrient
maths on the user. `quantity` is free text ("1 bowl", "2 rotis", "half a
katori") because that is how people actually describe what they ate, and
demanding grams would either block the log or invite an invented number.
Nutrient composition, when it is wanted at all, is looked up separately
and honestly from nutrition_library/food_composition.py, which says
plainly that its own numbers are curated estimates.

Nothing here scores a meal, computes a calorie total, or judges a food.
"""

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")

MAX_STRING_LENGTH = 200
MAX_NOTES_LENGTH = 500
MAX_WATER_INTAKE_ML = 10000

ACCEPTED_FIELDS = (
    "meal",
    "food_id",
    "food_name",
    "quantity",
    "notes",
    "water_intake_ml",
)


class FoodLogValidationError(ValueError):
    """Raised when a submitted food log entry cannot be accepted."""


def _fail(message: str):
    raise FoodLogValidationError(message)


def _optional_string(value, label: str, max_length: int = MAX_STRING_LENGTH):
    if value is None:
        return None

    if not isinstance(value, str):
        _fail(f"{label} must be null or a string")

    cleaned = value.strip()

    if not cleaned:
        return None

    if len(cleaned) > max_length:
        _fail(f"{label} must be at most {max_length} characters")

    return cleaned


def build_food_log_entry(
    meal,
    food_id=None,
    food_name=None,
    quantity=None,
    notes=None,
    water_intake_ml=None,
) -> dict:
    """Build and validate one food log entry document.

    Returns the cleaned entry (the exact shape store.save_food_log_entry
    expects). Raises FoodLogValidationError for anything it cannot accept —
    it never fills in a missing meal, food, or quantity on the user's
    behalf.
    """

    entry = {
        "meal": meal,
        "food_id": food_id,
        "food_name": food_name,
        "quantity": quantity,
        "notes": notes,
        "water_intake_ml": water_intake_ml,
    }

    return validate_food_log_entry(entry)


def validate_food_log_entry(entry) -> dict:
    """Validate a food log entry and return the cleaned document."""

    if not isinstance(entry, dict):
        _fail("a food log entry must be an object")

    unknown = set(entry) - set(ACCEPTED_FIELDS)

    if unknown:
        _fail(f"unexpected field(s): {', '.join(sorted(unknown))}")

    meal = entry.get("meal")

    if meal not in MEAL_TYPES:
        _fail(f"meal is required and must be one of {', '.join(MEAL_TYPES)}")

    food_id = _optional_string(entry.get("food_id"), "food_id")
    food_name = _optional_string(entry.get("food_name"), "food_name")

    if food_id is None and food_name is None:
        _fail(
            "a food log entry must name what was eaten: give food_id (a "
            "nutrition_library.food_composition id) or food_name (free "
            "text), or both"
        )

    quantity = _optional_string(entry.get("quantity"), "quantity")
    notes = _optional_string(entry.get("notes"), "notes", MAX_NOTES_LENGTH)

    water = entry.get("water_intake_ml")

    if water is not None:
        if isinstance(water, bool) or not isinstance(water, (int, float)):
            _fail("water_intake_ml must be null or a non-negative number of millilitres")

        if water < 0 or water > MAX_WATER_INTAKE_ML:
            _fail(
                "water_intake_ml must be between 0 and "
                f"{MAX_WATER_INTAKE_ML} millilitres"
            )

    return {
        "meal": meal,
        "food_id": food_id,
        "food_name": food_name,
        "quantity": quantity,
        "notes": notes,
        "water_intake_ml": water,
    }
