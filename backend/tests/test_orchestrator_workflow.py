import unittest

from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import ExerciseToolClient, InProcessExerciseToolClient
from behaviour_agent.tool_client import InProcessBehaviourToolClient
from nutrition_agent.tool_client import InProcessNutritionToolClient
from progress_agent.tool_client import InProcessProgressToolClient
from workflow.response import serialise_workflow_state
from user_state.schema import build_user_state


def _need_entry(level):
    return {
        "level": level,
        "score": 0.5 if level != "NOT_ASSESSED" else None,
        "evidence": ["fixture evidence"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(mobility, stability, functional_movement, exercise="HIGH"):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry(mobility),
        "stability_need": _need_entry(stability),
        "functional_movement_need": _need_entry(functional_movement),
        "behaviour_need": _need_entry("NOT_ASSESSED"),
        "nutrition_need": _need_entry("NOT_ASSESSED"),
        "exercise_need": _need_entry(exercise),
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


def _state_with_needs(mobility, stability, functional_movement):
    state = build_user_state()
    state["medical_context"] = {
        "available": True,
        "reason": None,
        "data": {
            "self_reported": {
                "source": "self_reported_onboarding",
                "values": {
                    "diabetes": "no", "hypertension": "no", "heart_condition": "no",
                    "previous_injury": "no", "joint_pain": "no", "back_neck_pain": "no",
                    "other_conditions": "",
                },
            },
            "confirmed_reports": {"source": "user_confirmed_medical_report", "reports": []},
        },
    }
    state["current_needs"] = {
        "available": True, "reason": None,
        "data": _needs(mobility, stability, functional_movement),
    }
    return state


class CountingToolClient(InProcessExerciseToolClient):
    """Same real tool implementations, but counts calls so a test can
    assert Physio was never even asked to search — proving "not required"
    really means no MCP call happened, not just an empty result."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.search_calls = 0

    def search_exercises(self, **kwargs):
        self.search_calls += 1
        return super().search_exercises(**kwargs)


class PositiveEndToEndTests(unittest.TestCase):
    """User State -> current_needs -> Orchestrator -> Physio selected ->
    Physio Agent -> Exercise MCP -> Exercise tool -> Exercise plan ->
    Agent Result -> Orchestrator -> User State update. The one chain the
    Phase 3 brief calls out as needing direct proof."""

    def test_the_full_chain_runs_and_updates_user_state(self):
        state = _state_with_needs("HIGH", "HIGH", "MEDIUM")
        client = CountingToolClient(workflow_id="wf_e2e", request_id="req_e2e")

        result = run_workflow(state, tool_client=client)

        self.assertTrue(result["orchestrator_decision"]["physio_required"])
        self.assertEqual(result["selected_agents"], ["physio"])
        self.assertEqual(len(result["agent_results"]), 1)

        physio_result = result["agent_results"][0]
        self.assertEqual(physio_result["agent"], "physio")
        self.assertEqual(physio_result["status"], "completed")
        self.assertTrue(physio_result["findings"]["plan"]["exercises"])
        for exercise in physio_result["findings"]["plan"]["exercises"]:
            self.assertTrue(exercise["instructions"])
            self.assertIn("sets", exercise)
            self.assertIn("equipment", exercise)
            self.assertIn("safety_notes", exercise)
            self.assertTrue(exercise.get("demonstration_id"))

        self.assertGreater(client.search_calls, 0)

        self.assertEqual(result["state_updates"], ["exercise_history"])
        self.assertTrue(result["updated_user_state"]["exercise_history"]["available"])
        self.assertEqual(
            result["updated_user_state"]["exercise_history"]["data"]["plans"][0]["exercise_ids"],
            [e["exercise_id"] for e in physio_result["findings"]["plan"]["exercises"]],
        )
        self.assertEqual(result["errors"], [])

    def test_original_user_state_is_never_mutated(self):
        state = _state_with_needs("HIGH", "LOW", "LOW")
        client = InProcessExerciseToolClient(workflow_id="wf_x", request_id="req_x")
        run_workflow(state, tool_client=client)
        self.assertFalse(state["exercise_history"]["available"])


class NegativeEndToEndTests(unittest.TestCase):
    """User State -> current_needs -> Orchestrator -> Physio NOT required
    -> no Physio Agent execution, and specifically: no exercise MCP call."""

    def test_all_low_needs_never_invoke_the_agent_or_any_mcp_call(self):
        state = _state_with_needs("LOW", "LOW", "LOW")
        client = CountingToolClient(workflow_id="wf_neg", request_id="req_neg")

        result = run_workflow(state, tool_client=client)

        self.assertFalse(result["orchestrator_decision"]["physio_required"])
        self.assertEqual(result["selected_agents"], [])
        self.assertEqual(result["agent_results"], [])
        self.assertEqual(result["state_updates"], [])
        self.assertEqual(client.search_calls, 0)

    def test_full_review_executes_all_six_and_builds_low_need_tracking_outputs(self):
        state = _state_with_needs("LOW", "LOW", "LOW")
        kwargs = {"workflow_id": "wf_all", "request_id": "req_all"}
        result = run_workflow(
            state,
            tool_client=InProcessExerciseToolClient(**kwargs),
            behaviour_tool_client=InProcessBehaviourToolClient(**kwargs),
            nutrition_tool_client=InProcessNutritionToolClient(**kwargs),
            progress_tool_client=InProcessProgressToolClient(**kwargs),
            execute_all_agents=True,
            **kwargs,
        )
        expected = {"physio", "nutrition", "behaviour", "recovery", "exercise_activity", "progress"}
        self.assertEqual(set(result["selected_agents"]), expected)
        results = {item["agent"]: item for item in result["agent_results"]}
        self.assertEqual(set(results), expected)
        self.assertTrue(results["physio"]["findings"]["catalog_candidates_reviewed"])
        self.assertTrue(results["physio"]["findings"]["exercise_safety_evaluations"])
        self.assertEqual(results["physio"]["findings"]["plan"]["exercises"] if "plan" in results["physio"]["findings"] else [], [])
        for agent_id, agent_result in results.items():
            self.assertEqual(agent_result["status"], "completed", agent_id)
            self.assertTrue(agent_result["findings"].get("tracking_activities"), agent_id)
            self.assertTrue(agent_result["findings"].get("next_action"), agent_id)
        self.assertTrue(results["nutrition"]["findings"]["activities"])
        self.assertTrue(results["behaviour"]["findings"]["activities"])
        response = serialise_workflow_state(
            result["updated_user_state"],
            safety_status=(result["safety_result"] or {}).get("status"),
            safety_result=result["safety_result"],
            agent_executions=results,
            selection_explanations=result["orchestrator_decision"]["selection_explanations"],
            approved_recommendations=result["final_recommendations"],
        )
        self.assertEqual(response["plan_state"]["state"], "PLAN_AVAILABLE")
        self.assertEqual(
            {item["agent"] for item in response["unified_plan"]["specialist_contributions"]},
            expected,
        )
        self.assertEqual(response["unified_plan"]["completion_state"]["recorded_complete_count"], 0)
        self.assertTrue(response["unified_plan"]["activities"])
        self.assertTrue(response["unified_plan"]["tracking_tasks"])
        self.assertTrue(all(item["type"] != "tracking_task" for item in response["unified_plan"]["activities"]))

    def test_not_required_is_distinguishable_from_required_but_failed(self):
        not_required = run_workflow(_state_with_needs("LOW", "LOW", "LOW"))
        self.assertEqual(not_required["selected_agents"], [])
        self.assertEqual(not_required["errors"], [])

        class BrokenClient(ExerciseToolClient):
            def search_exercises(self, **kwargs):
                raise ConnectionError("down")
            def get_exercise_details(self, exercise_id):
                raise ConnectionError("down")
            def check_exercise_constraints(self, exercise_id):
                raise ConnectionError("down")

        required_but_failed = run_workflow(
            _state_with_needs("HIGH", "LOW", "LOW"), tool_client=BrokenClient()
        )
        self.assertEqual(required_but_failed["selected_agents"], ["physio"])
        self.assertEqual(required_but_failed["agent_results"][0]["status"], "failed")


class SafetyAndInvalidInputTests(unittest.TestCase):
    def test_missing_user_state_returns_an_incomplete_state_result_not_a_crash(self):
        result = run_workflow({"not": "a real state"})
        self.assertFalse(result["orchestrator_decision"]["physio_required"])
        self.assertTrue(result["errors"])
        self.assertIsNone(result["updated_user_state"])

    def test_none_user_state_does_not_crash(self):
        # None is not even a dict; run_workflow must fail SAFELY (an
        # incomplete-state result with a named error), never raise an
        # unhandled exception up into a caller.
        result = run_workflow(None)
        self.assertFalse(result["orchestrator_decision"]["physio_required"])
        self.assertTrue(result["errors"])
        self.assertIsNone(result["updated_user_state"])

    def test_malformed_need_profile_inside_a_valid_user_state_is_handled(self):
        state = build_user_state()
        # Available but missing required dimension keys — malformed content
        # inside an otherwise well-shaped section.
        state["current_needs"] = {"available": True, "reason": None, "data": {"mobility_need": {"level": "HIGH"}}}
        result = run_workflow(state)
        # decide_physio_required reads only the three keys it knows about;
        # a malformed/incomplete profile must not crash the Orchestrator.
        self.assertIn("physio_required", result["orchestrator_decision"])

    def test_physio_required_with_no_tool_client_is_a_distinct_error_not_a_crash(self):
        result = run_workflow(_state_with_needs("HIGH", "HIGH", "HIGH"))
        self.assertEqual(result["selected_agents"], ["physio"])
        self.assertEqual(result["agent_results"], [])
        self.assertTrue(result["errors"])

    def test_an_exercise_constraint_rejection_still_yields_a_valid_workflow_result(self):
        class AllRejectedClient(InProcessExerciseToolClient):
            def check_exercise_constraints(self, exercise_id):
                return {"error": "rejected for test"}

        state = _state_with_needs("HIGH", "LOW", "LOW")
        client = AllRejectedClient(workflow_id="wf_rej", request_id="req_rej")
        result = run_workflow(state, tool_client=client)

        self.assertEqual(result["agent_results"][0]["status"], "completed")
        self.assertEqual(result["agent_results"][0]["findings"]["plan"]["exercises"], [])
        self.assertEqual(result["state_updates"], [])

    def test_self_reported_health_reaches_physio_and_is_not_treated_as_confirmed(self):
        state = _state_with_needs("HIGH", "LOW", "LOW")
        state["medical_context"] = {
            "available": True, "reason": None,
            "data": {
                "self_reported": {"source": "self_reported_onboarding", "values": {"diabetes": "yes"}},
                "confirmed_reports": {"source": "user_confirmed_medical_report", "reports": []},
            },
        }
        client = InProcessExerciseToolClient(workflow_id="wf_med", request_id="req_med")
        result = run_workflow(state, tool_client=client)

        physio_result = result["agent_results"][0]
        findings = physio_result["findings"]
        self.assertEqual(findings["reported_health_context_status"], "INCOMPLETE")
        self.assertEqual(findings["confirmed_medical_context_status"], "NONE_CONFIRMED")
        self.assertTrue(findings["exercise_safety_evaluations"])
        self.assertTrue(all(
            entry["status"] == "DEFERRED_CONTEXT_REQUIRED"
            for entry in findings["exercise_safety_evaluations"]
        ))


if __name__ == "__main__":
    unittest.main()
