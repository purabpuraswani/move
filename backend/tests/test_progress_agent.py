"""Progress Agent (Phase 5) — input contract, findings schema, and the full
agent execution lifecycle, including the five explicit brief scenarios
(steps 21-25): improvement+high adherence, missing-current-data,
stagnation+high adherence, regression+high adherence, and
stable+low-adherence.
"""

import unittest

from datetime import datetime, timedelta, timezone

from orchestration.ids import TraceContext, start_workflow
from progress_agent.agent import run_progress_agent
from progress_agent.input_contract import (
    ProgressAgentInputValidationError,
    build_progress_agent_input,
    validate_progress_agent_input,
)
from progress_agent.schema import ProgressFindingsValidationError, validate_progress_findings
from progress_agent.tool_client import InProcessProgressToolClient, ProgressToolClient

# A completion timestamp that is genuinely recent, relative to whatever
# "now" is when this suite runs. These tests are about what the Progress
# Agent concludes from a *current* assessment; a hard-coded calendar date
# silently became a "stale assessment" case once enough real time passed,
# which is not what any of them is testing.
RECENT_COMPLETED_AT = (
    datetime.now(timezone.utc) - timedelta(days=3)
).strftime("%Y-%m-%dT%H:%M:%SZ")



def _balance_doc(hold, completed_at="2026-01-01T00:00:00Z"):
    return {
        "tests": {
            "balance": {
                "status": "completed",
                "measurements": {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": hold},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": hold},
                },
            },
        },
        "completed_at": completed_at,
    }


def _trace():
    wf = start_workflow()
    return TraceContext(workflow_id=wf.workflow_id, request_id=wf.request_id)


def _client():
    trace = _trace()
    return InProcessProgressToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id), trace


class InputContractTests(unittest.TestCase):
    def test_build_minimal_input_all_optional_fields_omitted(self):
        payload = build_progress_agent_input(
            workflow_id="wf", request_id="req", agent_run_id="run",
        )
        self.assertIsNone(payload["baseline_assessment"])
        self.assertEqual(payload["exercise_results"], [])
        validate_progress_agent_input(payload)  # does not raise

    def test_missing_required_id_rejected(self):
        with self.assertRaises(ProgressAgentInputValidationError):
            build_progress_agent_input(workflow_id="", request_id="req", agent_run_id="run")

    def test_unexpected_field_rejected(self):
        payload = build_progress_agent_input(workflow_id="wf", request_id="req", agent_run_id="run")
        payload["raw_video_frame"] = "not allowed"
        with self.assertRaises(ProgressAgentInputValidationError):
            validate_progress_agent_input(payload)

    def test_missing_field_rejected(self):
        payload = build_progress_agent_input(workflow_id="wf", request_id="req", agent_run_id="run")
        del payload["current_needs"]
        with self.assertRaises(ProgressAgentInputValidationError):
            validate_progress_agent_input(payload)

    def test_forbidden_media_data_is_rejected(self):
        # Pose/media DATA is refused; prose that merely mentions it is not.
        # The old rule refused the word, and the browser sends
        # `quality.meanKeypointScore` with every real assessment, so this
        # contract used to refuse the product's own normal input.
        with self.assertRaises(ProgressAgentInputValidationError):
            build_progress_agent_input(
                workflow_id="wf", request_id="req", agent_run_id="run",
                baseline_assessment={"keypoints": [[0.1, 0.2]]},
            )

    def test_a_real_assessment_quality_summary_is_accepted(self):
        payload = build_progress_agent_input(
            workflow_id="wf", request_id="req", agent_run_id="run",
            baseline_assessment={
                "tests": {
                    "shoulder": {
                        "quality": {"meanKeypointScore": 0.71, "framesSeen": 188}
                    }
                }
            },
            current_assessment={
                "tests": {
                    "shoulder": {
                        "quality": {"meanKeypointScore": 0.8, "longestPoseLossMs": 40}
                    }
                }
            },
        )

        validate_progress_agent_input(payload)  # must not raise

    def test_exercise_results_must_be_a_list(self):
        with self.assertRaises(ProgressAgentInputValidationError):
            build_progress_agent_input(
                workflow_id="wf", request_id="req", agent_run_id="run",
                exercise_results="not-a-list",
            )


