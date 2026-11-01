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

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from database import StorageError

from agents.sources import load_profile
from assessments.store import (
    baseline_assessment,
    latest_assessment,
    latest_valid_assessment,
    previous_assessment,
)
from auth.deps import get_current_user
from behaviour_log.store import list_behaviour_actions
from daily_checkins.store import list_daily_checkins
from exercise_assessment.store import list_exercise_results
from food_log.store import list_food_log_entries
from orchestrator.decision import evaluate_specialist_selection
from orchestrator.orchestrator import _candidate_recommendations, run_workflow
from orchestration.ids import start_workflow
from reports.store import confirmed_values_for_user
from user_state.store import get_user_state, save_user_state
from workflow_execution.store import get_execution, latest_execution, list_executions, save_execution
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


def _is_mcp_enabled() -> bool:
    """Check whether external MCP tool servers are explicitly configured."""
    return os.getenv("USE_MCP", "").lower() in ("true", "1", "yes")


def _build_physio_client(*, workflow_id: str, request_id: str):
    if _is_mcp_enabled() or os.getenv("PHYSIO_MCP_URL"):
        url = os.getenv("PHYSIO_MCP_URL", PHYSIO_MCP_URL)
        try:
            from physio_agent.mcp_client import McpExerciseToolClient

            client = McpExerciseToolClient(
                server_url=url, workflow_id=workflow_id, request_id=request_id
            )
            logger.info("Workflow tools: using MCP exercise client (%s)", url)
            return client
        except (ImportError, Exception) as exc:
            logger.info(
                "Workflow tools: MCP exercise client unavailable (%s), using in-process exercise client",
                exc,
            )
    else:
        logger.info("Workflow tools: MCP unavailable, using in-process exercise client")

    from physio_agent.tool_client import InProcessExerciseToolClient

    return InProcessExerciseToolClient(workflow_id=workflow_id, request_id=request_id)


def _build_behaviour_client(*, workflow_id: str, request_id: str):
    if _is_mcp_enabled() or os.getenv("BEHAVIOUR_MCP_URL"):
        url = os.getenv("BEHAVIOUR_MCP_URL", BEHAVIOUR_MCP_URL)
        try:
            from behaviour_agent.mcp_client import McpBehaviourToolClient

            client = McpBehaviourToolClient(
                server_url=url, workflow_id=workflow_id, request_id=request_id
            )
            logger.info("Workflow tools: using MCP behaviour client (%s)", url)
            return client
        except (ImportError, Exception) as exc:
            logger.info(
                "Workflow tools: MCP behaviour client unavailable (%s), using in-process behaviour client",
                exc,
            )
    else:
        logger.info("Workflow tools: MCP unavailable, using in-process behaviour client")

    from behaviour_agent.tool_client import InProcessBehaviourToolClient

    return InProcessBehaviourToolClient(workflow_id=workflow_id, request_id=request_id)


def _build_nutrition_client(*, workflow_id: str, request_id: str):
    if _is_mcp_enabled() or os.getenv("NUTRITION_MCP_URL"):
        url = os.getenv("NUTRITION_MCP_URL", NUTRITION_MCP_URL)
        try:
            from nutrition_agent.mcp_client import McpNutritionToolClient

            client = McpNutritionToolClient(
                server_url=url, workflow_id=workflow_id, request_id=request_id
            )
            logger.info("Workflow tools: using MCP nutrition client (%s)", url)
            return client
        except (ImportError, Exception) as exc:
            logger.info(
                "Workflow tools: MCP nutrition client unavailable (%s), using in-process nutrition client",
                exc,
            )
    else:
        logger.info("Workflow tools: MCP unavailable, using in-process nutrition client")

    from nutrition_agent.tool_client import InProcessNutritionToolClient

    return InProcessNutritionToolClient(workflow_id=workflow_id, request_id=request_id)


