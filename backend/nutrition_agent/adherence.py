"""Deterministic food-log adherence, computed only from real logged data.

Mirrors progress_agent/adherence.py's discipline exactly, with one rule
this module takes even more seriously than that one, because the data is
more easily misread:

    NO FOOD LOG IS NOT EVIDENCE THAT THE USER DID NOT EAT.

An unlogged day means the tracking did not happen. It does not mean a meal
was skipped, and it is never reported as NOT_ADHERED. That outcome exists
only when there IS logging in the period and it covers fewer days than the
period contains — i.e. when the user demonstrably was logging and there are
gaps — and even then what is being measured is LOGGING adherence, never
"the user ate badly". Nothing in this module scores a food, computes a
calorie total, or judges diet quality.

What "adherence" means here, precisely and narrowly: of the days in the
observation period during which a given nutrition plan was actually in
effect, on how many days did this user record at least one food log entry
against that plan. There is no scheduling system in this application (see
progress_agent/adherence.py's docstring on why), and this project's
nutrition plans set general goals, not a meal count — so a "3 meals a day"
target the user never agreed to is deliberately NOT invented here. Days
with any logging is the honest denominator the real data supports.

Same input, same output, always: no clock is read, no randomness is used,
and every collection is sorted before it is returned.
"""

from datetime import date, datetime, timezone

# Outcomes. Exactly four, and the difference between the last two matters:
#   ADHERED           logging covered the period at or above the threshold
#   NOT_ADHERED       the user WAS logging, and there are real gaps
#   NOT_LOGGED        no food log entries at all for this plan/period
#   INSUFFICIENT_DATA nothing can be honestly computed (no period, a period
#                     too short to mean anything, a plan not yet in effect)
ADHERED = "ADHERED"
NOT_ADHERED = "NOT_ADHERED"
NOT_LOGGED = "NOT_LOGGED"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# A single day of observation cannot distinguish "does not log" from "has
# not logged yet today", so anything shorter than this is INSUFFICIENT_DATA
# rather than a number that reads like a verdict.
MIN_OBSERVATION_DAYS = 3

# At or above this share of observed days carrying at least one entry is
# reported as ADHERED. It is a logging-coverage threshold, not a clinical
# or dietary one, and it is stated here rather than buried in a comparison.
ADHERENCE_THRESHOLD = 0.8

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


class FoodLogAdherenceError(ValueError):
    """Raised for a structurally invalid input, never silently coerced."""


def _as_date(value, label: str):
    """Normalise a date/datetime/ISO-string to a date. None stays None."""

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value

        try:
            parsed = datetime.fromisoformat(text)

        except ValueError:
            try:
                return date.fromisoformat(text[:10])

            except ValueError:
                raise FoodLogAdherenceError(
                    f"{label} must be a date, datetime, or ISO 8601 string, got {value!r}"
                ) from None

        return parsed.astimezone(timezone.utc).date() if parsed.tzinfo else parsed.date()

    raise FoodLogAdherenceError(
        f"{label} must be a date, datetime, or ISO 8601 string, got {value!r}"
    )


def _entry_date(entry: dict):
    """The date an entry was recorded, or None if the entry carries no
    usable timestamp — an undated entry is counted as an entry but cannot
    be attributed to a day, and is reported separately rather than being
    silently dropped or silently assigned to today."""

    for field in ("recorded_at", "recordedAt"):
        if field in entry and entry[field] is not None:
            try:
                return _as_date(entry[field], field)

            except FoodLogAdherenceError:
                return None

    return None


def _result(
    *,
    plan_id,
    status,
    completion_rate,
    observation_days,
    logged_days,
    period_start,
    period_end,
    entries_considered=0,
    entries_excluded_other_plan=0,
    entries_without_date=0,
    per_day=None,
    per_meal_type=None,
    notes=None,
):
    return {
        "plan_id": plan_id,
        "status": status,
        "completion_rate": completion_rate,
        "observation_days": observation_days,
        "logged_days": logged_days,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "entries_considered": entries_considered,
        "entries_excluded_other_plan": entries_excluded_other_plan,
        "entries_without_date": entries_without_date,
        "per_day": per_day or {},
        "per_meal_type": per_meal_type or {meal: 0 for meal in MEAL_TYPES},
        "adherence_threshold": ADHERENCE_THRESHOLD,
        "min_observation_days": MIN_OBSERVATION_DAYS,
        "notes": sorted(notes or []),
    }


