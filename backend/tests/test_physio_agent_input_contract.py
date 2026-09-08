import unittest

from physio_agent.input_contract import (
    PhysioAgentInputValidationError,
    build_physio_agent_input,
    validate_physio_agent_input,
)
from user_state.schema import build_user_state


class BuildPhysioAgentInputTests(unittest.TestCase):
    def test_a_brand_new_state_produces_all_none_optional_fields(self):
        state = build_user_state()
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )

        self.assertIsNone(payload["physical_assessment"])
        self.assertIsNone(payload["current_needs"])
        self.assertIsNone(payload["relevant_user_profile"])
        self.assertIsNone(payload["relevant_lifestyle_constraints"])
        self.assertIsNone(payload["confirmed_medical_context"])
        self.assertIsNone(payload["exercise_preferences"])

    def test_identifiers_are_carried_through_exactly(self):
        state = build_user_state()
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        self.assertEqual(payload["workflow_id"], "wf_1")
        self.assertEqual(payload["request_id"], "req_1")
        self.assertEqual(payload["agent_run_id"], "run_1")

    def test_available_current_needs_is_carried_through(self):
        state = build_user_state()
        state["current_needs"] = {"available": True, "reason": None, "data": {"x": 1}}
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        self.assertEqual(payload["current_needs"], {"x": 1})

    def test_only_confirmed_reports_populate_confirmed_medical_context(self):
        state = build_user_state()
        state["medical_context"] = {
            "available": True,
            "reason": None,
            "data": {
                "self_reported": {"source": "self_reported_onboarding", "values": {"diabetes": "yes"}},
                "confirmed_reports": {
                    "source": "user_confirmed_medical_report",
                    "reports": [{"field": "value"}],
                },
            },
        }
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        self.assertEqual(payload["confirmed_medical_context"]["reports"], [{"field": "value"}])
        # self_reported must never leak into this contract at all.
        self.assertNotIn("self_reported", str(payload))

    def test_empty_confirmed_reports_list_yields_none_not_an_empty_object(self):
        state = build_user_state()
        state["medical_context"] = {
            "available": True,
            "reason": None,
            "data": {
                "self_reported": {"source": "self_reported_onboarding", "values": {"diabetes": "yes"}},
                "confirmed_reports": {"source": "user_confirmed_medical_report", "reports": []},
            },
        }
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        self.assertIsNone(payload["confirmed_medical_context"])

    def test_exercise_preferences_is_always_none_no_collector_exists(self):
        state = build_user_state()
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        self.assertIsNone(payload["exercise_preferences"])

    def test_a_payload_naming_keypoints_is_refused(self):
        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(
                {
                    "workflow_id": "wf",
                    "request_id": "req",
                    "agent_run_id": "run",
                    "physical_assessment": {"note": "keypoint sequence embedded here"},
                    "current_needs": None,
                    "relevant_user_profile": None,
                    "relevant_lifestyle_constraints": None,
                    "confirmed_medical_context": None,
                    "exercise_preferences": None,
                }
            )

    def test_missing_field_is_rejected(self):
        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input({"workflow_id": "wf"})

    def test_unexpected_field_is_rejected(self):
        state = build_user_state()
        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        payload["not_a_real_field"] = True
        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(payload)

    def test_blank_identifier_is_rejected(self):
        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(
                {
                    "workflow_id": "",
                    "request_id": "req",
                    "agent_run_id": "run",
                    "physical_assessment": None,
                    "current_needs": None,
                    "relevant_user_profile": None,
                    "relevant_lifestyle_constraints": None,
                    "confirmed_medical_context": None,
                    "exercise_preferences": None,
                }
            )


if __name__ == "__main__":
    unittest.main()
