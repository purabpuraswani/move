"""The Exercise MCP Server: real MCP tools over the Exercise Library.

Run standalone:

    cd backend
    .venv\\Scripts\\python.exe -m mcp_servers.exercise_server

Requires the `mcp` package (see backend/requirements.txt and this package's
`__init__.py` for why it is optional and why Streamable HTTP). Nothing else
in the application imports this module, so its absence never breaks the
rest of the backend — the same "optional, and says so" pattern the AI
provider already uses (backend/reports/extraction.py, backend/agents/llm.py).

Every tool below is a thin wrapper: it validates/normalises its arguments,
calls exactly one function from exercise_library.catalog or
exercise_assessment.schema (the same functions backend/tests/*
exercises directly, without MCP in the loop at all), and returns a plain
JSON-serialisable dict. No tool here calls a model, touches a database, or
makes a decision about what a user should do — this server answers
questions about the library and accepts a structured result; it does not
interpret either.

Tools implemented, and why these five and not more:

    search_exercises            exercise_library.catalog.search_exercises
    get_exercise_details        exercise_library.catalog.get_exercise_details
    get_demo_animation          points at src/movementDemos by id (see below)
    check_exercise_constraints  exercise_library.catalog.check_exercise_constraints
    record_exercise_result      exercise_assessment.schema.record_exercise_result

create_exercise_plan / update_exercise_plan are NOT implemented in Phase 2:
there is no exercise-plan concept anywhere in the backend yet (no schema, no
storage) — building one now, with no Physio Agent to populate it
meaningfully, would be exactly the "meaningless placeholder tool" this
phase was told not to create. They belong with the Physio Agent, in Phase 3,
once there is a real plan structure for them to operate on.

get_demo_animation does not return animation frame data. The demonstration
content it points at (src/movementDemos/registry.js) is authored in
JavaScript and rendered client-side by design (Phase 0) — duplicating it
into this Python module would create two sources of truth for the same
content. What an agent actually needs from this tool is confirmation that a
demonstration exists for a given exercise and its id, so it can, for
example, avoid recommending an exercise with no demonstration; that is what
this tool answers.
"""

try:
    from mcp.server.fastmcp import FastMCP

except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to run the Exercise MCP Server. Install it with "
        "`pip install mcp` inside backend's virtual environment, then run "
        "`python -m mcp_servers.exercise_server` again. Nothing else in "
        "MoveWell AI depends on this package."
    ) from exc

from exercise_assessment.schema import (
    ExerciseResultValidationError,
    record_exercise_result,
)
from exercise_library.catalog import (
    ExerciseNotFoundError,
    check_exercise_constraints,
    get_exercise_details,
    search_exercises,
)
from exercise_library.schema import ExerciseValidationError
from mcp_servers.observability import tool_call_metadata
from orchestration.ids import TraceContext, start_agent_run, start_workflow

server = FastMCP("movewell-exercise")


def _trace(workflow_id: str = None, request_id: str = None) -> TraceContext:
    """Continue a caller's trace if given both ids, otherwise start a new one.

    A tool call sits inside an agent run in the id hierarchy (workflow ->
    request -> agent run -> tool call), so an agent_run_id is derived here
    before the tool call is traced. Without it start_tool_call() correctly
    refuses the context and every tool raises -- which is exactly what
    happened, unnoticed, for as long as these servers could not be run.

    The agent run issued here is this server's own handling of one incoming
    call. It does not claim to be the caller's agent run: the caller's
    workflow_id and request_id are carried through when supplied, but the
    tool protocol carries no agent_run_id to continue, so a fresh one is
    minted rather than a caller's invented.
    """

    if workflow_id and request_id:
        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
    else:
        parent = start_workflow()

    return start_agent_run(parent)


