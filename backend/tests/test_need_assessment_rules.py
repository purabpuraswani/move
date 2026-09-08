import unittest

from need_assessment.rules import (
    SHOULDER_HIGH_NEED_BELOW_DEG,
    SHOULDER_MEDIUM_NEED_BELOW_DEG,
    BALANCE_HIGH_NEED_BELOW_SECONDS,
    BALANCE_MEDIUM_NEED_BELOW_SECONDS,
    FTSST_HIGH_NEED_ABOVE_SECONDS,
    FTSST_MEDIUM_NEED_ABOVE_SECONDS,
    assess_behaviour_need,
    assess_exercise_need,
    assess_functional_movement_need,
    assess_mobility_need,
    assess_nutrition_need,
    assess_safety_status,
    assess_stability_need,
)
from user_state.schema import build_user_state


def shoulder_state(left_deg, right_deg, difference=None):
    return build_user_state(
        assessment_doc={
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {
                        "left": {"finalElevationDeg": left_deg},
                        "right": {"finalElevationDeg": right_deg},
                        "observableDifferenceDeg": difference,
                    },
                },
                "ftsst": {"status": "not_started"},
                "balance": {"status": "not_started"},
            }
        }
    )


def balance_state(left_seconds, right_seconds):
    def side(seconds):
        if seconds is None:
            return {"attempted": False}

        return {"attempted": True, "valid": True, "holdDurationSeconds": seconds}

    return build_user_state(
        assessment_doc={
            "tests": {
                "shoulder": {"status": "not_started"},
                "ftsst": {"status": "not_started"},
                "balance": {
                    "status": "completed",
                    "measurements": {
                        "left": side(left_seconds),
                        "right": side(right_seconds),
                        "observableDifferenceMs": None,
                    },
                },
            }
        }
    )


def ftsst_state(seconds, detected=5, required=5):
    return build_user_state(
        assessment_doc={
            "tests": {
                "shoulder": {"status": "not_started"},
                "ftsst": {
                    "status": "completed",
                    "measurements": {
                        "completionTimeSeconds": seconds,
                        "repetitionsDetected": detected,
                        "requiredRepetitions": required,
                    },
                },
                "balance": {"status": "not_started"},
            }
        }
    )


def questionnaire_state(**fields):
    return build_user_state(profile_doc=fields)


