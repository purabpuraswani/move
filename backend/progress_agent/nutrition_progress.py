"""Nutrition-specific progress, kept explicitly separate from physical
progress (progress_agent/comparison.py).

This module answers exactly one question: across two observation periods,
did this user's FOOD-LOG ADHERENCE (see nutrition_agent/adherence.py) get
better, stay the same, or get worse? It never answers, and must never be
read as answering, "did this user's health improve" — adherence is a
measure of whether logging (and, by extension, plan-following) happened,
not a measure of a health outcome. A caller that wants to say "nutrition
improved" to a user is making a claim this module does not make and must
not attribute to it.

Two pure functions, mirroring progress_agent/comparison.py's discipline
exactly: same input, same output, always; no clock read, no randomness,
nothing inferred beyond what the two adherence results already state.
"""

IMPROVED = "IMPROVED"
STABLE = "STABLE"
DECLINED = "DECLINED"
NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"

NUTRITION_PROGRESS_STATUSES = (IMPROVED, STABLE, DECLINED, NOT_ENOUGH_DATA)

# A system-decision tolerance band, exactly like compare_metric()'s own
# per-metric tolerance in progress_agent/comparison.py: a change in
# logging-coverage rate smaller than this is noise, not a real trend, and
# is reported as STABLE rather than a confident IMPROVED/DECLINED.
ADHERENCE_RATE_TOLERANCE = 0.10

# The nutrition-specific adaptation vocabulary this module recommends
# from. Deliberately a subset of progress_agent.schema.ADAPTATION_RECOMMENDATIONS
# — PROGRESS/REGRESS are physical-difficulty concepts ("make the exercise
# harder/easier") that have no nutrition equivalent, so they are never
# produced here.
NUTRITION_ADAPTATION_RECOMMENDATIONS = ("CONTINUE", "MAINTAIN", "MODIFY", "REASSESS")


def compare_nutrition_adherence(previous_result: dict, current_result: dict) -> dict:
    """Compare two nutrition_agent.adherence.compute_food_log_adherence()
    results (previous period, current period) into a nutrition_progress
    dict.

    Returns:
        {
            "status": one of NUTRITION_PROGRESS_STATUSES,
            "adherence_rate": the current period's completion_rate, or
                None when the current period has none,
            "current_adherence_status": the current period's own
                ADHERED/NOT_ADHERED/NOT_LOGGED/INSUFFICIENT_DATA status,
            "previous_adherence_status": the previous period's own status,
                or None if no previous result was given at all,
            "evidence": a list of plain, specific strings citing both
                periods' actual logged-day counts — never a bare verdict
                with no basis shown,
            "confidence": "COMPUTED" when a real rate-to-rate comparison
                was made, "NONE" otherwise,
        }

    `current_result` missing, or carrying no computed `completion_rate`
    (its status is NOT_LOGGED or INSUFFICIENT_DATA), is always
    NOT_ENOUGH_DATA — there is nothing current to report progress on. A
    missing/rate-less `previous_result` with a real current rate is also
    NOT_ENOUGH_DATA — a single period is a snapshot, not a trend, and is
    never treated as "improved from nothing."
    """

    current_status = (current_result or {}).get("status")
    current_rate = (current_result or {}).get("completion_rate")

    if current_result is None or current_rate is None:
        return {
            "status": NOT_ENOUGH_DATA,
            "adherence_rate": None,
            "current_adherence_status": current_status,
            "previous_adherence_status": (previous_result or {}).get("status"),
            "evidence": [
                "the current period has no computed adherence rate "
                f"(status={current_status!r}), so no progress can be reported"
            ],
            "confidence": "NONE",
        }

    previous_status = (previous_result or {}).get("status")
    previous_rate = (previous_result or {}).get("completion_rate")

    if previous_result is None or previous_rate is None:
        return {
            "status": NOT_ENOUGH_DATA,
            "adherence_rate": current_rate,
            "current_adherence_status": current_status,
            "previous_adherence_status": previous_status,
            "evidence": [
                "the current period has a computed adherence rate of "
                f"{current_rate:.0%}, but no comparable previous-period rate "
                "exists yet, so no trend can be computed from a single period"
            ],
            "confidence": "NONE",
        }

    change = current_rate - previous_rate

    if abs(change) <= ADHERENCE_RATE_TOLERANCE:
        status = STABLE
    elif change > 0:
        status = IMPROVED
    else:
        status = DECLINED

    evidence = [
        (
            f"previous period: {previous_result.get('logged_days')}/"
            f"{previous_result.get('observation_days')} day(s) logged "
            f"({previous_rate:.0%}, status={previous_status})"
        ),
        (
            f"current period: {current_result.get('logged_days')}/"
            f"{current_result.get('observation_days')} day(s) logged "
            f"({current_rate:.0%}, status={current_status})"
        ),
    ]

    return {
        "status": status,
        "adherence_rate": current_rate,
        "current_adherence_status": current_status,
        "previous_adherence_status": previous_status,
        "evidence": evidence,
        "confidence": "COMPUTED",
    }


def recommend_nutrition_adaptation(nutrition_progress: dict) -> tuple:
    """The nutrition-specific decision table. Returns (recommendation,
    reason). Deterministic: identical `nutrition_progress` always
    produces the identical recommendation.

        NOT_ENOUGH_DATA          -> REASSESS
        IMPROVED                 -> CONTINUE
        STABLE, current ADHERED  -> MAINTAIN
        STABLE, current not ADHERED (NOT_ADHERED/NOT_LOGGED/INSUFFICIENT_DATA)
                                  -> MODIFY
        DECLINED                 -> MODIFY

    PROGRESS/REGRESS are never returned here — see module docstring on
    why those physical-difficulty concepts do not apply to nutrition.
    This function recommends only; the Nutrition Agent alone owns
    whether/how to actually change the plan (see
    orchestrator/orchestrator.py's dispatch discipline for physical
    adaptation, mirrored here).
    """

    status = nutrition_progress.get("status")

    if status == NOT_ENOUGH_DATA:
        return "REASSESS", (
            "Not enough food-logging data exists yet to compare adherence "
            "across periods."
        )

    if status == IMPROVED:
        return "CONTINUE", "Food-logging adherence improved; keep the current plan."

    if status == STABLE:
        if nutrition_progress.get("current_adherence_status") == "ADHERED":
            return "MAINTAIN", "Food-logging adherence is stable and already high; hold the current plan steady."

        return "MODIFY", (
            "Food-logging adherence is stable but not at the adherence "
            "threshold — the plan's approach (not the user's effort) should "
            "be reconsidered, since low logging adherence has not improved "
            "on its own."
        )

    if status == DECLINED:
        return "MODIFY", (
            "Food-logging adherence declined between periods — reconsider "
            "the plan's approach rather than continuing it unchanged."
        )

    raise ValueError(f"unhandled nutrition progress status {status!r}")  # pragma: no cover
