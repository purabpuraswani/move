"""Deterministic adherence/completion-rate calculation over real data.

There is no scheduling system anywhere in this application (no "planned
for Tuesday", no recurring reminders) — see mcp_servers/behaviour_server.py's
docstring on why get_adherence/record_adherence were never built as MCP
tools in Phase 4. What DOES now exist, after Phase 5 added
exercise_assessment/store.py, is real data this module can compute from
honestly: a created plan names which exercises it calls for
(orchestrator/state_update.py's exercise_history plan record), and each
submitted exercise result (exercise_assessment/store.py) says which
exercise was actually completed and against which plan_id.

"Adherence" here means exactly one thing: of the exercises a specific plan
named, how many has this user submitted at least one completed result
for. It is not a claim about a schedule ("3 sessions/week") this
application does not track, and it is never fabricated when the data to
compute it does not exist — see calculate_completion_rate's None handling.
"""

NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"


class AdherenceCalculationError(ValueError):
    """Raised for a structurally invalid input, never silently coerced."""


def calculate_completion_rate(planned_sessions, completed_sessions) -> dict:
    """The atomic, deterministic calculation. Returns
    {"planned_sessions", "completed_sessions", "completion_rate", "status"}.

    `status` is "completed" (a real, computable rate — including 0.0, a
    real rate meaning "planned but none done yet") or "NOT_ENOUGH_DATA"
    (planned_sessions is None/unknown, or either value is invalid) —
    missing data is never silently turned into a 0% rate, per the Phase 5
    brief's explicit rule.

    Raises AdherenceCalculationError for a negative or non-numeric,
    non-None value — an invalid input is refused, not clamped or guessed.
    """

    for name, value in (("planned_sessions", planned_sessions), ("completed_sessions", completed_sessions)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            raise AdherenceCalculationError(f"{name} must be null or a non-negative number, got {value!r}")

    if planned_sessions is None or completed_sessions is None:
        return {
            "planned_sessions": planned_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": None,
            "status": NOT_ENOUGH_DATA,
        }

    if planned_sessions == 0:
        # Zero planned sessions is not a 0% or 100% rate — there was
        # nothing to adhere to, so a rate is not a meaningful number here.
        return {
            "planned_sessions": 0,
            "completed_sessions": completed_sessions,
            "completion_rate": None,
            "status": NOT_ENOUGH_DATA,
        }

    rate = min(completed_sessions, planned_sessions) / planned_sessions

    return {
        "planned_sessions": planned_sessions,
        "completed_sessions": completed_sessions,
        "completion_rate": rate,
        "status": "completed",
    }


def compute_plan_adherence(plan_record: dict, exercise_results: list) -> dict:
    """Compute adherence for one exercise_history plan record
    (orchestrator/state_update.py's shape: plan_id, exercise_ids, ...)
    against a list of stored exercise results
    (exercise_assessment/store.py's shape: exerciseId, status, plan_id).

    `planned_sessions` is the number of distinct exercises the plan named.
    `completed_sessions` is the number of those exercises with at least
    one result recorded against this plan_id with status "completed" —
    never a result for a different plan or a different exercise entirely.
    Returns calculate_completion_rate's result plus `plan_id` for
    traceability.
    """

    if not isinstance(plan_record, dict) or "plan_id" not in plan_record:
        raise AdherenceCalculationError("plan_record must be an object with a plan_id")

    plan_id = plan_record["plan_id"]
    planned_exercise_ids = set(plan_record.get("exercise_ids") or [])
    planned_sessions = len(planned_exercise_ids)

    completed_exercise_ids = {
        result.get("exerciseId")
        for result in (exercise_results or [])
        if result.get("plan_id") == plan_id
        and result.get("status") == "completed"
        and result.get("exerciseId") in planned_exercise_ids
    }

    rate_result = calculate_completion_rate(planned_sessions, len(completed_exercise_ids))

    return {"plan_id": plan_id, **rate_result}
