"""The Nutrition & Lifestyle domain evidence view.

Separate from `nutrition_agent/input_contract.py`, which builds the
agent's run input. This module answers a different question, asked in
two places: *what does this project actually know about this user's
eating pattern, and what is it still missing?*

It exists because the honest answer to an unanswered nutrition
questionnaire is a list of the questions that were never asked -- not
"eat more vegetables, drink more water". The Nutrition Agent reports it
in its findings, and the specialist card reports the same thing from the
same function, so the screen and the agent can never disagree.

Nothing here infers a diet, a deficiency or a restriction, and an
unanswered question is never read as a poor diet.
"""

from need_assessment.rules import (
    MEAL_PATTERN_KNOWN_VALUES,
    PROCESSED_FOOD_KNOWN_VALUES,
)
from orchestration.evidence import (
    KNOWN,
    MISSING,
    STATUS_ASSESSED,
    STATUS_INSUFFICIENT_EVIDENCE,
    confidence_from,
    evidence_lines,
    known,
    missing_labels,
    signal,
)


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _vocabulary_value(value, vocabulary):
    return value if isinstance(value, str) and value in vocabulary else None


def build_nutrition_evidence_view(user_state: dict, *, food_log_entries: list = None) -> dict:
    """What is known and what is missing in the nutrition domain.

    Returns `{"signals", "status", "missing_information", "evidence_used",
    "confidence"}`. `status` is INSUFFICIENT_EVIDENCE whenever no
    nutrition answer and no logged food exist -- the state in which this
    specialist must say what it needs rather than offer general advice.
    """

    section = user_state.get("nutrition") or {}
    data = (section.get("data") or {}) if section.get("available") else {}

    signals = {
        "meal_pattern": signal(
            "meal_pattern",
            _vocabulary_value(data.get("meal_pattern"), MEAL_PATTERN_KNOWN_VALUES),
            label="Meal pattern",
        ),
        "fruit_vegetable_servings": signal(
            "fruit_vegetable_servings",
            _number(data.get("fruit_vegetable_servings")),
            label="Fruit and vegetable servings",
            unit="servings/day",
        ),
        "water_glasses_per_day": signal(
            "water_glasses_per_day",
            _number(data.get("water_glasses_per_day")),
            label="Water intake",
            unit="glasses/day",
        ),
        "processed_food_frequency": signal(
            "processed_food_frequency",
            _vocabulary_value(data.get("processed_food_frequency"), PROCESSED_FOOD_KNOWN_VALUES),
            label="Processed food frequency",
        ),
    }

    if food_log_entries is None:
        signals["logged_meals"] = signal(
            "logged_meals", None, label="Logged meals", state=MISSING
        )
    else:
        signals["logged_meals"] = signal(
            "logged_meals",
            len(food_log_entries),
            label="Logged meals",
            unit="entries",
            state=KNOWN,
        )

    answered = [
        name
        for name, entry in known(signals).items()
        if name != "logged_meals" or entry["value"]
    ]

    return {
        "signals": signals,
        "status": STATUS_ASSESSED if answered else STATUS_INSUFFICIENT_EVIDENCE,
        "evidence_used": evidence_lines(signals),
        "missing_information": missing_labels(signals),
        "confidence": confidence_from(signals),
    }
