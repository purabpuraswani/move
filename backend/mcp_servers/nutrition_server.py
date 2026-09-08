"""The Nutrition MCP Server: real MCP tools over the Nutrition Guidance Library.

Run standalone:

    cd backend
    .venv\\Scripts\\python.exe -m mcp_servers.nutrition_server

Mirrors mcp_servers/exercise_server.py exactly: requires the `mcp` package,
optional (nothing else in the application imports this module), and every
tool is a thin wrapper around exactly one nutrition_library.catalog
function — no tool here calls a model, touches a database, diagnoses a
deficiency, or prescribes a diet/supplement.

Tools implemented, and what real function each one wraps:

    search_nutrition_guidance_tool   nutrition_library.catalog.search_nutrition_guidance
    get_nutrition_topic_details_tool nutrition_library.catalog.get_nutrition_topic_details
    search_food_tool                 nutrition_library.catalog.search_foods
    get_food_details_tool            nutrition_library.catalog.get_food
    record_food_log_tool             food_log.schema + food_log.store.save_food_log_entry
    calculate_food_adherence_tool    nutrition_agent.adherence.compute_food_log_adherence

record_food_log_tool is the one tool here that writes to a database; it is
still ownership-scoped (it requires an explicit user_id and stores nothing
without one) and it validates before it stores, exactly as
routes/food_log.py does.

Suggested tools deliberately NOT built, and why — the same honest-omission
discipline mcp_servers/progress_server.py already uses: get_nutrition_assessment
and get_food_preferences would only re-read fields the Nutrition Agent
already receives in its own input contract (nutrition_agent/input_contract.py's
relevant_nutrition_signals and food_preferences, the latter still honestly
None because no preference-collection UI exists), and create_nutrition_plan /
update_nutrition_plan would only re-package the Nutrition Agent's own plan
construction plus orchestrator/state_update.py's write to User State — so
all four would be tools that repackage an existing call with no new real
capability, which this project's rules forbid.

NOT EXECUTED HERE: as with every other MCP server in this project, this
module could not be run in the development sandbox (the `mcp` package
cannot be installed — no PyPI network access, and no network egress at all
for a live transport). It is verified here by py_compile/ast.parse and by
testing the underlying functions directly; the MCP transport itself is
unverified in this environment, and that is stated rather than glossed.
"""

try:
    from mcp.server.fastmcp import FastMCP

except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to run the Nutrition MCP Server. Install it with "
        "`pip install mcp` inside backend's virtual environment, then run "
        "`python -m mcp_servers.nutrition_server` again. Nothing else in "
        "MoveWell AI depends on this package."
    ) from exc

from food_log.schema import FoodLogValidationError, validate_food_log_entry
from mcp_servers.observability import tool_call_metadata
from nutrition_agent.adherence import (
    FoodLogAdherenceError,
    compute_food_log_adherence,
)
from nutrition_library.catalog import (
    NutritionTopicNotFoundError,
    get_food,
    get_nutrition_topic_details,
    search_foods,
    search_nutrition_guidance,
)
from orchestration.ids import TraceContext, start_agent_run, start_workflow

server = FastMCP("movewell-nutrition")


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
def search_nutrition_guidance_tool(
    target_signal: str | None = None,
    category: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Search the nutrition guidance library by self-reported signal or category.

    `target_signal` is one of the four Phase 4 self-reported nutrition
    fields (meal_pattern, fruit_vegetable_servings, water_glasses_per_day,
    processed_food_frequency). Both filters are optional.
    """

    trace = _trace(workflow_id, request_id)

    results = search_nutrition_guidance(target_signal=target_signal, category=category)

    return {
        "topics": results,
        "count": len(results),
        "metadata": tool_call_metadata(trace),
    }


@server.tool()
def get_nutrition_topic_details_tool(
    topic_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return the full library entry for one nutrition guidance topic_id."""

    trace = _trace(workflow_id, request_id)

    try:
        topic = get_nutrition_topic_details(topic_id)

    except NutritionTopicNotFoundError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"topic": topic, "metadata": tool_call_metadata(trace)}


