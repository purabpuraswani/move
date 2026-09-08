import unittest

from need_assessment.assessment import (
    apply_need_profile,
    assemble_need_profile,
    run_need_assessment,
)
from need_assessment.schema import NEED_DIMENSIONS, validate_need_profile
from user_state.schema import UserStateValidationError, build_user_state, validate_user_state


def complete_user_state(**profile_overrides):
    profile_doc = {
        "age": 45,
        "sex": "male",
        "daily_sitting_hours": 9,
        "daily_screen_hours": 8,
        "sleep_hours": 6,
        "sleep_quality": "fair",
        "daily_steps": 2500,
        "exercise_days": 1,
        "exercise_minutes": 20,
        "work_type": "desk",
        **profile_overrides,
    }

    assessment_doc = {
        "protocol_version": "1.0.0",
        "completed_at": "2026-01-01T00:00:00+00:00",
        "tests": {
            "shoulder": {
                "status": "completed",
                "measurements": {
                    "left": {"finalElevationDeg": 40},
                    "right": {"finalElevationDeg": 45},
                    "observableDifferenceDeg": 5,
                },
            },
            "ftsst": {
                "status": "completed",
                "measurements": {
                    "completionTimeSeconds": 18,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                },
            },
            "balance": {
                "status": "completed",
                "measurements": {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": 4},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": 6},
                    "observableDifferenceMs": 2000,
                },
            },
        },
    }

    return build_user_state(profile_doc=profile_doc, assessment_doc=assessment_doc)


class CompleteAssessmentTests(unittest.TestCase):
    def test_a_need_profile_is_generated_with_all_dimensions_populated(self):
        state = complete_user_state()
        profile = assemble_need_profile(state)

        validate_need_profile(profile)

        for dimension in NEED_DIMENSIONS:
            self.assertIn(dimension, profile)
            self.assertIn(profile[dimension]["level"], ("LOW", "MEDIUM", "HIGH", "NOT_ASSESSED"))

        # This fixture is deliberately built to show real need: low elevation,
        # a short balance hold, a slow sit-to-stand, and a sedentary
        # questionnaire — all three physical dimensions and behaviour should
        # come back assessed (not NOT_ASSESSED), with evidence attached.
        for dimension in ("mobility_need", "stability_need", "functional_movement_need", "behaviour_need"):
            self.assertNotEqual(profile[dimension]["level"], "NOT_ASSESSED")
            self.assertTrue(profile[dimension]["evidence"])

        # Nutrition and safety have no source in this application yet.
        self.assertEqual(profile["nutrition_need"]["level"], "NOT_ASSESSED")
        self.assertEqual(profile["safety_status"]["level"], "NOT_ASSESSED")

    def test_overall_summary_names_the_high_dimensions(self):
        state = complete_user_state()
        profile = assemble_need_profile(state)

        summary = profile["overallSummary"]

        self.assertIn("stability_need", summary["dimensionsAtHigh"] + summary["dimensionsAtMedium"])

    def test_metadata_carries_workflow_and_request_ids(self):
        profile = assemble_need_profile(complete_user_state())

        self.assertTrue(profile["metadata"]["workflowId"])
        self.assertTrue(profile["metadata"]["requestId"])

    def test_a_given_workflow_id_is_carried_through(self):
        profile = assemble_need_profile(
            complete_user_state(), workflow_id="wf_fixed", request_id="req_fixed"
        )

        self.assertEqual(profile["metadata"]["workflowId"], "wf_fixed")
        self.assertEqual(profile["metadata"]["requestId"], "req_fixed")

    def test_workflow_id_and_request_id_must_be_given_together(self):
        with self.assertRaises(ValueError):
            assemble_need_profile(complete_user_state(), workflow_id="wf_only")


class ApplyNeedProfileTests(unittest.TestCase):
    def test_current_needs_is_populated_on_the_returned_state(self):
        state = complete_user_state()
        profile = assemble_need_profile(state)
        updated = apply_need_profile(state, profile)

        validate_user_state(updated)

        self.assertTrue(updated["current_needs"]["available"])
        self.assertEqual(updated["current_needs"]["data"], profile)

    def test_the_original_state_is_not_mutated(self):
        state = complete_user_state()
        profile = assemble_need_profile(state)
        apply_need_profile(state, profile)

        self.assertFalse(state["current_needs"]["available"])

    def test_run_need_assessment_does_both_steps(self):
        state = complete_user_state()
        updated = run_need_assessment(state)

        self.assertTrue(updated["current_needs"]["available"])
        self.assertIn("mobility_need", updated["current_needs"]["data"])


