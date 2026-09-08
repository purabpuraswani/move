"""The deterministic, direction-aware comparison engine.

Every function here is pure: same input, same output, always — no
randomness, no external call, no clock read except where a caller
explicitly passes a "now" (see agent.py's reassessment check, not this
module). This is what makes the Progress Agent's output verifiable rather
than a black box.

Three physical baseline metrics are supported, each reusing exactly the
same raw-value extraction logic need_assessment/rules.py already applies
to the same tests, so this module can never quietly disagree with the
Need Profile about what a test's own measurement means:

    mobility_shoulder_elevation_deg     higher is better (more elevation)
    stability_balance_hold_seconds      higher is better (longer hold)
    functional_movement_ftsst_seconds   LOWER is better (faster completion)

Each metric's "direction" is a named, documented constant — never assumed.
STABLE is not "close to zero change"; it is "change too small, in this
project's own opinion, to call improved or declined" — a system-decision
tolerance per metric, exactly like need_assessment/rules.py's thresholds.
"""

from user_state.schema import extract_assessment_tests

DIRECTION_HIGHER_IS_BETTER = "higher_is_better"
DIRECTION_LOWER_IS_BETTER = "lower_is_better"

METRIC_DIRECTIONS = {
    "mobility_shoulder_elevation_deg": DIRECTION_HIGHER_IS_BETTER,
    "stability_balance_hold_seconds": DIRECTION_HIGHER_IS_BETTER,
    "functional_movement_ftsst_seconds": DIRECTION_LOWER_IS_BETTER,
}

# System decision tolerances — see module docstring. A change smaller than
# this, in the metric's own unit, is STABLE rather than IMPROVED/DECLINED.
STABLE_TOLERANCE = {
    "mobility_shoulder_elevation_deg": 5,
    "stability_balance_hold_seconds": 2,
    "functional_movement_ftsst_seconds": 1,
}

IMPROVED = "IMPROVED"
STABLE = "STABLE"
DECLINED = "DECLINED"
NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"

PROGRESS_DIRECTIONS = (IMPROVED, STABLE, DECLINED, NOT_ENOUGH_DATA)


def extract_shoulder_metric(tests: dict):
    """Lowest observed elevation across sides, in degrees — the same value
    need_assessment.rules.assess_mobility_need() bases its level on.
    Returns None if the test was not completed or produced nothing usable.
    """

    test = (tests or {}).get("shoulder") or {}

    if test.get("status") != "completed":
        return None

    measurements = test.get("measurements") or {}
    values = []

    for side in ("left", "right"):
        angle = (measurements.get(side) or {}).get("finalElevationDeg")

        if isinstance(angle, (int, float)):
            values.append(angle)

    return min(values) if values else None


def extract_balance_metric(tests: dict):
    """Shortest valid hold across sides, in seconds — the same value
    need_assessment.rules.assess_stability_need() bases its level on.
    """

    test = (tests or {}).get("balance") or {}

    if test.get("status") != "completed":
        return None

    measurements = test.get("measurements") or {}
    holds = []

    for side in ("left", "right"):
        side_data = measurements.get(side) or {}

        if side_data.get("attempted") and side_data.get("valid"):
            duration = side_data.get("holdDurationSeconds")

            if isinstance(duration, (int, float)):
                holds.append(duration)

    return min(holds) if holds else None


def extract_ftsst_metric(tests: dict):
    """Sit-to-stand x5 completion time, in seconds — the same value
    need_assessment.rules.assess_functional_movement_need() bases its level
    on. Lower is better for this one metric — see METRIC_DIRECTIONS.
    """

    test = (tests or {}).get("ftsst") or {}

    if test.get("status") != "completed":
        return None

    seconds = (test.get("measurements") or {}).get("completionTimeSeconds")

    return seconds if isinstance(seconds, (int, float)) else None


_METRIC_EXTRACTORS = {
    "mobility_shoulder_elevation_deg": extract_shoulder_metric,
    "stability_balance_hold_seconds": extract_balance_metric,
    "functional_movement_ftsst_seconds": extract_ftsst_metric,
}


def compare_metric(baseline_value, current_value, metric_name: str) -> dict:
    """Compare one metric's baseline/current value pair. Deterministic:
    identical inputs always produce an identical result. Returns
    {"baseline", "current", "change", "direction"} — `direction` is one of
    PROGRESS_DIRECTIONS. `change` is None whenever `direction` is
    NOT_ENOUGH_DATA — a missing value is never silently treated as 0.
    """

    if metric_name not in METRIC_DIRECTIONS:
        raise ValueError(f"unknown metric {metric_name!r}")

    if baseline_value is None or current_value is None:
        return {
            "baseline": baseline_value,
            "current": current_value,
            "change": None,
            "direction": NOT_ENOUGH_DATA,
        }

    raw_change = current_value - baseline_value
    metric_direction = METRIC_DIRECTIONS[metric_name]

    # A positive "signed_change" always means "moved the good way",
    # regardless of whether the raw metric itself goes up or down when
    # things improve.
    signed_change = raw_change if metric_direction == DIRECTION_HIGHER_IS_BETTER else -raw_change
    tolerance = STABLE_TOLERANCE[metric_name]

    if signed_change > tolerance:
        direction = IMPROVED
    elif signed_change < -tolerance:
        direction = DECLINED
    else:
        direction = STABLE

    return {
        "baseline": baseline_value,
        "current": current_value,
        "change": raw_change,
        "direction": direction,
    }


def compare_physical_assessments(
    baseline_assessment_doc, previous_assessment_doc, current_assessment_doc
) -> dict:
    """Compare all three physical baseline metrics across baseline/previous/
    current raw assessment documents (assessments/schema.py's stored
    shape — the same shape assessments/store.py returns). Any of the three
    documents may be None (e.g. no previous session exists yet, or the
    user has only a baseline and nothing since) — handled per-metric as
    NOT_ENOUGH_DATA, never a crash.

    Returns {metric_name: {"baseline_vs_current": {...}, "previous_vs_current": {...}}}.
    """

    baseline_tests = extract_assessment_tests(baseline_assessment_doc) if baseline_assessment_doc else {}
    previous_tests = extract_assessment_tests(previous_assessment_doc) if previous_assessment_doc else {}
    current_tests = extract_assessment_tests(current_assessment_doc) if current_assessment_doc else {}

    result = {}

    for metric_name, extractor in _METRIC_EXTRACTORS.items():
        baseline_value = extractor(baseline_tests)
        previous_value = extractor(previous_tests)
        current_value = extractor(current_tests)

        result[metric_name] = {
            "baseline_vs_current": compare_metric(baseline_value, current_value, metric_name),
            "previous_vs_current": compare_metric(previous_value, current_value, metric_name),
        }

    return result


def overall_direction(metric_comparisons: dict, *, key: str = "baseline_vs_current") -> str:
    """Roll several per-metric comparisons (as produced by
    compare_physical_assessments) up into one overall PROGRESS_DIRECTIONS
    value. Deterministic priority order: any DECLINED -> DECLINED (a
    regression is never hidden by an improvement elsewhere); else any
    IMPROVED -> IMPROVED; else, if at least one metric had enough data,
    STABLE; else NOT_ENOUGH_DATA (nothing at all could be compared).
    """

    directions = [entry[key]["direction"] for entry in metric_comparisons.values()]

    if DECLINED in directions:
        return DECLINED

    if IMPROVED in directions:
        return IMPROVED

    if STABLE in directions:
        return STABLE

    return NOT_ENOUGH_DATA
