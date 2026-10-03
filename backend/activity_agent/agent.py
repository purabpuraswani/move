"""The Exercise & Physical Activity specialist's execution lifecycle.

    Activity Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the domain view (activity_agent/evidence.py) -- activity signals
        only; no medical context, no sleep, no raw movement measurements
          |
    Deterministic domain reasoning (activity_agent/reasoning.py)
          |
    Return an Agent Result (orchestration.agent_result)

Coordination, stated explicitly because it is the one place this agent
reads something another specialist produced: the Orchestrator may pass a
`recovery_constraint` (Recovery & Care's own output for this cycle). It
can only slow progression down. Recovery cannot add an activity
recommendation, change a target upwards, or decide anything else in this
domain, and this agent never reads Recovery's raw sleep evidence.

Why this specialist produces no plan section: an activity target is a
volume, not a programme. Exercise selection stays with physio_agent, and
nothing here writes to the User State.
"""

from activity_agent.evidence import build_activity_view
from activity_agent.reasoning import assess_activity
from orchestration.agent_result import build_agent_result
from orchestration.evidence import STATUS_INSUFFICIENT_EVIDENCE
from orchestration.ids import TraceContext, start_agent_run

AGENT_ID = "exercise_activity"


def run_activity_agent(
    user_state: dict,
    *,
    parent_trace: TraceContext,
    exercise_results: list = None,
    recovery_constraint: dict = None,
) -> dict:
    """Run one Exercise & Physical Activity execution.

    Returns a validated Agent Result whose `findings` carry this domain's
    own shape (status, activity_findings, activity_recommendations,
    progression, constraints, missing_information, confidence) and whose
    `recommendations` are the volume actions, so the Orchestrator and the
    Safety Gate can read them without knowing this agent's internals.

    An absence of activity answers is reported as INSUFFICIENT_EVIDENCE
    with the specific questions that are missing -- never as generic
    advice to "move more", and never as a finding that the user is
    inactive.
    """

    trace = start_agent_run(parent_trace)

    view = build_activity_view(
        user_state,
        exercise_results=exercise_results,
        recovery_constraint=recovery_constraint,
    )

    domain = assess_activity(view)

    recommendations = [
        {
            "id": item["id"],
            "title": item["title"],
            "action": item["action"],
            "why": item["why"],
        }
        for item in domain["activity_recommendations"]
    ]

    priority = None

    if domain["status"] != STATUS_INSUFFICIENT_EVIDENCE and domain["activity_recommendations"]:
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
        # Missing answers are a reason to ask the question again, not a
        # reason to re-run the camera assessment.
        requires_reassessment=False,
    )
