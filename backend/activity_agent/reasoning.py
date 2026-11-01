"""Deterministic reasoning for the Exercise & Physical Activity domain.

Pure functions over an activity view (activity_agent/evidence.py). No
randomness, no model call, no clock: the same view always produces the
same findings, which is what makes this specialist's output auditable
beside the measurements it came from.

Every threshold below is a SYSTEM DECISION, the same discipline
need_assessment/rules.py applies to its own: a line this project chose so
activity volume can be discussed consistently. None of them is a clinical
prescription, and none is presented to a user as one. Where a threshold
already exists elsewhere in this codebase it is imported rather than
restated, so the two can never drift apart.

What this module may decide: how much daily activity the user is doing,
whether that volume is low by the project's own marker, and what a
realistic next volume target is. What it must never decide: which
exercise to perform (physio_agent), whether a recommendation is safe
(safety), how to sleep (recovery_agent), or what to eat (nutrition).
"""

from need_assessment.rules import (
    EXERCISE_DAYS_LOW_THRESHOLD,
    SITTING_HOURS_HIGH_THRESHOLD,
    WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD,
)
from orchestration.evidence import (
    STATUS_ASSESSED,
    STATUS_INSUFFICIENT_EVIDENCE,
    confidence_from,
    evidence_lines,
    known,
    missing_labels,
)

# Daily step count below which this project treats activity volume as low.
# Shared with orchestrator/decision.py so the selection rule and this
# agent's own finding can never disagree about what "low" means.
STEPS_LOW_THRESHOLD = 5000

# How far a step target may move in one cycle: a share of what the user is
# already doing, never a fixed population number, and never more than the
# absolute cap. Progression is relative to this person's own baseline.
STEPS_PROGRESSION_RATIO = 0.20
STEPS_PROGRESSION_CAP = 1500
STEPS_PROGRESSION_ROUNDING = 250

# The same increment, halved, when another specialist has reported a
# constraint this cycle (see the Coordination note in agent.py).
CONSTRAINED_PROGRESSION_RATIO = 0.10

# Weekly session frequency is raised by at most one day per cycle, and
# never beyond this ceiling without new evidence.
MAX_SESSION_DAYS_PER_WEEK = 5

# Components for a transparent, project-defined indicator. These are the
# existing planning markers (plus the five-day planning ceiling), not clinical
# targets. Missing inputs are omitted from the average rather than scored 0.
ACTIVITY_SCORE_STEPS_MARKER = STEPS_LOW_THRESHOLD
ACTIVITY_SCORE_WEEKLY_MINUTES_MARKER = WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD
ACTIVITY_SCORE_EXERCISE_DAYS_MARKER = MAX_SESSION_DAYS_PER_WEEK
ACTIVITY_SCORE_SITTING_MARKER = SITTING_HOURS_HIGH_THRESHOLD
ACTIVITY_SCORE_MOVEMENT_BREAKS_MARKER = 3

# Core signals: at least one must be KNOWN for this domain to say anything.
CORE_SIGNALS = (
    "daily_steps",
    "exercise_days",
    "weekly_exercise_minutes",
    "daily_sitting_hours",
)


def _round_to(value, step):
    return int(round(value / step) * step)


def _step_target(current, *, constrained):
    ratio = CONSTRAINED_PROGRESSION_RATIO if constrained else STEPS_PROGRESSION_RATIO
    increment = min(current * ratio, STEPS_PROGRESSION_CAP)

    return _round_to(current + increment, STEPS_PROGRESSION_ROUNDING)


def _finding(name, text, *, value=None):
    return {"signal": name, "finding": text, "value": value, "measured": True}


