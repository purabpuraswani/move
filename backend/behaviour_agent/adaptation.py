"""How the Behaviour Agent changes an existing plan when real evidence
arrives.

What evidence exists, in order of how specific it is
----------------------------------------------------
1. RECORDED ACTIONS (behaviour_log). The user saying they did — or
   skipped — this exact habit goal, optionally with how it felt. This is
   evidence about the goal itself, so it decides first.
2. A RE-ANSWERED QUESTIONNAIRE. The signal the goal was chosen for, moving
   the wrong way while the goal was in place, is real evidence that this
   approach is not working for them.
3. RECORDED EXERCISE SESSIONS, and only for the two signals that genuinely
   are about activity (`exercise_days`, `weekly_exercise_minutes`). A
   sitting or screen goal is never judged on squats: those are different
   things, and telling someone they are failing at "take a break from
   sitting" because they missed a workout would be inventing a finding.

More specific evidence always wins, which is why the checks are in that
order.

The decisions this module produces:

  ADD       a newly triggered signal has no goal yet
  MAINTAIN  still triggered, and nothing recorded contradicts it
  MODIFY    recorded actions show it is being skipped or is consistently
            hard, or the signal it targets got worse while it was in place
  REMOVE    the signal no longer crosses the threshold

And the rule that governs all of them: no record is never read as failure.
Someone who does the habit daily and never opens the app is indistinguish-
able, to this system, from someone who did nothing — so the honest output
is NOT_LOGGED and a request to record, never a judgement.
"""

from behaviour_agent.adherence import (
    ADHERED,
    DIFFICULTY_THRESHOLD,
    INSUFFICIENT_DATA,
    NOT_ADHERED,
    compute_behaviour_adherence,
)

ADHERENCE_KNOWN = "KNOWN"
ADHERENCE_NOT_LOGGED = "NOT_LOGGED"
ADHERENCE_UNKNOWN = "UNKNOWN"

DECISION_ADD = "ADD"
DECISION_MAINTAIN = "MAINTAIN"
DECISION_MODIFY = "MODIFY"
DECISION_REMOVE = "REMOVE"

# The two questionnaire signals that recorded exercise sessions are real
# evidence about. The sitting and screen signals are deliberately absent:
# nothing in this application observes them.
ACTIVITY_SIGNALS = ("exercise_days", "weekly_exercise_minutes")

# How many recorded sessions count as evidence that the activity side of
# the plan is being acted on. Two, for the same reason the Physio Agent
# requires two: one session is not a pattern.
MIN_SESSIONS_FOR_EVIDENCE = 2

# For each signal, whether a HIGHER value is worse. Sitting and screen
# hours going up is worse; exercise days going down is worse. Used only to
# decide whether a re-answer moved the wrong way.
_HIGHER_IS_WORSE = {
    "daily_sitting_hours": True,
    "daily_screen_hours": True,
    "exercise_days": False,
    "weekly_exercise_minutes": False,
}

# The signals in the user's own terms, so an evidence line says what it is
# about rather than being a bare number.
_SIGNAL_WORDING = {
    "daily_sitting_hours": "hours a day sitting",
    "daily_screen_hours": "hours a day on screens",
    "exercise_days": "days a week you exercise",
    "weekly_exercise_minutes": "minutes of exercise a week",
}

EVIDENCE_NEEDED_RECORD_IT = (
    "Mark this as done (or skipped) when the moment comes, so there is "
    "something real to review it against."
)

EVIDENCE_NEEDED_SESSIONS = (
    "Record a couple of exercise sessions so there is something to review "
    "this against."
)


def completed_session_count(exercise_results) -> int:
    """How many exercise sessions the user actually completed.

    Only `completed` counts. An `incomplete` session says the movement was
    not finished, and an `invalid` one says the camera could not see it —
    neither is evidence of the activity habit being kept, and neither is
    evidence against it either.
    """

    if not exercise_results:
        return 0

    return sum(
        1
        for result in exercise_results
        if isinstance(result, dict) and result.get("status") == "completed"
    )


def _got_worse(signal, previous_value, current_value) -> bool:
    """Did a re-answered signal move the wrong way?

    Returns False whenever either value is missing or the direction for
    this signal is not known — an unknown direction is a reason to do
    nothing, never a reason to guess.
    """

    if signal not in _HIGHER_IS_WORSE:
        return False

    if not isinstance(previous_value, (int, float)) or isinstance(
        previous_value, bool
    ):
        return False

    if not isinstance(current_value, (int, float)) or isinstance(current_value, bool):
        return False

    if _HIGHER_IS_WORSE[signal]:
        return current_value > previous_value

    return current_value < previous_value


