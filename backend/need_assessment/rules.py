"""Deriving each Need Profile dimension from a User State.

Every threshold named _SOMETHING_THRESHOLD in this file is a SYSTEM DECISION
THRESHOLD: a value this project chose so the Need Assessment layer has
somewhere consistent to draw a line, not a clinically validated cut-off. None
of them come from `src/assessment/config/protocol.js` (which is explicit that
its own numbers are detection parameters, not clinical norms, and this file
does not add clinical authority protocol.js does not claim either) and none
of them come from a medical guideline. A healthcare/physio reviewer should
treat every threshold here as a draft to correct, not as a finding to trust.

Language discipline: a function here may say a *need* is HIGH. It must never
say a user *has* a condition. "stability_need = HIGH" means "the available
evidence suggests a stability-focused intervention may help" — it does not
mean "this user has a balance disorder", and the evidence strings below are
worded to keep that distinction even when quoted out of context.

Each function takes the User State (as built by user_state.schema) and
returns a need_assessment.schema entry via build_need_entry(). A function
that finds no usable input returns a NOT_ASSESSED entry explaining why,
rather than guessing, and never returns LOW for that reason — LOW is a
finding, not a default.
"""

from need_assessment.schema import build_need_entry

# ---------------------------------------------------------------------------
# mobility_need — from the shoulder (hand/shoulder raise) baseline test.
# ---------------------------------------------------------------------------

# Minimum observed arm elevation, in degrees, below which the system treats
# mobility need as HIGH / MEDIUM. System decision thresholds — see module
# docstring.
SHOULDER_HIGH_NEED_BELOW_DEG = 60
SHOULDER_MEDIUM_NEED_BELOW_DEG = 90

# A left/right difference at or above this, in degrees, is called out as
# evidence regardless of which need level the elevation itself produced.
SHOULDER_ASYMMETRY_NOTABLE_DEG = 20


def assess_mobility_need(user_state: dict) -> dict:
    section = user_state.get("physical_assessment") or {}
    test = ((section.get("data") or {}).get("tests") or {}).get("shoulder") or {}

    if not section.get("available") or test.get("status") != "completed":
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The shoulder (hand/shoulder raise) baseline test has not "
                "produced a usable result for this user."
            ],
        )

    measurements = test.get("measurements") or {}
    left = (measurements.get("left") or {}).get("finalElevationDeg")
    right = (measurements.get("right") or {}).get("finalElevationDeg")
    difference = measurements.get("observableDifferenceDeg")

    usable = [value for value in (left, right) if isinstance(value, (int, float))]

    if not usable:
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The shoulder test completed but produced no usable elevation "
                "angle on either side."
            ],
        )

    lowest = min(usable)
    evidence = [
        f"Lowest observed arm elevation across sides: {lowest:g} degrees "
        f"(camera-observed, not a clinical range-of-motion measurement)."
    ]

    if isinstance(difference, (int, float)) and difference >= SHOULDER_ASYMMETRY_NOTABLE_DEG:
        evidence.append(
            f"Observed difference between sides was {difference:g} degrees, "
            f"at or above the project's {SHOULDER_ASYMMETRY_NOTABLE_DEG}-degree "
            "threshold for calling out an asymmetry."
        )

    notable_asymmetry = (
        len(usable) == 2
        and isinstance(difference, (int, float))
        and difference >= SHOULDER_ASYMMETRY_NOTABLE_DEG
    )

    if lowest < SHOULDER_HIGH_NEED_BELOW_DEG:
        level = "HIGH"
        score = 1.0 - lowest / SHOULDER_HIGH_NEED_BELOW_DEG * 0.5
    elif lowest < SHOULDER_MEDIUM_NEED_BELOW_DEG:
        level = "MEDIUM"
        score = 0.5 - (
            (lowest - SHOULDER_HIGH_NEED_BELOW_DEG)
            / (SHOULDER_MEDIUM_NEED_BELOW_DEG - SHOULDER_HIGH_NEED_BELOW_DEG)
            * 0.25
        )
    elif notable_asymmetry:
        # Reuse the existing asymmetry marker as a domain need when both
        # sides were measured adequately; do not invent a second threshold.
        level = "MEDIUM"
        score = 0.25
    else:
        level = "LOW"
        score = max(0.0, 0.25 - (lowest - SHOULDER_MEDIUM_NEED_BELOW_DEG) / 360)

    confidence = "HIGH" if len(usable) == 2 else "MEDIUM"

    return build_need_entry(
        level=level, score=score, evidence=evidence, confidence=confidence
    )


