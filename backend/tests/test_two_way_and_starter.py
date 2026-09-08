"""Tests for starter_plan.py and two_way_contract.py.

Verifies:
1. Healthy/low-need user receives an active 3-exercise maintenance plan with Safety Gate ALLOW.
2. Two-way clarification loops for Physio, Nutrition, and Behaviour specialists.
"""

import unittest

from orchestration.starter_plan import build_maintenance_starter_plan, STARTER_EXERCISE_IDS
from orchestration.two_way_contract import (
    SpecialistStatus,
    build_specialist_request,
    build_specialist_response,
    handle_physio_feedback_clarification,
    handle_nutrition_log_clarification,
    handle_behaviour_adherence_clarification,
)
from user_state.schema import build_user_state


class StarterPlanTests(unittest.TestCase):
    def test_healthy_user_receives_maintenance_starter_plan(self):
        state = build_user_state()
        state["physical_assessment"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "1.0.0",
                "completed_at": "2026-01-01T00:00:00Z",
                "tests": {
                    "shoulder": {"status": "completed"},
                    "ftsst": {"status": "completed"},
                    "balance": {"status": "completed"},
                },
            },
        }

        updated_state, safety_result = build_maintenance_starter_plan(
            state, workflow_id="wf_starter", request_id="req_starter"
        )

        self.assertEqual(safety_result["status"], "ALLOW")
        self.assertTrue(updated_state["exercise_history"]["available"])

        plans = updated_state["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["exercise_ids"], list(STARTER_EXERCISE_IDS))
        self.assertIn("Personalized starter and maintenance plan", plans[0]["goal"])

        # Behaviour and Nutrition plans also initialized
        self.assertTrue(updated_state["behaviour"]["available"])
        self.assertTrue(updated_state["nutrition_plan"]["available"])

    def test_starter_plan_serialisation_and_clean_public_shape(self):
        from workflow.response import serialise_workflow_state

        state = build_user_state()
        state["physical_assessment"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "1.0.0",
                "completed_at": "2026-01-01T00:00:00Z",
                "tests": {
                    "shoulder": {"status": "completed"},
                    "ftsst": {"status": "completed"},
                    "balance": {"status": "completed"},
                },
            },
        }

        updated_state, safety_result = build_maintenance_starter_plan(
            state, workflow_id="wf_starter", request_id="req_starter"
        )
        serialised = serialise_workflow_state(updated_state, safety_status=safety_result["status"])

        self.assertEqual(serialised["plan_status"], "PLAN_AVAILABLE")
        self.assertEqual(serialised["safety_status"], "Reviewed and approved.")
        self.assertTrue(serialised["exercise_plan"]["available"])
        self.assertEqual(serialised["exercise_plan"]["exercise_count"], 3)
        self.assertEqual(
            [item["id"] for item in serialised["exercise_plan"]["exercise_items"]],
            list(STARTER_EXERCISE_IDS),
        )
        self.assertTrue(serialised["nutrition_plan"]["available"])
        self.assertTrue(serialised["behaviour_plan"]["available"])

        # Check for forbidden internal keys
        serialized_str = str(serialised)
        for forbidden in ("workflow_id", "request_id", "agent_run_id", "mcp_session_id"):
            self.assertNotIn(forbidden, serialized_str)


class TwoWayContractTests(unittest.TestCase):
    def test_physio_two_way_clarification_cycle(self):
        user_feedback = {"rating": "pain", "notes": "My knee hurts when I do sit-to-stand."}
        user_state = build_user_state()

        # Step 1: specialist requests clarification
        response1 = handle_physio_feedback_clarification(user_feedback, user_state)
        self.assertEqual(response1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(response1["follow_up_required"])
        self.assertIn("during the movement", response1["questions"][0])

        # Step 2: user clarifies discomfort timing -> specialist adapts plan
        response2 = handle_physio_feedback_clarification(
            user_feedback, user_state, clarification_answer="During the movement"
        )
        self.assertEqual(response2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(response2["follow_up_required"])
        self.assertTrue(any("Regress" in rec["guidance"] for rec in response2["recommendations"]))

    def test_nutrition_two_way_clarification_cycle(self):
        food_logs = [{"meal_type": "breakfast", "food_item": "poha"}]

        # Step 1: dinner is unlogged -> Nutrition requests clarification
        resp1 = handle_nutrition_log_clarification(food_logs)
        self.assertEqual(resp1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(resp1["follow_up_required"])
        self.assertIn("dinner", resp1["questions"][0].lower())

        # Step 2: user clarifies dinner
        resp2 = handle_nutrition_log_clarification(
            food_logs, clarification_answer="I had dal, roti, and sabzi."
        )
        self.assertEqual(resp2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(resp2["follow_up_required"])

    def test_behaviour_two_way_clarification_cycle(self):
        # 1 out of 4 sessions completed
        resp1 = handle_behaviour_adherence_clarification(completed_sessions=1, planned_sessions=4)
        self.assertEqual(resp1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(resp1["follow_up_required"])

        # User provides barrier: busy work schedule
        resp2 = handle_behaviour_adherence_clarification(
            completed_sessions=1, planned_sessions=4, clarification_answer="Work was too busy this week"
        )
        self.assertEqual(resp2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(resp2["follow_up_required"])
        self.assertTrue(any("5-minute" in rec.get("guidance", "") for rec in resp2["recommendations"]))


if __name__ == "__main__":
    unittest.main()
