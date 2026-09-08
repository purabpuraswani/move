"""Computing habit adherence from recorded Behaviour Actions.

The one place a habit-adherence figure is worked out, so the Behaviour
Agent and the Progress Agent can never disagree about what the records say.
Mirrors nutrition_agent/adherence.py: the same four-state vocabulary, the
same refusal to let an absence of records become a rate of 0.0, and the
same rule that the denominator has to be something real.

What the denominator is, and why it is not "days"
-------------------------------------------------
A habit goal has no fixed schedule in this project — nothing says "once
daily", and inventing one would invent the denominator with it. So the
denominator is what the user actually reported on: each recorded action is
one occasion they told us about, and the rate is how many of those they
completed.

That makes the figure honest but narrow, and the narrowness is stated
rather than hidden: it answers "of the times you told us about, how often
did you do it", not "how often did you do it". `notes` on the result says
so, and the Progress Agent passes that wording straight through.

Someone who does the habit every day and never records it reads as
NOT_LOGGED, which is correct: this system does not know.
"""

# Same four values nutrition_agent/adherence.py reports, so a caller can
# read either without a second vocabulary.
ADHERED = "ADHERED"
NOT_ADHERED = "NOT_ADHERED"
NOT_LOGGED = "NOT_LOGGED"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# How many recorded actions before a rate is reported at all. Three, so a
# single bad day cannot read as a pattern -- one more than the physio
# threshold because a habit is reported on more often than an exercise is
# performed.
MIN_ACTIONS_FOR_A_RATE = 3

# At or above this share completed, the habit is being kept. A project
# decision, not a clinical one, and the same 0.8 nutrition_agent/
# adherence.py uses so the two specialists hold users to one standard.
ADHERENCE_THRESHOLD = 0.8

# At or above this share reported "difficult", the goal is producing
# friction worth acting on even when it is being completed.
DIFFICULTY_THRESHOLD = 0.5

DENOMINATOR_NOTE = (
    "This counts the occasions you told us about, not every day -- a habit "
    "goal here has no fixed schedule to measure against."
)


class BehaviourAdherenceError(ValueError):
    """Raised when adherence cannot be computed from what was given."""


def _result(
    *,
    status,
    completed,
    recorded,
    completion_rate,
    difficult,
    difficulty_rate,
    notes,
):
    return {
        "status": status,
        "completed_actions": completed,
        "recorded_actions": recorded,
        # A real computed number or None. Never 0.0 standing in for "no
        # data" -- that is the single most tempting lie in this whole
        # module and the reason it exists as its own function.
        "completion_rate": completion_rate,
        "difficult_actions": difficult,
        "difficulty_rate": difficulty_rate,
        "notes": list(notes),
    }


def compute_behaviour_adherence(actions, *, topic_id: str = None) -> dict:
    """Adherence from a list of recorded behaviour actions.

    `actions` is a list of stored behaviour_log documents (or None).
    `topic_id`, when given, narrows to one habit goal; otherwise every
    action given is counted.

    Never raises for an empty list — no records is a normal, meaningful
    answer and is returned as NOT_LOGGED.
    """

    if actions is not None and not isinstance(actions, (list, tuple)):
        raise BehaviourAdherenceError("actions must be a list")

    relevant = [
        action
        for action in (actions or [])
        if isinstance(action, dict)
        and (topic_id is None or action.get("topic_id") == topic_id)
    ]

    if not relevant:
        return _result(
            status=NOT_LOGGED,
            completed=0,
            recorded=0,
            completion_rate=None,
            difficult=0,
            difficulty_rate=None,
            notes=[
                "no actions have been recorded for this goal; this is an "
                "absence of recording, not evidence that the user did not do it"
            ],
        )

    recorded = len(relevant)
    completed = sum(1 for action in relevant if action.get("status") == "completed")
    difficult = sum(1 for action in relevant if action.get("difficulty") == "difficult")

    if recorded < MIN_ACTIONS_FOR_A_RATE:
        return _result(
            status=INSUFFICIENT_DATA,
            completed=completed,
            recorded=recorded,
            completion_rate=None,
            difficult=difficult,
            difficulty_rate=None,
            notes=[
                f"only {recorded} action(s) recorded; at least "
                f"{MIN_ACTIONS_FOR_A_RATE} are needed before a rate means "
                "anything",
                DENOMINATOR_NOTE,
            ],
        )

    completion_rate = round(completed / recorded, 2)
    difficulty_rate = round(difficult / recorded, 2)

    return _result(
        status=ADHERED if completion_rate >= ADHERENCE_THRESHOLD else NOT_ADHERED,
        completed=completed,
        recorded=recorded,
        completion_rate=completion_rate,
        difficult=difficult,
        difficulty_rate=difficulty_rate,
        notes=[
            f"{completed} of {recorded} recorded actions were completed.",
            DENOMINATOR_NOTE,
        ],
    )


def summarise_for_progress(actions) -> dict:
    """The behaviour evidence the Progress Agent reports, across all goals.

    Returns the same result shape plus a plain-language `summary`, so the
    Progress Agent can state what the records show without computing
    anything itself. With too little recorded it says exactly that rather
    than producing a rate.
    """

    result = compute_behaviour_adherence(actions)

    if result["status"] == NOT_LOGGED:
        summary = "No behaviour actions have been recorded yet."
    elif result["status"] == INSUFFICIENT_DATA:
        summary = (
            f"{result['recorded_actions']} action(s) recorded so far -- not "
            "enough recorded data to say how it is going."
        )
    else:
        summary = (
            f"{result['completed_actions']} completed of "
            f"{result['recorded_actions']} recorded actions."
        )

    return {**result, "summary": summary}