# ---------------------------------------------------------------------------
# stability_need — from the one-leg (balance) baseline test.
# ---------------------------------------------------------------------------

BALANCE_HIGH_NEED_BELOW_SECONDS = 5
BALANCE_MEDIUM_NEED_BELOW_SECONDS = 15

# For scoring only: the same ceiling the protocol itself uses as the maximum
# time a hold is even measured up to (src/assessment/config/protocol.js,
# BALANCE.maxDurationMs). Reused here purely as a scaling reference, not as a
# claim that 30 seconds is a clinical pass mark.
BALANCE_SCALE_CEILING_SECONDS = 30


def assess_stability_need(user_state: dict) -> dict:
    section = user_state.get("physical_assessment") or {}
    test = ((section.get("data") or {}).get("tests") or {}).get("balance") or {}

    if not section.get("available") or test.get("status") != "completed":
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The one-leg stand baseline test has not produced a usable "
                "result for this user."
            ],
        )

    measurements = test.get("measurements") or {}
    holds = {}

    for side in ("left", "right"):
        side_data = measurements.get(side) or {}

        if side_data.get("attempted") and side_data.get("valid"):
            duration = side_data.get("holdDurationSeconds")

            if isinstance(duration, (int, float)):
                holds[side] = duration

    if not holds:
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The balance test completed but neither side produced a "
                "usable hold duration."
            ],
        )

    shortest_side, shortest = min(holds.items(), key=lambda item: item[1])
    evidence = [
        f"Shortest held stance across sides ({shortest_side}): {shortest:g} "
        "seconds (camera-timed, not a clinical balance screen)."
    ]

    difference_ms = measurements.get("observableDifferenceMs")

    if isinstance(difference_ms, (int, float)) and len(holds) == 2:
        evidence.append(
            f"Difference between sides: {difference_ms / 1000:g} seconds."
        )

    if shortest < BALANCE_HIGH_NEED_BELOW_SECONDS:
        level = "HIGH"
        score = 1.0 - shortest / BALANCE_HIGH_NEED_BELOW_SECONDS * 0.5
    elif shortest < BALANCE_MEDIUM_NEED_BELOW_SECONDS:
        level = "MEDIUM"
        score = 0.5 - (
            (shortest - BALANCE_HIGH_NEED_BELOW_SECONDS)
            / (BALANCE_MEDIUM_NEED_BELOW_SECONDS - BALANCE_HIGH_NEED_BELOW_SECONDS)
            * 0.25
        )
    else:
        level = "LOW"
        score = max(
            0.0,
            0.25
            - (shortest - BALANCE_MEDIUM_NEED_BELOW_SECONDS)
            / BALANCE_SCALE_CEILING_SECONDS,
        )

    confidence = "HIGH" if len(holds) == 2 else "MEDIUM"

    return build_need_entry(
        level=level, score=score, evidence=evidence, confidence=confidence
    )


# ---------------------------------------------------------------------------
# functional_movement_need — from the chair sit-to-stand x5 baseline test.
# ---------------------------------------------------------------------------

FTSST_HIGH_NEED_ABOVE_SECONDS = 15
FTSST_MEDIUM_NEED_ABOVE_SECONDS = 10

# Scaling reference only, matching FTSST.maxTestDurationMs in protocol.js
# (the point at which the protocol itself abandons the attempt).
FTSST_SCALE_CEILING_SECONDS = 60


