"""Food Log endpoints.

Every route here is authenticated and scoped to the caller, the exact same
discipline as routes/exercise_results.py. This is what turns
food_log/schema.py's validation into a real, structured food history —
the input nutrition_agent/adherence.py reads back out.

None of these endpoints interpret an entry, compute a calorie total, judge
a food, or decide whether the user is eating well. A food log here is a
record of what the user said they ate, nothing more.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from auth.deps import get_current_user
from food_log.schema import FoodLogValidationError, validate_food_log_entry
from food_log.store import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    FoodLogEntryNotFoundError,
    count_food_log_entries,
    get_food_log_entry,
    list_food_log_entries,
    save_food_log_entry,
    serialise_food_log_entry,
)


router = APIRouter(
    prefix="/api/food-log",
    tags=["Food Log"]
)


DATABASE_UNAVAILABLE = (
    "The food log entry could not be saved right now. This is a server or "
    "database problem, not a problem with what you logged."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE
    )


def _parse_timestamp(value: str, label: str):
    """Parse an ISO 8601 query parameter, or refuse it. Never guessed."""

    if value is None:
        return None

    text = value[:-1] + "+00:00" if value.endswith("Z") else value

    try:
        parsed = datetime.fromisoformat(text)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must be an ISO 8601 timestamp, got {value!r}"
        ) from None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


@router.post("", status_code=status.HTTP_201_CREATED)
def create_food_log_entry(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Validate and store one food log entry.

    Accepts either:
      - nested: `{"payload": {...}, "plan_id": ...}`
      - or flat: `{"meal": ..., "food_name": ..., "quantity": ..., "notes": ..., "plan_id": ...}`
    """
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a JSON object"
        )

    if "payload" in body and isinstance(body["payload"], dict):
        payload = body["payload"]
        plan_id = body.get("plan_id")
    else:
        payload = {k: v for k, v in body.items() if k != "plan_id"}
        plan_id = body.get("plan_id")

    try:
        document = validate_food_log_entry(payload)

    except FoodLogValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from None

    user_id = str(current_user["_id"])

    try:
        saved = save_food_log_entry(user_id, document, plan_id=plan_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "message": "Food log entry saved",
        "entry": serialise_food_log_entry(saved)
    }


@router.get("")
def read_food_log_history(
    meal: str | None = Query(None),
    plan_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """The caller's food log entries, newest first. Optionally narrowed by
    meal, plan_id, and an ISO 8601 recorded_at range."""

    user_id = str(current_user["_id"])

    parsed_from = _parse_timestamp(date_from, "date_from")
    parsed_to = _parse_timestamp(date_to, "date_to")

    try:
        documents = list_food_log_entries(
            user_id,
            meal=meal,
            plan_id=plan_id,
            date_from=parsed_from,
            date_to=parsed_to,
            limit=limit,
            skip=skip,
        )
        total = count_food_log_entries(user_id, plan_id=plan_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "entries": [serialise_food_log_entry(document) for document in documents],
        "total": total,
        "limit": limit,
        "skip": skip
    }


@router.get("/{entry_id}")
def read_food_log_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user)
):
    """One stored food log entry belonging to the caller."""

    user_id = str(current_user["_id"])

    try:
        document = get_food_log_entry(user_id, entry_id)

    except FoodLogEntryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from None

    except PyMongoError:
        raise _database_error() from None

    return {"entry": serialise_food_log_entry(document)}