class FindingsSchemaTests(unittest.TestCase):
    def _valid_findings(self, **overrides):
        base = {
            "physical_comparison": {},
            "overall_direction": "STABLE",
            "adherence": {"completion_rate": 0.9},
            "adaptation_recommendation": "MAINTAIN",
            "reassessment": {"required": False, "reason": "recent enough"},
        }
        base.update(overrides)
        return base

    def test_valid_findings_pass(self):
        validate_progress_findings(self._valid_findings())  # does not raise

    def test_missing_field_rejected(self):
        findings = self._valid_findings()
        del findings["adherence"]
        with self.assertRaises(ProgressFindingsValidationError):
            validate_progress_findings(findings)

    def test_bad_overall_direction_rejected(self):
        with self.assertRaises(ProgressFindingsValidationError):
            validate_progress_findings(self._valid_findings(overall_direction="GETTING_BETTER"))

    def test_bad_adaptation_recommendation_rejected(self):
        with self.assertRaises(ProgressFindingsValidationError):
            validate_progress_findings(self._valid_findings(adaptation_recommendation="DO_SOMETHING"))

    def test_reassessment_must_have_exactly_required_and_reason(self):
        with self.assertRaises(ProgressFindingsValidationError):
            validate_progress_findings(self._valid_findings(reassessment={"required": True}))

    def test_reassessment_reason_must_be_nonempty(self):
        with self.assertRaises(ProgressFindingsValidationError):
            validate_progress_findings(self._valid_findings(reassessment={"required": True, "reason": "  "}))

    def test_extra_fields_allowed(self):
        findings = self._valid_findings()
        findings["adherence_level"] = "HIGH"
        validate_progress_findings(findings)  # does not raise


class _RaisingToolClient(ProgressToolClient):
    """TEST-ONLY double that fails every call — simulates an MCP outage."""

    def compare_assessments(self, **kwargs):
        raise RuntimeError("mcp transport unavailable")

    def calculate_adherence(self, **kwargs):
        raise RuntimeError("mcp transport unavailable")

    def check_reassessment_required(self, **kwargs):
        raise RuntimeError("mcp transport unavailable")


class _ErrorReturningToolClient(ProgressToolClient):
    """TEST-ONLY double whose compare_assessments returns a tool-level
    {"error": ...} instead of raising — a distinct failure mode from a
    transport exception."""

    def compare_assessments(self, **kwargs):
        return {"error": "malformed assessment document"}

    def calculate_adherence(self, **kwargs):
        return {"adherence": {"completion_rate": None, "status": "NOT_ENOUGH_DATA"}}

    def check_reassessment_required(self, **kwargs):
        return {"required": True, "reason": "no current assessment"}


