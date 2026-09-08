"""Storage and retrieval for recorded Behaviour Actions.

Mirrors backend/food_log/store.py field-for-field in spirit: ownership
enforced in the query (every read filters on user_id), records accumulate
(one document per action, never overwritten in place), and `recorded_at` is
set on the server rather than trusted from the client.

The store never re-validates content — behaviour_log/schema.py did that —
and never interprets a record. It also never invents one: an absence of
documents is returned as an absence, and it is
behaviour_agent/adaptation.py, not this module, that says what an absence
means. Its rule is explicit: no recorded action is NOT evidence that the
user failed to do it.
"""

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING

from database import behaviour_log_collection

DEFAULT_HISTORY_LIMIT = 100
MAX_HISTORY_LIMIT = 500


def ensure_indexes():
    """Create the indexes the read paths rely on. Safe to run repeatedly."""

    behaviour_log_collection.create_index(
        [("user_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_recorded_at",
    )
    behaviour_log_collection.create_index(
        [("user_id", ASCENDING), ("topic_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_topic_recorded_at",
    )


def save_behaviour_action(user_id: str, document: dict, *, plan_id: str = None) -> dict:
    """Store one validated behaviour action for the authenticated user.

    `document` must already be validated — this function attaches ownership
    and the server-set `recorded_at` only, the same division of
    responsibility food_log/store.py's save_food_log_entry uses. `plan_id`
    links the record back to the habit plan it was done against, so
    adherence can later be computed per-plan; an action recorded with no
    known plan is still stored, with plan_id=None, never fabricated.
    """

    stored = {
        **document,
        "user_id": user_id,
        "plan_id": plan_id,
        "recorded_at": datetime.now(timezone.utc),
    }

    inserted_id = behaviour_log_collection.insert_one(stored).inserted_id

    return {**stored, "_id": inserted_id}


def list_behaviour_actions(
    user_id: str,
    *,
    topic_id: str = None,
    plan_id: str = None,
    date_from=None,
    date_to=None,
    limit: int = DEFAULT_HISTORY_LIMIT,
    skip: int = 0,
) -> list:
    """The user's behaviour actions, newest first.

    Every filter is additive over the user_id ownership filter, which is
    always present and is never taken from the client.
    """

    query = {"user_id": user_id}

    if topic_id is not None:
        query["topic_id"] = topic_id

    if plan_id is not None:
        query["plan_id"] = plan_id

    recorded_at = {}

    if date_from is not None:
        recorded_at["$gte"] = date_from

    if date_to is not None:
        recorded_at["$lte"] = date_to

    if recorded_at:
        query["recorded_at"] = recorded_at

    cursor = (
        behaviour_log_collection.find(query)
        .sort("recorded_at", DESCENDING)
        .skip(max(0, skip))
        .limit(max(1, min(limit, MAX_HISTORY_LIMIT)))
    )

    return list(cursor)


def count_behaviour_actions(user_id: str, *, topic_id: str = None) -> int:
    query = {"user_id": user_id}

    if topic_id is not None:
        query["topic_id"] = topic_id

    return behaviour_log_collection.count_documents(query)


def _isoformat(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()

    return value


def serialise_behaviour_action(document: dict) -> dict:
    """Same discipline as food_log.store.serialise_food_log_entry: a stored
    document is never returned to a client unchanged (that would also leak
    user_id)."""

    return {
        "id": str(document["_id"]),
        "topicId": document.get("topic_id"),
        "status": document.get("status"),
        "difficulty": document.get("difficulty"),
        "notes": document.get("notes"),
        "planId": document.get("plan_id"),
        "recordedAt": _isoformat(document.get("recorded_at")),
    }
