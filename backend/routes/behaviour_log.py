"""Behaviour Action endpoints.

Every route here is authenticated and scoped to the caller, the exact same
discipline as routes/food_log.py and routes/exercise_results.py. This is
what turns behaviour_log/schema.py's validation into a real, structured
record of what the user actually did — the evidence
behaviour_agent/adaptation.py reads back out.

None of these endpoints interpret an action, compute a rate, or judge the
user. Recording that you skipped something is as valid a record as
recording that you did it, and neither is scored here.

The route deliberately accepts no adherence figure of any kind. A client
that could post one could post a number nothing happened to produce, and
the whole point of this collection is that "how is it going" is answered
from records.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from auth.deps import get_current_user
from behaviour_log.schema import (
    BehaviourActionValidationError,
    build_behaviour_action,
)
from behaviour_log.store import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    count_behaviour_actions,
    list_behaviour_actions,
    save_behaviour_action,
    serialise_behaviour_action,
)

router = APIRouter(
    prefix="/api/behaviour-log",
    tags=["Behaviour Log"],
)

DATABASE_UNAVAILABLE = (
    "That could not be recorded right now. This is a server or database "
    "problem, not a problem with what you did."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE,
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
            detail=f"{label} must be an ISO 8601 timestamp, got {value!r}",
        ) from None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


@router.post("", status_code=status.HTTP_201_CREATED)
def create_behaviour_action(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Record that the caller did (or skipped) one habit goal.

    Accepts either:
      - nested: `{"payload": {...}, "plan_id": ...}`
      - or flat: `{"topic_id": ..., "status": ..., "difficulty": ...,
                   "notes": ..., "plan_id": ...}`

    Matching routes/food_log.py's own body handling, so the two client
    services can be written the same way.
    """

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a JSON object",
        )

    if "payload" in body and isinstance(body["payload"], dict):
        payload = body["payload"]
    else:
        payload = {key: value for key, value in body.items() if key != "plan_id"}

    plan_id = body.get("plan_id")

    try:
        document = build_behaviour_action(
            payload.get("topic_id"),
            status=payload.get("status", "completed"),
            difficulty=payload.get("difficulty"),
            notes=payload.get("notes"),
        )

    except BehaviourActionValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from None

    # Never from the body: ownership is the caller's identity, resolved
    # from their own token.
    user_id = str(current_user["_id"])

    try:
        saved = save_behaviour_action(user_id, document, plan_id=plan_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "message": "Action recorded",
        "action": serialise_behaviour_action(saved),
    }


@router.get("")
def read_behaviour_action_history(
    topic_id: str | None = Query(None),
    plan_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """The caller's recorded actions, newest first. This is what makes a
    completed action survive a page reload: the UI reads its state back
    from here rather than holding it in React."""

    user_id = str(current_user["_id"])

    parsed_from = _parse_timestamp(date_from, "date_from")
    parsed_to = _parse_timestamp(date_to, "date_to")

    try:
        documents = list_behaviour_actions(
            user_id,
            topic_id=topic_id,
            plan_id=plan_id,
            date_from=parsed_from,
            date_to=parsed_to,
            limit=limit,
            skip=skip,
        )
        total = count_behaviour_actions(user_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "total": total,
        "actions": [serialise_behaviour_action(document) for document in documents],
    }
