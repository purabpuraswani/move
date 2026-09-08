import unittest

from orchestration.agent_result import validate_agent_result
from orchestration.ids import start_workflow
from physio_agent.agent import (
    AGENT_ID,
    MAX_EXERCISES_PER_PLAN,
    run_physio_agent,
)
from physio_agent.tool_client import ExerciseToolClient, InProcessExerciseToolClient
from user_state.schema import build_user_state, validate_user_state


def _need_entry(level):
    return {
        "level": level,
        "score": 0.5 if level != "NOT_ASSESSED" else None,
        "evidence": ["fixture evidence"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(mobility, stability, functional_movement):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry(mobility),
        "stability_need": _need_entry(stability),
        "functional_movement_need": _need_entry(functional_movement),
        "behaviour_need": _need_entry("NOT_ASSESSED"),
        "nutrition_need": _need_entry("NOT_ASSESSED"),
        "exercise_need": _need_entry("HIGH"),
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


def _run(state):
    trace = start_workflow()
    client = InProcessExerciseToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
    return run_physio_agent(state, client, parent_trace=trace), client


class PhysioAgentHighNeedTests(unittest.TestCase):
    def setUp(self):
        self.state = _state_with_needs("HIGH", "HIGH", "MEDIUM")
        self.result, self.client = _run(self.state)

    def test_returns_a_valid_agent_result(self):
        validate_agent_result(self.result)
        self.assertEqual(self.result["agent"], AGENT_ID)

    def test_status_is_completed(self):
        self.assertEqual(self.result["status"], "completed")

    def test_priority_reflects_the_highest_triggering_level(self):
        self.assertEqual(self.result["priority"], "high")

    def test_a_non_empty_plan_was_built_from_real_tool_results(self):
        plan = self.result["findings"]["plan"]
        self.assertTrue(plan["exercises"])

        all_exercise_ids = {
            e["exercise_id"] for e in self.client.search_exercises()["exercises"]
        }
        for entry in plan["exercises"]:
            self.assertIn(entry["exercise_id"], all_exercise_ids)

    def test_every_plan_entry_has_a_non_diagnostic_rationale(self):
        for entry in self.result["findings"]["plan"]["exercises"]:
            self.assertTrue(entry["rationale"])
            self.assertNotIn("diagnos", entry["rationale"].lower())
            self.assertNotIn("disorder", entry["rationale"].lower())

    def test_recommendations_mirror_the_plan(self):
        plan_ids = {e["exercise_id"] for e in self.result["findings"]["plan"]["exercises"]}
        rec_ids = {r["exercise_id"] for r in self.result["recommendations"]}
        self.assertEqual(plan_ids, rec_ids)

    def test_only_beginner_or_intermediate_exercises_are_recommended(self):
        for entry in self.result["findings"]["plan"]["exercises"]:
            self.assertIn(entry["difficulty"], ("beginner", "intermediate"))

    def test_does_not_exceed_the_max_plan_size(self):
        # Against the module's own cap rather than a copy of the number:
        # the cap moved from 5 to 6 when the Physio Agent started building
        # a programme across capabilities instead of filling from whichever
        # search ran first, and a duplicated literal here would have made
        # that a test failure rather than a decision.
        self.assertLessEqual(
            len(self.result["findings"]["plan"]["exercises"]),
            MAX_EXERCISES_PER_PLAN,
        )

    def test_no_pose_or_video_language_anywhere_in_the_result(self):
        serialised = str(self.result).lower()
        for forbidden in ("keypoint", "landmark", "skeleton", "rawframe", "video", "base64"):
            self.assertNotIn(forbidden, serialised)

    def test_metadata_carries_real_observability_ids(self):
        metadata = self.result["metadata"]
        self.assertTrue(metadata["workflow_id"])
        self.assertTrue(metadata["request_id"])
        self.assertTrue(metadata["agent_run_id"])
        # No live MCP transport session exists via the in-process test
        # double — this must stay honestly None, never a fabricated value.
        self.assertIsNone(metadata["mcp_session_id"])


class PhysioAgentLowNeedTests(unittest.TestCase):
    def test_low_needs_direct_call_still_returns_a_valid_completed_result_with_no_plan(self):
        # The Orchestrator is what normally prevents this agent from running
        # at all on all-LOW needs; calling it directly still must not crash.
        state = _state_with_needs("LOW", "LOW", "LOW")
        result, _client = _run(state)
        validate_agent_result(result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"], [])


class PhysioAgentMissingNeedsTests(unittest.TestCase):
    def test_missing_current_needs_returns_a_failed_result_not_a_crash(self):
        state = build_user_state()
        result, _client = _run(state)
        validate_agent_result(result)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["requiresReassessment"])


class BrokenToolClient(ExerciseToolClient):
    def search_exercises(self, **kwargs):
        raise ConnectionError("mcp server unreachable")

    def get_exercise_details(self, exercise_id):
        raise ConnectionError("mcp server unreachable")

    def check_exercise_constraints(self, exercise_id):
        raise ConnectionError("mcp server unreachable")


class PhysioAgentMcpFailureTests(unittest.TestCase):
    def test_a_tool_client_failure_produces_a_structured_failed_result(self):
        from orchestration.ids import start_workflow as _sw

        state = _state_with_needs("HIGH", "LOW", "LOW")
        trace = _sw()
        result = run_physio_agent(state, BrokenToolClient(), parent_trace=trace)
        validate_agent_result(result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("mcp_unavailable_or_tool_error", result["safetyFlags"])


class ErroringConstraintsToolClient(InProcessExerciseToolClient):
    """Search works normally; every constraint check reports 'not found' —
    exercises every candidate's real safety-gate rejection path."""

    def check_exercise_constraints(self, exercise_id):
        return {"error": f"no exercise with id {exercise_id!r} exists in the library"}


class PhysioAgentAllCandidatesRejectedTests(unittest.TestCase):
    def test_every_candidate_failing_the_safety_gate_yields_an_empty_but_valid_plan(self):
        from orchestration.ids import start_workflow as _sw

        state = _state_with_needs("HIGH", "LOW", "LOW")
        trace = _sw()
        client = ErroringConstraintsToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
        result = run_physio_agent(state, client, parent_trace=trace)
        validate_agent_result(result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["findings"]["plan"]["exercises"], [])
        self.assertTrue(result["requiresReassessment"])
        self.assertIn("no_suitable_exercise_found", result["safetyFlags"])
        self.assertTrue(result["findings"]["rejected_candidates"])


if __name__ == "__main__":
    unittest.main()