def assess_functional_movement_need(user_state: dict) -> dict:
    section = user_state.get("physical_assessment") or {}
    test = ((section.get("data") or {}).get("tests") or {}).get("ftsst") or {}

    if not section.get("available") or test.get("status") != "completed":
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The chair sit-to-stand x5 baseline test has not produced a "
                "usable result for this user."
            ],
        )

    measurements = test.get("measurements") or {}
    seconds = measurements.get("completionTimeSeconds")

    if not isinstance(seconds, (int, float)):
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The sit-to-stand test completed but produced no usable "
                "completion time."
            ],
        )

    evidence = [
        f"Five sit-to-stand repetitions took {seconds:g} seconds "
        "(software-timed from camera-observed knee angle, not a clinician-"
        "timed test)."
    ]

    detected = measurements.get("repetitionsDetected")
    required = measurements.get("requiredRepetitions")

    if isinstance(detected, int) and isinstance(required, int) and detected < required:
        evidence.append(
            f"Only {detected} of {required} repetitions were recognised by "
            "the software."
        )

    if seconds > FTSST_HIGH_NEED_ABOVE_SECONDS:
        level = "HIGH"
        score = min(
            1.0,
            0.5
            + (seconds - FTSST_HIGH_NEED_ABOVE_SECONDS) / FTSST_SCALE_CEILING_SECONDS,
        )
    elif seconds > FTSST_MEDIUM_NEED_ABOVE_SECONDS:
        level = "MEDIUM"
        score = 0.25 + (
            (seconds - FTSST_MEDIUM_NEED_ABOVE_SECONDS)
            / (FTSST_HIGH_NEED_ABOVE_SECONDS - FTSST_MEDIUM_NEED_ABOVE_SECONDS)
            * 0.25
        )
    else:
        level = "LOW"
        score = max(0.0, 0.25 - (FTSST_MEDIUM_NEED_ABOVE_SECONDS - seconds) / 40)

    return build_need_entry(
        level=level, score=score, evidence=evidence, confidence="HIGH"
    )


# ---------------------------------------------------------------------------
# behaviour_need — from the onboarding questionnaire's lifestyle answers.
#
# Deliberately reads user_state["questionnaire"], not user_state["behaviour"].
# The "behaviour" section of the User State is reserved for future adherence
# tracking (whether a user follows a plan over time) — a different kind of
# data the application does not collect yet. What is derived here is a
# one-time, self-reported lifestyle read, which is what the questionnaire
# actually is.
# ---------------------------------------------------------------------------

SITTING_HOURS_HIGH_THRESHOLD = 8
SCREEN_HOURS_HIGH_THRESHOLD = 8
EXERCISE_DAYS_LOW_THRESHOLD = 2  # fewer than this many days/week counts
WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD = 90  # exercise_days * exercise_minutes

RISK_LOW_UPPER_BOUND = 1 / 3
RISK_MEDIUM_UPPER_BOUND = 2 / 3


def assess_behaviour_need(user_state: dict) -> dict:
    section = user_state.get("questionnaire") or {}
    data = section.get("data") or {}

    sitting = data.get("daily_sitting_hours")
    screen = data.get("daily_screen_hours")
    exercise_days = data.get("exercise_days")
    exercise_minutes = data.get("exercise_minutes")

    if not section.get("available") or (sitting is None and exercise_days is None):
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The onboarding questionnaire has no answer for daily sitting "
                "time or exercise frequency, so a behaviour read cannot be "
                "made."
            ],
        )

    factors_available = 0
    factors_triggered = 0
    evidence = []

    if isinstance(sitting, (int, float)):
        factors_available += 1

        if sitting >= SITTING_HOURS_HIGH_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported sitting time is {sitting:g} hours/day, at or "
                f"above the project's {SITTING_HOURS_HIGH_THRESHOLD}-hour "
                "threshold."
            )

    if isinstance(screen, (int, float)):
        factors_available += 1

        if screen >= SCREEN_HOURS_HIGH_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported screen time is {screen:g} hours/day, at or "
                f"above the project's {SCREEN_HOURS_HIGH_THRESHOLD}-hour "
                "threshold."
            )

    if isinstance(exercise_days, (int, float)):
        factors_available += 1

        if exercise_days < EXERCISE_DAYS_LOW_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported exercise frequency is {exercise_days:g} "
                f"day(s)/week, below the project's "
                f"{EXERCISE_DAYS_LOW_THRESHOLD}-day threshold."
            )

    if isinstance(exercise_days, (int, float)) and isinstance(
        exercise_minutes, (int, float)
    ):
        weekly_minutes = exercise_days * exercise_minutes
        factors_available += 1

        if weekly_minutes < WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported exercise volume is about {weekly_minutes:g} "
                f"minutes/week, below the project's "
                f"{WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD}-minute threshold."
            )

    if factors_available == 0:
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The questionnaire fields relevant to behaviour were answered "
                "with values that could not be read as numbers."
            ],
        )

    risk_ratio = factors_triggered / factors_available

    if risk_ratio > RISK_MEDIUM_UPPER_BOUND:
        level = "HIGH"
    elif risk_ratio > RISK_LOW_UPPER_BOUND:
        level = "MEDIUM"
    else:
        level = "LOW"

        if not evidence:
            evidence.append(
                "None of the self-reported lifestyle answers crossed the "
                "project's sedentary-behaviour thresholds."
            )

    confidence = "HIGH" if factors_available >= 3 else "MEDIUM"

    return build_need_entry(
        level=level, score=risk_ratio, evidence=evidence, confidence=confidence
    )


