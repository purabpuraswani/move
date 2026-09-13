"""Final Architectural Verification Test Suite for MoveWell-AI.

Validates the core architectural points required for final completion:
1. Personalized Starter vs Specialist Plan Selection (A, B, C, D)
2. Real MCP vs InProcess Fallback honesty
3. Functional Two-Way Communication loops (Physio, Nutrition, Behaviour)
4. Multi-Agent Collaboration aggregated into ONE coherent plan
5. ONE Safety Gate enforcement (ALLOW, MODIFY, PAUSE, REFER, NOT_ASSESSED)
6. User State persistence & plan versioning (Plan V1 -> Plan V2)
"""

import unittest

from orchestration.starter_plan import build_maintenance_starter_plan, STARTER_EXERCISE_IDS
from orchestration.two_way_contract import (
    SpecialistStatus,
    handle_physio_feedback_clarification,
    handle_nutrition_log_clarification,
    handle_behaviour_adherence_clarification,
)
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from behaviour_agent.tool_client import InProcessBehaviourToolClient
from nutrition_agent.tool_client import InProcessNutritionToolClient
from safety.gate import evaluate_safety
from user_state.schema import build_user_state, validate_user_state
from workflow.response import serialise_workflow_state


class PersonalizedPlanAndNeedPriorityTests(unittest.TestCase):
    """Point 1: Personalized Starter Plan vs Specialist Need Prioritization."""

    def test_A_healthy_user_receives_safe_starter_maintenance_plan(self):
        """A: Healthy users receive a safe starter/maintenance plan."""
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
            state, workflow_id="wf_test_healthy", request_id="req_test_healthy"
        )

        self.assertEqual(safety_result["status"], "ALLOW")
        self.assertTrue(updated_state["exercise_history"]["available"])
        plans = updated_state["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["exercise_ids"], list(STARTER_EXERCISE_IDS))
        self.assertEqual(plans[0]["plan_version"], 1)

    def test_B_user_with_meaningful_movement_needs_receives_physio_driven_exercises(self):
        """B: Users with meaningful movement needs receive appropriate Physio-driven exercises,
        not the generic maintenance starter plan."""
        state = build_user_state()
        # High mobility need with specific shoulder deficit
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "mobility_need": {
                    "level": "HIGH",
                    "evidence": ["Shoulder bilateral elevation difference > 20 degrees"],
                },
                "functional_movement_need": {"level": "LOW", "evidence": []},
                "stability_need": {"level": "LOW", "evidence": []},
                "exercise_readiness": {"level": "LOW", "evidence": []},
                "safety_status": {"level": "LOW", "evidence": []},
            },
        }

        tool_client = InProcessExerciseToolClient(workflow_id="wf_needs", request_id="req_needs")
        result = run_workflow(
            state,
            tool_client=tool_client,
            workflow_id="wf_needs",
            request_id="req_needs",
        )

        self.assertIn("physio", result["selected_agents"])
        updated_state = result["updated_user_state"]
        self.assertTrue(updated_state["exercise_history"]["available"])
        plans = updated_state["exercise_history"]["data"]["plans"]
        self.assertGreaterEqual(len(plans), 1)
        # Specialist-generated exercise plan targeting mobility deficit
        # Specialist-generated exercise plan targeting mobility deficit with genuine interventions
        self.assertEqual(plans[0]["source"], "physio_agent")
        self.assertIn("standing-shoulder-rolls", plans[0]["exercise_ids"])
        self.assertIn("standing-overhead-reach", plans[0]["exercise_ids"])
        self.assertNotIn("standing-shoulder-raise", plans[0]["exercise_ids"])
        self.assertNotEqual(plans[0]["exercise_ids"], list(STARTER_EXERCISE_IDS))

    def test_C_safety_constraints_block_or_modify_exercises(self):
        """C: Safety constraints can remove/modify an otherwise selected exercise."""
        # Case 1: HIGH safety status triggers REFER and blocks all exercises
        safety_high_result = evaluate_safety(
            need_profile={"safety_status": {"level": "HIGH", "evidence": ["Acute red flag detected"]}},
            confirmed_medical_context=None,
            candidate_recommendations=[
                {"id": "chair-sit-to-stand", "agent": "physio", "type": "exercise", "difficulty": "beginner"}
            ],
        )
        self.assertEqual(safety_high_result["status"], "REFER")
        self.assertTrue(safety_high_result["requires_referral"])
        self.assertIn("chair-sit-to-stand", safety_high_result["blocked_recommendation_ids"])

        # Starter plan respects the REFER status and refuses to prescribe unsafe exercises
        state = build_user_state()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "safety_status": {"level": "HIGH", "evidence": ["Severe acute chest pain on exertion"]},
            },
        }
        updated_state, starter_safety = build_maintenance_starter_plan(
            state, workflow_id="wf_safety", request_id="req_safety"
        )
        self.assertEqual(starter_safety["status"], "REFER")
        # No unsafe exercises added to exercise_history
        self.assertFalse(updated_state["exercise_history"]["available"])

        # Case 2: Confirmed medical context pauses advanced exercises
        med_safety = evaluate_safety(
            need_profile=None,
            confirmed_medical_context={"reports": [{"id": "rep1", "title": "Cardiac evaluation"}]},
            candidate_recommendations=[
                {"id": "advanced-drill", "agent": "physio", "type": "exercise", "difficulty": "advanced"}
            ],
        )
        self.assertEqual(med_safety["status"], "PAUSE")
        self.assertIn("advanced-drill", med_safety["blocked_recommendation_ids"])

    def test_D_not_assessed_remains_unknown(self):
        """D: NOT_ASSESSED capabilities remain UNKNOWN, never converted to LOW or claimed as optimal."""
        from workflow.assembly import assemble_user_state_from_documents

        state = assemble_user_state_from_documents()
        needs = state["current_needs"]["data"]

        self.assertEqual(needs["mobility_need"]["level"], "NOT_ASSESSED")
        self.assertEqual(needs["functional_movement_need"]["level"], "NOT_ASSESSED")
        self.assertEqual(needs["stability_need"]["level"], "NOT_ASSESSED")
        self.assertNotEqual(needs["mobility_need"]["level"], "LOW")
        self.assertNotEqual(needs["mobility_need"]["level"], "optimal")


