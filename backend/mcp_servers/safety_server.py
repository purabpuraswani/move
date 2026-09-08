"""The Safety MCP Server: real MCP tools over the deterministic Safety Gate.

Run standalone:

    cd backend
    .venv\\Scripts\\python.exe -m mcp_servers.safety_server

Mirrors mcp_servers/exercise_server.py's pattern. Every tool wraps
safety.gate.evaluate_safety() or a read of an exercise's own declared
constraints (exercise_library.catalog.check_exercise_constraints) — never
a model call, never an invented medical rule.

Tools implemented, and why these two and not more:

    check_safety_tool             safety.gate.evaluate_safety
    check_contraindications_tool  exercise_library.catalog.check_exercise_constraints

evaluate_risk / trigger_alert / pause_intervention / create_referral are
NOT implemented as separate MCP tools in Phase 4: check_safety_tool's
result (status + flags + actions + requires_referral) already IS the risk
evaluation, the pause signal, and the referral signal, all in the one real
Safety Result this system computes — inventing four more tool names for
things that would all just re-return pieces of check_safety_tool's already
real output would be exactly the "meaningless placeholder tool" this
project's rules forbid. There is no separate alerting/paging system, and
no separate referral-record store, in this application to give
trigger_alert or create_referral real behaviour of their own.
"""

try:
    from mcp.server.fastmcp import FastMCP

except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to run the Safety MCP Server. Install it with "
        "`pip install mcp` inside backend's virtual environment, then run "
        "`python -m mcp_servers.safety_server` again. Nothing else in "
        "MoveWell AI depends on this package."
    ) from exc

from exercise_library.catalog import ExerciseNotFoundError, check_exercise_constraints
from mcp_servers.observability import tool_call_metadata
from orchestration.ids import TraceContext, start_agent_run, start_workflow
from safety.gate import SafetyEvaluationError, evaluate_safety

server = FastMCP("movewell-safety")


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
def check_safety_tool(
    candidate_recommendations: list,
    need_profile: dict | None = None,
    confirmed_medical_context: dict | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Evaluate candidate specialist-agent recommendations deterministically.

    `candidate_recommendations` is the same normalised list the
    Orchestrator builds from Physio/Behaviour/Nutrition Agent Results (see
    orchestrator/orchestrator.py's _candidate_recommendations()) —
    [{"id", "agent", "type", "difficulty"}, ...]. Returns a full Safety
    Result (safety/schema.py): status, flags, actions, reason,
    requires_referral, modified/blocked recommendation ids.
    """

    trace = _trace(workflow_id, request_id)

    try:
        result = evaluate_safety(
            need_profile=need_profile,
            confirmed_medical_context=confirmed_medical_context,
            candidate_recommendations=candidate_recommendations,
        )

    except SafetyEvaluationError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {**result, "metadata": tool_call_metadata(trace)}


@server.tool()
def check_contraindications_tool(
    exercise_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return the safety-relevant, already-authored constraints for one
    exercise — the same real data check_exercise_constraints_tool
    (mcp_servers/exercise_server.py) exposes, surfaced here too since a
    caller doing a safety check plausibly wants it without a second server
    round trip through the Exercise MCP Server.
    """

    trace = _trace(workflow_id, request_id)

    try:
        constraints = check_exercise_constraints(exercise_id)

    except ExerciseNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {**constraints, "metadata": tool_call_metadata(trace)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Safety MCP Server.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.port is not None:
        server.settings.port = args.port

    server.run(transport="streamable-http")