# ---------------------------------------------------------------------------
# nutrition_need — from the four optional self-reported nutrition questions
# added in Phase 4 (backend/user_state/schema.py's `nutrition` section):
# meal_pattern, fruit_vegetable_servings, water_glasses_per_day, and
# processed_food_frequency. Mirrors assess_behaviour_need()'s
# fraction-of-factors-triggered pattern immediately above. If a user's
# profile has none of these answered, the `nutrition` User State section is
# NOT_YET_COLLECTED and this stays NOT_ASSESSED, exactly as it did before
# Phase 4 — this function only ever produces a real level when the user
# actually answered at least one of the new questions.
# ---------------------------------------------------------------------------

# System decision thresholds — see module docstring. Not derived from any
# clinical dietary guideline; a lower serving/water count, or a more
# irregular/processed-food-heavy pattern, simply counts as one more
# "triggered" factor in the same style as assess_behaviour_need() above.
FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD = 3
WATER_GLASSES_LOW_THRESHOLD = 6

# Closed vocabularies this project expects for the two free-text fields.
# Any other string is treated the same as a missing answer (not counted as
# an available factor, and not guessed at) rather than crashing or being
# silently miscounted — the same discipline assess_behaviour_need() applies
# to non-numeric questionnaire answers.
MEAL_PATTERN_TRIGGER_VALUES = frozenset({"irregular", "skips_meals"})
MEAL_PATTERN_KNOWN_VALUES = frozenset({"regular"}) | MEAL_PATTERN_TRIGGER_VALUES

PROCESSED_FOOD_TRIGGER_VALUES = frozenset({"often", "daily"})
PROCESSED_FOOD_KNOWN_VALUES = (
    frozenset({"rarely", "sometimes"}) | PROCESSED_FOOD_TRIGGER_VALUES
)


def assess_nutrition_need(user_state: dict) -> dict:
    section = user_state.get("nutrition") or {}
    data = section.get("data") or {}

    if not section.get("available"):
        reason = section.get("reason") or (
            "This user has not answered the optional nutrition questions."
        )
        return build_need_entry(level="NOT_ASSESSED", confidence="NONE", evidence=[reason])

    meal_pattern = data.get("meal_pattern")
    fruit_veg = data.get("fruit_vegetable_servings")
    water = data.get("water_glasses_per_day")
    processed_food = data.get("processed_food_frequency")

    factors_available = 0
    factors_triggered = 0
    evidence = []

    if isinstance(meal_pattern, str) and meal_pattern in MEAL_PATTERN_KNOWN_VALUES:
        factors_available += 1

        if meal_pattern in MEAL_PATTERN_TRIGGER_VALUES:
            factors_triggered += 1
            evidence.append(
                f"Self-reported meal pattern is '{meal_pattern}'."
            )

    if isinstance(fruit_veg, (int, float)):
        factors_available += 1

        if fruit_veg < FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported fruit/vegetable intake is {fruit_veg:g} "
                f"serving(s)/day, below the project's "
                f"{FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD}-serving threshold."
            )

    if isinstance(water, (int, float)):
        factors_available += 1

        if water < WATER_GLASSES_LOW_THRESHOLD:
            factors_triggered += 1
            evidence.append(
                f"Self-reported water intake is {water:g} glass(es)/day, "
                f"below the project's {WATER_GLASSES_LOW_THRESHOLD}-glass "
                "threshold."
            )

    if (
        isinstance(processed_food, str)
        and processed_food in PROCESSED_FOOD_KNOWN_VALUES
    ):
        factors_available += 1

        if processed_food in PROCESSED_FOOD_TRIGGER_VALUES:
            factors_triggered += 1
            evidence.append(
                f"Self-reported processed-food frequency is "
                f"'{processed_food}'."
            )

    if factors_available == 0:
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "The nutrition fields present on this profile could not be "
                "read as any of the values this project recognizes."
            ],
        )

    risk_ratio = factors_triggered / factors_available

    if risk_ratio > RISK_MEDIUM_UPPER_BOUND:
        level = "HIGH"
    elif risk_ratio > RISK_LOW_UPPER_BOUND:
        level = "MEDIUM"
    else:
        level = "LOW"

        if not evidence:
            evidence.append(
                "None of the self-reported nutrition answers crossed the "
                "project's thresholds."
            )

    confidence = "HIGH" if factors_available >= 3 else "MEDIUM"

    return build_need_entry(
        level=level, score=risk_ratio, evidence=evidence, confidence=confidence
    )


