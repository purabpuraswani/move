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
        self.assertEqual(payload["movement_evidence"]["shoulder"]["status"], "not_started")
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

    def test_raw_baseline_parameters_are_normalized_into_movement_evidence(self):
        state = build_user_state()
        state["physical_assessment"] = {
            "available": True,
            "reason": None,
            "data": {
                "tests": {
                    "shoulder": {
                        "status": "completed",
                        "measurements": {
                            "left": {"finalElevationDeg": 135.9, "repetitionCount": 3},
                            "right": {"finalElevationDeg": 178.3, "repetitionCount": 3},
                            "observableDifferenceDeg": 42.4,
                        },
                    },
                    "ftsst": {
                        "status": "completed",
                        "measurements": {
                            "completionTimeSeconds": 13.84,
                            "repetitionsDetected": 5,
                            "requiredRepetitions": 5,
                        },
                        "setup": {"chairSeatHeightCm": 60, "measuredSide": "left"},
                    },
                    "balance": {
                        "status": "completed",
                        "measurements": {
                            "left": {"holdDurationSeconds": 5.97, "endReason": "foot_lowered"},
                            "right": {"holdDurationSeconds": 3.5, "endReason": "foot_lowered"},
                            "observableDifferenceMs": 2470,
                        },
                    },
                }
            },
        }

        payload = build_physio_agent_input(
            state, workflow_id="wf_1", request_id="req_1", agent_run_id="run_1"
        )
        evidence = payload["movement_evidence"]

        self.assertEqual(evidence["shoulder"]["left_elevation_deg"], 135.9)
        self.assertEqual(evidence["shoulder"]["right_elevation_deg"], 178.3)
        self.assertEqual(evidence["shoulder"]["side_difference_deg"], 42.4)
        self.assertEqual(evidence["sit_to_stand"]["time_seconds"], 13.84)
        self.assertEqual(evidence["sit_to_stand"]["chair_height_cm"], 60)
        self.assertEqual(evidence["sit_to_stand"]["measured_side"], "left")
        self.assertEqual(evidence["balance"]["left_hold_seconds"], 5.97)
        self.assertEqual(evidence["balance"]["right_hold_seconds"], 3.5)
        self.assertEqual(evidence["balance"]["side_difference_seconds"], 2.47)

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

    def test_a_real_assessment_quality_summary_is_accepted(self):
        # The regression this guards: the boundary used to refuse any payload
        # whose serialised text contained "keypoint", and the browser sends
        # `quality.meanKeypointScore` with every session. A real assessment
        # therefore made the Physio Agent refuse its own input, and no movement
        # plan could be produced from a real recording.
        payload = self._payload()
        payload["physical_assessment"] = {
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {"left": {"finalElevationDeg": 104.0}},
                    "quality": {
                        "meanKeypointScore": 0.71,
                        "longestPoseLossMs": 132,
                        "framesSeen": 188,
                    },
                }
            }
        }

        validate_physio_agent_input(payload)  # must not raise

    def test_a_pose_named_list_is_still_refused(self):
        payload = self._payload()
        payload["physical_assessment"] = {
            "tests": {"shoulder": {"keypointSeries": [[0.1, 0.2], [0.3, 0.4]]}}
        }

        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(payload)

    def test_a_media_named_scalar_is_still_refused(self):
        payload = self._payload()
        payload["physical_assessment"] = {"debugFrameSnapshot": "abc"}

        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(payload)

    def test_a_data_uri_is_still_refused(self):
        payload = self._payload()
        payload["physical_assessment"] = {"note": "data:image/png;base64,iVBORw0KGgo="}

        with self.assertRaises(PhysioAgentInputValidationError):
            validate_physio_agent_input(payload)

    def test_prose_about_pose_data_is_not_a_violation(self):
        # Free text is free text. The boundary's job is to stop pose DATA, and
        # a reason sentence that happens to mention keypoints is not data — the
        # previous substring rule refused it, which is how false positives get
        # into a safety check and then get switched off.
        payload = self._payload()
        payload["physical_assessment"] = {
            "note": "The camera lost the keypoint sequence briefly during this attempt."
        }

        validate_physio_agent_input(payload)  # must not raise

    @staticmethod
    def _payload():
        return {
            "workflow_id": "wf",
            "request_id": "req",
            "agent_run_id": "run",
            "physical_assessment": None,
            "movement_evidence": {},
            "current_needs": None,
            "relevant_user_profile": None,
            "relevant_lifestyle_constraints": None,
            "confirmed_medical_context": None,
            "exercise_preferences": None,
        }

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
                    "movement_evidence": {},
                    "current_needs": None,
                    "relevant_user_profile": None,
                    "relevant_lifestyle_constraints": None,
                    "confirmed_medical_context": None,
                    "exercise_preferences": None,
                }
            )


if __name__ == "__main__":
    unittest.main()
