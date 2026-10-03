"""Deterministic reasoning for the Recovery & Care domain.

Pure functions over a recovery view (recovery_agent/evidence.py).

This specialist answers one question: does the rest and workload evidence
support the pace the user is being asked to work at? Its distinctive
output is a *constraint* other specialists must respect, not a programme
of its own -- it never prescribes exercises, never repeats the activity
plan, and never names a sleep disorder. Short or poor sleep is reported
as reported, as a reason to slow progression and look at rest routines,
never as a diagnosis.

Thresholds are system decisions, consistent with the rest of this
project, and are not clinical cut-offs.
"""

from orchestration.evidence import (
    STATUS_ASSESSED,
    STATUS_INSUFFICIENT_EVIDENCE,
    confidence_from,
    evidence_lines,
    known,
    missing_labels,
)
from recovery_agent.evidence import SLEEP_QUALITY_CONCERN_VALUES

# Nightly sleep below which this project treats rest as a constraint on
# how quickly activity should increase. Shared with
# orchestrator/decision.py so the selection rule and this agent's own
# finding cannot disagree.
SLEEP_SHORT_THRESHOLD_HOURS = 6.0

# A programme of at least this many exercises, with short or poor sleep
# reported alongside it, is treated as a workload worth pacing.
WORKLOAD_EXERCISE_COUNT = 4

RECOVERY_SUPPORTIVE = "SUPPORTIVE"
RECOVERY_CONSTRAINED = "CONSTRAINED"

CORE_SIGNALS = ("sleep_hours", "sleep_quality")


def _finding(name, text, *, value=None):
    return {"signal": name, "finding": text, "value": value, "measured": True}


def assess_recovery(view: dict) -> dict:
    """The Recovery & Care domain finding for one user.

    Returns status, evidence used, findings, recovery recommendations, the
    constraint this domain places on progression (the field other
    specialists read), what is still missing, and a confidence.
    """

    signals = view["signals"]
    present = known(signals)

    if not any(name in present for name in CORE_SIGNALS):
        return {
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "recovery_status": None,
            "evidence_used": evidence_lines(signals),
            "recovery_findings": [],
            "recovery_recommendations": [],
            "constraint": {"limit_progression": False, "reason": None},
            "missing_information": missing_labels(signals),
            "confidence": confidence_from(signals),
        }

    sleep_hours = present.get("sleep_hours", {}).get("value")
    quality = present.get("sleep_quality", {}).get("value")
    planned = present.get("planned_exercises", {}).get("value")
    completed = present.get("completed_sessions", {}).get("value")

    findings = []
    recommendations = []
    reasons = []

    if sleep_hours is not None and sleep_hours < SLEEP_SHORT_THRESHOLD_HOURS:
        findings.append(
            _finding(
                "sleep_hours",
                f"Self-reported sleep is {sleep_hours:g} hours a night, below this project's "
                f"{SLEEP_SHORT_THRESHOLD_HOURS:g}-hour marker for treating rest as a constraint.",
                value=sleep_hours,
            )
        )
        reasons.append(f"sleep is {sleep_hours:g} hours a night")
        recommendations.append(
            {
                "id": "protect_sleep_window",
                "title": "Protect a longer sleep window",
                "action": (
                    "Pick a fixed time to stop work and screens, and keep the same wake time "
                    "every day for the next two weeks."
                ),
                "why": (
                    f"You reported {sleep_hours:g} hours a night. A consistent window is the "
                    "part of that you can change without changing anything else in the day."
                ),
            }
        )
    elif sleep_hours is not None:
        findings.append(
            _finding(
                "sleep_hours",
                f"Self-reported sleep is {sleep_hours:g} hours a night, at or above this "
                f"project's {SLEEP_SHORT_THRESHOLD_HOURS:g}-hour marker.",
                value=sleep_hours,
            )
        )

    if quality in SLEEP_QUALITY_CONCERN_VALUES:
        findings.append(
            _finding(
                "sleep_quality",
                f"Self-reported sleep quality is '{quality}'.",
                value=quality,
            )
        )
        reasons.append(f"sleep quality is reported as '{quality}'")
        recommendations.append(
            {
                "id": "wind_down_routine",
                "title": "Add a short wind-down before bed",
                "action": "Spend the last 20 minutes before bed off screens and out of work.",
                "why": (
                    f"You described your sleep as '{quality}'. This is a routine change, not "
                    "treatment, and a professional is the right next step if it persists."
                ),
            }
        )
    elif quality is not None:
        findings.append(
            _finding("sleep_quality", f"Self-reported sleep quality is '{quality}'.", value=quality)
        )

    workload_heavy = planned is not None and planned >= WORKLOAD_EXERCISE_COUNT

    if workload_heavy:
        findings.append(
            _finding(
                "planned_exercises",
                f"The current programme asks for {planned} exercises.",
                value=planned,
            )
        )

    if completed is not None:
        findings.append(
            _finding(
                "completed_sessions",
                f"{completed} session(s) recorded against the current programme.",
                value=completed,
            )
        )

    limit_progression = bool(reasons)

    if limit_progression and workload_heavy:
        recommendations.append(
            {
                "id": "space_demanding_sessions",
                "title": "Leave a rest day between harder sessions",
                "action": (
                    "Keep at least one full day between the more demanding sessions in your "
                    "programme rather than stacking them."
                ),
                "why": (
                    f"Your programme currently asks for {planned} exercises while "
                    + " and ".join(reasons)
                    + "."
                ),
            }
        )

    reason_text = None

    if limit_progression:
        reason_text = (
            "Recovery evidence this cycle: " + " and ".join(reasons) + "."
        )

    return {
        "status": STATUS_ASSESSED,
        "recovery_status": RECOVERY_CONSTRAINED if limit_progression else RECOVERY_SUPPORTIVE,
        "evidence_used": evidence_lines(signals),
        "recovery_findings": findings,
        "recovery_recommendations": recommendations,
        # The field other specialists read. Activity halves its step
        # increment and holds session frequency when this is set; nothing
        # else in the system may raise a target because of it.
        "constraint": {"limit_progression": limit_progression, "reason": reason_text},
        "missing_information": missing_labels(signals),
        "confidence": confidence_from(signals),
    }
