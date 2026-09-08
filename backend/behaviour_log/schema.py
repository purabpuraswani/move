"""Validating one recorded Behaviour Action.

A behaviour action is the user saying "I did the habit goal my plan asked
me to". It is the smallest record that closes the behaviour evidence loop:
until this existed, the Behaviour Agent could set a habit goal and then had
nothing whatsoever to review it against, so habit adherence was
structurally UNKNOWN forever.

Mirrors food_log/schema.py and exercise_assessment/schema.py: one
ValueError subclass, a `_fail` helper, a closed set of accepted fields, and
a refusal rather than a silently corrected best guess.

What this module deliberately does NOT accept, and why
------------------------------------------------------
No adherence rate, no streak, no score, no "percent complete". Those are
computed from records, and a client that could post one could post a number
nothing happened to produce. The client sends what the user did; the rate,
if there is enough evidence for one, is worked out later from the records
themselves (behaviour_agent/adaptation.py).

No user id and no timestamp either — both are set by the server
(behaviour_log/store.py), for the same reason every other store in this
project sets them.

`difficulty` is the user's own word for how it felt, from a fixed set of
three. It is deliberately not a 1-10 scale: a number invites averaging, and
an average of "how did that feel" is not a measurement of anything.
"""

# What actually happened to the action. `skipped` is a real, useful answer
# and is stored as itself -- it is never inferred from an absence of
# records, because someone who did not open the app and someone who chose
# to skip are different people.
STATUS_VALUES = ("completed", "skipped")

# The user's own word for how it felt. Optional: an action recorded with no
# difficulty is a perfectly good record, and the field stays None rather
# than defaulting to "manageable".
DIFFICULTY_VALUES = ("easy", "manageable", "difficult")

MAX_NOTES_LENGTH = 500
MAX_TOPIC_ID_LENGTH = 100

ACCEPTED_FIELDS = ("topic_id", "status", "difficulty", "notes")


class BehaviourActionValidationError(ValueError):
    """Raised when a submitted behaviour action cannot be accepted."""


def _fail(message: str):
    raise BehaviourActionValidationError(message)


def build_behaviour_action(topic_id, status="completed", difficulty=None, notes=None) -> dict:
    """Build and validate one behaviour action document.

    Returns the cleaned action — the exact shape
    `store.save_behaviour_action` expects. Raises for anything it cannot
    accept; it never fills in a missing topic or invents a status.
    """

    action = {
        "topic_id": topic_id,
        "status": status,
        "difficulty": difficulty,
        "notes": notes,
    }

    validate_behaviour_action(action)

    return {
        "topic_id": topic_id.strip(),
        "status": status,
        "difficulty": difficulty,
        "notes": notes.strip() if isinstance(notes, str) and notes.strip() else None,
    }


def validate_behaviour_action(action) -> None:
    if not isinstance(action, dict):
        _fail("a behaviour action must be an object")

    unexpected = set(action) - set(ACCEPTED_FIELDS)

    if unexpected:
        _fail(
            "a behaviour action has unexpected field(s): "
            + ", ".join(sorted(unexpected))
            + ". Adherence is computed from records, never submitted"
        )

    topic_id = action.get("topic_id")

    if not isinstance(topic_id, str) or not topic_id.strip():
        _fail("topic_id is required and must be a non-empty string")

    if len(topic_id.strip()) > MAX_TOPIC_ID_LENGTH:
        _fail(f"topic_id must be at most {MAX_TOPIC_ID_LENGTH} characters")

    if action.get("status") not in STATUS_VALUES:
        _fail(f"status must be one of {', '.join(STATUS_VALUES)}")

    difficulty = action.get("difficulty")

    if difficulty is not None and difficulty not in DIFFICULTY_VALUES:
        _fail(
            "difficulty must be null or one of "
            + ", ".join(DIFFICULTY_VALUES)
        )

    notes = action.get("notes")

    if notes is not None:
        if not isinstance(notes, str):
            _fail("notes must be null or a string")

        if len(notes.strip()) > MAX_NOTES_LENGTH:
            _fail(f"notes must be at most {MAX_NOTES_LENGTH} characters")
