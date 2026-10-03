import unittest

from behaviour_agent.tool_client import BehaviourToolClient, InProcessBehaviourToolClient
from nutrition_agent.tool_client import NutritionToolClient, InProcessNutritionToolClient
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from user_state.schema import build_user_state


def _need_entry(level):
    return {
        "level": level,
        "score": 0.5 if level != "NOT_ASSESSED" else None,
        "evidence": ["fixture evidence"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(mobility, stability, functional_movement, behaviour, nutrition):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry(mobility),
        "stability_need": _need_entry(stability),
        "functional_movement_need": _need_entry(functional_movement),
        "behaviour_need": _need_entry(behaviour),
        "nutrition_need": _need_entry(nutrition),
        "exercise_need": _need_entry("NOT_ASSESSED"),
        "safety_status": _need_entry("NOT_ASSESSED"),
        "overallSummary": {
            "headline": "x", "dimensionsAtHigh": [], "dimensionsAtMedium": [],
            "dimensionsAtLow": [], "dimensionsNotAssessed": [], "assessedCount": 0,
            "notAssessedCount": 0,
        },
        "metadata": {
            "assessmentVersion": "0.1.0", "generatedAt": "2026-01-01T00:00:00Z",
            "workflowId": "wf_fixture", "requestId": "req_fixture",
        },
    }


def _state(mobility, stability, functional_movement, behaviour, nutrition, profile_doc=None):
    state = build_user_state(profile_doc=profile_doc or {})
    state["current_needs"] = {
        "available": True, "reason": None,
        "data": _needs(mobility, stability, functional_movement, behaviour, nutrition),
    }
    return state


def _clients(workflow_id="wf", request_id="req"):
    return {
        "tool_client": InProcessExerciseToolClient(workflow_id=workflow_id, request_id=request_id),
        "behaviour_tool_client": InProcessBehaviourToolClient(workflow_id=workflow_id, request_id=request_id),
        "nutrition_tool_client": InProcessNutritionToolClient(workflow_id=workflow_id, request_id=request_id),
    }


class DynamicSelectionTests(unittest.TestCase):
    """The five explicit selection cases from the Phase 4 brief, plus the
    all-LOW case. Each proves the Orchestrator's selection is dynamic and
    explainable — never "always run all three"."""

    def test_case_1_physio_only(self):
        state = _state("HIGH", "HIGH", "MEDIUM", "LOW", "NOT_ASSESSED")
        result = run_workflow(state, **_clients())
        self.assertEqual(result["selected_agents"], ["physio"])

    def test_case_2_behaviour_and_nutrition(self):
        state = _state("LOW", "LOW", "LOW", "HIGH", "HIGH")
        result = run_workflow(state, **_clients())
        self.assertEqual(set(result["selected_agents"]), {"behaviour", "nutrition"})

    def test_case_3_nutrition_only(self):
        state = _state("LOW", "LOW", "LOW", "LOW", "HIGH")
        result = run_workflow(state, **_clients())
        self.assertEqual(result["selected_agents"], ["nutrition"])

    def test_case_4_behaviour_only(self):
        state = _state("LOW", "LOW", "LOW", "HIGH", "LOW")
        result = run_workflow(state, **_clients())
        self.assertEqual(result["selected_agents"], ["behaviour"])

    def test_case_5_all_three(self):
        state = _state("HIGH", "HIGH", "HIGH", "HIGH", "HIGH")
        result = run_workflow(state, **_clients())
        self.assertEqual(set(result["selected_agents"]), {"physio", "behaviour", "nutrition"})

    def test_case_6_all_low_runs_nothing(self):
        state = _state("LOW", "LOW", "LOW", "LOW", "LOW")
        result = run_workflow(state, **_clients())
        self.assertEqual(result["selected_agents"], [])
        self.assertEqual(result["agent_results"], [])
        self.assertIsNone(result["safety_result"])


class MultiAgentEndToEndTests(unittest.TestCase):
    """Need Assessment -> Orchestrator -> Physio -> Behaviour -> Nutrition
    -> MCP tools -> Agent Results -> Safety Gate -> Orchestrator -> User
    State update. Proves real execution, not faked results."""

    def test_full_chain_runs_all_three_and_updates_state(self):
        from need_assessment.assessment import run_need_assessment

        profile_doc = {
            "daily_sitting_hours": 11, "daily_screen_hours": 9,
            "exercise_days": 0, "exercise_minutes": 0,
            "meal_pattern": "skips_meals", "fruit_vegetable_servings": 1,
            "water_glasses_per_day": 2, "processed_food_frequency": "daily",
        }
        assessment_doc = {
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {
                        "left": {"finalElevationDeg": 50},
                        "right": {"finalElevationDeg": 55},
                        "observableDifferenceDeg": 5,
                    },
                },
                "ftsst": {"status": "not_started"},
                "balance": {"status": "not_started"},
            }
        }
        state = build_user_state(profile_doc=profile_doc, assessment_doc=assessment_doc)
        state = run_need_assessment(state)

        result = run_workflow(state, **_clients(workflow_id="wf_e2e4", request_id="req_e2e4"))

        # The three plan-producing specialists all run. Exercise & Physical
        # Activity runs too, because this profile carries real activity
        # answers (sitting hours, exercise frequency) -- its own evidence,
        # independent of the three need levels above.
        self.assertTrue(
            {"physio", "behaviour", "nutrition"}.issubset(set(result["selected_agents"]))
        )
        self.assertIn("exercise_activity", result["selected_agents"])
        statuses = {r["agent"]: r["status"] for r in result["agent_results"]}
        for agent_id in ("physio", "behaviour", "nutrition"):
            self.assertEqual(statuses[agent_id], "completed")

        self.assertIsNotNone(result["safety_result"])
        self.assertIn(result["safety_result"]["status"], ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED"))

        self.assertEqual(
            set(result["state_updates"]),
            {"exercise_history", "behaviour", "nutrition_plan"},
        )
        self.assertTrue(result["updated_user_state"]["exercise_history"]["available"])
        self.assertTrue(result["updated_user_state"]["behaviour"]["available"])
        self.assertTrue(result["updated_user_state"]["nutrition_plan"]["available"])
        self.assertEqual(result["errors"], [])

        # A real coordination note: behaviour_need is HIGH and physio has a
        # plan, so the Orchestrator should have identified the conflict
        # named in the Phase 4 brief.
        self.assertTrue(result["coordination_notes"])


class PartialFailureTests(unittest.TestCase):
    """Physio succeeds, Behaviour succeeds, Nutrition fails, Safety still
    evaluates what is available."""

    def test_nutrition_failure_does_not_hide_the_other_two_successes(self):
        class BrokenNutritionClient(NutritionToolClient):
            def search_nutrition_guidance(self, **kwargs):
                raise ConnectionError("nutrition mcp down")

            def get_nutrition_topic_details(self, topic_id):
                raise ConnectionError("nutrition mcp down")

        state = _state(
            "HIGH", "LOW", "LOW", "HIGH", "HIGH",
            profile_doc={
                "daily_sitting_hours": 12, "daily_screen_hours": 10,
                "fruit_vegetable_servings": 1, "water_glasses_per_day": 2,
            },
        )
        result = run_workflow(
            state,
            tool_client=InProcessExerciseToolClient(workflow_id="wfp", request_id="reqp"),
            behaviour_tool_client=InProcessBehaviourToolClient(workflow_id="wfp", request_id="reqp"),
            nutrition_tool_client=BrokenNutritionClient(),
        )

        statuses = {r["agent"]: r["status"] for r in result["agent_results"]}
        self.assertEqual(statuses["physio"], "completed")
        self.assertEqual(statuses["behaviour"], "completed")
        self.assertEqual(statuses["nutrition"], "failed")

        # The Orchestrator never claims every agent succeeded.
        self.assertFalse(all(s == "completed" for s in statuses.values()))

        # No state update was attempted for the failed agent.
        self.assertNotIn("nutrition_plan", result["state_updates"])
        self.assertIn("exercise_history", result["state_updates"])
        self.assertIn("behaviour", result["state_updates"])

        # Safety still evaluated the recommendations that did exist.
        self.assertIsNotNone(result["safety_result"])


class SafetyOverrideTests(unittest.TestCase):
    """A rejected/modified candidate must not appear unchanged in the
    final approved set, nor be written to the User State unchanged."""

    def test_paused_exercise_is_absent_from_final_recommendations_and_state(self):
        from need_assessment.assessment import run_need_assessment

        assessment_doc = {
            "tests": {
                "shoulder": {"status": "not_started"},
                "ftsst": {"status": "completed", "measurements": {"completionTimeSeconds": 20}},
                "balance": {"status": "not_started"},
            }
        }
        confirmed_reports_doc = {"reports": [{"report_id": "r1", "confirmed": True}]}
        state = build_user_state(
            profile_doc={}, assessment_doc=assessment_doc, confirmed_reports_doc=confirmed_reports_doc
        )
        state = run_need_assessment(state)
        self.assertEqual(state["current_needs"]["data"]["functional_movement_need"]["level"], "HIGH")

        result = run_workflow(
            state, tool_client=InProcessExerciseToolClient(workflow_id="wfs", request_id="reqs")
        )

        original_ids = {e["exercise_id"] for e in result["agent_results"][0]["findings"]["plan"]["exercises"]}
        self.assertIn("wall-sit", original_ids)  # the agent DID propose it

        self.assertEqual(result["safety_result"]["status"], "PAUSE")
        self.assertIn("wall-sit", result["safety_result"]["blocked_recommendation_ids"])

        final_ids = {r["id"] for r in result["final_recommendations"]}
        self.assertNotIn("wall-sit", final_ids)

        persisted_ids = set(
            result["updated_user_state"]["exercise_history"]["data"]["plans"][0]["exercise_ids"]
        )
        self.assertNotIn("wall-sit", persisted_ids)


if __name__ == "__main__":
    unittest.main()
