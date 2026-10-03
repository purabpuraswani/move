"""Exercise Result endpoints (Phase 5).

Every route here is authenticated and scoped to the caller, same discipline
as routes/assessments.py. This is what turns exercise_assessment.schema's
validation (Phase 2, never persisted) into a real, structured performance
history — the "User Performs Plan -> Structured Performance Data" step the
Phase 5 closed loop needs.

None of these endpoints interpret a result, decide whether it represents
improvement, or compare it to anything. That is Progress Agent work
(backend/progress_agent/), reading this history back out, later.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from auth.deps import get_current_user
from exercise_assessment.schema import (
    ExerciseResultValidationError,
    record_exercise_result,
)
from exercise_assessment.store import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    ExerciseResultNotFoundError,
    count_exercise_results,
    delete_manual_exercise_result,
    get_exercise_result,
    list_exercise_results,
    save_exercise_result,
    serialise_exercise_result,
)
from exercise_library.catalog import ExerciseNotFoundError


router = APIRouter(
    prefix="/api/exercise-results",
    tags=["Exercise Results"]
)


DATABASE_UNAVAILABLE = (
    "The result could not be saved right now. This is a server or database "
    "problem, not a problem with your exercise submission."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_exercise_result(
    payload: dict = Body(...),
    plan_id: str | None = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """Validate and store one completed exercise's performance result.

    `payload` is the same shape exercise_assessment.schema.record_exercise_result
    already validates (exerciseId, status, measurements, ...) — this route
    adds nothing new to that contract, it only makes the validated result
    outlive the request. `plan_id` is optional: pass the plan_id from the
    User State's exercise_history record this result is performing against,
    if known, so the Progress Agent can later compute adherence per-plan.
    """

    try:
        document = record_exercise_result(payload)

    except ExerciseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from None

    except ExerciseResultValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from None

    user_id = str(current_user["_id"])

    try:
        saved = save_exercise_result(user_id, document, plan_id=plan_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "message": "Exercise result saved",
        "result": serialise_exercise_result(saved)
    }


@router.get("")
def read_exercise_result_history(
    exercise_id: str | None = Query(None),
    plan_id: str | None = Query(None),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """The caller's exercise results, newest first. Optionally narrowed to
    one exercise_id or one plan_id."""

    user_id = str(current_user["_id"])

    try:
        documents = list_exercise_results(
            user_id, exercise_id=exercise_id, plan_id=plan_id, limit=limit, skip=skip
        )
        total = count_exercise_results(user_id, plan_id=plan_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "results": [serialise_exercise_result(document) for document in documents],
        "total": total,
        "limit": limit,
        "skip": skip
    }


@router.get("/{result_id}")
def read_exercise_result(
    result_id: str,
    current_user: dict = Depends(get_current_user)
):
    """One stored result belonging to the caller."""

    user_id = str(current_user["_id"])

    try:
        document = get_exercise_result(user_id, result_id)

    except ExerciseResultNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from None

    except PyMongoError:
        raise _database_error() from None

    return {"result": serialise_exercise_result(document)}


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise_result(
    result_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove one manually confirmed result -- un-ticking "mark as completed".

    Only a manual confirmation can be deleted, and only by the user who
    recorded it. A camera session is a measurement that actually happened,
    so this history stays append-only for those: a 404 here means either
    no such row, or a row this endpoint is not allowed to touch, and the
    caller cannot tell the two apart.
    """

    user_id = str(current_user["_id"])

    try:
        deleted = delete_manual_exercise_result(user_id, result_id)

    except PyMongoError:
        raise _database_error() from None

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No manually confirmed result with that id was found for this "
                "account. Camera-recorded sessions cannot be deleted."
            ),
        )

    return None