class MobilityNeedTests(unittest.TestCase):
    def test_no_assessment_is_not_assessed(self):
        state = build_user_state()
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")
        self.assertIsNone(entry["score"])

    def test_low_elevation_on_both_sides_is_high_need(self):
        state = shoulder_state(SHOULDER_HIGH_NEED_BELOW_DEG - 20, SHOULDER_HIGH_NEED_BELOW_DEG - 10)
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "HIGH")
        self.assertTrue(entry["evidence"])

    def test_moderate_elevation_is_medium_need(self):
        midpoint = (SHOULDER_HIGH_NEED_BELOW_DEG + SHOULDER_MEDIUM_NEED_BELOW_DEG) / 2
        state = shoulder_state(midpoint, midpoint)
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "MEDIUM")

    def test_full_elevation_is_low_need(self):
        state = shoulder_state(150, 150)
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "LOW")

    def test_notable_asymmetry_is_called_out_as_evidence(self):
        state = shoulder_state(150, 150, difference=25)
        entry = assess_mobility_need(state)

        self.assertTrue(any("Difference" in item or "difference" in item for item in entry["evidence"]))

    def test_only_one_usable_side_lowers_confidence(self):
        state = shoulder_state(30, None)
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "MEDIUM")

    def test_an_invalid_test_status_is_not_assessed(self):
        state = shoulder_state(30, 30)
        state["physical_assessment"]["data"]["tests"]["shoulder"]["status"] = "invalid"
        entry = assess_mobility_need(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")


class StabilityNeedTests(unittest.TestCase):
    def test_no_assessment_is_not_assessed(self):
        entry = assess_stability_need(build_user_state())
        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_short_hold_is_high_need(self):
        state = balance_state(BALANCE_HIGH_NEED_BELOW_SECONDS - 2, BALANCE_HIGH_NEED_BELOW_SECONDS - 1)
        entry = assess_stability_need(state)

        self.assertEqual(entry["level"], "HIGH")

    def test_moderate_hold_is_medium_need(self):
        midpoint = (BALANCE_HIGH_NEED_BELOW_SECONDS + BALANCE_MEDIUM_NEED_BELOW_SECONDS) / 2
        state = balance_state(midpoint, midpoint)
        entry = assess_stability_need(state)

        self.assertEqual(entry["level"], "MEDIUM")

    def test_long_hold_is_low_need(self):
        state = balance_state(25, 28)
        entry = assess_stability_need(state)

        self.assertEqual(entry["level"], "LOW")

    def test_only_one_side_attempted_lowers_confidence(self):
        state = balance_state(3, None)
        entry = assess_stability_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "MEDIUM")

    def test_neither_side_valid_is_not_assessed(self):
        state = balance_state(None, None)
        entry = assess_stability_need(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")


class FunctionalMovementNeedTests(unittest.TestCase):
    def test_no_assessment_is_not_assessed(self):
        entry = assess_functional_movement_need(build_user_state())
        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_a_long_completion_time_is_high_need(self):
        state = ftsst_state(FTSST_HIGH_NEED_ABOVE_SECONDS + 5)
        entry = assess_functional_movement_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "HIGH")

    def test_a_moderate_completion_time_is_medium_need(self):
        midpoint = (FTSST_MEDIUM_NEED_ABOVE_SECONDS + FTSST_HIGH_NEED_ABOVE_SECONDS) / 2
        state = ftsst_state(midpoint)
        entry = assess_functional_movement_need(state)

        self.assertEqual(entry["level"], "MEDIUM")

    def test_a_short_completion_time_is_low_need(self):
        state = ftsst_state(6)
        entry = assess_functional_movement_need(state)

        self.assertEqual(entry["level"], "LOW")

    def test_partial_repetitions_are_named_in_evidence(self):
        state = ftsst_state(FTSST_HIGH_NEED_ABOVE_SECONDS + 1, detected=3, required=5)
        entry = assess_functional_movement_need(state)

        self.assertTrue(any("3 of 5" in item for item in entry["evidence"]))


class BehaviourNeedTests(unittest.TestCase):
    def test_no_questionnaire_is_not_assessed(self):
        entry = assess_behaviour_need(build_user_state())
        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_high_sitting_and_low_exercise_is_high_need(self):
        state = questionnaire_state(
            daily_sitting_hours=10,
            daily_screen_hours=9,
            exercise_days=0,
            exercise_minutes=0,
        )
        entry = assess_behaviour_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "HIGH")

    def test_active_lifestyle_is_low_need(self):
        state = questionnaire_state(
            daily_sitting_hours=4,
            daily_screen_hours=3,
            exercise_days=5,
            exercise_minutes=45,
        )
        entry = assess_behaviour_need(state)

        self.assertEqual(entry["level"], "LOW")

    def test_only_sitting_hours_known_still_produces_a_result(self):
        state = questionnaire_state(daily_sitting_hours=9)
        entry = assess_behaviour_need(state)

        self.assertIn(entry["level"], ("LOW", "MEDIUM", "HIGH"))
        self.assertEqual(entry["confidence"], "MEDIUM")