def decide_for_goal(
    *,
    topic_id: str,
    target_signal,
    previous_value,
    current_value,
    still_triggered: bool,
    completed_sessions: int = 0,
    actions=None,
) -> dict:
    """One habit goal's decision for this cycle.

    Returns `{"topic_id", "decision_type", "reason", "adherence_status",
    "evidence_used", "evidence_needed", "target_signal", "signal_value"}`.
    """

    is_activity = target_signal in ACTIVITY_SIGNALS
    evidence_used = []

    # The most specific evidence there is: what the user recorded about
    # this exact goal.
    adherence = compute_behaviour_adherence(actions, topic_id=topic_id)
    has_action_evidence = adherence["status"] in (ADHERED, NOT_ADHERED)

    if adherence["recorded_actions"]:
        evidence_used.append(
            f"You have recorded {adherence['completed_actions']} completed of "
            f"{adherence['recorded_actions']} action(s) for this."
        )

    if adherence["difficult_actions"]:
        evidence_used.append(
            f"You marked {adherence['difficult_actions']} of them difficult."
        )

    if is_activity and completed_sessions:
        evidence_used.append(
            f"You have completed {completed_sessions} recorded exercise "
            f"{'session' if completed_sessions == 1 else 'sessions'}."
        )

    if isinstance(current_value, (int, float)) and not isinstance(
        current_value, bool
    ):
        described = _SIGNAL_WORDING.get(target_signal, "this")
        evidence_used.append(f"You last told us {current_value} {described}.")

    if has_action_evidence:
        status = ADHERENCE_KNOWN
    elif adherence["status"] == INSUFFICIENT_DATA:
        status = ADHERENCE_UNKNOWN
    elif is_activity:
        # No recorded actions for this goal, but recorded exercise sessions
        # are real evidence for an activity signal specifically.
        if completed_sessions >= MIN_SESSIONS_FOR_EVIDENCE:
            status = ADHERENCE_KNOWN
        elif completed_sessions == 0:
            status = ADHERENCE_NOT_LOGGED
        else:
            status = ADHERENCE_UNKNOWN
    else:
        status = ADHERENCE_NOT_LOGGED

    def decision(decision_type, reason, evidence_needed=None):
        return {
            "topic_id": topic_id,
            "decision_type": decision_type,
            "reason": reason,
            "adherence_status": status,
            "evidence_used": evidence_used,
            "evidence_needed": [evidence_needed] if evidence_needed else [],
            "target_signal": target_signal,
            # Recorded so the next cycle has something to compare a
            # re-answer against. Without it, MODIFY is unreachable.
            "signal_value": current_value,
        }

    if not still_triggered:
        return decision(
            DECISION_REMOVE,
            "Your latest answers no longer flag this, so it has been taken "
            "out of your plan.",
        )

    # 1. Recorded actions for this goal, when there are enough of them.
    if has_action_evidence:
        if adherence["status"] == NOT_ADHERED:
            return decision(
                DECISION_MODIFY,
                "You have been recording this as skipped more often than "
                "done, so it is swapped for a different approach.",
            )

        if (adherence["difficulty_rate"] or 0) >= DIFFICULTY_THRESHOLD:
            return decision(
                DECISION_MODIFY,
                "You have been doing this, but marking it difficult most "
                "times, so it is swapped for something more manageable.",
            )

        return decision(
            DECISION_MAINTAIN,
            "You have been recording this as done, so it stays as your "
            "current habit to work on.",
        )

    # 2. The signal it targets, moving the wrong way while it was in place.
    if _got_worse(target_signal, previous_value, current_value):
        return decision(
            DECISION_MODIFY,
            "You have answered this again and it has moved the wrong way "
            "while this goal was in place, so it is swapped for a different "
            "approach.",
        )

    if status == ADHERENCE_KNOWN:
        return decision(
            DECISION_MAINTAIN,
            "You have been recording sessions, so this stays as your current "
            "habit to work on.",
        )

    if status == ADHERENCE_NOT_LOGGED:
        return decision(
            DECISION_MAINTAIN,
            "Nothing has been recorded against this yet, so it stays as it "
            "is. That is a gap in what is recorded, not a judgement about "
            "what you have been doing.",
            EVIDENCE_NEEDED_SESSIONS,
        )

    return decision(
        DECISION_MAINTAIN,
        "This stays as your current habit to work on.",
        EVIDENCE_NEEDED_RECORD_IT,
    )


def summarise(decisions: list) -> str:
    """One plain sentence naming what changed, or None when nothing did."""

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
        f"{count} {'habit' if count == 1 else 'habits'} {wording[kind]}"
        for kind, count in sorted(counts.items())
        if kind in wording
    ]

    return "Based on what you recorded: " + ", ".join(parts) + "."