def _activity_score(signals, movement_breaks_context=None):
    """Equal-weight available activity dimensions; unknowns are not zeroes."""
    values = {name: signals.get(name, {}).get("value") for name in (
        "daily_steps", "exercise_days", "weekly_exercise_minutes",
        "daily_sitting_hours", "movement_breaks_per_day",
    )}
    formulas = {
        "daily_steps": lambda value: min(value / ACTIVITY_SCORE_STEPS_MARKER, 1.0) * 100,
        "exercise_days": lambda value: min(value / ACTIVITY_SCORE_EXERCISE_DAYS_MARKER, 1.0) * 100,
        "weekly_exercise_minutes": lambda value: min(value / ACTIVITY_SCORE_WEEKLY_MINUTES_MARKER, 1.0) * 100,
        "daily_sitting_hours": lambda value: (1.0 - min(value / ACTIVITY_SCORE_SITTING_MARKER, 1.0)) * 100,
        "movement_breaks_per_day": lambda value: min(value / ACTIVITY_SCORE_MOVEMENT_BREAKS_MARKER, 1.0) * 100,
    }
    labels = {
        "daily_steps": "Daily steps",
        "exercise_days": "Exercise days per week",
        "weekly_exercise_minutes": "Weekly exercise minutes",
        "daily_sitting_hours": "Daily sitting time",
        "movement_breaks_per_day": "Movement breaks per day",
    }
    units = {
        "daily_steps": "steps/day",
        "exercise_days": "days/week",
        "weekly_exercise_minutes": "minutes/week",
        "daily_sitting_hours": "hours/day",
        "movement_breaks_per_day": "breaks/day",
    }
    thresholds = {
        "daily_steps": ACTIVITY_SCORE_STEPS_MARKER,
        "exercise_days": ACTIVITY_SCORE_EXERCISE_DAYS_MARKER,
        "weekly_exercise_minutes": ACTIVITY_SCORE_WEEKLY_MINUTES_MARKER,
        "daily_sitting_hours": ACTIVITY_SCORE_SITTING_MARKER,
        "movement_breaks_per_day": ACTIVITY_SCORE_MOVEMENT_BREAKS_MARKER,
    }
    components = []
    for metric, value in values.items():
        available = isinstance(value, (int, float)) and not isinstance(value, bool)
        score = round(formulas[metric](value), 1) if available and metric in formulas else None
        components.append({
            "metric": metric,
            "label": labels[metric],
            "unit": units[metric],
            "project_marker": thresholds[metric],
            "direction": "lower_is_better" if metric == "daily_sitting_hours" else "higher_is_better",
            "input_value": value if available else None,
            "score": score,
            "status": "AVAILABLE" if score is not None else "UNKNOWN",
        })
    scored = [item["score"] for item in components if item["score"] is not None]
    return {
        "value": round(sum(scored) / len(scored), 1) if scored else None,
        "scale": "0–100",
        "label": "MoveWell Activity Indicator",
        "interpretation": "Project-defined activity summary, not a medically validated clinical score.",
        "method": "Each available input is normalized against its listed project marker (sitting is inverse); component scores are equally weighted and unknown inputs are excluded.",
        "inputs": values,
        "thresholds": {
            **thresholds,
        },
        "components": components,
        "movement_breaks_observation": movement_breaks_context or {
            "basis": "No daily check-in movement-break values were supplied.",
            "dates": [],
            "days_observed": 0,
        },
    }


