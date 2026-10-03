"""The Recovery & Care specialist's execution lifecycle.

    Recovery Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the domain view (recovery_agent/evidence.py) -- sleep and
        workload volume only
          |
    Deterministic domain reasoning (recovery_agent/reasoning.py)
          |
    Return an Agent Result whose findings carry a `constraint` the
        Orchestrator passes to Exercise & Physical Activity

This agent runs before Activity in the Orchestrator for exactly one
reason: its constraint is an input to activity progression. It writes no
plan section, selects no exercise, and makes no escalation decision.
"""

from orchestration.agent_result import build_agent_result
from orchestration.evidence import STATUS_INSUFFICIENT_EVIDENCE
from orchestration.ids import TraceContext, start_agent_run
from recovery_agent.evidence import build_recovery_view
from recovery_agent.reasoning import assess_recovery

AGENT_ID = "recovery"


def run_recovery_agent(
    user_state: dict,
    *,
    parent_trace: TraceContext,
    exercise_results: list = None,
) -> dict:
    """Run one Recovery & Care execution. Returns a validated Agent Result."""

    trace = start_agent_run(parent_trace)

    view = build_recovery_view(user_state, exercise_results=exercise_results)
    domain = assess_recovery(view)

    recommendations = [
        {"id": item["id"], "title": item["title"], "action": item["action"], "why": item["why"]}
        for item in domain["recovery_recommendations"]
    ]

    priority = None

    if domain["status"] != STATUS_INSUFFICIENT_EVIDENCE and domain["constraint"]["limit_progression"]:
        priority = "medium"

    return build_agent_result(
        agent=AGENT_ID,
        status="completed",
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        priority=priority,
        findings=domain,
        recommendations=recommendations,
        requires_reassessment=False,
    )
