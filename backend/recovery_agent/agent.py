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

    if not domain["recovery_recommendations"]:
        sleep_signal = (view.get("signals") or {}).get("sleep_hours") or {}
        sleep_hours = sleep_signal.get("value")
        if isinstance(sleep_hours, (int, float)) and not isinstance(sleep_hours, bool):
            # A neutral maintenance activity only: no sleep target, treatment,
            # or inferred recovery problem is added to the user's report.
            domain["mode"] = "general_maintenance"
            domain["recovery_recommendations"].append({
                "id": "maintain_sleep_timing",
                "title": "Keep a steady sleep routine",
                "action": "Keep your usual bedtime and wake time consistent where practical; no change to sleep duration is suggested from this report.",
                "frequency": "Daily, as practical",
                "why": (
                    f"You reported about {sleep_hours:g} hours of sleep. No recovery trigger was identified from the available answers, so this is a general maintenance activity rather than a response to a reported problem."
                ),
                "evidence_used": [f"Self-reported sleep duration: {sleep_hours:g} hours/night"],
                "safety_notes": ["General routine guidance only; it is not treatment or a prescribed sleep target."],
                "personalization_status": "GENERAL_MAINTENANCE_FROM_REPORTED_CONTEXT",
            })

    recommendations = [
        {"id": item["id"], "title": item["title"], "action": item["action"], "frequency": item.get("frequency"), "why": item["why"], "evidence_used": item.get("evidence_used") or domain.get("evidence_used", []), "safety_notes": item.get("safety_notes") or []}
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
