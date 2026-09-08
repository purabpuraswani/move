"""The Behaviour MCP Server: real MCP tools over the Behaviour Guidance Library.

Run standalone:

    cd backend
    .venv\\Scripts\\python.exe -m mcp_servers.behaviour_server

Mirrors mcp_servers/exercise_server.py and mcp_servers/nutrition_server.py
exactly. Every tool wraps exactly one behaviour_library.catalog function —
no tool here diagnoses a mental health condition or claims to treat one.

Tools implemented:

    search_behaviour_guidance_tool    behaviour_library.catalog.search_behaviour_guidance
    get_behaviour_topic_details_tool  behaviour_library.catalog.get_behaviour_topic_details

create_habit_plan / record_adherence / update_habit_plan are NOT
implemented here, for the same reason create_exercise_plan and
create_nutrition_plan are not MCP tools: plan/adherence tracking operates
on user-specific state, which is the Behaviour Agent + Orchestrator's job
(orchestrator/state_update.py), not a capability over this server's static
library content. get_behaviour_history / get_daily_routine / get_adherence
/ get_user_feedback / identify_barriers are also NOT implemented as MCP
tools: this application stores no behaviour-history, feedback, or
adherence data anywhere yet (confirmed by inspection — the questionnaire's
daily_sitting_hours/daily_screen_hours/exercise_days/exercise_minutes are
one-time onboarding answers, not a history), so a tool named
get_behaviour_history would have no real data source behind it — exactly
the placeholder this project's rules forbid. The Behaviour Agent instead
reads those onboarding answers directly from the User State it is handed
(see behaviour_agent/input_contract.py), the same way the Physio Agent
reads physical_assessment directly rather than through an MCP tool for it.
"""

try:
    from mcp.server.fastmcp import FastMCP

except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to run the Behaviour MCP Server. Install it with "
        "`pip install mcp` inside backend's virtual environment, then run "
        "`python -m mcp_servers.behaviour_server` again. Nothing else in "
        "MoveWell AI depends on this package."
    ) from exc

from behaviour_library.catalog import (
    BehaviourTopicNotFoundError,
    get_behaviour_topic_details,
    search_behaviour_guidance,
)
from mcp_servers.observability import tool_call_metadata
from orchestration.ids import TraceContext, start_agent_run, start_workflow

server = FastMCP("movewell-behaviour")


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
def search_behaviour_guidance_tool(
    target_signal: str | None = None,
    category: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Search the behaviour guidance library by questionnaire signal or category.

    `target_signal` is one of the four questionnaire-derived signals
    (daily_sitting_hours, daily_screen_hours, exercise_days,
    weekly_exercise_minutes). Both filters are optional.
    """

    trace = _trace(workflow_id, request_id)

    results = search_behaviour_guidance(target_signal=target_signal, category=category)

    return {
        "topics": results,
        "count": len(results),
        "metadata": tool_call_metadata(trace),
    }


@server.tool()
def get_behaviour_topic_details_tool(
    topic_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return the full library entry for one behaviour guidance topic_id."""

    trace = _trace(workflow_id, request_id)

    try:
        topic = get_behaviour_topic_details(topic_id)

    except BehaviourTopicNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"topic": topic, "metadata": tool_call_metadata(trace)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Behaviour MCP Server.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.port is not None:
        server.settings.port = args.port

    server.run(transport="streamable-http")
