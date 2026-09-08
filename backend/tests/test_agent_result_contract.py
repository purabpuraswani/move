import unittest

from orchestration.agent_result import (
    AgentResultValidationError,
    build_agent_result,
    validate_agent_result,
)
from orchestration.ids import start_agent_run, start_workflow


def _trace():
    return start_agent_run(start_workflow())


class BuildValidResultTests(unittest.TestCase):
    def test_a_minimal_valid_result_passes(self):
        trace = _trace()

        result = build_agent_result(
            agent="physio",
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
        )

        validate_agent_result(result)

        self.assertEqual(result["agent"], "physio")
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(result["priority"])
        self.assertEqual(result["findings"], {})
        self.assertEqual(result["recommendations"], [])
        self.assertFalse(result["requiresReassessment"])
        self.assertEqual(result["safetyFlags"], [])

    def test_a_fully_populated_result_passes(self):
        trace = _trace()

        result = build_agent_result(
            agent="behaviour",
            status="completed",
            priority="high",
            findings={"adherencePercent": 35, "barrier": "lack_of_time"},
            recommendations=[{"action": "shorten_plan", "toMinutes": 10}],
            requires_reassessment=True,
            safety_flags=[],
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
        )

        validate_agent_result(result)

        self.assertTrue(result["requiresReassessment"])
        self.assertEqual(result["findings"]["adherencePercent"], 35)

    def test_optional_metadata_ids_can_be_included(self):
        trace = _trace()

        result = build_agent_result(
            agent="physio",
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            tool_call_id="tool_example",
            mcp_session_id=None,
        )

        self.assertEqual(result["metadata"]["tool_call_id"], "tool_example")
        self.assertIsNone(result["metadata"]["mcp_session_id"])


class InvalidResultTests(unittest.TestCase):
    def test_an_unknown_agent_id_is_rejected(self):
        trace = _trace()

        with self.assertRaises(AgentResultValidationError):
            build_agent_result(
                agent="wellness_guidance",
                status="completed",
                workflow_id=trace.workflow_id,
                request_id=trace.request_id,
                agent_run_id=trace.agent_run_id,
            )

    def test_an_unknown_status_is_rejected(self):
        trace = _trace()

        with self.assertRaises(AgentResultValidationError):
            build_agent_result(
                agent="physio",
                status="in_progress",
                workflow_id=trace.workflow_id,
                request_id=trace.request_id,
                agent_run_id=trace.agent_run_id,
            )

    def test_an_unknown_priority_is_rejected(self):
        trace = _trace()

        with self.assertRaises(AgentResultValidationError):
            build_agent_result(
                agent="physio",
                status="completed",
                priority="urgent",
                workflow_id=trace.workflow_id,
                request_id=trace.request_id,
                agent_run_id=trace.agent_run_id,
            )

    def test_missing_required_metadata_is_rejected(self):
        with self.assertRaises(AgentResultValidationError):
            validate_agent_result(
                {
                    "agent": "physio",
                    "status": "completed",
                    "priority": None,
                    "findings": {},
                    "recommendations": [],
                    "requiresReassessment": False,
                    "safetyFlags": [],
                    "metadata": {
                        "workflow_id": "wf_1",
                        "request_id": "req_1",
                        # agent_run_id missing
                        "tool_call_id": None,
                        "mcp_session_id": None,
                    },
                }
            )

    def test_extra_metadata_cannot_override_reserved_keys(self):
        trace = _trace()

        with self.assertRaises(AgentResultValidationError):
            build_agent_result(
                agent="physio",
                status="completed",
                workflow_id=trace.workflow_id,
                request_id=trace.request_id,
                agent_run_id=trace.agent_run_id,
                extra_metadata={"workflow_id": "spoofed"},
            )

    def test_findings_must_be_an_object(self):
        with self.assertRaises(AgentResultValidationError):
            validate_agent_result(
                {
                    "agent": "physio",
                    "status": "completed",
                    "priority": None,
                    "findings": ["not", "an", "object"],
                    "recommendations": [],
                    "requiresReassessment": False,
                    "safetyFlags": [],
                    "metadata": {
                        "workflow_id": "wf_1",
                        "request_id": "req_1",
                        "agent_run_id": "run_1",
                        "tool_call_id": None,
                        "mcp_session_id": None,
                    },
                }
            )

    def test_unexpected_top_level_field_is_rejected(self):
        trace = _trace()

        result = build_agent_result(
            agent="physio",
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
        )

        result["confidence"] = 0.9

        with self.assertRaises(AgentResultValidationError):
            validate_agent_result(result)


if __name__ == "__main__":
    unittest.main()
