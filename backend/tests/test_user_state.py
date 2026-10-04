import unittest

from user_state.schema import (
    NOT_YET_COLLECTED,
    SECTION_NAMES,
    USER_STATE_SCHEMA_VERSION,
    UserStateValidationError,
    build_user_state,
    validate_user_state,
)


class BuildEmptyUserStateTests(unittest.TestCase):
    def test_a_state_with_no_sources_is_fully_shaped_but_unavailable(self):
        state = build_user_state()

        validate_user_state(state)

        self.assertEqual(state["schemaVersion"], USER_STATE_SCHEMA_VERSION)

        for name in SECTION_NAMES:
            self.assertFalse(state[name]["available"])
            self.assertIsNone(state[name]["data"])
            self.assertTrue(state[name]["reason"])

    def test_not_yet_collected_sections_carry_their_documented_reason(self):
        state = build_user_state()

        for name, reason in NOT_YET_COLLECTED.items():
            self.assertEqual(state[name]["reason"], reason)


class PartialPopulationTests(unittest.TestCase):
    def test_basic_profile_and_questionnaire_from_a_profile_document(self):
        profile_doc = {
            "age": 34,
            "sex": "female",
            "height_cm": 165,
            "weight_kg": 62,
            "bmi": 22.8,
            "daily_sitting_hours": 9,
            "daily_screen_hours": 7,
            "sleep_hours": 6.5,
            "sleep_quality": "fair",
            "daily_steps": 3000,
            "exercise_days": 2,
            "exercise_minutes": 30,
            "work_type": "desk",
        }

        state = build_user_state(profile_doc=profile_doc)

        validate_user_state(state)

        self.assertTrue(state["basic_profile"]["available"])
        self.assertEqual(state["basic_profile"]["data"]["age"], 34)

        self.assertTrue(state["questionnaire"]["available"])
        self.assertEqual(
            state["questionnaire"]["data"]["daily_sitting_hours"], 9
        )

        # Sections with no source at all remain unavailable, independently.
        self.assertFalse(state["physical_assessment"]["available"])
        self.assertFalse(state["nutrition"]["available"])

    def test_a_profile_document_with_only_health_checklist_fields(self):
        profile_doc = {"joint_pain": "yes", "back_neck_pain": "sometimes"}

        state = build_user_state(profile_doc=profile_doc)

        validate_user_state(state)

        self.assertTrue(state["medical_context"]["available"])
        self.assertEqual(
            state["medical_context"]["data"]["self_reported"]["values"][
                "joint_pain"
            ],
            "yes",
        )
        self.assertEqual(
            state["medical_context"]["data"]["confirmed_reports"]["reports"], []
        )

        # No age/sex/etc, and no sitting/screen/etc, so those stay unavailable.
        self.assertFalse(state["basic_profile"]["available"])
        self.assertFalse(state["questionnaire"]["available"])

    def test_confirmed_reports_populate_medical_context_without_a_profile(self):
        confirmed = {
            "reportCount": 1,
            "reports": [
                {
                    "title": "Blood panel",
                    "values": [{"label": "Haemoglobin", "value": 13.2}],
                }
            ],
        }

        state = build_user_state(confirmed_reports_doc=confirmed)

        validate_user_state(state)

        self.assertTrue(state["medical_context"]["available"])
        self.assertIsNone(
            state["medical_context"]["data"]["self_reported"]["values"]
        )
        self.assertEqual(
            len(state["medical_context"]["data"]["confirmed_reports"]["reports"]),
            1,
        )


class PhysicalAssessmentRepresentationTests(unittest.TestCase):
    def test_a_completed_assessment_session_is_represented(self):
        assessment_doc = {
            "protocol_version": "1.0.0",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {"observableDifferenceDeg": 4},
                },
                "ftsst": {"status": "skipped"},
                "balance": {"status": "not_started"},
            },
        }

        state = build_user_state(assessment_doc=assessment_doc)

        validate_user_state(state)

        section = state["physical_assessment"]

        self.assertTrue(section["available"])
        self.assertEqual(section["data"]["tests"]["shoulder"]["status"], "completed")
        self.assertEqual(section["data"]["tests"]["ftsst"]["status"], "skipped")
        self.assertEqual(
            section["data"]["tests"]["balance"]["status"], "not_started"
        )

    def test_completed_test_carries_quality_invalid_reasons_and_attempts(self):
        assessment_doc = {
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {},
                    "quality": {"meanFps": 28, "meanKeypointScore": 0.71},
                    "invalid_reasons": [],
                    "attempts": 2,
                },
                "ftsst": {"status": "not_started"},
                "balance": {"status": "not_started"},
            }
        }

        state = build_user_state(assessment_doc=assessment_doc)

        shoulder = state["physical_assessment"]["data"]["tests"]["shoulder"]

        self.assertEqual(shoulder["quality"]["meanFps"], 28)
        self.assertEqual(shoulder["invalidReasons"], [])
        self.assertEqual(shoulder["attempts"], 2)

    def test_completed_sit_to_stand_preserves_setup_context(self):
        state = build_user_state(
            assessment_doc={
                "tests": {
                    "shoulder": {"status": "not_started"},
                    "ftsst": {
                        "status": "completed",
                        "measurements": {"completionTimeSeconds": 13.84},
                        "setup": {"chairSeatHeightCm": 60, "measuredSide": "left"},
                    },
                    "balance": {"status": "not_started"},
                }
            }
        )

        setup = state["physical_assessment"]["data"]["tests"]["ftsst"]["setup"]
        self.assertEqual(setup["chairSeatHeightCm"], 60)
        self.assertEqual(setup["measuredSide"], "left")

    def test_a_session_with_no_completed_test_is_marked_unavailable(self):
        assessment_doc = {
            "tests": {
                "shoulder": {"status": "invalid"},
                "ftsst": {"status": "skipped"},
                "balance": {"status": "not_started"},
            }
        }

        state = build_user_state(assessment_doc=assessment_doc)

        self.assertFalse(state["physical_assessment"]["available"])
        # The gap is explained, but the recorded statuses are still there for
        # a caller that wants to know what was attempted.
        self.assertEqual(
            state["physical_assessment"]["data"]["tests"]["shoulder"]["status"],
            "invalid",
        )


class ValidationTests(unittest.TestCase):
    def test_a_missing_section_is_rejected(self):
        state = build_user_state()

        del state["safety"]

        with self.assertRaises(UserStateValidationError):
            validate_user_state(state)

    def test_an_unavailable_section_without_a_reason_is_rejected(self):
        state = build_user_state()

        state["nutrition"]["reason"] = None

        with self.assertRaises(UserStateValidationError):
            validate_user_state(state)

    def test_an_available_section_with_no_data_is_rejected(self):
        state = build_user_state()

        state["basic_profile"] = {"available": True, "reason": None, "data": None}

        with self.assertRaises(UserStateValidationError):
            validate_user_state(state)

    def test_a_wrong_schema_version_is_rejected(self):
        state = build_user_state()

        state["schemaVersion"] = "9.9.9"

        with self.assertRaises(UserStateValidationError):
            validate_user_state(state)

    def test_not_a_dict_is_rejected(self):
        with self.assertRaises(UserStateValidationError):
            validate_user_state(["not", "a", "state"])


if __name__ == "__main__":
    unittest.main()
