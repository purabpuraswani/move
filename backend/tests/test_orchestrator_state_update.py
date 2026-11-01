import unittest

from orchestration.agent_result import build_agent_result
from orchestration.ids import start_agent_run, start_workflow
from orchestrator.state_update import apply_physio_plan, apply_physio_safety_review
from physio_agent.plan_schema import build_exercise_plan, build_exercise_plan_entry
from user_state.schema import build_user_state, validate_user_state
from workflow.response import movement_specialist


def _completed_physio_result(plan):
    trace = start_agent_run(start_workflow())
    return build_agent_result(
        agent="physio",
        status="completed",
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        findings={"plan": plan},
        recommendations=[{"exercise_id": e["exercise_id"], "reason": e["rationale"]} for e in plan["exercises"]],
    )


def _sample_plan():
    entry = build_exercise_plan_entry(
        exercise_id="wall-sit", sets=None, repetitions=None, duration_seconds=30,
        difficulty="beginner", progression="p", regression="r",
        rationale="Supports stability training at the beginner level.",
    )
    return build_exercise_plan(goal="g", exercises=[entry])


class ApplyPhysioPlanTests(unittest.TestCase):
    def test_a_completed_result_with_a_plan_populates_exercise_history(self):
        state = build_user_state()
        result = _completed_physio_result(_sample_plan())
        updated = apply_physio_plan(state, result)

        validate_user_state(updated)
        self.assertTrue(updated["exercise_history"]["available"])
        plans = updated["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["exercise_ids"], ["wall-sit"])
        self.assertEqual(plans[0]["plan_version"], 1)

    def test_safety_review_persists_even_when_no_plan_was_approved(self):
        state = build_user_state()
        trace = start_agent_run(start_workflow())
        review = {
            "exercise_id": "wall-sit", "target_need": "stability_need",
            "exercise_body_areas": ["legs", "knees"],
            "decision": "EXCLUDE", "status": "DEFERRED_CONTEXT_REQUIRED",
            "clinical_approval": False, "metadata_constraints_status": "AVAILABLE",
            "metadata_constraints": ["Stop if pain occurs."],
            "reported_context_status": "UNKNOWN",
            "confirmed_medical_context_status": "UNKNOWN",
            "evidence_used": [], "assessment_evidence": {"balance": {"status": "completed"}},
            "potential_conflicts": ["Health screen incomplete."],
            "additional_information_required": ["Complete health screen"],
            "exclusion_reason": "Required context is unknown.",
        }
        result = build_agent_result(
            agent="physio", status="completed", workflow_id=trace.workflow_id,
            request_id=trace.request_id, agent_run_id=trace.agent_run_id,
            findings={
                "exercise_safety_evaluations": [review],
                "movement_evidence": {"balance": {"status": "completed"}},
                "reported_health_context_status": "UNKNOWN",
                "confirmed_medical_context_status": "UNKNOWN",
            },
        )
        updated = apply_physio_safety_review(state, result)
        self.assertFalse(state["exercise_history"]["available"])
        self.assertEqual(len(updated["exercise_history"]["data"]["safety_reviews"]), 1)
        self.assertEqual(
            updated["exercise_history"]["data"]["safety_reviews"][0]["evaluations"][0]["exclusion_reason"],
            "Required context is unknown.",
        )

    def test_a_deferred_latest_review_hides_the_older_plan_as_current(self):
        state = apply_physio_plan(build_user_state(), _completed_physio_result(_sample_plan()))
        trace = start_agent_run(start_workflow())
        evaluation = {
            "exercise_id": "wall-sit", "target_need": "stability_need",
            "exercise_body_areas": ["legs", "knees"],
            "decision": "EXCLUDE", "status": "DEFERRED_HEALTHCARE_REVIEW",
            "clinical_approval": False, "metadata_constraints_status": "AVAILABLE",
            "metadata_constraints": ["Stop if pain occurs."],
            "reported_context_status": "COMPLETE",
            "confirmed_medical_context_status": "AVAILABLE",
            "evidence_used": [], "assessment_evidence": {},
            "potential_conflicts": ["Requires professional review."],
            "additional_information_required": ["Healthcare-professional review"],
            "exclusion_reason": "Suitability could not be established.",
        }
        review_result = build_agent_result(
            agent="physio", status="completed", workflow_id=trace.workflow_id,
            request_id=trace.request_id, agent_run_id=trace.agent_run_id,
            findings={
                "plan": {"plan_id": "deferred-plan", "exercises": []},
                "exercise_safety_evaluations": [evaluation],
                "movement_evidence": {},
                "reported_health_context_status": "COMPLETE",
                "confirmed_medical_context_status": "AVAILABLE",
            },
        )
        updated = apply_physio_safety_review(state, review_result)
        movement = movement_specialist(updated)
        self.assertEqual(movement["programme"], [])
        self.assertEqual(movement["safety_review"]["plan_id"], "deferred-plan")

    def test_does_not_mutate_the_input_state(self):
        state = build_user_state()
        result = _completed_physio_result(_sample_plan())
        apply_physio_plan(state, result)
        self.assertFalse(state["exercise_history"]["available"])

    def test_a_second_plan_increments_plan_version_and_keeps_history(self):
        state = build_user_state()
        first = apply_physio_plan(state, _completed_physio_result(_sample_plan()))
        second = apply_physio_plan(first, _completed_physio_result(_sample_plan()))

        plans = second["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]["plan_version"], 1)
        self.assertEqual(plans[1]["plan_version"], 2)

    def test_never_claims_the_user_completed_the_exercises(self):
        state = build_user_state()
        updated = apply_physio_plan(state, _completed_physio_result(_sample_plan()))
        serialised = str(updated["exercise_history"]).lower()
        for claim in ("completed the exercise", "user performed", "finished workout"):
            self.assertNotIn(claim, serialised)

    def test_a_failed_result_is_rejected_not_silently_recorded(self):
        trace = start_agent_run(start_workflow())
        failed_result = build_agent_result(
            agent="physio", status="failed", workflow_id=trace.workflow_id,
            request_id=trace.request_id, agent_run_id=trace.agent_run_id,
            findings={"reason": "no client"},
        )
        state = build_user_state()
        with self.assertRaises(ValueError):
            apply_physio_plan(state, failed_result)

    def test_a_completed_result_with_an_empty_plan_is_rejected(self):
        trace = start_agent_run(start_workflow())
        empty_plan = build_exercise_plan(goal="g", exercises=[])
        result = _completed_physio_result(empty_plan)
        state = build_user_state()
        with self.assertRaises(ValueError):
            apply_physio_plan(state, result)


if __name__ == "__main__":
    unittest.main()
