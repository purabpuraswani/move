"""Progress endpoints: what the user has recorded, over time.

Read-only and derived entirely from existing stores. Nothing here
measures, scores, or decides anything -- it reshapes stored exercise
results, stored assessments, and the user's stored plan versions into
the series the Progress page plots, using progress_agent/series.py.

Why a dedicated endpoint rather than widening the workflow response:
plotting history needs the assessments' MEASUREMENTS, and the workflow
response deliberately carries only the latest state. Fetching each
assessment separately from the browser would also mean one request per
session; doing it here keeps it to one.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import PyMongoError

from assessments.store import list_assessments
from auth.deps import get_current_user
from exercise_assessment.store import list_exercise_results, serialise_exercise_result
from progress_agent.series import build_progress_series
from routes.workflow import build_user_state_for_user


router = APIRouter(prefix="/api/progress", tags=["Progress"])

# How far back the page looks. Generous enough to show a real history,
# bounded so one request cannot pull an unlimited number of documents.
DEFAULT_RESULT_LIMIT = 200
MAX_RESULT_LIMIT = 500
DEFAULT_ASSESSMENT_LIMIT = 50


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Your progress could not be read just now. Please try again.",
    )


@router.get("/series")
def read_progress_series(
    limit: int = Query(DEFAULT_RESULT_LIMIT, ge=1, le=MAX_RESULT_LIMIT),
    current_user: dict = Depends(get_current_user),
):
    """The caller's recorded progress, with sufficiency flags per series.

    Every series says how many points it has and whether it is
    plottable. A caller must not draw a trend through a series flagged
    unplottable: one point is a record, not a direction of travel.
    """

    user_id = str(current_user["_id"])

    try:
        results = [
            serialise_exercise_result(document)
            for document in list_exercise_results(user_id, limit=limit)
        ]
        assessment_documents = list_assessments(user_id, limit=DEFAULT_ASSESSMENT_LIMIT)
        user_state = build_user_state_for_user(user_id)

    except PyMongoError:
        raise _database_error() from None

    series = build_progress_series(
        exercise_results=results,
        assessment_documents=assessment_documents,
        user_state=user_state,
    )

    return series