# ---------------------------------------------------------------------------
# exercise_need — a composite: does this user need a structured exercise
# intervention at all, combining the questionnaire's exercise-habit signal
# with whatever the physical-capability dimensions above already found.
# ---------------------------------------------------------------------------


def assess_exercise_need(
    user_state: dict,
    *,
    mobility: dict,
    stability: dict,
    functional_movement: dict,
    behaviour: dict,
) -> dict:
    physical_levels = {
        "mobility_need": mobility["level"],
        "stability_need": stability["level"],
        "functional_movement_need": functional_movement["level"],
    }

    assessed_physical = {
        name: level for name, level in physical_levels.items() if level != "NOT_ASSESSED"
    }

    behaviour_assessed = behaviour["level"] != "NOT_ASSESSED"

    if not assessed_physical and not behaviour_assessed:
        return build_need_entry(
            level="NOT_ASSESSED",
            confidence="NONE",
            evidence=[
                "Neither the physical assessment nor the questionnaire's "
                "exercise-habit answers are available, so an overall exercise "
                "need cannot be derived."
            ],
        )

    evidence = []
    high_sources = [name for name, level in assessed_physical.items() if level == "HIGH"]
    medium_sources = [
        name for name, level in assessed_physical.items() if level == "MEDIUM"
    ]

    if high_sources:
        evidence.append(
            "Physical assessment shows a HIGH need in: "
            + ", ".join(sorted(high_sources))
            + "."
        )

    if behaviour["level"] == "HIGH":
        evidence.append(
            "Questionnaire-derived behaviour need is HIGH (sedentary/low-"
            "exercise lifestyle indicators)."
        )

    if high_sources or behaviour["level"] == "HIGH":
        level = "HIGH"
    elif medium_sources or behaviour["level"] == "MEDIUM":
        level = "MEDIUM"

        if medium_sources:
            evidence.append(
                "Physical assessment shows a MEDIUM need in: "
                + ", ".join(sorted(medium_sources))
                + "."
            )

        if behaviour["level"] == "MEDIUM":
            evidence.append(
                "Questionnaire-derived behaviour need is MEDIUM (some "
                "sedentary/low-exercise lifestyle indicators)."
            )
    elif assessed_physical or behaviour_assessed:
        level = "LOW"
        evidence.append(
            "No physical-assessment dimension and no questionnaire behaviour "
            "signal reached the project's MEDIUM or HIGH exercise-need "
            "thresholds."
        )
    else:  # pragma: no cover — unreachable given the guard above
        level = "NOT_ASSESSED"

    contributing_scores = [
        entry["score"]
        for entry in (mobility, stability, functional_movement, behaviour)
        if entry["score"] is not None
    ]

    score = (
        round(sum(contributing_scores) / len(contributing_scores), 2)
        if contributing_scores
        else None
    )

    confidence_pool = [
        entry["confidence"]
        for entry in (mobility, stability, functional_movement, behaviour)
        if entry["level"] != "NOT_ASSESSED"
    ]

    if "HIGH" in confidence_pool:
        confidence = "HIGH"
    elif "MEDIUM" in confidence_pool:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return build_need_entry(
        level=level, score=score, evidence=evidence, confidence=confidence
    )


# ---------------------------------------------------------------------------
# safety_status — Phase 1 has no validated safety/escalation rules to run.
# ---------------------------------------------------------------------------


def assess_safety_status(user_state: dict) -> dict:
    """Always NOT_ASSESSED in Phase 1.

    Per the project's safety principle, a safety/referral status must come
    from deterministic, curated, reviewed rules — not from this layer
    inventing red flags because some data happens to be present. No such
    rules exist in the repository yet (the dedicated Safety/Referral system
    is future-phase work), so the honest output here is NOT_ASSESSED, not a
    guess at low risk.
    """

    evidence = [
        "No validated safety/escalation rules exist in the project yet. The "
        "Safety/Referral system is planned for a later phase."
    ]

    medical_context = user_state.get("medical_context") or {}

    if medical_context.get("available"):
        evidence.append(
            "Note: this user has self-reported health information and/or a "
            "confirmed medical report on file; it was not used to derive this "
            "status, and is not being interpreted here."
        )

    return build_need_entry(level="NOT_ASSESSED", confidence="NONE", evidence=evidence)
