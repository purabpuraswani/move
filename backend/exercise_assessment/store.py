"""Storage and retrieval for submitted Exercise Results (Phase 5).

Mirrors backend/assessments/store.py's exact discipline: ownership enforced
in the query (every read filters on user_id), and results accumulate — one
document per submitted result, never overwritten in place, so a real
performance history exists for the Progress Agent to read.

Before Phase 5, exercise_assessment/schema.py's `record_exercise_result`
validated a submission and returned it, but nothing stored it anywhere
(its own docstring said so explicitly) — the closed loop the Phase 5 brief
asks for ("User Performs Plan -> Structured Performance Data -> Progress
Agent") cannot exist without a real store, so this module is that store,
built the moment it was actually needed rather than earlier "for later".
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from database import exercise_results_collection

DEFAULT_HISTORY_LIMIT = 50
MAX_HISTORY_LIMIT = 200


class ExerciseResultNotFoundError(LookupError):
    """Raised when no exercise result matches both the id and the owner."""


def ensure_indexes():
    """Create the indexes the read paths rely on. Safe to run repeatedly."""

    exercise_results_collection.create_index(
        [("user_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_recorded_at",
    )
    exercise_results_collection.create_index(
        [("user_id", ASCENDING), ("exercise_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="user_exercise_recorded_at",
    )


def _object_id(value, label: str = "exercise result id") -> ObjectId:
    try:
        return ObjectId(value)

    except (InvalidId, TypeError):
        raise ExerciseResultNotFoundError(f"{label} is not a valid id") from None


def save_exercise_result(
    user_id: str,
    document: dict,
    *,
    plan_id: str = None,
    item_id: str = None,
) -> dict:
    """Store one validated Exercise Result (exercise_assessment.schema's
    output) for the authenticated user.

    `document` must already be validated (validate_exercise_result /
    record_exercise_result) — this function does not re-validate content,
    only attaches ownership and server-set timestamps, the same division
    of responsibility assessments/store.py's save_assessment uses.
    `plan_id` is optional and links a result back to the plan that
    recommended it (from the User State's exercise_history record), so
    adherence can later be computed per-plan; a result with no known plan
    (a user doing an exercise on their own) is still stored, with
    plan_id=None — never fabricated.

    `item_id` is optional and links the result to the specific plan item
    that asked for it. For an exercise item that is the exercise library id
    (the same identifier the unified plan publishes as `item_id`), which is
    what makes "this exact plan item was performed" answerable later rather
    than only "this exercise was performed at some point".
    """

    now = datetime.now(timezone.utc)

    stored = {
        **document,
        "user_id": user_id,
        "plan_id": plan_id,
        "item_id": item_id,
        "recorded_at": now,
    }

    inserted_id = exercise_results_collection.insert_one(stored).inserted_id

    return {**stored, "_id": inserted_id}


def list_exercise_results(
    user_id: str,
    *,
    exercise_id: str = None,
    plan_id: str = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
    skip: int = 0,
) -> list:
    """The user's exercise results, newest first. Optionally narrowed to one
    exercise_id or one plan_id — both are additional, additive filters, not
    a replacement for the user_id ownership filter.
    """

    query = {"user_id": user_id}

    if exercise_id is not None:
        query["exerciseId"] = exercise_id

    if plan_id is not None:
        query["plan_id"] = plan_id

    cursor = (
        exercise_results_collection.find(query)
        .sort("recorded_at", DESCENDING)
        .skip(max(0, skip))
        .limit(max(1, min(limit, MAX_HISTORY_LIMIT)))
    )

    return list(cursor)


def count_exercise_results(user_id: str, *, plan_id: str = None) -> int:
    query = {"user_id": user_id}

    if plan_id is not None:
        query["plan_id"] = plan_id

    return exercise_results_collection.count_documents(query)


def delete_manual_exercise_result(user_id: str, result_id: str) -> bool:
    """Delete one manually confirmed result belonging to this user.

    Deliberately narrow: only a `manual_confirmation` row can be removed,
    and only by the user who owns it. A camera session is a measurement
    that happened, and this store stays append-only for those -- un-ticking
    a box is a correction to a self-report, not a licence to erase
    recorded evidence.

    Returns True when a row was deleted, False when nothing matched (an
    unknown id, another user's row, or a camera result).
    """

    result = exercise_results_collection.delete_one(
        {
            "_id": _object_id(result_id),
            "user_id": user_id,
            "source": "manual_confirmation",
        }
    )

    return result.deleted_count == 1


def get_exercise_result(user_id: str, result_id: str) -> dict:
    document = exercise_results_collection.find_one(
        {"_id": _object_id(result_id), "user_id": user_id}
    )

    if document is None:
        raise ExerciseResultNotFoundError("No exercise result found with that id")

    return document


def _isoformat(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    return str(value)


def serialise_exercise_result(document: dict) -> dict:
    """Same snake_case-to-camelCase discipline as
    assessments.store.serialise_assessment — stored documents are never
    returned to a client unchanged (that would also leak user_id)."""

    return {
        "id": str(document["_id"]),
        "exerciseId": document.get("exerciseId"),
        "status": document.get("status"),
        # Documents written before this field existed were all camera
        # sessions, so that is what they are reported as.
        "source": document.get("source") or "camera",
        "startedAt": document.get("startedAt"),
        "completedAt": document.get("completedAt"),
        "measurements": document.get("measurements"),
        "errors": document.get("errors", []),
        "planId": document.get("plan_id"),
        "itemId": document.get("item_id"),
        "recordedAt": _isoformat(document.get("recorded_at")),
    }
