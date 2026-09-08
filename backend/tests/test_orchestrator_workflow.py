import unittest

from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import ExerciseToolClient, InProcessExerciseToolClient
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

    def test_unconfirmed_medical_context_never_reaches_the_physio_input(self):
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

        # The Physio Agent's OWN reasoning/output must never have seen or
        # echoed self-reported (unconfirmed) medical context — checked
        # against its Agent Result specifically, not the pass-through full
        # User State the Orchestrator also returns (which legitimately
        # keeps self_reported for other, non-Physio purposes; Phase 0's
        # User State was never scoped to exclude it entirely).
        physio_result = result["agent_results"][0]
        serialised_agent_output = str(physio_result).lower()
        self.assertNotIn("self_reported", serialised_agent_output)
        self.assertNotIn("diabetes", serialised_agent_output)


if __name__ == "__main__":
    unittest.main()
