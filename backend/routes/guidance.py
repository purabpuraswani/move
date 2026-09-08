"""Guidance endpoints.

Four things a client needs: what the agents are, what could be produced right
now, a run, and the last run. They are separate requests on purpose, because
only one of them costs a model call and a screen that spends money on mount is a
screen nobody can afford to leave open.

The reads never trigger a run and the run is never triggered by anything but an
explicit POST from the user. `GET /latest` returns whatever was produced last,
with whether the user's information has changed since, so the page can open
instantly and say plainly how current what it is showing is.

No report values are echoed back through these endpoints. Guidance is written
from confirmed values but the response carries counts and dates, not readings:
those belong to the reports screens, and a second copy in a second place is a
second thing to get wrong.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from agents.guardrails import DISCLAIMER, SAFETY_NOTE
from agents.llm import AgentFailed, AgentUnavailable
from agents.orchestrator import guidance_status, run_guidance
from agents.outputs import professional_type_options
from agents.registry import describe_agents
from agents.sources import load_context
from agents.store import latest_run, save_run, serialise_run
from auth.deps import get_current_user

router = APIRouter(
    prefix="/api/guidance",
    tags=["Guidance"]
)


DATABASE_UNAVAILABLE = (
    "Your information could not be reached right now. This is a server or "
    "database problem, and nothing about your guidance has been lost."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE
    )


@router.get("/agents")
def read_agents(_current_user: dict = Depends(get_current_user)):
    """The three agents, what each may do, and what none of them may do.

    Static, and deliberately available to any signed-in user: somebody deciding
    whether to trust this should be able to read the limits without first having
    to generate something.
    """

    return {
        "agents": describe_agents(),
        "professionalTypes": professional_type_options(),
        "disclaimer": DISCLAIMER,
        "safetyNote": SAFETY_NOTE,
    }


@router.get("/status")
def read_status(current_user: dict = Depends(get_current_user)):
    """What could be produced for this user right now, without producing it."""

    user_id = str(current_user["_id"])

    try:
        context = load_context(user_id)

    except PyMongoError:
        raise _database_error() from None

    return guidance_status(context)


@router.get("/latest")
def read_latest(current_user: dict = Depends(get_current_user)):
    """The last guidance produced for this user, if any."""

    user_id = str(current_user["_id"])

    try:
        document = latest_run(user_id)

        if document is None:
            return {"run": None}

        # The context is rebuilt so the stored run can be compared against the
        # user's information as it is now. Cheaper than it looks — three indexed
        # reads — and the alternative is presenting old guidance as current.
        context = load_context(user_id)

    except PyMongoError:
        raise _database_error() from None

    return {
        "run": serialise_run(
            document,
            current_signature=context.get("signature"),
        ),
        "disclaimer": DISCLAIMER,
        "safetyNote": SAFETY_NOTE,
    }


@router.post("/run")
def create_run(current_user: dict = Depends(get_current_user)):
    """Run the guidance agents for this user and keep the result.

    A user with nothing to work from gets a 200 with `ran: false` and the reason,
    not an error. Having recorded nothing yet is the ordinary state of a new
    account, and an error response would put a failure on the screen where an
    explanation belongs.
    """

    user_id = str(current_user["_id"])

    try:
        context = load_context(user_id)

    except PyMongoError:
        raise _database_error() from None

    try:
        result = run_guidance(context)

    except AgentUnavailable as error:
        # Not set up on this server. A configuration fact, so it is reported as
        # one rather than as a failure of the user's request.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from None

    except AgentFailed as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from None

    try:
        document = save_run(user_id, result)

    except PyMongoError:
        # The guidance exists and the user asked for it, so it is returned even
        # though it could not be kept. Losing it to protect a write would be the
        # wrong way round.
        return {**result, "saved": False}

    return {
        **result,
        "saved": True,
        "id": str(document["_id"]),
    }
