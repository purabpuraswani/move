"""Workflow endpoints: `run_workflow()` (orchestrator/orchestrator.py) wired
into the real, running application (Phase 6).

Before this module existed, `run_workflow()` — the whole multi-agent
Physio/Nutrition/Behaviour -> Progress -> Safety Gate pipeline — was only
ever invoked from `backend/tests/`. There was no way for a real HTTP
request to build a User State from this project's actual database
documents and run it. This module is that wiring, and nothing else: it
assembles a User State for the calling user, runs the Orchestrator against
it with the real `Mcp*ToolClient` classes, persists the result, and
returns a small, deliberately narrow, user-facing summary of what came out
— never an internal orchestration id, never a raw Mongo `_id`, never a raw
Agent Result.

Every route here is authenticated (`auth.deps.get_current_user`) and
scoped strictly to the caller's own `user_id` — exactly like every other
route in `backend/routes/`. `user_id` is never accepted from the request
body or query string.

Assessment history (Phase 6): a progress-triggered run now passes a real
three-point history — `baseline_assessment` (the user's oldest session,
read-only and never promoted or rewritten, so reassessment adds a document
and leaves the comparison anchor where it was), `previous_assessment` (the
session before the latest, or None with fewer than two), and
`current_assessment` (the latest). With fewer than two sessions the
Progress Agent still correctly reports NOT_ENOUGH_DATA — the history is
supplied, never fabricated.

Nutrition closed loop (Phase 6): a progress-triggered run also passes two
real food-log observation windows, derived in `_nutrition_periods()` from
the active nutrition plan's own lifetime. Before this, those arguments were
never supplied over HTTP, so `findings["nutrition_progress"]` was always
None outside `backend/tests/` — the loop existed but was not closed in the
running application.

KNOWN LIMITATION, disclosed honestly rather than silently assumed away:
adherence for both windows is measured against the *latest* nutrition plan
record, because that is the record `run_workflow()` derives from the User
State. Food-log entries recorded against an earlier plan version are
therefore reported by `compute_food_log_adherence()` as belonging to
another plan rather than folded in — correct, but it means the comparison
is "the first half of this plan's life vs the second half", not "the old
plan vs the new plan".
"""

import logging
import os
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from agents.sources import load_profile
from assessments.store import (
    baseline_assessment,
    latest_assessment,
    previous_assessment,
)
from auth.deps import get_current_user
from behaviour_log.store import list_behaviour_actions
from exercise_assessment.store import list_exercise_results
from food_log.store import list_food_log_entries
from orchestrator.decision import (
    decide_behaviour_required,
    decide_nutrition_required,
    decide_physio_required,
    decide_progress_required,
)
from orchestrator.orchestrator import run_workflow
from orchestration.ids import start_workflow
from reports.store import confirmed_values_for_user
from user_state.store import get_user_state, save_user_state
from workflow.assembly import assemble_user_state_from_documents
from workflow.response import never_run_response, serialise_workflow_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


# ---------------------------------------------------------------------------
# MCP server locations. Each specialist's real MCP client (physio_agent/
# mcp_client.py and its Phase 4/5 siblings) needs a `server_url` to connect
# to; there is no other application code yet that decides one. These are
# honest, documented localhost defaults for local development — matching
# where `backend/mcp_servers/*.py` would run one server per specialist — not
# a claim that a server is actually listening there. A real deployment sets
# these explicitly via the environment.
# ---------------------------------------------------------------------------

PHYSIO_MCP_URL = os.getenv("PHYSIO_MCP_URL", "http://localhost:8001/mcp")
NUTRITION_MCP_URL = os.getenv("NUTRITION_MCP_URL", "http://localhost:8002/mcp")
BEHAVIOUR_MCP_URL = os.getenv("BEHAVIOUR_MCP_URL", "http://localhost:8003/mcp")
PROGRESS_MCP_URL = os.getenv("PROGRESS_MCP_URL", "http://localhost:8004/mcp")


