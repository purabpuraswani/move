"""Assessment session endpoints.

Every route here is authenticated and scoped to the caller. The user id comes
from the verified token through get_current_user and is never read from the
request body, the query string, or a path parameter, so one user cannot write
or read another user's sessions.

None of these endpoints interpret a measurement. They store what the browser
measured and return it unchanged. Nothing here produces a score, a rating, or a
comparison, and nothing here decides whether a change between two sessions
means anything, because from two webcam recordings taken in uncontrolled
conditions that judgement cannot be made honestly.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from assessments.schema import AssessmentValidationError, validate_assessment_payload
from assessments.store import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    AssessmentNotFoundError,
    count_assessments,
    get_assessment,
    get_assessment_by_session,
    latest_assessment,
    list_assessments,
    save_assessment,
    serialise_assessment,
    serialise_assessment_listing,
)
from auth.deps import get_current_user


router = APIRouter(
    prefix="/api/assessments",
    tags=["Assessments"]
)


DATABASE_UNAVAILABLE = (
    "The results could not be reached right now. This is a server or database "
    "problem, not a problem with your assessment."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Store one completed assessment session.

    The payload is the object the browser builds from its own measurements. It
    is validated for structure and re-checked against the privacy rules before
    anything is written; see assessments/schema.py.
    """

    user_id = str(current_user["_id"])

    try:
        document = validate_assessment_payload(payload)

    except AssessmentValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from None

    try:
        result = save_assessment(user_id, document)

    except DuplicateKeyError:
        # Two submissions of the same session raced. The other one won, and it
        # holds the same session, so this is not an error for the caller.
        try:
            existing = get_assessment_by_session(user_id, document["session_id"])

        except (AssessmentNotFoundError, PyMongoError):
            raise _database_error() from None

        return {
            "message": "This session was already saved",
            "assessment": serialise_assessment(existing)
        }

    except PyMongoError:
        raise _database_error() from None

    return {
        "message": "Assessment saved" if result["created"] else "Assessment updated",
        "assessment": serialise_assessment(result["document"])
    }


@router.get("/latest")
def read_latest_assessment(current_user: dict = Depends(get_current_user)):
    """The caller's most recent session.

    A user who has never completed one is not an error: assessment is null and
    the client shows that no assessment has been taken, rather than showing
    zeros or placeholder numbers.
    """

    user_id = str(current_user["_id"])

    try:
        document = latest_assessment(user_id)
        total = count_assessments(user_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "assessment": serialise_assessment(document) if document else None,
        "total": total
    }


@router.get("")
def read_assessment_history(
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """The caller's sessions, newest first, without their measurements."""

    user_id = str(current_user["_id"])

    try:
        documents = list_assessments(user_id, limit=limit, skip=skip)
        total = count_assessments(user_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "assessments": [serialise_assessment_listing(document) for document in documents],
        "total": total,
        "limit": limit,
        "skip": skip
    }


@router.get("/{assessment_id}")
def read_assessment(
    assessment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """One full session belonging to the caller.

    An id that exists but belongs to someone else returns the same 404 as an id
    that does not exist, so the endpoint cannot be used to discover which
    sessions exist.
    """

    user_id = str(current_user["_id"])

    try:
        document = get_assessment(user_id, assessment_id)

    except AssessmentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from None

    except PyMongoError:
        raise _database_error() from None

    return {"assessment": serialise_assessment(document)}
