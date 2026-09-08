"""The Progress MCP Server: real MCP tools over the deterministic
comparison, adherence, and reassessment engines (Phase 5).

Run standalone:

    cd backend
    .venv\\Scripts\\python.exe -m mcp_servers.progress_server

Mirrors mcp_servers/exercise_server.py's pattern exactly. Every tool wraps
exactly one already-tested pure function from progress_agent.comparison,
progress_agent.adherence, or progress_agent.reassessment — no tool here
calls a model, invents a clinical claim, or judges outcome quality.

Tools implemented, and why these three and not the six suggested:

    compare_assessments_tool           progress_agent.comparison.compare_physical_assessments
    calculate_adherence_tool            progress_agent.adherence.compute_plan_adherence
    check_reassessment_required_tool    progress_agent.reassessment.check_reassessment_required
    calculate_nutrition_adherence_tool  nutrition_agent.adherence.compute_food_log_adherence (Phase 6)

`get_progress`/`generate_progress_report` were not built as separate
tools: their entire real content is already these three tools' combined
output — a fourth tool that just re-packaged the same three calls would
be exactly the "meaningless placeholder tool" this project's rules
forbid. `trigger_reassessment` was deliberately renamed/scoped to
`check_reassessment_required_tool`: this application has no notification
or scheduling system to "trigger" (same precedent as Phase 4's Safety MCP
Server not implementing `trigger_alert`) — what this server can honestly
provide is the deterministic *check*, not an action.
"""

try:
    from mcp.server.fastmcp import FastMCP

except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to run the Progress MCP Server. Install it with "
        "`pip install mcp` inside backend's virtual environment, then run "
        "`python -m mcp_servers.progress_server` again. Nothing else in "
        "MoveWell AI depends on this package."
    ) from exc

from mcp_servers.observability import tool_call_metadata
from orchestration.ids import TraceContext, start_agent_run, start_workflow
from progress_agent.adherence import AdherenceCalculationError, compute_plan_adherence
from progress_agent.comparison import compare_physical_assessments
from progress_agent.reassessment import check_reassessment_required
from nutrition_agent.adherence import FoodLogAdherenceError, compute_food_log_adherence

server = FastMCP("movewell-progress")


def _trace(workflow_id: str = None, request_id: str = None) -> TraceContext:
    """Continue a caller's trace if given both ids, otherwise start a new one.

    A tool call sits inside an agent run in the id hierarchy (workflow ->
    request -> agent run -> tool call), so an agent_run_id is derived here
    before the tool call is traced. Without it start_tool_call() correctly
    refuses the context and every tool raises -- which is exactly what
    happened, unnoticed, for as long as these servers could not be run.

    The agent run issued here is this server's own handling of one incoming
    call. It does not claim to be the caller's: workflow_id and request_id
    are carried through when supplied, but the tool protocol carries no
    agent_run_id to continue, so a fresh one is minted rather than a
    caller's invented.
    """

    if workflow_id and request_id:
        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
    else:
        parent = start_workflow()

    return start_agent_run(parent)


@server.tool()
def compare_assessments_tool(
    baseline_assessment: dict | None = None,
    previous_assessment: dict | None = None,
    current_assessment: dict | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Compare the three physical baseline metrics (mobility/stability/
    functional movement) across baseline/previous/current raw assessment
    documents. Any argument may be omitted/None — handled as
    NOT_ENOUGH_DATA per metric, never a crash or a guessed value.
    """

    trace = _trace(workflow_id, request_id)

    comparison = compare_physical_assessments(
        baseline_assessment, previous_assessment, current_assessment
    )

    return {"comparison": comparison, "metadata": tool_call_metadata(trace)}


@server.tool()
def calculate_adherence_tool(
    plan_record: dict,
    exercise_results: list | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Compute completion-rate adherence for one exercise_history plan
    record against a list of stored exercise results. Never claims
    adherence when the plan or the results say nothing about it — see
    progress_agent.adherence's own docstring for how missing data stays
    NOT_ENOUGH_DATA rather than becoming a fabricated 0%.
    """

    trace = _trace(workflow_id, request_id)

    try:
        adherence = compute_plan_adherence(plan_record, exercise_results or [])

    except AdherenceCalculationError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"adherence": adherence, "metadata": tool_call_metadata(trace)}


@server.tool()
def check_reassessment_required_tool(
    current_assessment_completed_at: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Check whether the most recent physical assessment is missing or
    stale enough that a reassessment should be requested before trusting a
    progress comparison. A system-decision threshold — see
    progress_agent.reassessment's own docstring; never a clinical timing
    claim.
    """

    trace = _trace(workflow_id, request_id)

    result = check_reassessment_required(current_assessment_completed_at)

    return {**result, "metadata": tool_call_metadata(trace)}


@server.tool()
def calculate_nutrition_adherence_tool(
    nutrition_plan: dict,
    food_log_entries: list | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Compute food-logging adherence for one nutrition_plan history record
    against a list of stored food_log entries. Wraps
    nutrition_agent.adherence.compute_food_log_adherence exactly — see that
    module's own docstring for why a missing food log is NOT_LOGGED, never
    a fabricated NOT_ADHERED or a fabricated 0% rate.
    """

    trace = _trace(workflow_id, request_id)

    try:
        adherence = compute_food_log_adherence(
            nutrition_plan,
            food_log_entries or [],
            period_start=period_start,
            period_end=period_end,
        )

    except FoodLogAdherenceError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"adherence": adherence, "metadata": tool_call_metadata(trace)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Progress MCP Server.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.port is not None:
        server.settings.port = args.port

    server.run(transport="streamable-http")
