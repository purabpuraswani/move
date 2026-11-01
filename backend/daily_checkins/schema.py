"""Validation for user-reported daily wellness check-ins."""

FIELDS = {
    "sleep_hours": (0, 24),
    "sleep_quality": (1, 5),
    "stress_level": (1, 5),
    "recovery_difficulty": (0, 1),
    "steps": (0, 200000),
    "sitting_minutes": (0, 1440),
    "walking_minutes": (0, 1440),
    "movement_breaks": (0, 100),
    "fruit_vegetable_servings": (0, 100),
    "water_intake_ml": (0, 20000),
}


class DailyCheckinValidationError(ValueError):
    pass


def validate_checkin(payload):
    if not isinstance(payload, dict):
        raise DailyCheckinValidationError("Check-in must be an object")
    unknown = set(payload) - set(FIELDS) - {"date"}
    if unknown:
        raise DailyCheckinValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    result = {}
    for key, value in payload.items():
        if key == "date":
            continue
        if value is None:
            continue
        low, high = FIELDS[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
            raise DailyCheckinValidationError(f"{key} must be a number between {low} and {high}")
        result[key] = value
    if not result:
        raise DailyCheckinValidationError("Provide at least one recorded value")
    return result
