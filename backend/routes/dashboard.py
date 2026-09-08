"""Internal healthcare/developer observability dashboard (Phase 6).

Every route here depends on `require_staff_user` (auth/deps.py), never
`get_current_user` -- this is explicitly NOT patient-facing. A normal
account gets a 403 from every endpoint in this file. Unlike
`routes/workflow.py`'s deliberately narrow, redacted, user-facing summary
(no internal ids, no raw Agent Results), the routes here return the real,
unredacted internal shapes on purpose: an authorized internal viewer needs
to see plan_version history, adaptation reasons, the real Safety Result,
and real MCP integration status to actually operate this system.

The actual logic lives in dashboard/serialisers.py, which has no
pymongo/bson/fastapi import and is directly unit-testable; this module's
only job is fetching the real documents and wiring them through.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from auth.deps import require_staff_user
from dashboard.serialisers import flatten_plan_history, mcp_status_report, safe_account_info
from database import users_collection
from user_state.store import get_user_state

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard (internal)"])


DATABASE_UNAVAILABLE = (
    "This data could not be read right now. This is a server or database "
    "problem, not a problem with the request."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _object_id_or_404(user_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        return ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@router.get("/users/{user_id}/state")
def get_user_state_internal(user_id: str, _staff=Depends(require_staff_user)):
    """The full, unredacted, persisted User State for one user, plus a
    safe subset of their account info. 404 if the account or the state
    does not exist."""

    object_id = _object_id_or_404(user_id)

    try:
        user_doc = users_collection.find_one({"_id": object_id})
        state_doc = get_user_state(user_id)
    except PyMongoError:
        raise _database_error() from None

    if user_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "account": safe_account_info(user_doc),
        "user_state_available": state_doc is not None,
        "user_state": state_doc.get("state") if state_doc else None,
        "updated_at": state_doc.get("updated_at") if state_doc else None,
    }


@router.get("/users/{user_id}/plan-history")
def get_plan_history(user_id: str, _staff=Depends(require_staff_user)):
    """Every historical plan version across physio/nutrition/behaviour for
    one user, unredacted."""

    _object_id_or_404(user_id)

    try:
        state_doc = get_user_state(user_id)
    except PyMongoError:
        raise _database_error() from None

    if state_doc is None:
        return {
            "available": False,
            "message": "No workflow has been run yet for this user.",
            "plan_history": {"physio": [], "nutrition": [], "behaviour": []},
        }

    return {"available": True, "plan_history": flatten_plan_history(state_doc.get("state") or {})}


@router.get("/users/{user_id}/safety")
def get_safety_result(user_id: str, _staff=Depends(require_staff_user)):
    """The real, persisted Safety Result from this user's last workflow
    run, unredacted. Read straight from user_state.store's
    `last_safety_result` — never re-derived or guessed."""

    _object_id_or_404(user_id)

    try:
        state_doc = get_user_state(user_id)
    except PyMongoError:
        raise _database_error() from None

    if state_doc is None or state_doc.get("last_safety_result") is None:
        return {
            "available": False,
            "message": "No workflow has been run yet for this user.",
        }

    return {"available": True, "safety_result": state_doc["last_safety_result"]}


@router.get("/mcp-status")
def get_mcp_status(_staff=Depends(require_staff_user)):
    """Real, honest MCP integration status for every specialist server."""

    return mcp_status_report()