RECOMMENDATION_ENGINE_UNAVAILABLE = (
    "The recommendation engine is temporarily unavailable. Please try "
    "again later."
)

DATABASE_UNAVAILABLE = (
    "Your plan could not be generated right now. This is a server or "
    "database problem, not a problem with your account."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE,
    )


# ---------------------------------------------------------------------------
# User State assembly — the only part of this module that touches MongoDB.
# The actual assembly logic lives in workflow/assembly.py, which takes
# plain documents and has no pymongo/bson import at all, so it is testable
# without a database connection; this function's only job is fetching the
# three real source documents this project already has a store for.
# ---------------------------------------------------------------------------


def build_user_state_for_user(user_id: str) -> dict:
    """Assemble a real, Need-Assessed User State for one authenticated user
    from this project's actual database documents: the onboarding profile
    (`agents.sources.load_profile`), the most recent physical assessment
    session (`assessments.store.latest_assessment` — the raw stored
    document, the same shape `user_state/schema.py`'s own tests build
    fixtures from), and this user's confirmed medical report values
    (`reports.store.confirmed_values_for_user`).
    """

    profile_doc = load_profile(user_id)
    assessment_doc = latest_assessment(user_id)
    confirmed_reports_doc = confirmed_values_for_user(user_id)

    # The User State this user already has, if any. Without it every run
    # rebuilt the state from source documents alone, and since no source
    # document can produce exercise_history / nutrition_plan / behaviour,
    # every previously created plan (and its whole version history) was
    # silently discarded on the next run. workflow/assembly.py carries the
    # merge rule that decides, section by section, which side wins.
    persisted_document = get_user_state(user_id)
    persisted_state = (persisted_document or {}).get("state")

    return assemble_user_state_from_documents(
        profile_doc=profile_doc,
        assessment_doc=assessment_doc,
        confirmed_reports_doc=confirmed_reports_doc,
        persisted_state=persisted_state,
    )


# ---------------------------------------------------------------------------
# Real MCP tool client construction. Imported lazily, inside this function,
# specifically so that `backend/main.py` importing `routes.workflow` never
# fails just because the `mcp` package is not installed — the same
# discipline every Mcp*ToolClient module documents about itself. Only the
# clients an agent that is actually required this cycle needs are built, so
# a user for whom no specialist is required is never affected by `mcp`
# being unavailable at all.
# ---------------------------------------------------------------------------


def _build_tool_clients(
    *,
    workflow_id: str,
    request_id: str,
    need_physio: bool,
    need_behaviour: bool,
    need_nutrition: bool,
    need_progress: bool,
) -> dict:
    """Construct the real Mcp*ToolClient(s) this cycle actually needs.

    Raises ImportError, uncaught, if the `mcp` package is not installed —
    the caller is responsible for turning that into a 503, never a stack
    trace surfaced to the end user.
    """

    clients = {}

    if need_physio:
        from physio_agent.mcp_client import McpExerciseToolClient

        clients["tool_client"] = McpExerciseToolClient(
            server_url=PHYSIO_MCP_URL, workflow_id=workflow_id, request_id=request_id
        )

    if need_behaviour:
        from behaviour_agent.mcp_client import McpBehaviourToolClient

        clients["behaviour_tool_client"] = McpBehaviourToolClient(
            server_url=BEHAVIOUR_MCP_URL, workflow_id=workflow_id, request_id=request_id
        )

    if need_nutrition:
        from nutrition_agent.mcp_client import McpNutritionToolClient

        clients["nutrition_tool_client"] = McpNutritionToolClient(
            server_url=NUTRITION_MCP_URL, workflow_id=workflow_id, request_id=request_id
        )

    if need_progress:
        from progress_agent.mcp_client import McpProgressToolClient

        clients["progress_tool_client"] = McpProgressToolClient(
            server_url=PROGRESS_MCP_URL, workflow_id=workflow_id, request_id=request_id
        )

    return clients


