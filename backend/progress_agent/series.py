"""Progress over time, assembled from what the user has actually recorded.

This is a READ-ONLY view for the Progress page. It introduces no new
measurement, no new comparison rule, and no derived "score": the movement
numbers come from comparison.py's existing extractors -- the very same
functions the Progress Agent compares and that need_assessment/rules.py
bases its levels on -- so a figure plotted here and a figure the agent
reasons about can never disagree.

The one rule that shapes everything below: a series with fewer than two
points is not a trend. Rather than drawing a line through a single dot,
each series reports how many points it has and whether it is plottable,
and the interface says so plainly. An empty series means "nothing
recorded yet", never "no progress".
"""

from exercise_library.catalog import ExerciseNotFoundError, get_exercise_details
from progress_agent.comparison import (
    DIRECTION_HIGHER_IS_BETTER,
    METRIC_DIRECTIONS,
    _METRIC_EXTRACTORS,
)

# Two points is the minimum that can show a change at all.
MIN_POINTS_FOR_TREND = 2

METRIC_LABELS = {
    "mobility_shoulder_elevation_deg": "Shoulder elevation",
    "stability_balance_hold_seconds": "One-leg balance hold",
    "functional_movement_ftsst_seconds": "Sit-to-stand x5 time",
}

METRIC_UNITS = {
    "mobility_shoulder_elevation_deg": "degrees",
    "stability_balance_hold_seconds": "seconds",
    "functional_movement_ftsst_seconds": "seconds",
}


def _day(value) -> str:
    """The calendar day of a timestamp, or None.

    Accepts a datetime as well as an ISO string: the exercise-result
    serialiser passes `completedAt` through untouched while it formats
    `recordedAt`, so both shapes genuinely reach here.
    """

    if value is None:
        return None

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    text = str(value)

    return text[:10] if len(text) >= 10 else None


def _result_day(result) -> str:
    """The day a result happened, preferring when it was completed.

    Falls through to `recordedAt` rather than discarding the result: a
    completion timestamp this function cannot read is a reason to use
    the other one, not a reason to drop a session the user did.
    """

    return _day(result.get("completedAt")) or _day(result.get("recordedAt"))


def completions_by_day(exercise_results) -> dict:
    """How many exercises were completed on each day the user recorded one.

    Camera-measured sessions and self-reported ticks are counted
    separately as well as together, because they are different kinds of
    evidence and a chart that merged them silently would overstate what
    was measured.
    """

    days = {}

    for result in exercise_results or []:
        if not isinstance(result, dict):
            continue

        day = _result_day(result)

        if day is None:
            continue

        bucket = days.setdefault(day, {"date": day, "total": 0, "measured": 0, "self_reported": 0})
        bucket["total"] += 1

        if result.get("source") == "manual_confirmation":
            bucket["self_reported"] += 1
        else:
            bucket["measured"] += 1

    points = [days[day] for day in sorted(days)]

    return {
        "points": points,
        "point_count": len(points),
        "plottable": len(points) >= MIN_POINTS_FOR_TREND,
        "total_completions": sum(point["total"] for point in points),
    }


def movement_metric_series(assessment_documents) -> list:
    """One series per movement metric, oldest first.

    `assessment_documents` are raw stored assessments (the shape
    assessments/store.py's `list_assessments` returns). An assessment
    that did not complete a given check contributes no point to that
    metric's series -- a skipped check is an absence, and carrying it
    forward as a zero would invent a decline that never happened.
    """

    ordered = sorted(
        (document for document in assessment_documents or [] if isinstance(document, dict)),
        key=lambda document: str(document.get("completed_at") or ""),
    )

    series = []

    for metric, extract in _METRIC_EXTRACTORS.items():
        points = []

        for document in ordered:
            completed_at = document.get("completed_at")
            value = extract(document.get("tests") or {})

            if value is None:
                continue

            points.append(
                {
                    "date": _day(str(completed_at)) if completed_at else None,
                    "recordedAt": str(completed_at) if completed_at else None,
                    "value": value,
                }
            )

        series.append(
            {
                "metric": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "unit": METRIC_UNITS.get(metric, ""),
                "higherIsBetter": METRIC_DIRECTIONS.get(metric) == DIRECTION_HIGHER_IS_BETTER,
                "points": points,
                "point_count": len(points),
                "plottable": len(points) >= MIN_POINTS_FOR_TREND,
            }
        )

    return series


def _plan_versions(section) -> list:
    """Every stored version of one domain's plan, oldest first.

    Reads the same `data.plans` list behind an `available` section that
    workflow/response.py's `_latest_plan_record` reads, so the history
    shown here and the plan shown on My Plan come from one place.
    """

    if not isinstance(section, dict) or not section.get("available"):
        return []

    versions = (section.get("data") or {}).get("plans") or []

    if not isinstance(versions, list):
        return []

    entries = []

    for record in versions:
        if not isinstance(record, dict):
            continue

        entries.append(
            {
                "version": record.get("plan_version"),
                "createdAt": record.get("created_at"),
                "changeCount": len(record.get("changes") or []),
                "adaptationReason": record.get("adaptation_reason"),
            }
        )

    return sorted(entries, key=lambda entry: str(entry.get("createdAt") or ""))


def plan_version_history(user_state) -> list:
    """Plan adaptations over time, per domain that actually has a plan."""

    domains = (
        ("Movement", "exercise_history"),
        ("Nutrition", "nutrition_plan"),
        ("Daily habits", "behaviour"),
    )

    history = []

    for label, section_name in domains:
        versions = _plan_versions((user_state or {}).get(section_name))

        if versions:
            history.append(
                {
                    "domain": label,
                    "versions": versions,
                    "version_count": len(versions),
                }
            )

    return history


def recent_completions(exercise_results, *, limit: int = 10) -> list:
    """The most recently completed exercises, newest first.

    Each entry carries the exercise's own library name as well as its id, so a
    screen can say "Chair Sit-to-Stand" instead of `chair-sit-to-stand`. The id
    is still sent: it is the identifier the exercise page and the results API
    use, and dropping it would leave the row unactionable.
    """

    dated = [
        result
        for result in exercise_results or []
        if isinstance(result, dict) and _result_day(result)
    ]

    dated.sort(key=_result_day, reverse=True)

    entries = []

    for result in dated[:limit]:
        exercise_id = result.get("exerciseId")

        try:
            name = get_exercise_details(exercise_id)["name"]
        except (ExerciseNotFoundError, TypeError):
            # An id from a library snapshot that no longer has it: the id is
            # shown rather than the row being hidden.
            name = exercise_id

        entries.append(
            {
                "exerciseId": exercise_id,
                "exerciseName": name,
                "completedAt": _result_day(result),
                "status": result.get("status"),
                "source": result.get("source") or "camera",
            }
        )

    return entries


def build_progress_series(
    *, exercise_results=None, assessment_documents=None, user_state=None
) -> dict:
    """Everything the Progress page plots, with its own sufficiency flags."""

    completions = completions_by_day(exercise_results)
    metrics = movement_metric_series(assessment_documents)
    plans = plan_version_history(user_state)

    return {
        "completions": completions,
        "movementMetrics": metrics,
        "planHistory": plans,
        "recentCompletions": recent_completions(exercise_results),
        # One flag the interface can trust instead of re-deriving the
        # same question in three places.
        "hasAnyTrend": completions["plottable"]
        or any(series["plottable"] for series in metrics),
        "minPointsForTrend": MIN_POINTS_FOR_TREND,
    }
