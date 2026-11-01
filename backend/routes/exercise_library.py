"""Read-only view of the existing general exercise library."""
from fastapi import APIRouter, Depends
from auth.deps import get_current_user
from exercise_library.data import EXERCISES

router = APIRouter(prefix="/api/exercise-library", tags=["Exercise Library"])


@router.get("")
def read_exercise_library(_current_user: dict = Depends(get_current_user)):
    # This endpoint is for general reference browsing only. Plan eligibility
    # and approval continue to come exclusively from the Physio + Safety Gate workflow.
    return {"exercises": EXERCISES}