def assess_activity(view: dict) -> dict:
    """The Exercise & Physical Activity domain finding for one user.

    Returns this specialist's own output shape: status, the evidence it
    used, what it found, the volume recommendations it is making, the
    progression behind them, the constraints it applied, what it still
    does not know, and a confidence reflecting how much of its own
    evidence actually existed.
    """

    signals = view["signals"]
    present = known(signals)

    constraint_input = view.get("recovery_constraint") or {}
    constrained = bool(constraint_input.get("limit_progression"))

    constraints = []

    if constrained:
        constraints.append(
            {
                "source": "recovery",
                "constraint": "limit_progression",
                "detail": constraint_input.get("reason")
                or "Recovery evidence this cycle suggests a slower rate of increase.",
            }
        )

    for dimension, level in (view.get("pacing_need_levels") or {}).items():
        if level == "HIGH":
            constraints.append(
                {
                    "source": "movement_assessment",
                    "constraint": "pace_alongside_movement_programme",
                    "detail": (
                        f"{dimension.replace('_', ' ')} is HIGH, so activity volume is "
                        "increased alongside the movement programme rather than ahead of it."
                    ),
                }
            )

    if not any(name in present for name in CORE_SIGNALS):
        return {
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "evidence_used": [],
            "activity_findings": [],
            "activity_recommendations": [],
            "progression": [],
            "constraints": constraints,
            "missing_information": missing_labels(signals),
            "confidence": 0.0,
            "activity_score": _activity_score(signals, view.get("movement_breaks_context")),
        }

    findings = []
    recommendations = []
    progression = []

    steps = present.get("daily_steps", {}).get("value")
    days = present.get("exercise_days", {}).get("value")
    weekly = present.get("weekly_exercise_minutes", {}).get("value")
    sitting = present.get("daily_sitting_hours", {}).get("value")
    sessions = present.get("recorded_sessions", {}).get("value")

    if steps is not None and steps < STEPS_LOW_THRESHOLD:
        target = _step_target(steps, constrained=constrained)
        findings.append(
            _finding(
                "daily_steps",
                f"Self-reported daily steps ({steps:g}) are below this project's "
                f"{STEPS_LOW_THRESHOLD:,}-step marker for an active day.",
                value=steps,
            )
        )
        recommendations.append(
            {
                "id": "increase_daily_steps",
                "title": "Build daily walking volume",
                "action": (
                    f"Work towards about {target:,} steps a day, up from your current "
                    f"{steps:g}, and hold that for a week before increasing again."
                ),
                "why": (
                    "The target is set from your own current step count rather than a "
                    "population average, so the increase stays realistic."
                ),
                "target": {"metric": "daily_steps", "from": steps, "to": target},
            }
        )
        progression.append(
            {
                "metric": "daily_steps",
                "current": steps,
                "next_target": target,
                "rate": "constrained" if constrained else "standard",
                "review_after": "one week of meeting the target",
            }
        )
    elif steps is not None:
        findings.append(
            _finding(
                "daily_steps",
                f"Self-reported daily steps ({steps:g}) are at or above this project's "
                f"{STEPS_LOW_THRESHOLD:,}-step marker.",
                value=steps,
            )
        )
        recommendations.append(
            {
                "id": "maintain_daily_steps",
                "title": "Keep your current walking volume",
                "action": f"Keep daily walking at around {steps:g} steps.",
                "why": "Your reported volume already meets this project's activity marker.",
                "target": {"metric": "daily_steps", "from": steps, "to": steps},
            }
        )

    if days is not None and days < EXERCISE_DAYS_LOW_THRESHOLD:
        findings.append(
            _finding(
                "exercise_days",
                f"Self-reported exercise frequency ({days:g} day(s)/week) is below this "
                f"project's {EXERCISE_DAYS_LOW_THRESHOLD}-day marker.",
                value=days,
            )
        )

        if constrained:
            recommendations.append(
                {
                    "id": "hold_activity_frequency",
                    "title": "Hold your current session frequency",
                    "action": f"Stay at {days:g} session(s) a week for now, and keep them short.",
                    "why": (
                        "A recovery constraint was reported this cycle, so frequency is held "
                        "rather than increased."
                    ),
                    "target": {"metric": "exercise_days", "from": days, "to": days},
                }
            )
        else:
            target_days = min(days + 1, MAX_SESSION_DAYS_PER_WEEK)
            recommendations.append(
                {
                    "id": "add_activity_session",
                    "title": "Add one activity session a week",
                    "action": (
                        f"Add a single planned session, taking you from {days:g} to "
                        f"{target_days:g} day(s) a week. Keep the length the same."
                    ),
                    "why": "One extra session is a change small enough to repeat next week.",
                    "target": {"metric": "exercise_days", "from": days, "to": target_days},
                }
            )
            progression.append(
                {
                    "metric": "exercise_days",
                    "current": days,
                    "next_target": target_days,
                    "rate": "standard",
                    "review_after": "two weeks",
                }
            )

    if weekly is not None and weekly < WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD:
        findings.append(
            _finding(
                "weekly_exercise_minutes",
                f"Self-reported weekly activity volume (about {weekly:g} minutes) is below "
                f"this project's {WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD}-minute marker.",
                value=weekly,
            )
        )

    if sitting is not None and sitting >= SITTING_HOURS_HIGH_THRESHOLD:
        findings.append(
            _finding(
                "daily_sitting_hours",
                f"Self-reported sitting time ({sitting:g} hours/day) is at or above this "
                f"project's {SITTING_HOURS_HIGH_THRESHOLD}-hour marker.",
                value=sitting,
            )
        )
        recommendations.append(
            {
                "id": "interrupt_sitting",
                "title": "Break up long sitting blocks",
                "action": (
                    "Interrupt sitting with two to three minutes of movement roughly once an "
                    "hour during your working day."
                ),
                "why": (
                    f"Your reported {sitting:g} hours of sitting a day is where most of your "
                    "waking time currently goes, so it is where extra movement fits."
                ),
                "target": {"metric": "sitting_breaks", "from": None, "to": "hourly"},
            }
        )

    if sessions is not None:
        findings.append(
            _finding(
                "recorded_sessions",
                f"{sessions} completed session(s) recorded against the current programme.",
                value=sessions,
            )
        )

    return {
        "status": STATUS_ASSESSED,
        "evidence_used": evidence_lines(signals),
        "activity_findings": findings,
        "activity_recommendations": recommendations,
        "progression": progression,
        "constraints": constraints,
        "missing_information": missing_labels(signals),
        "confidence": confidence_from(signals),
        "activity_score": _activity_score(signals, view.get("movement_breaks_context")),
    }
