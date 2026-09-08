"""How the Nutrition Agent changes an existing plan when real evidence
arrives.

The Nutrition Agent could already decide what to work on: it reads the four
self-reported signals, checks each against this project's own thresholds,
and only targets the ones that actually crossed one. What it could not do
was look at what happened afterwards. A user could log food for three weeks
and the plan would be rebuilt from the same questionnaire answers, because
nothing carried the logs back to the agent that wrote the plan.

This module is that step, and its whole design is about one distinction:

    KNOWN        Real recorded evidence exists and was used.
    NOT_LOGGED   The user recorded nothing. This is a fact about logging,
                 and it is NEVER read as "they did not follow the plan".
    UNKNOWN      There is some evidence but not enough to conclude
                 anything, so nothing is concluded.

Those three are kept apart everywhere, for the same reason NOT_ASSESSED is
kept apart from LOW in the Need Profile: "we did not see it" and "we saw it
and it was poor" are different findings, and a system that collapses them
will eventually tell someone they are failing at something they were never
measured on.

The adherence numbers themselves are not computed here. They come from the
Nutrition MCP server's `calculate_food_adherence` tool, whose own
implementation (nutrition_agent/adherence.py) already refuses to report a
completion rate of 0.0 when the real answer is "no data". This module reads
that tool's four-state status and decides what to do about it.
"""

# What `compute_food_log_adherence` reports, mapped to what is actually
# known. The tool's own status vocabulary is the source of truth; this is a
# reading of it, not a second one.
ADHERENCE_KNOWN = "KNOWN"
ADHERENCE_NOT_LOGGED = "NOT_LOGGED"
ADHERENCE_UNKNOWN = "UNKNOWN"

DECISION_ADD = "ADD"
DECISION_MAINTAIN = "MAINTAIN"
DECISION_MODIFY = "MODIFY"
DECISION_REMOVE = "REMOVE"

# What the user is asked for when there is nothing to go on. Phrased as a
# request, never as a criticism -- the app cannot tell the difference
# between someone who ate badly and someone who simply did not open the log.
EVIDENCE_NEEDED_LOGGING = (
    "Log what you eat for a few days so this can be reviewed against what "
    "you are actually doing."
)

EVIDENCE_NEEDED_MORE_DAYS = (
    "Keep logging for a few more days -- there is not yet enough to compare."
)


def evidence_status_of(adherence) -> str:
    """The three-way reading of one adherence result.

    `adherence` is the tool's result dict (status ADHERED / NOT_ADHERED /
    NOT_LOGGED / INSUFFICIENT_DATA), or None when no adherence could be
    computed at all. Anything unrecognised reads as UNKNOWN: an unfamiliar
    status is a reason to know less, never a reason to assume more.
    """

    if not isinstance(adherence, dict):
        return ADHERENCE_UNKNOWN

    status = adherence.get("status")

    if status in ("ADHERED", "NOT_ADHERED"):
        return ADHERENCE_KNOWN

    if status == "NOT_LOGGED":
        return ADHERENCE_NOT_LOGGED

    return ADHERENCE_UNKNOWN


def _evidence_used(adherence) -> list:
    """What the decision was actually made from, in the tool's own terms.

    Returns an empty list when there was nothing -- an empty list is a
    truthful "nothing was used", where a placeholder sentence would not be.
    """

    if not isinstance(adherence, dict):
        return []

    used = []
    logged_days = adherence.get("logged_days")
    observation_days = adherence.get("observation_days")

    if isinstance(logged_days, int) and isinstance(observation_days, int):
        used.append(
            f"You logged food on {logged_days} of {observation_days} days in "
            "the period reviewed."
        )

    rate = adherence.get("completion_rate")

    if isinstance(rate, (int, float)):
        used.append(f"That is {round(rate * 100)}% of the days.")

    for note in adherence.get("notes") or []:
        if isinstance(note, str) and note:
            used.append(note)

    return used


def decide_for_goal(
    *,
    topic_id: str,
    target_signal,
    adherence,
    still_triggered: bool,
) -> dict:
    """One nutrition goal's decision for this cycle.

    Returns `{"topic_id", "decision_type", "reason", "adherence_status",
    "evidence_used", "evidence_needed", "target_signal"}`.
    """

    status = evidence_status_of(adherence)
    evidence_used = _evidence_used(adherence)

    def decision(decision_type, reason, evidence_needed=None):
        return {
            "topic_id": topic_id,
            "decision_type": decision_type,
            "reason": reason,
            "adherence_status": status,
            "evidence_used": evidence_used,
            "evidence_needed": [evidence_needed] if evidence_needed else [],
            "target_signal": target_signal,
        }

    # Checked before the evidence rules: how well someone followed a goal
    # they no longer need does not decide whether it stays.
    if not still_triggered:
        return decision(
            DECISION_REMOVE,
            "Your answers no longer flag this as something to work on, so it "
            "has been taken out.",
        )

    if status == ADHERENCE_NOT_LOGGED:
        return decision(
            DECISION_MAINTAIN,
            "Nothing has been logged for this yet, so it stays as it is. "
            "That is a gap in what has been recorded, not a judgement about "
            "how you have been eating.",
            EVIDENCE_NEEDED_LOGGING,
        )

    if status == ADHERENCE_UNKNOWN:
        return decision(
            DECISION_MAINTAIN,
            "There is not yet enough logged to review this, so it stays as "
            "it is.",
            EVIDENCE_NEEDED_MORE_DAYS,
        )

    if adherence.get("status") == "ADHERED":
        return decision(
            DECISION_MAINTAIN,
            "You have been logging consistently against this, so it stays as "
            "your current focus.",
        )

    return decision(
        DECISION_MODIFY,
        "This has been hard to keep up with, so it is swapped for a "
        "different approach to the same thing.",
        EVIDENCE_NEEDED_LOGGING,
    )


def summarise(decisions: list) -> str:
    """One plain sentence naming what actually changed, or None when
    nothing did — so a plan version is never created for a review that
    decided to leave everything alone."""

    changed = [
        entry for entry in decisions if entry["decision_type"] != DECISION_MAINTAIN
    ]

    if not changed:
        return None

    counts = {}

    for entry in changed:
        counts[entry["decision_type"]] = counts.get(entry["decision_type"], 0) + 1

    wording = {
        DECISION_MODIFY: "changed",
        DECISION_REMOVE: "removed",
        DECISION_ADD: "added",
    }

    parts = [
        f"{count} {'focus' if count == 1 else 'areas of focus'} {wording[kind]}"
        for kind, count in sorted(counts.items())
        if kind in wording
    ]

    return "Based on what you logged: " + ", ".join(parts) + "."