def _build_progress_client(*, workflow_id: str, request_id: str):
    if _is_mcp_enabled() or os.getenv("PROGRESS_MCP_URL"):
        url = os.getenv("PROGRESS_MCP_URL", PROGRESS_MCP_URL)
        try:
            from progress_agent.mcp_client import McpProgressToolClient

            client = McpProgressToolClient(
                server_url=url, workflow_id=workflow_id, request_id=request_id
            )
            logger.info("Workflow tools: using MCP progress client (%s)", url)
            return client
        except (ImportError, Exception) as exc:
            logger.info(
                "Workflow tools: MCP progress client unavailable (%s), using in-process progress client",
                exc,
            )
    else:
        logger.info("Workflow tools: MCP unavailable, using in-process progress client")

    from progress_agent.tool_client import InProcessProgressToolClient

    return InProcessProgressToolClient(workflow_id=workflow_id, request_id=request_id)


def _build_tool_clients(
    *,
    workflow_id: str,
    request_id: str,
    need_physio: bool,
    need_behaviour: bool,
    need_nutrition: bool,
    need_progress: bool,
) -> dict:
    """Construct the tool client(s) this cycle actually needs.

    Uses real MCP tool clients when MCP is configured and available;
    falls back cleanly to native in-process tool clients so the workflow
    runs reliably in environments without external MCP daemons.
    """
    clients = {}

    if need_physio:
        clients["tool_client"] = _build_physio_client(
            workflow_id=workflow_id, request_id=request_id
        )

    if need_behaviour:
        clients["behaviour_tool_client"] = _build_behaviour_client(
            workflow_id=workflow_id, request_id=request_id
        )

    if need_nutrition:
        clients["nutrition_tool_client"] = _build_nutrition_client(
            workflow_id=workflow_id, request_id=request_id
        )

    if need_progress:
        clients["progress_tool_client"] = _build_progress_client(
            workflow_id=workflow_id, request_id=request_id
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

    # Use one complete saved session as the Progress Agent's current input.
    # User State may be assembled from legacy records, so choose the latest
    # session that contains an extractable active measurement.
    current_assessment = latest_valid_assessment(user_id)

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
        "nutrition_food_log_entries": list_food_log_entries(user_id, limit=100),
        "nutrition_period_previous": period_previous,
        "nutrition_period_current": period_current,
    }


def _latest_execution_response(
    user_state: dict,
    execution: dict,
    *,
    selection_explanations: dict | None = None,
    last_safety_result: dict | None = None,
) -> dict:
    """Rebuild the response envelope from saved results using current rules.

    Execution results, selection decisions, User State and Safety Gate result
    are read from storage; no specialist is rerun. Re-serializing lets
    response fixes and clarified source data take effect after refresh while
    preserving the actual historical agent outputs.
    """
    snapshot = (execution or {}).get("response")
    agent_executions = (execution or {}).get("agent_executions") or {}
    created_at = (execution or {}).get("created_at")
    workflow_created_at = created_at.isoformat() if hasattr(created_at, "isoformat") else created_at
    if not agent_executions and isinstance(snapshot, dict):
        # Compatibility for early execution records that saved only their
        # response snapshot, with no dedicated execution result map.
        return {"available": True, **snapshot, "workflow_created_at": workflow_created_at}
    safety_result = last_safety_result or (execution or {}).get("safety_result")
    approved_recommendations = []
    if safety_result is not None:
        blocked = set(safety_result.get("blocked_recommendation_ids") or [])
        candidates = _candidate_recommendations(agent_executions)
        if safety_result.get("status") == "REFER":
            blocked.update(item.get("id") for item in candidates)
        modified = set(safety_result.get("modified_recommendation_ids") or [])
        for item in candidates:
            if item.get("id") in blocked:
                continue
            approved = dict(item)
            if safety_result.get("status") == "MODIFY" and item.get("id") in modified:
                approved["safety_note_added"] = True
            approved_recommendations.append(approved)

    explanations = selection_explanations or (execution or {}).get(
        "orchestrator_decision", {}
    ).get("selection_explanations", {})
    result = serialise_workflow_state(
        user_state,
        safety_status=(safety_result or {}).get("status"),
        safety_result=safety_result,
        agent_executions=agent_executions,
        selection_explanations=explanations,
        approved_recommendations=approved_recommendations,
        errors=(execution or {}).get("errors", []),
    )
    result["selection_explanations"] = explanations
    return {"available": True, **result, "workflow_created_at": workflow_created_at}


