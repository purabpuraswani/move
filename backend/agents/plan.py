"""Deciding what can run before anything is run.

Separated from the orchestrator so the decision is testable on its own: given a
context and whether a model is configured, which agents can produce something,
what is stopping the others, and what the person could do about it.

The distinction this file keeps is between a blocker and a note. A blocker means
an agent cannot produce anything honest and will not be called. A note means it
can run but something is worth saying about the basis it is running on — reports
sitting unconfirmed, only one source of information available, a session where
every test came out invalid. Collapsing the two would either refuse to help
somebody who could be helped, or produce guidance that quietly rests on less
than it appears to.

Standard library only.
"""

from agents.registry import (
    CARE_NAVIGATION,
    REPORT_EXTRACTION,
    WELLNESS_GUIDANCE,
)

# Things the person can do to make guidance possible or better. Named rather
# than described, so the wording and the link belong to the interface.
ACTION_COMPLETE_PROFILE = "complete_profile"
ACTION_RECORD_ASSESSMENT = "record_assessment"
ACTION_ADD_REPORT = "add_report"
ACTION_CONFIRM_REPORT = "confirm_report"


def report_stage_state(report_context: dict, *, extraction_available: bool) -> dict:
    """Where the report stage has got to for this user.

    The first agent in the sequence is the report reader, and the rule that it
    runs before anything downstream is not enforced by calling it here — it is
    enforced by the fact that only confirmed values reach a context at all. What
    this function does is explain the situation, so a user with a report waiting
    to be checked is told that rather than left wondering why their readings are
    not mentioned.
    """

    confirmed = report_context.get("confirmedReportCount") or 0
    unconfirmed = report_context.get("unconfirmedReportCount") or 0

    if confirmed:
        state = "complete"
        note = (
            f"{confirmed} confirmed report"
            + ("s" if confirmed != 1 else "")
            + " are being used."
        )

    elif unconfirmed:
        state = "waiting_for_your_confirmation"
        note = (
            f"{unconfirmed} report"
            + ("s are" if unconfirmed != 1 else " is")
            + " waiting for you to check the values. Nothing from "
            + ("them" if unconfirmed != 1 else "it")
            + " is used until you confirm."
        )

    elif not extraction_available:
        state = "not_configured"
        note = (
            "Automatic reading of reports is not set up on this server. You can "
            "still enter your values by hand."
        )

    else:
        state = "no_reports"
        note = "No report has been added yet."

    return {
        "id": REPORT_EXTRACTION["id"],
        "stage": REPORT_EXTRACTION["stage"],
        "name": REPORT_EXTRACTION["name"],
        "state": state,
        "note": note,
        "confirmedReportCount": confirmed,
        "unconfirmedReportCount": unconfirmed,
    }


def _suggested_actions(context: dict) -> list:
    """What would give the agents more to work from, most useful first."""

    actions = []

    if not context["movement"]["available"]:
        actions.append(ACTION_RECORD_ASSESSMENT)

    if not context["profile"]["available"]:
        actions.append(ACTION_COMPLETE_PROFILE)

    reports = context["reports"]

    if not reports["available"]:
        actions.append(
            ACTION_CONFIRM_REPORT
            if reports.get("unconfirmedReportCount")
            else ACTION_ADD_REPORT
        )

    return actions


def guidance_plan(context: dict, *, model_available: bool,
                  model_reason=None, extraction_available: bool = False) -> dict:
    """Whether guidance can be produced, and what to say if it cannot."""

    blockers = []
    notes = []

    if not model_available:
        blockers.append(
            model_reason
            or "AI guidance is not set up on this server."
        )

    if not context["availability"]["hasAnything"]:
        blockers.append(
            "There is nothing to work from yet. Record a movement assessment, "
            "answer the setup questions, or confirm a report, and guidance can "
            "be written from it."
        )

    reports = context["reports"]

    if reports.get("unconfirmedReportCount"):
        notes.append(
            f"{reports['unconfirmedReportCount']} report"
            + ("s have" if reports["unconfirmedReportCount"] != 1 else " has")
            + " not been confirmed, so no values from "
            + ("them" if reports["unconfirmedReportCount"] != 1 else "it")
            + " are used."
        )

    movement = context["movement"]

    if movement["tests"] and not movement["available"]:
        notes.append(
            "Your movement session did not produce a usable measurement, so "
            "there is nothing from it to work from."
        )

    elif movement["available"]:
        unusable = [
            test["name"]
            for test in movement["tests"]
            if test["status"] in ("invalid", "skipped", "not_started")
        ]

        if unusable:
            notes.append(
                "These tests produced no measurement and are treated as absent "
                "rather than as a result: " + ", ".join(unusable) + "."
            )

    if not blockers and context["availability"]["isThin"]:
        notes.append(
            "Only one kind of information is available, so this will be general. "
            "It gets more specific as you add more."
        )

    can_run = not blockers

    return {
        "canRun": can_run,
        "blockers": blockers,
        "notes": notes,
        "suggestedActions": _suggested_actions(context),
        "stages": [
            report_stage_state(reports, extraction_available=extraction_available),
            {
                "id": WELLNESS_GUIDANCE["id"],
                "stage": WELLNESS_GUIDANCE["stage"],
                "name": WELLNESS_GUIDANCE["name"],
                "state": "ready" if can_run else "blocked",
                "note": None if can_run else blockers[0],
            },
            {
                "id": CARE_NAVIGATION["id"],
                "stage": CARE_NAVIGATION["stage"],
                "name": CARE_NAVIGATION["name"],
                # Runs on what the wellness agent produced, so on its own it is
                # never "ready" — it is waiting for the step before it.
                "state": "runs_after_wellness_guidance" if can_run else "blocked",
                "note": None if can_run else blockers[0],
            },
        ],
    }