@server.tool()
def search_exercises_tool(
    target_capability: str | None = None,
    target_body_area: str | None = None,
    difficulty: str | None = None,
    category: str | None = None,
    movenet_implemented_only: bool = False,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Search the exercise library by capability, body area, difficulty, or category.

    All filters are optional; omitting every one returns the whole library.
    `movenet_implemented_only` narrows to exercises this project can already
    produce structured movement metrics for (see get_exercise_details'
    movenet_support field) — useful for a caller that specifically wants a
    monitorable exercise rather than any exercise.
    """

    trace = _trace(workflow_id, request_id)

    results = search_exercises(
        target_capability=target_capability,
        target_body_area=target_body_area,
        difficulty=difficulty,
        category=category,
        movenet_implemented_only=movenet_implemented_only,
    )

    return {
        "exercises": results,
        "count": len(results),
        "metadata": tool_call_metadata(trace),
    }


@server.tool()
def get_exercise_details_tool(
    exercise_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return the full library entry for one exercise_id."""

    trace = _trace(workflow_id, request_id)

    try:
        exercise = get_exercise_details(exercise_id)

    except ExerciseNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"exercise": exercise, "metadata": tool_call_metadata(trace)}


@server.tool()
def get_demo_animation_tool(
    exercise_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Confirm the movement demonstration reference for one exercise.

    Returns the demonstration_id the exercise library declares
    (src/movementDemos/registry.js renders the actual content client-side
    from this id) — not animation frame data. See this module's docstring
    for why.
    """

    trace = _trace(workflow_id, request_id)

    try:
        exercise = get_exercise_details(exercise_id)

    except ExerciseNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {
        "exerciseId": exercise_id,
        "demonstrationId": exercise["demonstration_id"],
        "renderedBy": "src/movementDemos (client-side)",
        "metadata": tool_call_metadata(trace),
    }


@server.tool()
def check_exercise_constraints_tool(
    exercise_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return the safety-relevant, already-authored constraints for one exercise.

    This is a read of the library's own data, not a personalised safety
    judgment about a specific user — combining this with a user's Need
    Profile or medical context is Physio Agent / Safety Agent work, later.
    """

    trace = _trace(workflow_id, request_id)

    try:
        constraints = check_exercise_constraints(exercise_id)

    except ExerciseNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {**constraints, "metadata": tool_call_metadata(trace)}


@server.tool()
def record_exercise_result_tool(
    exercise_id: str,
    status: str,
    measurements: dict | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    errors: list | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Validate and accept a structured exercise performance result.

    `measurements` must already be the reduced, structured numbers a
    browser-side movement-assessment engine produced (see
    src/exerciseAssessment/) — repetitions, durationSeconds, rangeOfMotion,
    and so on. This tool refuses (does not silently drop) anything shaped
    like raw pose or frame data, and refuses a metric an exercise does not
    declare it can produce. It does not persist the result anywhere yet —
    see exercise_assessment/schema.py's docstring on why — it validates and
    returns it, structurally, as record_exercise_result() promises to.
    """

    trace = _trace(workflow_id, request_id)

    payload = {
        "exerciseId": exercise_id,
        "status": status,
        "measurements": measurements,
        "startedAt": started_at,
        "completedAt": completed_at,
        "errors": errors,
    }

    try:
        result = record_exercise_result(payload)

    except ExerciseNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    except ExerciseResultValidationError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"result": result, "accepted": True, "metadata": tool_call_metadata(trace)}


if __name__ == "__main__":
    import argparse

    # --port exists specifically so backend/tests/test_physio_agent_mcp_integration.py
    # (Phase 3) can start this server on an ephemeral port rather than a
    # fixed one, which would collide across parallel test runs. Defaults to
    # FastMCP's own default (8000) when not given, matching plain
    # `python -m mcp_servers.exercise_server` with no arguments.
    parser = argparse.ArgumentParser(description="Run the Exercise MCP Server.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.port is not None:
        server.settings.port = args.port

    # Streamable HTTP: stateful, issues a real Mcp-Session-Id on initialize.
    # See this package's __init__.py for why this transport was chosen over
    # stdio for this server.
    server.run(transport="streamable-http")