class MissingAndPartialDataTests(unittest.TestCase):
    def test_a_brand_new_user_state_does_not_crash_and_is_all_not_assessed(self):
        state = build_user_state()
        profile = assemble_need_profile(state)

        validate_need_profile(profile)

        for dimension in NEED_DIMENSIONS:
            self.assertEqual(profile[dimension]["level"], "NOT_ASSESSED")

        self.assertEqual(profile["overallSummary"]["assessedCount"], 0)
        self.assertEqual(profile["overallSummary"]["notAssessedCount"], len(NEED_DIMENSIONS))

    def test_questionnaire_only_still_produces_a_profile(self):
        state = build_user_state(profile_doc={"daily_sitting_hours": 9, "exercise_days": 1})
        profile = assemble_need_profile(state)

        validate_need_profile(profile)
        self.assertNotEqual(profile["behaviour_need"]["level"], "NOT_ASSESSED")
        self.assertEqual(profile["mobility_need"]["level"], "NOT_ASSESSED")

    def test_assessment_only_still_produces_a_profile(self):
        state = build_user_state(
            assessment_doc={
                "tests": {
                    "shoulder": {
                        "status": "completed",
                        "measurements": {
                            "left": {"finalElevationDeg": 20},
                            "right": {"finalElevationDeg": 20},
                        },
                    },
                    "ftsst": {"status": "skipped"},
                    "balance": {"status": "not_started"},
                }
            }
        )

        profile = assemble_need_profile(state)

        validate_need_profile(profile)
        self.assertEqual(profile["mobility_need"]["level"], "HIGH")
        self.assertEqual(profile["behaviour_need"]["level"], "NOT_ASSESSED")

    def test_a_malformed_user_state_is_rejected_rather_than_silently_processed(self):
        state = build_user_state()
        del state["safety"]

        with self.assertRaises(UserStateValidationError):
            assemble_need_profile(state)

    def test_a_non_numeric_measurement_does_not_crash_the_assessment(self):
        state = build_user_state(
            assessment_doc={
                "tests": {
                    "shoulder": {
                        "status": "completed",
                        "measurements": {
                            "left": {"finalElevationDeg": "not-a-number"},
                            "right": {"finalElevationDeg": None},
                        },
                    },
                    "ftsst": {"status": "not_started"},
                    "balance": {"status": "not_started"},
                }
            }
        )

        profile = assemble_need_profile(state)

        self.assertEqual(profile["mobility_need"]["level"], "NOT_ASSESSED")


class MedicalContextBoundaryTests(unittest.TestCase):
    def test_unconfirmed_reports_never_reach_the_need_assessment(self):
        # confirmed_reports_doc is what reports/store.py's
        # confirmed_values_for_user() returns — only ever confirmed values.
        # There is no code path in user_state.schema or need_assessment that
        # reads an unconfirmed candidate, so this test documents the
        # boundary at the one place data enters: build_user_state() is never
        # given anything but already-confirmed report data.
        confirmed = {"reportCount": 1, "reports": [{"title": "Blood panel", "values": []}]}
        state = build_user_state(confirmed_reports_doc=confirmed)

        profile = assemble_need_profile(state)

        # No dimension derives a level from medical_context content in Phase 1.
        for dimension in NEED_DIMENSIONS:
            self.assertNotIn("Blood panel", " ".join(profile[dimension]["evidence"]))

    def test_confirmed_medical_context_does_not_change_any_need_level(self):
        base_state = complete_user_state()
        base_profile = assemble_need_profile(base_state, workflow_id="wf_x", request_id="req_x")

        confirmed = {"reportCount": 1, "reports": [{"title": "Blood panel", "values": []}]}
        state_with_medical = complete_user_state()
        state_with_medical["medical_context"] = build_user_state(
            confirmed_reports_doc=confirmed
        )["medical_context"]

        profile_with_medical = assemble_need_profile(
            state_with_medical, workflow_id="wf_x", request_id="req_x"
        )

        for dimension in NEED_DIMENSIONS:
            self.assertEqual(
                base_profile[dimension]["level"], profile_with_medical[dimension]["level"]
            )


class DeterminismTests(unittest.TestCase):
    def test_identical_input_produces_identical_dimension_results(self):
        state = complete_user_state()

        first = assemble_need_profile(state, workflow_id="wf_1", request_id="req_1")
        second = assemble_need_profile(state, workflow_id="wf_1", request_id="req_1")

        for dimension in NEED_DIMENSIONS:
            self.assertEqual(first[dimension], second[dimension])

        self.assertEqual(first["safety_status"], second["safety_status"])
        self.assertEqual(first["overallSummary"], second["overallSummary"])


if __name__ == "__main__":
    unittest.main()