def _nutrition_periods(nutrition_plan_record: dict | None) -> tuple:
    """Two consecutive observation windows over the active nutrition plan's
    own lifetime, or (None, None) when there is nothing to observe.

    The windows are derived, never guessed: the plan's `created_at` is the
    earliest day any adherence claim about it could apply to, and today is
    the latest. That span is split in half, giving "the first half of this
    plan's life" and "the second half" — which is what
    `compare_nutrition_adherence()` is being asked to compare.

    A plan too young to split (under two days) yields (None, None) rather
    than two overlapping or zero-length windows. `compute_food_log_adherence`
    would in any case return INSUFFICIENT_DATA below its own
    MIN_OBSERVATION_DAYS, so a short window is never silently treated as
    evidence — but returning None here keeps the reason accurate: there is
    no period yet, as opposed to a period with too little in it.
    """

    if not nutrition_plan_record:
        return None, None

    created_raw = nutrition_plan_record.get("created_at")

    if not created_raw:
        return None, None

    try:
        if isinstance(created_raw, datetime):
            created = created_raw
        else:
            text_value = str(created_raw)
            if text_value.endswith("Z"):
                text_value = text_value[:-1] + "+00:00"
            created = datetime.fromisoformat(text_value)

    except (TypeError, ValueError):
        # An unparseable created_at is a data problem, not a licence to
        # invent a window. No period is better than a wrong one.
        return None, None

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    created_day = created.astimezone(timezone.utc).date()
    today = datetime.now(timezone.utc).date()

    total_days = (today - created_day).days + 1

    if total_days < 2:
        return None, None

    half = total_days // 2

    previous_start = created_day
    previous_end = created_day + timedelta(days=half - 1)
    current_start = created_day + timedelta(days=half)
    current_end = today

    def window(start_day, end_day):
        return {
            "start": datetime.combine(start_day, time.min, tzinfo=timezone.utc),
            "end": datetime.combine(end_day, time.max, tzinfo=timezone.utc),
        }

    return window(previous_start, previous_end), window(current_start, current_end)


def _progress_inputs(user_state: dict, user_id: str) -> dict:
    """The Progress Agent inputs this route supplies, as `run_workflow()`
    keyword arguments.

    Every key returned here is an actual `run_workflow()` parameter. It is
    splatted into that call, so a key the orchestrator does not accept is
    not a cosmetic mismatch — it raises TypeError and fails the request.
    In particular `current_plan`, `current_needs` and `nutrition_plan` are
    deliberately NOT returned: `run_workflow()` derives all three from the
    User State it is already given.
    """

    nutrition_section = user_state.get("nutrition_plan") or {}
    nutrition_plans = (
        (nutrition_section.get("data") or {}).get("plans", [])
        if nutrition_section.get("available")
        else []
    )
    nutrition_plan_record = nutrition_plans[-1] if nutrition_plans else None

    physical_section = user_state.get("physical_assessment") or {}
    current_assessment = (
        physical_section.get("data") if physical_section.get("available") else None
    )

    period_previous, period_current = _nutrition_periods(nutrition_plan_record)

    food_log_previous = None
    food_log_current = None

    if period_previous is not None and period_current is not None:
        # Not filtered by plan_id here on purpose: compute_food_log_adherence
        # does the ownership accounting itself and reports entries belonging
        # to another plan separately. Filtering them out at the query would
        # destroy that distinction and make another plan's logging look like
        # an absence of logging.
        food_log_previous = list_food_log_entries(
            user_id,
            date_from=period_previous["start"],
            date_to=period_previous["end"],
        )
        food_log_current = list_food_log_entries(
            user_id,
            date_from=period_current["start"],
            date_to=period_current["end"],
        )

    return {
        "baseline_assessment": baseline_assessment(user_id),
        "previous_assessment": previous_assessment(user_id),
        "current_assessment": current_assessment,
        "exercise_results": list_exercise_results(user_id),
        "nutrition_food_log_previous_period": food_log_previous,
        "nutrition_food_log_current_period": food_log_current,
        "nutrition_period_previous": period_previous,
        "nutrition_period_current": period_current,
    }