class RunProgressAgentTests(unittest.TestCase):
    def test_valid_input_produces_a_completed_result_matching_agent_result_contract(self):
        client, trace = _client()
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=_balance_doc(60, completed_at=RECENT_COMPLETED_AT),
            tool_client=client,
            parent_trace=trace,
        )
        self.assertEqual(result["agent"], "progress")
        self.assertEqual(result["status"], "completed")
        self.assertIn("physical_comparison", result["findings"])
        self.assertIn("overall_direction", result["findings"])
        self.assertIn("adaptation_recommendation", result["findings"])
        self.assertIn("reassessment", result["findings"])
        self.assertIn("agent_run_id", result["metadata"])

    def test_mcp_transport_failure_is_a_failed_result_not_a_crash(self):
        client, trace = _client()
        # Swap in a raising double after construction to simulate an
        # MCP-unavailable condition mid-run.
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=_balance_doc(60),
            tool_client=_RaisingToolClient(),
            parent_trace=trace,
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("mcp_unavailable_or_tool_error", result["safetyFlags"])

    def test_tool_level_error_result_is_also_a_failed_agent_result(self):
        client, trace = _client()
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=_balance_doc(60),
            tool_client=_ErrorReturningToolClient(),
            parent_trace=trace,
        )
        self.assertEqual(result["status"], "failed")

    # --- The five explicit brief scenarios (steps 21-25) -----------------

    def test_scenario_improvement_high_adherence_recommends_progress(self):
        client, trace = _client()
        plan = {"plan_id": "p1", "exercise_ids": ["a", "b", "c", "d"]}
        exercise_results = [
            {"exerciseId": eid, "plan_id": "p1", "status": "completed"} for eid in ["a", "b", "c"]
        ]
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=_balance_doc(60, completed_at=RECENT_COMPLETED_AT),
            current_plan=plan,
            exercise_results=exercise_results,
            tool_client=client,
            parent_trace=trace,
        )
        findings = result["findings"]
        self.assertEqual(findings["overall_direction"], "IMPROVED")
        self.assertEqual(findings["adherence_level"], "HIGH")
        self.assertEqual(findings["adaptation_recommendation"], "PROGRESS")
        self.assertFalse(result["requiresReassessment"])

    def test_scenario_missing_current_assessment_is_not_enough_data(self):
        client, trace = _client()
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=None,
            tool_client=client,
            parent_trace=trace,
        )
        findings = result["findings"]
        self.assertEqual(findings["overall_direction"], "NOT_ENOUGH_DATA")
        self.assertEqual(findings["adaptation_recommendation"], "REASSESS")
        self.assertTrue(result["requiresReassessment"])

    def test_scenario_stagnation_high_adherence_recommends_maintain(self):
        client, trace = _client()
        plan = {"plan_id": "p1", "exercise_ids": ["a", "b", "c", "d"]}
        exercise_results = [
            {"exerciseId": eid, "plan_id": "p1", "status": "completed"} for eid in ["a", "b", "c", "d"]
        ]
        result = run_progress_agent(
            baseline_assessment=_balance_doc(50),
            current_assessment=_balance_doc(50, completed_at=RECENT_COMPLETED_AT),
            current_plan=plan,
            exercise_results=exercise_results,
            tool_client=client,
            parent_trace=trace,
        )
        findings = result["findings"]
        self.assertEqual(findings["overall_direction"], "STABLE")
        self.assertEqual(findings["adherence_level"], "HIGH")
        self.assertEqual(findings["adaptation_recommendation"], "MAINTAIN")

    def test_scenario_regression_high_adherence_recommends_reassess(self):
        client, trace = _client()
        plan = {"plan_id": "p1", "exercise_ids": ["a", "b", "c", "d"]}
        exercise_results = [
            {"exerciseId": eid, "plan_id": "p1", "status": "completed"} for eid in ["a", "b", "c", "d"]
        ]
        result = run_progress_agent(
            baseline_assessment=_balance_doc(60),
            current_assessment=_balance_doc(45, completed_at=RECENT_COMPLETED_AT),
            current_plan=plan,
            exercise_results=exercise_results,
            tool_client=client,
            parent_trace=trace,
        )
        findings = result["findings"]
        self.assertEqual(findings["overall_direction"], "DECLINED")
        self.assertEqual(findings["adherence_level"], "HIGH")
        # Regression despite high adherence is flagged for review, not
        # silently downgraded — matches brief step 12/24 exactly.
        self.assertEqual(findings["adaptation_recommendation"], "REASSESS")

    def test_scenario_unchanged_performance_low_adherence_recommends_modify(self):
        client, trace = _client()
        plan = {"plan_id": "p1", "exercise_ids": ["a", "b", "c", "d"]}
        exercise_results = [
            {"exerciseId": "a", "plan_id": "p1", "status": "completed"},
        ]
        result = run_progress_agent(
            baseline_assessment=_balance_doc(50),
            current_assessment=_balance_doc(50, completed_at=RECENT_COMPLETED_AT),
            current_plan=plan,
            exercise_results=exercise_results,
            tool_client=client,
            parent_trace=trace,
        )
        findings = result["findings"]
        self.assertEqual(findings["overall_direction"], "STABLE")
        self.assertEqual(findings["adherence_level"], "LOW")
        # Distinguishes "intervention effectiveness uncertain" (MODIFY)
        # from "the plan itself failed" (never claimed here).
        self.assertEqual(findings["adaptation_recommendation"], "MODIFY")

    def test_deterministic_same_input_same_output(self):
        client1, trace1 = _client()
        client2, trace2 = _client()
        baseline = _balance_doc(40)
        current = _balance_doc(60, completed_at=RECENT_COMPLETED_AT)

        result1 = run_progress_agent(baseline_assessment=baseline, current_assessment=current, tool_client=client1, parent_trace=trace1)
        result2 = run_progress_agent(baseline_assessment=baseline, current_assessment=current, tool_client=client2, parent_trace=trace2)

        self.assertEqual(result1["findings"]["overall_direction"], result2["findings"]["overall_direction"])
        self.assertEqual(result1["findings"]["adaptation_recommendation"], result2["findings"]["adaptation_recommendation"])
        self.assertEqual(result1["findings"]["physical_comparison"], result2["findings"]["physical_comparison"])

    def test_no_plan_yet_produces_not_enough_data_adherence_not_a_fabricated_rate(self):
        client, trace = _client()
        result = run_progress_agent(
            baseline_assessment=_balance_doc(40),
            current_assessment=_balance_doc(60, completed_at=RECENT_COMPLETED_AT),
            current_plan=None,
            tool_client=client,
            parent_trace=trace,
        )
        self.assertEqual(result["findings"]["adherence"]["status"], "NOT_ENOUGH_DATA")
        self.assertIsNone(result["findings"]["adherence"]["completion_rate"])


if __name__ == "__main__":
    unittest.main()
