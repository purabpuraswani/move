"""How the Physio Agent changes an existing plan when real evidence arrives.

Before this module, the Physio Agent could only ever build a plan. A
progress-triggered adaptation re-ran it with the same User State, so it
produced another first-draft plan and the six decision types
(ADD/REMOVE/REPLACE/MAINTAIN/PROGRESS/REGRESS) existed in the schema
without anything able to produce five of them. That is the gap this module
closes: given the plan the user already has and the results they actually
recorded against it, decide what happens to each exercise.

Everything here is deterministic and evidence-bound:

  * The evidence is `exercise_assessment/schema.py`'s recorded results —
    `status` of "completed" / "incomplete" / "invalid", produced from the
    browser's own derived measurements. No LLM, no inference from absence.

  * "invalid" is never read as difficulty. A result the camera could not
    measure says nothing about how the user performed, so it can never
    justify a REGRESS. It is treated as no evidence, which is what it is.

  * A single result is never enough to change anything. One good day is not
    a trend, and one bad day is not a reason to take an exercise away.

  * When there is no evidence, the decision is MAINTAIN with a reason that
    says so. MAINTAIN is a real decision here, not a default that hides an
    inability to decide.

None of these thresholds is a clinical rule. They are this project's own
stated policy about how much evidence is enough to change a wellness
programme, and they are named constants so a reviewer can see and argue
with each one.
"""

# How many recorded results for one exercise are needed before its
# prescription changes at all. Two, so that a change always reflects a
# repeated observation rather than a single session.
MIN_RESULTS_TO_DECIDE = 2

# How many of the most recent results are considered. Older sessions still
# exist in the history; they are simply not what "how is it going now"
# means.
RECENT_RESULTS_WINDOW = 2

DECISION_MAINTAIN = "MAINTAIN"
DECISION_PROGRESS = "PROGRESS"
DECISION_REGRESS = "REGRESS"
DECISION_REPLACE = "REPLACE"
DECISION_REMOVE = "REMOVE"
DECISION_ADD = "ADD"


def results_for_exercise(exercise_results, exercise_id: str) -> list:
    """This user's recorded results for one exercise, oldest first.

    `exercise_results` is the list `exercise_assessment.store.
    list_exercise_results()` returns (or None). Entries without a matching
    `exerciseId` are ignored rather than guessed at.
    """

    if not exercise_results:
        return []

    return [
        result
        for result in exercise_results
        if isinstance(result, dict) and result.get("exerciseId") == exercise_id
    ]


def _recent(results: list) -> list:
    return results[-RECENT_RESULTS_WINDOW:]


def _statuses(results: list) -> list:
    return [result.get("status") for result in results]