@server.tool()
def search_food_tool(
    query: str | None = None, workflow_id: str = None, request_id: str = None
) -> dict:
    """Search this project's curated Indian food composition dataset.

    The result also reports the secondary sources (Open Food Facts, USDA
    FoodData Central) as consulted-but-unavailable in this environment, so
    a caller can tell "no such food" apart from "the source that would
    know could not be reached". No result here is ever fabricated from an
    unavailable source, and the curated numbers are honest estimates, not
    official IFCT 2017 figures — see nutrition_library/food_composition.py.
    """

    trace = _trace(workflow_id, request_id)

    result = search_foods(query)

    return {**result, "metadata": tool_call_metadata(trace)}


@server.tool()
def get_food_details_tool(
    food_id: str, workflow_id: str = None, request_id: str = None
) -> dict:
    """Return one curated food composition record by food_id.

    `food` is null when the id is not in the curated dataset — an honest
    miss, never a guessed nearest match.
    """

    trace = _trace(workflow_id, request_id)

    food = get_food(food_id)

    if food is None:
        return {
            "food": None,
            "reason": (
                f"{food_id!r} is not in this project's curated Indian food "
                "composition dataset, and the secondary sources that might "
                "know it are unavailable in this environment"
            ),
            "metadata": tool_call_metadata(trace),
        }

    return {"food": food, "metadata": tool_call_metadata(trace)}


@server.tool()
def record_food_log_tool(
    entry: dict,
    user_id: str,
    plan_id: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Validate and store one food log entry for one owning user.

    `entry` is food_log/schema.py's shape (meal, food_id/food_name,
    quantity, notes, water_intake_ml). `user_id` is required: this tool
    never stores an entry it cannot attribute to an owner. Validation
    failures and storage failures are both returned as {"error": ...},
    never as a silent success.
    """

    trace = _trace(workflow_id, request_id)

    try:
        document = validate_food_log_entry(entry)

    except FoodLogValidationError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    if not isinstance(user_id, str) or not user_id.strip():
        return {
            "error": "user_id is required: a food log entry is always owned",
            "metadata": tool_call_metadata(trace),
        }

    # Imported here, not at module scope, so the rest of this server's
    # tools stay importable in an environment without pymongo installed.
    from food_log.store import save_food_log_entry, serialise_food_log_entry

    try:
        saved = save_food_log_entry(user_id, document, plan_id=plan_id)

    except Exception as error:  # noqa: BLE001 — reported, never hidden
        return {
            "error": f"food log entry could not be stored: {error}",
            "metadata": tool_call_metadata(trace),
        }

    return {
        "entry": serialise_food_log_entry(saved),
        "metadata": tool_call_metadata(trace),
    }


@server.tool()
def calculate_food_adherence_tool(
    plan_record: dict,
    food_log_entries: list | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    workflow_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Compute deterministic food-logging adherence for one nutrition plan.

    Returns one of ADHERED / NOT_ADHERED / NOT_LOGGED / INSUFFICIENT_DATA.
    An absence of food logs is reported as NOT_LOGGED (or
    INSUFFICIENT_DATA), never as NOT_ADHERED: no food log is not evidence
    that the user did not eat.
    """

    trace = _trace(workflow_id, request_id)

    try:
        adherence = compute_food_log_adherence(
            plan_record,
            food_log_entries or [],
            period_start=period_start,
            period_end=period_end,
        )

    except FoodLogAdherenceError as error:
        return {"error": str(error), "metadata": tool_call_metadata(trace)}

    return {"adherence": adherence, "metadata": tool_call_metadata(trace)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Nutrition MCP Server.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    if args.port is not None:
        server.settings.port = args.port

    server.run(transport="streamable-http")