def compute_food_log_adherence(
    plan_record: dict,
    food_log_entries: list,
    *,
    period_start=None,
    period_end=None,
) -> dict:
    """Compute food-logging adherence for one nutrition plan record.

    `plan_record` is the User State nutrition_plan history record shape
    (orchestrator/state_update.py's apply_nutrition_plan output: plan_id,
    created_at, goal, topic_ids, ...). `food_log_entries` is a list of
    stored food_log documents (food_log/store.py's shape: meal, plan_id,
    recorded_at, ...).

    The observation window is [period_start, period_end], intersected with
    the period the plan was actually in effect: a plan created part-way
    through the window is only held to the days from its own created_at
    onward, so a plan that changed mid-period is never charged for days
    that belonged to the previous plan.

    Returns a structured result whose `status` is one of ADHERED,
    NOT_ADHERED, NOT_LOGGED, INSUFFICIENT_DATA, and whose
    `completion_rate` is a real computed number or None — never a 0.0
    standing in for missing data.
    """

    if not isinstance(plan_record, dict) or "plan_id" not in plan_record:
        raise FoodLogAdherenceError("plan_record must be an object with a plan_id")

    if food_log_entries is not None and not isinstance(food_log_entries, (list, tuple)):
        raise FoodLogAdherenceError("food_log_entries must be a list")

    plan_id = plan_record["plan_id"]
    entries = list(food_log_entries or [])

    start = _as_date(period_start, "period_start")
    end = _as_date(period_end, "period_end")
    plan_created = _as_date(plan_record.get("created_at"), "plan_record.created_at")

    notes = []

    if start is None or end is None:
        return _result(
            plan_id=plan_id,
            status=INSUFFICIENT_DATA,
            completion_rate=None,
            observation_days=None,
            logged_days=None,
            period_start=start,
            period_end=end,
            notes=[
                "no observation period was given, so there is no denominator "
                "to compute a rate against; this is not a claim about the "
                "user's logging"
            ],
        )

    if end < start:
        raise FoodLogAdherenceError("period_end must not be earlier than period_start")

    effective_start = start

    if plan_created is not None and plan_created > start:
        effective_start = plan_created
        notes.append(
            "the plan was created part-way through the requested period; only "
            "days from its created_at onward are counted"
        )

    if effective_start > end:
        return _result(
            plan_id=plan_id,
            status=INSUFFICIENT_DATA,
            completion_rate=None,
            observation_days=0,
            logged_days=None,
            period_start=start,
            period_end=end,
            notes=notes
            + ["this plan was not yet in effect during the requested period"],
        )

    observation_days = (end - effective_start).days + 1

    # Ownership of an entry to this plan is explicit: only entries recorded
    # against this plan_id count. Entries for another plan are counted and
    # reported separately, never folded in and never treated as a gap.
    mine = []
    excluded_other_plan = 0

    for entry in entries:
        entry_date = _entry_date(entry)

        if entry_date is not None and not (effective_start <= entry_date <= end):
            continue

        if entry.get("plan_id") != plan_id:
            excluded_other_plan += 1
            continue

        mine.append((entry_date, entry))

    entries_without_date = sum(1 for entry_date, _ in mine if entry_date is None)

    if entries_without_date:
        notes.append(
            "some entries for this plan carry no usable timestamp and could "
            "not be attributed to a day; they are counted in "
            "entries_considered but not in logged_days"
        )

    per_day = {}
    per_meal_type = {meal: 0 for meal in MEAL_TYPES}

    for entry_date, entry in mine:
        meal = entry.get("meal")

        if meal in per_meal_type:
            per_meal_type[meal] += 1

        if entry_date is None:
            continue

        key = entry_date.isoformat()
        day = per_day.setdefault(key, {"entries": 0, "meals": []})
        day["entries"] += 1

        if meal is not None and meal not in day["meals"]:
            day["meals"].append(meal)

    for day in per_day.values():
        day["meals"].sort()

    per_day = {key: per_day[key] for key in sorted(per_day)}
    logged_days = len(per_day)

    if not mine:
        # Nothing was logged for this plan in this period. That is a
        # tracking fact, not an eating fact — NOT_LOGGED, never
        # NOT_ADHERED, and no rate is invented.
        if excluded_other_plan:
            notes.append(
                "food log entries exist in this period but were recorded "
                "against a different plan_id, so they say nothing about "
                "this plan"
            )

        return _result(
            plan_id=plan_id,
            status=NOT_LOGGED,
            completion_rate=None,
            observation_days=observation_days,
            logged_days=0,
            period_start=start,
            period_end=end,
            entries_considered=0,
            entries_excluded_other_plan=excluded_other_plan,
            per_meal_type=per_meal_type,
            notes=notes
            + [
                "no food log entries for this plan in this period; this is an "
                "absence of tracking, not evidence that the user did not eat"
            ],
        )

    if observation_days < MIN_OBSERVATION_DAYS:
        return _result(
            plan_id=plan_id,
            status=INSUFFICIENT_DATA,
            completion_rate=None,
            observation_days=observation_days,
            logged_days=logged_days,
            period_start=start,
            period_end=end,
            entries_considered=len(mine),
            entries_excluded_other_plan=excluded_other_plan,
            entries_without_date=entries_without_date,
            per_day=per_day,
            per_meal_type=per_meal_type,
            notes=notes
            + [
                f"the observation period is {observation_days} day(s), shorter "
                f"than the {MIN_OBSERVATION_DAYS} days needed to say anything "
                "meaningful about a logging pattern"
            ],
        )

    completion_rate = min(logged_days, observation_days) / observation_days
    status = ADHERED if completion_rate >= ADHERENCE_THRESHOLD else NOT_ADHERED

    if status == NOT_ADHERED:
        notes.append(
            "this measures LOGGING coverage across the period, not diet "
            "quality: days without an entry are days without tracking"
        )

    return _result(
        plan_id=plan_id,
        status=status,
        completion_rate=completion_rate,
        observation_days=observation_days,
        logged_days=logged_days,
        period_start=start,
        period_end=end,
        entries_considered=len(mine),
        entries_excluded_other_plan=excluded_other_plan,
        entries_without_date=entries_without_date,
        per_day=per_day,
        per_meal_type=per_meal_type,
        notes=notes,
    )