@router.post("/run")
def run_user_workflow(
    payload: dict | None = Body(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
):
    """Build the caller's User State and run the Orchestrator against it.

    Optional JSON body: `{"progress_trigger": {"reason": "..."}}` to also
    run a progress-triggered review this cycle. Omit the body (or pass
    `{}`) for a plain need-based run.
    """

    user_id = str(current_user["_id"])

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=400, detail="Idempotency-Key must contain 1 to 128 characters")
        try:
            previous = get_execution(user_id, idempotency_key)
        except StorageError:
            raise _database_error() from None
        if previous and isinstance(previous.get("response"), dict):
            prior_response = dict(previous["response"])
            created_at = previous.get("created_at")
            prior_response["workflow_created_at"] = created_at.isoformat() if hasattr(created_at, "isoformat") else created_at
            return prior_response

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
    except StorageError:
        raise _database_error() from None

    current_needs_section = user_state.get("current_needs") or {}
    need_profile = (
        current_needs_section.get("data")
        if current_needs_section.get("available")
        else None
    )

    try:
        behaviour_actions = list_behaviour_actions(user_id)
    except StorageError:
        raise _database_error() from None

    try:
        daily_checkins = list_daily_checkins(user_id, limit=7)
    except StorageError:
        raise _database_error() from None

    # Progress runs on every wellness workflow to report the baseline and
    # what history is still missing. Adaptation dispatch remains gated by a
    # real progress trigger inside the Orchestrator.
    try:
        progress_kwargs = _progress_inputs(user_state, user_id)
    except StorageError:
        raise _database_error() from None

    _, selection_explanations = evaluate_specialist_selection(
        user_state, need_profile, progress_trigger,
        behaviour_actions=behaviour_actions,
        progress_context=progress_kwargs,
    )
    # Every specialist analyses available evidence on a workflow run;
    # selection eligibility still governs whether it may create a tailored
    # intervention or dispatch a Progress adaptation.
    need_physio = need_behaviour = need_nutrition = need_progress = True

    # A completed Progress finding can dispatch a plan adaptation to one of
    # these specialists. Prepare only the clients a supported dispatch could
    # need; the specialist itself still runs only after that finding exists.
    nutrition_plans = (
        ((user_state.get("nutrition_plan") or {}).get("data") or {}).get("plans") or []
    )
    need_physio = need_physio or need_progress
    need_behaviour = need_behaviour or need_progress
    need_nutrition = need_nutrition or (need_progress and bool(nutrition_plans))

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
    except (ImportError, Exception) as error:
        # Never a stack trace to the end user — the real technical detail
        # goes to the server log only.
        logger.error(
            "Could not construct tool clients for user %s: %s",
            user_id,
            error,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=RECOMMENDATION_ENGINE_UNAVAILABLE,
        ) from None

    result = run_workflow(
        user_state,
        behaviour_actions=behaviour_actions,
        daily_checkins=daily_checkins,
        tool_client=clients.get("tool_client"),
        behaviour_tool_client=clients.get("behaviour_tool_client"),
        nutrition_tool_client=clients.get("nutrition_tool_client"),
        progress_tool_client=clients.get("progress_tool_client"),
        progress_trigger=progress_trigger,
        execute_all_agents=True,
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
        save_user_state(
            user_id,
            updated_user_state,
            safety_result=safety_result,
            selection_explanations=result["orchestrator_decision"].get(
                "selection_explanations", selection_explanations
            ),
        )
    except StorageError:
        raise _database_error() from None

    agent_executions = {
        item.get("agent"): item
        for item in (result.get("agent_results") or [])
        if isinstance(item, dict) and item.get("agent")
    }
    response = serialise_workflow_state(
        updated_user_state,
        safety_status=safety_result["status"] if safety_result else None,
        safety_result=safety_result,
        agent_executions=agent_executions,
        selection_explanations=result["orchestrator_decision"].get(
            "selection_explanations", selection_explanations
        ),
        approved_recommendations=result.get("final_recommendations", []),
        errors=result.get("errors", []),
    )
    response["selection_explanations"] = result["orchestrator_decision"].get(
        "selection_explanations", selection_explanations
    )
    execution_key = idempotency_key or result["workflow_id"]
    final_explanations = result["orchestrator_decision"].get(
        "selection_explanations", selection_explanations
    )
    progress_dispatches = {
        agent_id: {
            "reason": explanation.get("reason_for_selection"),
            "evidence": explanation.get("evidence_used", []),
        }
        for agent_id, explanation in final_explanations.items()
        if "Progress Agent recommended" in (explanation.get("reason_for_selection") or "")
    }
    try:
        saved_execution = save_execution(
            user_id,
            execution_key,
            {
                "workflow_id": result["workflow_id"],
                "selected_agents": result.get("selected_agents", []),
                "orchestrator_decision": result.get("orchestrator_decision", {}),
                "progress_dispatches": progress_dispatches,
                "agent_executions": agent_executions,
                "unified_plan": response.get("unified_plan"),
                "safety_result": safety_result,
                "errors": result.get("errors", []),
                "response": response,
            },
        )
    except StorageError:
        raise _database_error() from None
    created_at = saved_execution.get("created_at") if isinstance(saved_execution, dict) else None
    response["workflow_created_at"] = created_at.isoformat() if hasattr(created_at, "isoformat") else created_at
    return response


@router.get("/latest")
def read_latest_workflow_state(current_user: dict = Depends(get_current_user)):
    """The caller's most recently persisted workflow result. A normal 200
    with an honest "nothing yet" shape if `POST /api/workflow/run` has
    never been called for this account — never a 404 or a 500 for that."""

    user_id = str(current_user["_id"])

    try:
        document = get_user_state(user_id)
        execution = latest_execution(user_id)
    except StorageError:
        raise _database_error() from None

    if document is None:
        try:
            assessment_doc = latest_assessment(user_id)
        except StorageError:
            raise _database_error() from None

        if assessment_doc is not None:
            user_state = build_user_state_for_user(user_id)
            serialized = serialise_workflow_state(user_state)
            serialized["plan_state"] = {
                "state": "NEVER_RUN",
                "reason": "Your movement assessment is saved and ready.",
                "missing": [],
                "next_action": None,
            }
            serialized["plan_status"] = "NEVER_RUN"
            return {
                "available": False,
                **serialise_workflow_state(user_state),
                **serialized,
            }

        return never_run_response()

    # Prefer the saved response for current snapshots. Legacy snapshots are
    # reserialized from their actual saved executions so refreshes expose the
    # current response contract without rerunning specialists.
    if execution:
        return _latest_execution_response(
            document["state"], execution,
            selection_explanations=document.get("last_selection_explanations", {}),
            last_safety_result=document.get("last_safety_result"),
        )

    response = {
        "available": True,
        **serialise_workflow_state(
            document["state"],
            safety_status=(document.get("last_safety_result") or {}).get("status")
            if document.get("last_safety_result")
            else None,
            safety_result=document.get("last_safety_result"),
            agent_executions=(execution or {}).get("agent_executions"),
        ),
    }
    response["selection_explanations"] = document.get(
        "last_selection_explanations", {}
    )
    return response


@router.get("/history")
def read_workflow_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Return this caller's workflow execution history, newest first."""
    user_id = str(current_user["_id"])
    try:
        records = list_executions(user_id, limit)
    except StorageError:
        raise _database_error() from None
    return {
        "available": bool(records),
        "executions": [
            {
                "created_at": record.get("created_at"),
                "selected_agents": record.get("selected_agents", []),
                "results": ((record.get("response") or {}).get("execution_results") or {}),
                "response": record.get("response"),
            }
            for record in records
        ],
    }

