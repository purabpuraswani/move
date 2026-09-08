"""Storage and retrieval for submitted Food Log entries.

Mirrors backend/exercise_assessment/store.py field-for-field in spirit:
ownership enforced in the query (every read filters on user_id), entries
accumulate (one document per logged food, never overwritten in place), and
`recorded_at` is set on the server rather than trusted from the client.

The store never re-validates content — food_log/schema.py did that — and
never interprets an entry. It also never invents a log: an absence of
documents for a period is returned as an absence, and it is
nutrition_agent/adherence.py, not this module, that says what an absence
means (and its explicit rule is that no food log is NOT evidence the user
did not eat).
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from database import food_log_collection

DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 200


class FoodLogEntryNotFoundError(LookupError):
    """Raised when no food log entry matches both the id and the owner."""


def ensure_indexes():
    """Create the indexes the read paths rely on. Safe to run repeatedly."""

    food_log_collection.create_index(
        [("user_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_recorded_at",
    )
    food_log_collection.create_index(
        [("user_id", ASCENDING), ("meal", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_meal_recorded_at",
    )
    food_log_collection.create_index(
        [("user_id", ASCENDING), ("plan_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_plan_recorded_at",
    )


def _object_id(value, label: str = "food log entry id") -> ObjectId:
    try:
        return ObjectId(value)

    except (InvalidId, TypeError):
        raise FoodLogEntryNotFoundError(f"{label} is not a valid id") from None


def save_food_log_entry(user_id: str, document: dict, *, plan_id: str = None) -> dict:
    """Store one validated food log entry (food_log.schema's output) for the
    authenticated user.

    `document` must already be validated — this function attaches ownership
    and the server-set `recorded_at` only, the same division of
    responsibility exercise_assessment/store.py's save_exercise_result
    uses. `plan_id` is optional and links the entry back to the nutrition
    plan it was logged against (the User State's nutrition_plan record), so
    adherence can later be computed per-plan; an entry logged with no known
    plan is still stored, with plan_id=None — never fabricated.
    """

    now = datetime.now(timezone.utc)

    stored = {
        **document,
        "user_id": user_id,
        "plan_id": plan_id,
        "recorded_at": now,
    }

    inserted_id = food_log_collection.insert_one(stored).inserted_id

    return {**stored, "_id": inserted_id}


def list_food_log_entries(
    user_id: str,
    *,
    meal: str = None,
    plan_id: str = None,
    date_from=None,
    date_to=None,
    limit: int = DEFAULT_HISTORY_LIMIT,
    skip: int = 0,
) -> list:
    """The user's food log entries, newest first.

    `meal`, `plan_id`, `date_from` and `date_to` are additional, additive
    filters over `recorded_at` — never a replacement for the user_id
    ownership filter, which is always present.
    """

    query = {"user_id": user_id}

    if meal is not None:
        query["meal"] = meal

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
        food_log_collection.find(query)
        .sort("recorded_at", DESCENDING)
        .skip(max(0, skip))
        .limit(max(1, min(limit, MAX_HISTORY_LIMIT)))
    )

    return list(cursor)


def count_food_log_entries(user_id: str, *, plan_id: str = None) -> int:
    query = {"user_id": user_id}

    if plan_id is not None:
        query["plan_id"] = plan_id

    return food_log_collection.count_documents(query)


def get_food_log_entry(user_id: str, entry_id: str) -> dict:
    document = food_log_collection.find_one(
        {"_id": _object_id(entry_id), "user_id": user_id}
    )

    if document is None:
        raise FoodLogEntryNotFoundError("No food log entry found with that id")

    return document


def _isoformat(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    return str(value)


def serialise_food_log_entry(document: dict) -> dict:
    """Same discipline as exercise_assessment.store.serialise_exercise_result:
    a stored document is never returned to a client unchanged (that would
    also leak user_id)."""

    return {
        "id": str(document["_id"]),
        "meal": document.get("meal"),
        "foodId": document.get("food_id"),
        "foodName": document.get("food_name"),
        "quantity": document.get("quantity"),
        "notes": document.get("notes"),
        "waterIntakeMl": document.get("water_intake_ml"),
        "planId": document.get("plan_id"),
        "recordedAt": _isoformat(document.get("recorded_at")),
    }
