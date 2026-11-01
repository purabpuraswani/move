"""Daily self-reported activity, nutrition, and recovery values."""
from datetime import date
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from auth.deps import get_current_user
from daily_checkins.schema import DailyCheckinValidationError, validate_checkin
from daily_checkins.store import list_daily_checkins, save_daily_checkin, serialise

router = APIRouter(prefix="/api/daily-checkins", tags=["Daily Check-ins"])


@router.post("")
def put_daily_checkin(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    try:
        if not isinstance(body, dict):
            raise ValueError("Check-in must be an object")
        day = date.fromisoformat(body.get("date", date.today().isoformat())).isoformat()
        values = validate_checkin(body)
        saved = save_daily_checkin(str(current_user["_id"]), day, values)
    except (TypeError, ValueError, DailyCheckinValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"checkin": serialise(saved)}


@router.get("")
def read_daily_checkins(limit: int = Query(90, ge=1, le=365), current_user: dict = Depends(get_current_user)):
    rows = list_daily_checkins(str(current_user["_id"]), limit)
    return {"checkins": [serialise(row) for row in rows]}