class McpTransportAndFallbackHonestyTests(unittest.TestCase):
    """Point 2: Real MCP vs InProcess Fallback honesty."""

    def test_inprocess_fallback_honestly_reports_none_mcp_session(self):
        """InProcess tool client must not claim an MCP session ID when running in fallback mode."""
        client = InProcessExerciseToolClient(workflow_id="wf_inproc", request_id="req_inproc")
        res = client.get_exercise_details("chair-sit-to-stand")

        metadata = res.get("metadata", {})
        self.assertIsNone(metadata.get("mcp_session_id"))
        self.assertIsNotNone(metadata.get("agent_run_id"))
        self.assertEqual(metadata.get("workflow_id"), "wf_inproc")


class TwoWaySpecialistCommunicationTests(unittest.TestCase):
    """Point 3: Two-Way Communication functional verification."""

    def test_physio_two_way_clarification_cycle(self):
        user_feedback = {"rating": "pain", "notes": "Knee feels sore when doing sit-to-stand."}
        user_state = build_user_state()

        # Step 1: Orchestrator -> Physio -> NEEDS_CLARIFICATION
        response1 = handle_physio_feedback_clarification(user_feedback, user_state)
        self.assertEqual(response1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(response1["follow_up_required"])
        self.assertTrue(len(response1["questions"]) > 0)
        self.assertIn("during the movement", response1["questions"][0].lower())

        # Step 2: User responds "During the movement" -> Orchestrator -> Physio -> COMPLETE
        response2 = handle_physio_feedback_clarification(
            user_feedback, user_state, clarification_answer="During the movement"
        )
        self.assertEqual(response2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(response2["follow_up_required"])
        self.assertTrue(any("Regress" in rec["guidance"] for rec in response2["recommendations"]))

    def test_nutrition_two_way_clarification_cycle(self):
        # Missing dinner in food log
        food_logs = [{"meal_type": "breakfast", "food_item": "idli"}]

        # Step 1: Nutrition requests clarification on unlogged meal
        resp1 = handle_nutrition_log_clarification(food_logs)
        self.assertEqual(resp1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(resp1["follow_up_required"])
        self.assertIn("dinner", resp1["questions"][0].lower())

        # Step 2: User supplies meal information -> COMPLETE
        resp2 = handle_nutrition_log_clarification(
            food_logs, clarification_answer="Had curd rice and steamed vegetables"
        )
        self.assertEqual(resp2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(resp2["follow_up_required"])

    def test_behaviour_two_way_clarification_cycle(self):
        # Adherence < 50%
        resp1 = handle_behaviour_adherence_clarification(completed_sessions=1, planned_sessions=4)
        self.assertEqual(resp1["status"], SpecialistStatus.NEEDS_CLARIFICATION.value)
        self.assertTrue(resp1["follow_up_required"])

        # User reports scheduling barrier
        resp2 = handle_behaviour_adherence_clarification(
            completed_sessions=1, planned_sessions=4, clarification_answer="Long work meetings all week"
        )
        self.assertEqual(resp2["status"], SpecialistStatus.COMPLETE.value)
        self.assertFalse(resp2["follow_up_required"])
        # Adapts recommendation to shorter routines
        self.assertTrue(any("5-minute" in rec.get("guidance", "") for rec in resp2["recommendations"]))


class MultiAgentCollaborationAndOnePlanTests(unittest.TestCase):
    """Point 4 & 5: Multi-agent aggregation into ONE coherent plan and ONE Safety Gate."""

    def test_all_three_specialists_aggregate_into_one_coherent_plan(self):
        state = build_user_state()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "mobility_need": {"level": "HIGH", "evidence": ["mobility deficit"]},
                "functional_movement_need": {"level": "LOW", "evidence": []},
                "stability_need": {"level": "LOW", "evidence": []},
                "exercise_readiness": {"level": "LOW", "evidence": []},
                "safety_status": {"level": "LOW", "evidence": []},
            },
        }
        # Trigger Behaviour and Nutrition
        state["lifestyle"] = {
            "available": True,
            "reason": None,
            "data": {"sedentary_hours": 9, "sleep_hours": 5},
        }

        tool_client = InProcessExerciseToolClient(workflow_id="wf_multi", request_id="req_multi")
        behaviour_client = InProcessBehaviourToolClient(workflow_id="wf_multi", request_id="req_multi")
        nutrition_client = InProcessNutritionToolClient(workflow_id="wf_multi", request_id="req_multi")

        result = run_workflow(
            state,
            tool_client=tool_client,
            behaviour_tool_client=behaviour_client,
            nutrition_tool_client=nutrition_client,
            workflow_id="wf_multi",
            request_id="req_multi",
        )

        updated_state = result["updated_user_state"]
        validate_user_state(updated_state)

        # ONE coherent user-facing plan shape produced
        summary = serialise_workflow_state(
            updated_state, safety_status=result["safety_result"]["status"]
        )

        self.assertEqual(summary["plan_status"], "PLAN_AVAILABLE")
        self.assertIn("Reviewed and approved", summary["safety_status"])
        self.assertTrue(summary["exercise_plan"]["available"])
        # Clean public representation: no internal IDs or agent names leaked
        summary_str = str(summary)
        for leak in ("workflow_id", "request_id", "agent_run_id", "tool_call_id", "mcp_session_id"):
            self.assertNotIn(leak, summary_str)


class PlanVersioningAndStateLifecycleTests(unittest.TestCase):
    """Point 6 & 7: User State retains history across adaptations (Plan V1 -> Plan V2)."""

    def test_plan_versioning_preserves_history(self):
        state = build_user_state()
        state["physical_assessment"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "1.0.0",
                "completed_at": "2026-01-01T00:00:00Z",
                "tests": {"shoulder": {"status": "completed"}, "ftsst": {"status": "completed"}},
            },
        }

        # Step 1: Initial starter plan (V1)
        state_v1, _ = build_maintenance_starter_plan(
            state, workflow_id="wf_v1", request_id="req_v1"
        )
        plans_v1 = state_v1["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans_v1), 1)
        self.assertEqual(plans_v1[0]["plan_version"], 1)

        # Step 2: Adaptation applied (e.g. feedback regression -> Plan V2)
        plans_copy = list(plans_v1)
        adapted_plan = dict(plans_v1[0])
        adapted_plan["plan_id"] = "plan_adapted_002"
        adapted_plan["plan_version"] = 2
        adapted_plan["adaptation_reason"] = "Elevate seat height to alleviate knee joint strain"
        plans_copy.append(adapted_plan)

        state_v2 = dict(state_v1)
        state_v2["exercise_history"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": plans_copy,
            },
        }

        validate_user_state(state_v2)

        # Verification: Plan V1 remains in history, Plan V2 is newest
        plans = state_v2["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0]["plan_version"], 1)
        self.assertEqual(plans[1]["plan_version"], 2)
        self.assertEqual(plans[1]["adaptation_reason"], "Elevate seat height to alleviate knee joint strain")

        # Serializer outputs newest plan (V2) with adaptation reason
        summary = serialise_workflow_state(state_v2, safety_status="ALLOW")
        self.assertEqual(summary["exercise_plan"]["adaptation_reason"], "Elevate seat height to alleviate knee joint strain")


if __name__ == "__main__":
    unittest.main()
