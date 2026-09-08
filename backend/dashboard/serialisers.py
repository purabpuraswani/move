"""Pure, testable logic behind routes/dashboard.py.

Nothing in this module imports pymongo, bson, or fastapi — every function
here takes already-fetched plain dicts and returns a plain dict, so it can
be unit-tested without a database connection or a running app, exactly
like workflow/assembly.py and workflow/response.py. routes/dashboard.py is
a thin wrapper: it fetches the real documents and calls straight into
these functions.
"""

import importlib.util


# ---------------------------------------------------------------------------
# Pure, testable helpers. None of these import pymongo/bson types directly
# in their signatures — they take already-fetched plain dicts/documents —
# so they can be unit-tested without a database connection.
# ---------------------------------------------------------------------------

# The real field name routes/auth.py stores a user's hashed password
# under. Never returned from any dashboard endpoint.
FORBIDDEN_ACCOUNT_FIELDS = ("password_hash",)


def safe_account_info(user_doc: dict) -> dict:
    """A small, safe subset of a user document for internal display.
    Explicitly excludes `password_hash` (and, defensively, any other
    forbidden field) rather than allow-listing by accident once and
    forgetting to update it later.
    """

    if user_doc is None:
        return None

    info = {
        "user_id": str(user_doc.get("_id")) if user_doc.get("_id") is not None else None,
        "email": user_doc.get("email"),
        "created_at": user_doc.get("created_at"),
        "is_staff": bool(user_doc.get("is_staff", False)),
    }

    for field in FORBIDDEN_ACCOUNT_FIELDS:
        assert field not in info, f"{field} must never appear in safe_account_info()'s output"

    return info


# One agent id -> the User State plan-section key it persists under, and
# the field name inside each plan record that names what was selected.
# Mirrors orchestrator/orchestrator.py's own _AGENT_PLAN_SHAPE table.
_PLAN_SECTIONS = {
    "physio": ("exercise_history", "exercise_ids"),
    "nutrition": ("nutrition_plan", "topic_ids"),
    "behaviour": ("behaviour", "topic_ids"),
}


def flatten_plan_history(user_state: dict) -> dict:
    """Every historical plan version across all three plan-producing
    agents, unredacted — real `plan_version`/`created_at`/
    `adaptation_reason`/`triggered_by` values straight from the persisted
    arrays. An agent with no section yet (or an empty history) contributes
    an empty list, never a fabricated entry.
    """

    history = {}

    for agent_id, (section_key, id_field) in _PLAN_SECTIONS.items():
        section = (user_state or {}).get(section_key) or {}
        plans = (
            (section.get("data") or {}).get("plans", [])
            if section.get("available")
            else []
        )

        history[agent_id] = [
            {
                "plan_id": plan.get("plan_id"),
                "plan_version": plan.get("plan_version"),
                "created_at": plan.get("created_at"),
                "goal": plan.get("goal"),
                "adaptation_reason": plan.get("adaptation_reason"),
                "triggered_by": plan.get("triggered_by"),
                "source": plan.get("source"),
                "agent_run_id": plan.get("agent_run_id"),
                "selected_ids": plan.get(id_field, []),
            }
            for plan in plans
        ]

    return history


# The real @server.tool()-decorated function names in each specialist's
# MCP server file (backend/mcp_servers/*.py) — read directly from those
# files, never invented. Physio's server module is named exercise_server.py,
# not physio_server.py.
_MCP_SERVER_TOOLS = {
    "physio": (
        "mcp_servers.exercise_server",
        (
            "search_exercises_tool",
            "get_exercise_details_tool",
            "get_demo_animation_tool",
            "check_exercise_constraints_tool",
            "record_exercise_result_tool",
        ),
    ),
    "behaviour": (
        "mcp_servers.behaviour_server",
        ("search_behaviour_guidance_tool", "get_behaviour_topic_details_tool"),
    ),
    "nutrition": (
        "mcp_servers.nutrition_server",
        (
            "search_nutrition_guidance_tool",
            "get_nutrition_topic_details_tool",
            "search_food_tool",
            "get_food_details_tool",
            "record_food_log_tool",
            "calculate_food_adherence_tool",
        ),
    ),
    "progress": (
        "mcp_servers.progress_server",
        (
            "compare_assessments_tool",
            "calculate_adherence_tool",
            "check_reassessment_required_tool",
            "calculate_nutrition_adherence_tool",
        ),
    ),
    "safety": (
        "mcp_servers.safety_server",
        (
            "check_safety_tool",
            "check_contraindications_tool",
        ),
    ),
}


def mcp_status_report(*, mcp_installed: bool = None) -> dict:
    """Honest, real MCP integration status per specialist.

    `mcp_installed` is normally left `None` so this checks the real
    runtime (`importlib.util.find_spec("mcp") is not None`); a caller may
    override it only for a direct unit test of the two branches. This
    function never claims a server is actually running/connected — only
    whether the `mcp` package that any real connection depends on is
    importable in this runtime, plus the real tool names each server
    module declares.
    """

    if mcp_installed is None:
        mcp_installed = importlib.util.find_spec("mcp") is not None

    status_text = (
        "The 'mcp' package is installed in this runtime; a real "
        "Streamable HTTP connection to a running server has not been "
        "separately verified by this endpoint."
        if mcp_installed
        else "NOT INSTALLED IN THIS ENVIRONMENT — no real MCP connection "
        "is possible until the 'mcp' package is installed."
    )

    return {
        "mcp_package_installed": mcp_installed,
        "status_message": status_text,
        "specialists": {
            agent_id: {"server_module": module_name, "real_tools": list(tool_names)}
            for agent_id, (module_name, tool_names) in _MCP_SERVER_TOOLS.items()
        },
    }