@router.post("/run")
def run_user_workflow(
    payload: dict | None = Body(None),
    current_user: dict = Depends(get_current_user),
):
    """Build the caller's User State and run the Orchestrator against it.

    Optional JSON body: `{"progress_trigger": {"reason": "..."}}` to also
    run a progress-triggered review this cycle. Omit the body (or pass
    `{}`) for a plain need-based run.
    """

    user_id = str(current_user["_id"])

    progress_trigger = None
    if payload:
        progress_trigger = payload.get("progress_trigger")

        if progress_trigger is not None and not isinstance(progress_trigger, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="progress_trigger must be an object, e.g. "
                '{"reason": "exercise activity recorded"}',
            )

    try:
        user_state = build_user_state_for_user(user_id)
    except PyMongoError:
        raise _database_error() from None

    current_needs_section = user_state.get("current_needs") or {}
    need_profile = (
        current_needs_section.get("data")
        if current_needs_section.get("available")
        else None
    )

    need_physio = decide_physio_required(need_profile)["physio_required"]
    need_behaviour = decide_behaviour_required(need_profile)["behaviour_required"]
    need_nutrition = decide_nutrition_required(need_profile)["nutrition_required"]
    need_progress = decide_progress_required(progress_trigger)["progress_required"]

    trace = start_workflow()

    try:
        clients = _build_tool_clients(
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            need_physio=need_physio,
            need_behaviour=need_behaviour,
            need_nutrition=need_nutrition,
            need_progress=need_progress,
        )
    except ImportError as error:
        # Never a stack trace, never the word "mcp"/"ImportError" to the
        # end user — the real technical detail goes to the server log only.
        logger.error(
            "Could not construct an Mcp*ToolClient for user %s (the 'mcp' "
            "package is likely not installed in this environment): %s",
            user_id,
            error,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=RECOMMENDATION_ENGINE_UNAVAILABLE,
        ) from None

    progress_kwargs = {}
    if need_progress:
        try:
            progress_kwargs = _progress_inputs(user_state, user_id)
        except PyMongoError:
            raise _database_error() from None

    try:
        behaviour_actions = list_behaviour_actions(user_id)
    except PyMongoError:
        raise _database_error() from None

    result = run_workflow(
        user_state,
        behaviour_actions=behaviour_actions,
        tool_client=clients.get("tool_client"),
        behaviour_tool_client=clients.get("behaviour_tool_client"),
        nutrition_tool_client=clients.get("nutrition_tool_client"),
        progress_tool_client=clients.get("progress_tool_client"),
        progress_trigger=progress_trigger,
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        **progress_kwargs,
    )

    updated_user_state = result["updated_user_state"]

    if updated_user_state is None:
        # Only reachable if build_user_state_for_user() somehow produced a
        # shape validate_user_state() rejects — a real bug, never silently
        # swallowed into a broken workflow.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not build a valid User State for this account: "
            + "; ".join(result["errors"] or ["unknown error"]),
        )

    safety_result = result["safety_result"]

    try:
        save_user_state(user_id, updated_user_state, safety_result=safety_result)
    except PyMongoError:
        raise _database_error() from None

    return serialise_workflow_state(
        updated_user_state,
        safety_status=safety_result["status"] if safety_result else None,
    )


@router.get("/latest")
def read_latest_workflow_state(current_user: dict = Depends(get_current_user)):
    """The caller's most recently persisted workflow result. A normal 200
    with an honest "nothing yet" shape if `POST /api/workflow/run` has
    never been called for this account — never a 404 or a 500 for that."""

    user_id = str(current_user["_id"])

    try:
        document = get_user_state(user_id)
    except PyMongoError:
        raise _database_error() from None

    if document is None:
        return never_run_response()

    return {
        "available": True,
        **serialise_workflow_state(
            document["state"],
            safety_status=(document.get("last_safety_result") or {}).get("status")
            if document.get("last_safety_result")
            else None,
        ),
    }

