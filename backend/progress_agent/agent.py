"""The Progress Agent's actual execution lifecycle.

    Progress Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the structured input (input_contract.py, from already-fetched
        baseline/previous/current assessment documents and plan/adherence
        data — never a User State lookup of its own)
          |
    Call Progress MCP tools (via the injected ProgressToolClient — never
        progress_agent.comparison/adherence/reassessment directly)
          |
    Apply the documented, deterministic adaptation-recommendation table
        (performance direction x adherence level -> one of
        ADAPTATION_RECOMMENDATIONS)
          |
    Return a Phase 0 Agent Result (orchestration.agent_result)

Mirrors physio_agent/agent.py's discipline exactly. This agent produces no
plan and selects no exercise/goal itself — its `recommendations` field
names an adaptation category, never a specific exercise_id or topic_id;
the Orchestrator is the only thing that acts on it (see
orchestrator/orchestrator.py).
"""

from orchestration.agent_result import build_agent_result
from orchestration.ids import TraceContext, start_agent_run
from progress_agent.comparison import (
    DECLINED,
    IMPROVED,
    NOT_ENOUGH_DATA,
    STABLE,
    overall_direction,
)
from progress_agent.input_contract import build_progress_agent_input
from behaviour_agent.adherence import summarise_for_progress
from progress_agent.nutrition_progress import (
    compare_nutrition_adherence,
    recommend_nutrition_adaptation,
)
from progress_agent.schema import validate_progress_findings
from progress_agent.tool_client import ProgressToolClient

AGENT_ID = "progress"

# System-decision adherence-level thresholds (see progress_agent/adherence.py's
# own docstring on why there is no clinical/scheduling authority behind
# these numbers). Applied only to a real, computed completion_rate — never
# to a missing one, which stays its own "UNKNOWN" level below.
ADHERENCE_HIGH_THRESHOLD = 0.7
ADHERENCE_LOW_THRESHOLD = 0.4


def _adherence_level(adherence_result: dict) -> str:
    rate = (adherence_result or {}).get("completion_rate")

    if rate is None:
        return "UNKNOWN"

    if rate >= ADHERENCE_HIGH_THRESHOLD:
        return "HIGH"

    if rate < ADHERENCE_LOW_THRESHOLD:
        return "LOW"

    return "MODERATE"


def _recommend_adaptation(direction: str, adherence_level: str, reassessment_required: bool) -> tuple:
    """The documented decision table (Phase 5 brief section 12). Returns
    (recommendation, reason). Deterministic: identical (direction,
    adherence_level, reassessment_required) always produces the identical
    recommendation.
    """

    if direction == NOT_ENOUGH_DATA:
        return "REASSESS", (
            "Not enough physical assessment data exists to compare baseline "
            "against current performance."
        )

    if reassessment_required:
        return "REASSESS", (
            "The most recent physical assessment is missing or stale enough "
            "that a comparison against it should not be trusted yet."
        )

    if direction == IMPROVED:
        return "PROGRESS", "Performance improved against the baseline comparison."

    if direction == STABLE:
        if adherence_level == "LOW":
            return "MODIFY", (
                "Performance is unchanged and adherence is low — the current "
                "plan's difficulty is not confirmed to be the limiting factor, "
                "so the approach (not the plan's difficulty) should be "
                "reconsidered before assuming the intervention itself failed."
            )

        return "MAINTAIN", "Performance is stable; hold the current plan steady."

    if direction == DECLINED:
        if adherence_level == "HIGH":
            return "REASSESS", (
                "Performance declined despite high adherence — this is "
                "unexpected enough to flag for closer review rather than "
                "reduce difficulty automatically."
            )

        return "REGRESS", (
            "Performance declined and adherence was not high — reduce "
            "difficulty/volume rather than continue the current plan."
        )

    raise ValueError(f"unhandled progress direction {direction!r}")  # pragma: no cover


def _mcp_session_id_of(*tool_results) -> str:
    """The real MCP session id these tool results ran under, or None.

    The value originates in the Streamable HTTP transport's own handshake
    and is carried into each tool result's metadata by the MCP client
    (progress_agent/mcp_client.py's _attach_session_id). Reading it back
    here is how the Agent Result reports the session its tool calls
    actually used.

    Never synthesised: workflow_id, request_id, agent_run_id and
    tool_call_id are four different identifiers with four different
    meanings, and none substitutes for this one. If no tool result carried
    a session id, this returns None and the Agent Result says so.
    """

    for tool_result in tool_results:
        if not isinstance(tool_result, dict):
            continue

        metadata = tool_result.get("metadata")

        if isinstance(metadata, dict) and metadata.get("mcp_session_id"):
            return metadata["mcp_session_id"]

    return None