class NutritionNeedTests(unittest.TestCase):
    def test_nutrition_is_always_not_assessed_in_phase_1(self):
        entry = assess_nutrition_need(build_user_state())

        self.assertEqual(entry["level"], "NOT_ASSESSED")
        self.assertIsNone(entry["score"])
        self.assertTrue(entry["evidence"])

    def test_nutrition_is_not_assessed_even_with_other_data_present(self):
        state = questionnaire_state(daily_sitting_hours=10, exercise_days=0)
        entry = assess_nutrition_need(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")

    # --- Phase 4: real nutrition-need logic once the new questions are
    # answered. The two tests above stay untouched and still pass, because
    # questionnaire_state() there never sets any of these four fields.

    def test_nutrition_need_high_when_all_factors_triggered(self):
        state = questionnaire_state(
            meal_pattern="skips_meals",
            fruit_vegetable_servings=1,
            water_glasses_per_day=2,
            processed_food_frequency="daily",
        )
        entry = assess_nutrition_need(state)

        self.assertEqual(entry["level"], "HIGH")
        self.assertEqual(entry["confidence"], "HIGH")
        self.assertEqual(len(entry["evidence"]), 4)

    def test_nutrition_need_low_when_no_factors_triggered(self):
        state = questionnaire_state(
            meal_pattern="regular",
            fruit_vegetable_servings=5,
            water_glasses_per_day=8,
            processed_food_frequency="rarely",
        )
        entry = assess_nutrition_need(state)

        self.assertEqual(entry["level"], "LOW")
        self.assertEqual(entry["confidence"], "HIGH")

    def test_nutrition_need_medium_with_partial_factors_triggered(self):
        state = questionnaire_state(
            meal_pattern="regular",
            fruit_vegetable_servings=1,
            water_glasses_per_day=2,
            processed_food_frequency="rarely",
        )
        entry = assess_nutrition_need(state)

        self.assertEqual(entry["level"], "MEDIUM")

    def test_nutrition_need_confidence_medium_with_partial_answers(self):
        state = questionnaire_state(fruit_vegetable_servings=1)
        entry = assess_nutrition_need(state)

        self.assertNotEqual(entry["level"], "NOT_ASSESSED")
        self.assertEqual(entry["confidence"], "MEDIUM")

    def test_nutrition_need_unrecognized_string_values_not_counted(self):
        state = questionnaire_state(
            meal_pattern="sometimes three meals",
            processed_food_frequency="not sure",
        )
        entry = assess_nutrition_need(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_nutrition_need_score_is_the_triggered_fraction(self):
        state = questionnaire_state(
            fruit_vegetable_servings=1, water_glasses_per_day=8
        )
        entry = assess_nutrition_need(state)

        self.assertAlmostEqual(entry["score"], 0.5)


class SafetyStatusTests(unittest.TestCase):
    def test_safety_status_is_always_not_assessed_in_phase_1(self):
        entry = assess_safety_status(build_user_state())
        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_safety_status_stays_not_assessed_even_with_medical_context(self):
        state = build_user_state(profile_doc={"joint_pain": "yes"})
        entry = assess_safety_status(state)

        self.assertEqual(entry["level"], "NOT_ASSESSED")
        self.assertTrue(
            any("medical" in item.lower() for item in entry["evidence"])
        )


class ExerciseNeedTests(unittest.TestCase):
    def _entries(self, state):
        from need_assessment.rules import (
            assess_behaviour_need as b,
            assess_functional_movement_need as f,
            assess_mobility_need as m,
            assess_stability_need as s,
        )

        return dict(mobility=m(state), stability=s(state), functional_movement=f(state), behaviour=b(state))

    def test_nothing_available_is_not_assessed(self):
        state = build_user_state()
        entry = assess_exercise_need(state, **self._entries(state))

        self.assertEqual(entry["level"], "NOT_ASSESSED")

    def test_a_high_physical_need_makes_exercise_need_high(self):
        state = shoulder_state(20, 20)
        entry = assess_exercise_need(state, **self._entries(state))

        self.assertEqual(entry["level"], "HIGH")
        self.assertTrue(entry["evidence"])

    def test_low_everything_is_low_exercise_need(self):
        state = build_user_state(
            profile_doc={
                "daily_sitting_hours": 4,
                "exercise_days": 5,
                "exercise_minutes": 45,
            },
            assessment_doc={
                "tests": {
                    "shoulder": {
                        "status": "completed",
                        "measurements": {
                            "left": {"finalElevationDeg": 150},
                            "right": {"finalElevationDeg": 150},
                        },
                    },
                    "ftsst": {
                        "status": "completed",
                        "measurements": {"completionTimeSeconds": 6},
                    },
                    "balance": {
                        "status": "completed",
                        "measurements": {
                            "left": {"attempted": True, "valid": True, "holdDurationSeconds": 28},
                            "right": {"attempted": True, "valid": True, "holdDurationSeconds": 27},
                        },
                    },
                }
            },
        )
        entry = assess_exercise_need(state, **self._entries(state))

        self.assertEqual(entry["level"], "LOW")


if __name__ == "__main__":
    unittest.main()