def decide_for_exercise(
    *,
    exercise_id: str,
    target_need,
    has_progression: bool,
    has_regression: bool,
    exercise_results,
    still_targeted: bool,
    programme_direction=None,
) -> dict:
    """One exercise's decision for this cycle.

    Returns `{"exercise_id", "decision_type", "reason", "evidence"}`, where
    `evidence` records exactly what the decision was made from — how many
    results were considered and what their statuses were — so the decision
    can be audited without re-running it.

    `programme_direction` is the Progress Agent's own recommendation for
    this cycle ("PROGRESS" or "REGRESS"), derived from the reassessment
    comparison and adherence rather than from any single exercise. It is
    used ONLY where this exercise's own results are not enough to decide:
    evidence about the specific exercise is more specific than evidence
    about the programme, so it always wins where it exists.
    """

    results = results_for_exercise(exercise_results, exercise_id)
    recent = _recent(results)
    statuses = _statuses(recent)

    evidence = {
        "results_recorded": len(results),
        "results_considered": len(recent),
        "recent_statuses": statuses,
    }

    def decision(decision_type, reason):
        return {
            "exercise_id": exercise_id,
            "decision_type": decision_type,
            "reason": reason,
            "evidence": evidence,
            "target_need": target_need,
        }

    # A capability that is no longer being worked on. Checked before the
    # evidence rules: how well the user did at something they no longer
    # need to do does not decide whether it stays.
    if not still_targeted:
        return decision(
            DECISION_REMOVE,
            "This is no longer one of the capabilities your programme is "
            "working on, so it has been taken out.",
        )

    if len(results) < MIN_RESULTS_TO_DECIDE:
        programme = _programme_decision(
            programme_direction, has_progression, has_regression, decision
        )

        if programme is not None:
            return programme

        if not results:
            return decision(
                DECISION_MAINTAIN,
                "You have not recorded this exercise yet, so it stays as it is.",
            )

        return decision(
            DECISION_MAINTAIN,
            "One recorded session is not enough to change anything, so this "
            "stays as it is for now.",
        )

    completed = statuses.count("completed")
    incomplete = statuses.count("incomplete")
    invalid = statuses.count("invalid")

    # Sessions the camera could not measure are not evidence of difficulty.
    if invalid == len(statuses):
        programme = _programme_decision(
            programme_direction, has_progression, has_regression, decision
        )

        if programme is not None:
            return programme

        return decision(
            DECISION_MAINTAIN,
            "Your recent attempts at this could not be measured clearly, so "
            "nothing has been changed based on them.",
        )

    if completed == len(statuses) and completed >= MIN_RESULTS_TO_DECIDE:
        if has_progression:
            return decision(
                DECISION_PROGRESS,
                "You completed this in each of your recent sessions, so it "
                "moves up a step.",
            )

        return decision(
            DECISION_MAINTAIN,
            "You completed this in each of your recent sessions. There is no "
            "harder version of it in the library, so it stays as it is.",
        )

    if incomplete >= MIN_RESULTS_TO_DECIDE and completed == 0:
        if has_regression:
            return decision(
                DECISION_REGRESS,
                "You have not been able to finish this recently, so it moves "
                "down to an easier version.",
            )

        return decision(
            DECISION_REPLACE,
            "You have not been able to finish this recently, and it has no "
            "easier version, so it is swapped for a different exercise that "
            "works the same capability.",
        )

    return decision(
        DECISION_MAINTAIN,
        "Your recent sessions are mixed, which is normal. This stays as it "
        "is while more evidence builds up.",
    )


def _programme_decision(
    programme_direction, has_progression, has_regression, decision
):
    """A decision taken from the Progress Agent's programme-level finding,
    or None when there is no such finding to act on.

    Kept to the two directions the Progress Agent actually produces for the
    physical axis. A direction with no matching progression/regression in
    the library yields nothing rather than a change with no instruction
    behind it.
    """

    if programme_direction == "PROGRESS" and has_progression:
        return decision(
            DECISION_PROGRESS,
            "Your reassessment and how consistently you have been training "
            "both point the right way, so this moves up a step.",
        )

    if programme_direction == "REGRESS" and has_regression:
        return decision(
            DECISION_REGRESS,
            "Your recent review suggests easing off, so this moves down to "
            "an easier version.",
        )

    return None


def summarise(decisions: list) -> str:
    """A single plain sentence naming what actually changed, for the plan
    version record's `adaptation_reason`.

    Returns None when nothing changed, so a plan version is never labelled
    with a change it did not make.
    """

    changed = [
        entry
        for entry in decisions
        if entry["decision_type"] != DECISION_MAINTAIN
    ]

    if not changed:
        return None

    counts = {}

    for entry in changed:
        counts[entry["decision_type"]] = counts.get(entry["decision_type"], 0) + 1

    wording = {
        DECISION_PROGRESS: "moved up",
        DECISION_REGRESS: "made easier",
        DECISION_REPLACE: "swapped",
        DECISION_REMOVE: "removed",
        DECISION_ADD: "added",
    }

    parts = [
        f"{count} {'exercise' if count == 1 else 'exercises'} {wording[kind]}"
        for kind, count in sorted(counts.items())
        if kind in wording
    ]

    return "Based on what you recorded: " + ", ".join(parts) + "."