def run_progress_agent(
    *,
    baseline_assessment: dict = None,
    previous_assessment: dict = None,
    current_assessment: dict = None,
    exercise_history: dict = None,
    exercise_results: list = None,
    current_plan: dict = None,
    current_needs: dict = None,
    nutrition_plan: dict = None,
    nutrition_food_log_previous_period: list = None,
    nutrition_food_log_current_period: list = None,
    nutrition_period_previous: dict = None,
    nutrition_period_current: dict = None,
    # Recorded behaviour actions. Read-only evidence: the Progress Agent
    # reports what they show and never prescribes from them -- routing a
    # behaviour adaptation stays the Orchestrator's decision.
    behaviour_actions: list = None,
    tool_client: ProgressToolClient,
    parent_trace: TraceContext,
) -> dict:
    """Run one Progress Agent execution. Returns a validated Agent Result.

    `current_plan` (an exercise_history plan record, if one exists) is
    what adherence is computed against — omit it (None) when no plan has
    been created yet, and adherence is correctly reported as
    NOT_ENOUGH_DATA rather than a fabricated rate.

    `nutrition_plan` (a nutrition_plan history record, if one exists),
    together with `nutrition_food_log_previous_period` /
    `nutrition_food_log_current_period` (lists of stored food_log entries)
    and `nutrition_period_previous` / `nutrition_period_current` (each
    `{"start": ..., "end": ...}`), are all optional and kept explicitly
    separate from the physical-comparison inputs above. When
    `nutrition_plan` is omitted, `findings["nutrition_progress"]` is
    `None` — this agent never fabricates a nutrition comparison when the
    caller has not supplied nutrition context at all (Phase 5's exercise
    adherence and Phase 6's nutrition adherence are independent axes; see
    progress_agent/nutrition_progress.py's module docstring on why
    "adherence improved" is never reported as "health improved").
    """

    trace = start_agent_run(parent_trace)

    payload = build_progress_agent_input(
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        baseline_assessment=baseline_assessment,
        previous_assessment=previous_assessment,
        current_assessment=current_assessment,
        exercise_history=exercise_history,
        exercise_results=exercise_results,
        adherence=None,
        previous_plan=None,
        current_plan=current_plan,
        current_needs=current_needs,
        nutrition_plan=nutrition_plan,
        nutrition_food_log_previous_period=nutrition_food_log_previous_period,
        nutrition_food_log_current_period=nutrition_food_log_current_period,
        nutrition_period_previous=nutrition_period_previous,
        nutrition_period_current=nutrition_period_current,
    )

    try:
        comparison_result = tool_client.compare_assessments(
            baseline_assessment=payload["baseline_assessment"],
            previous_assessment=payload["previous_assessment"],
            current_assessment=payload["current_assessment"],
        )

        if payload["current_plan"] is not None:
            adherence_result = tool_client.calculate_adherence(
                plan_record=payload["current_plan"],
                exercise_results=payload["exercise_results"],
            )
        else:
            adherence_result = {
                "adherence": {
                    "plan_id": None,
                    "planned_sessions": None,
                    "completed_sessions": None,
                    "completion_rate": None,
                    "status": "NOT_ENOUGH_DATA",
                }
            }

        reassessment_result = tool_client.check_reassessment_required(
            current_assessment_completed_at=(
                (payload["current_assessment"] or {}).get("completed_at")
                if payload["current_assessment"]
                else None
            )
        )

        nutrition_previous_adherence_result = None
        nutrition_current_adherence_result = None

        if payload["nutrition_plan"] is not None:
            nutrition_period_previous_arg = payload["nutrition_period_previous"] or {}
            nutrition_period_current_arg = payload["nutrition_period_current"] or {}

            nutrition_previous_adherence_result = tool_client.calculate_nutrition_adherence(
                nutrition_plan=payload["nutrition_plan"],
                food_log_entries=payload["nutrition_food_log_previous_period"],
                period_start=nutrition_period_previous_arg.get("start"),
                period_end=nutrition_period_previous_arg.get("end"),
            )
            nutrition_current_adherence_result = tool_client.calculate_nutrition_adherence(
                nutrition_plan=payload["nutrition_plan"],
                food_log_entries=payload["nutrition_food_log_current_period"],
                period_start=nutrition_period_current_arg.get("start"),
                period_end=nutrition_period_current_arg.get("end"),
            )

    except Exception as error:  # noqa: BLE001
        return build_agent_result(
            agent=AGENT_ID,
            status="failed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={"reason": f"Progress MCP call failed: {error}"},
            safety_flags=["mcp_unavailable_or_tool_error"],
            requires_reassessment=True,
        )

    if "error" in comparison_result:
        return build_agent_result(
            agent=AGENT_ID,
            status="failed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={"reason": f"Progress MCP comparison failed: {comparison_result['error']}"},
            safety_flags=["mcp_unavailable_or_tool_error"],
            requires_reassessment=True,
            mcp_session_id=_mcp_session_id_of(comparison_result),
        )

    comparison = comparison_result["comparison"]
    adherence = adherence_result.get("adherence") or adherence_result.get("error")
    direction = overall_direction(comparison, key="baseline_vs_current")
    adherence_level = _adherence_level(adherence if isinstance(adherence, dict) else None)
    reassessment = {
        "required": reassessment_result["required"],
        "reason": reassessment_result["reason"],
    }

    recommendation, recommendation_reason = _recommend_adaptation(
        direction, adherence_level, reassessment["required"]
    )

    nutrition_progress = None

    if payload["nutrition_plan"] is not None:

        def _nutrition_result_or_none(raw_result):
            if raw_result is None:
                return None, None

            if "error" in raw_result:
                return None, raw_result["error"]

            return raw_result.get("adherence"), None

        previous_nutrition_result, previous_nutrition_error = _nutrition_result_or_none(
            nutrition_previous_adherence_result
        )
        current_nutrition_result, current_nutrition_error = _nutrition_result_or_none(
            nutrition_current_adherence_result
        )

        nutrition_progress = compare_nutrition_adherence(
            previous_nutrition_result, current_nutrition_result
        )

        if previous_nutrition_error or current_nutrition_error:
            nutrition_progress["evidence"] = list(nutrition_progress["evidence"]) + [
                note
                for note in (
                    f"previous period adherence could not be computed: {previous_nutrition_error}"
                    if previous_nutrition_error
                    else None,
                    f"current period adherence could not be computed: {current_nutrition_error}"
                    if current_nutrition_error
                    else None,
                )
                if note is not None
            ]

        nutrition_recommendation, nutrition_reason = recommend_nutrition_adaptation(nutrition_progress)
        nutrition_progress["adaptation_recommendation"] = nutrition_recommendation
        nutrition_progress["adaptation_reason"] = nutrition_reason

    # Behaviour evidence, computed by the one module that computes it
    # (behaviour_agent/adherence.py) rather than by a second mechanism
    # here. It reports NOT_LOGGED or INSUFFICIENT_DATA instead of a rate
    # when the records cannot support one.
    behaviour_progress = summarise_for_progress(behaviour_actions)

    findings = {
        "physical_comparison": comparison,
        "behaviour_progress": behaviour_progress,
        "overall_direction": direction,
        "adherence": adherence if isinstance(adherence, dict) else {"error": adherence},
        "adherence_level": adherence_level,
        "adaptation_recommendation": recommendation,
        "reassessment": reassessment,
        "nutrition_progress": nutrition_progress,
    }

    validate_progress_findings(findings)

    priority = "high" if recommendation in ("REASSESS", "REGRESS") else (
        "medium" if recommendation in ("MODIFY", "PROGRESS") else "low"
    )

    return build_agent_result(
        agent=AGENT_ID,
        status="completed",
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        priority=priority,
        findings=findings,
        recommendations=[{"type": "adaptation", "recommendation": recommendation, "reason": recommendation_reason}],
        requires_reassessment=reassessment["required"],
        safety_flags=[],
        # Every one of these came back over the same real transport this
        # cycle; the first that reports a session id is the session this
        # agent's work ran on.
        mcp_session_id=_mcp_session_id_of(
            comparison_result,
            adherence_result,
            reassessment_result,
            nutrition_previous_adherence_result,
            nutrition_current_adherence_result,
        ),
    )
