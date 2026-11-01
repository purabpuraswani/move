import unittest

from need_assessment.assessment import run_need_assessment
from orchestrator.decision import evaluate_specialist_selection
from user_state.schema import build_user_state


def _state(profile=None, assessment=None, confirmed_reports=None):
    state = build_user_state(
        profile_doc=profile,
        assessment_doc=assessment,
        confirmed_reports_doc=confirmed_reports,
    )
    return run_need_assessment(state)


def _assessment(*, shoulder=145, balance=24, include_legacy_ftsst=False):
    tests = {
        "shoulder": {
            "status": "completed",
            "measurements": {
                "left": {"finalElevationDeg": shoulder},
                "right": {"finalElevationDeg": shoulder},
                "observableDifferenceDeg": 0,
            },
        },
        "balance": {
            "status": "completed",
            "measurements": {
                "left": {"attempted": True, "valid": True, "holdDurationSeconds": balance},
                "right": {"attempted": True, "valid": True, "holdDurationSeconds": balance},
            },
        },
    }
    if include_legacy_ftsst:
        tests["ftsst"] = {
            "status": "completed",
            "measurements": {"completionTimeSeconds": 40},
        }
    return {"completed_at": "2026-10-15T00:00:00Z", "tests": tests}


def _selections(state, progress_trigger=None, behaviour_actions=None, progress_context=None):
    needs = state["current_needs"]["data"]
    _, explanations = evaluate_specialist_selection(
        state, needs, progress_trigger, behaviour_actions=behaviour_actions,
        progress_context=progress_context,
    )
    return explanations


class ProfileBasedSelectionTests(unittest.TestCase):
    def test_movement_limitation_selects_physio_only_for_movement_evidence(self):
        state = _state(
            profile={"daily_steps": 7000, "daily_sitting_hours": 4, "exercise_days": 4,
                     "exercise_minutes": 40},
            assessment=_assessment(shoulder=45),
        )
        decisions = _selections(state)
        self.assertEqual(decisions["physio"]["selection_status"], "SELECTED")
        self.assertEqual(decisions["exercise_activity"]["selection_status"], "NOT SELECTED")
        self.assertTrue(decisions["physio"]["evidence_used"])

    def test_movement_related_history_selects_physio_but_requests_assessment_context(self):
        state = _state(profile={"joint_pain": "sometimes"})
        decision = _selections(state)["physio"]
        self.assertIn("CONTEXT REQUIRED", decision["selection_status"])
        self.assertEqual(decision["missing_required_information"], ["details of the current pain or injury and its effect on movement"])
        self.assertFalse(decision["execution_eligibility"])

    def test_nutritional_needs_select_nutrition(self):
        state = _state(profile={"meal_pattern": "skips_meals", "fruit_vegetable_servings": 1,
                                "water_glasses_per_day": 2, "processed_food_frequency": "daily"})
        self.assertEqual(_selections(state)["nutrition"]["selection_status"], "SELECTED")

    def test_confirmed_nutrition_relevant_report_requires_dietary_context(self):
        report = {
            "reports": [{
                "id": "report-1",
                "values": [{"key": "glucose", "label": "Glucose", "category": "lab_result"}],
            }]
        }
        state = _state(confirmed_reports=report)
        decision = _selections(state)["nutrition"]
        self.assertIn("CONTEXT REQUIRED", decision["selection_status"])
        self.assertEqual(decision["missing_required_information"], ["self-reported nutrition profile"])
        self.assertFalse(decision["execution_eligibility"])

    def test_sleep_concerns_select_recovery(self):
        state = _state(profile={"sleep_hours": 4.5, "sleep_quality": "poor"})
        decisions = _selections(state)
        self.assertEqual(decisions["recovery"]["selection_status"], "SELECTED")
        self.assertEqual(decisions["nutrition"]["selection_status"], "NOT SELECTED")

    def test_sedentary_profile_selects_activity_and_behaviour(self):
        state = _state(profile={"daily_steps": 3000, "daily_sitting_hours": 10,
                                "daily_screen_hours": 9, "exercise_days": 0,
                                "exercise_minutes": 0})
        decisions = _selections(state)
        self.assertEqual(decisions["exercise_activity"]["selection_status"], "SELECTED")
        self.assertEqual(decisions["behaviour"]["selection_status"], "SELECTED")

    def test_low_adherence_to_current_plan_selects_behaviour(self):
        state = _state()
        state["behaviour"] = {
            "available": True, "reason": None,
            "data": {"plans": [{"plan_id": "plan-current", "plan_version": 1}]},
        }
        actions = [
            {"plan_id": "plan-current", "status": "completed", "difficulty": "easy"},
            {"plan_id": "plan-current", "status": "skipped", "difficulty": "difficult"},
            {"plan_id": "plan-current", "status": "skipped", "difficulty": "difficult"},
            {"plan_id": "old-plan", "status": "skipped", "difficulty": "difficult"},
        ]
        decision = _selections(state, behaviour_actions=actions)["behaviour"]
        self.assertEqual(decision["selection_status"], "SELECTED")
        self.assertTrue(any("1 of 3" in line for line in decision["evidence_used"]))

    def test_multiple_wellness_needs_select_only_relevant_specialists(self):
        state = _state(
            profile={"daily_steps": 3000, "daily_sitting_hours": 10,
                     "daily_screen_hours": 9, "exercise_days": 0, "exercise_minutes": 0,
                     "sleep_hours": 4.5, "sleep_quality": "poor",
                     "meal_pattern": "skips_meals", "fruit_vegetable_servings": 1,
                     "water_glasses_per_day": 2, "processed_food_frequency": "daily"},
            assessment=_assessment(shoulder=45, balance=3),
        )
        decisions = _selections(state)
        selected = {key for key, item in decisions.items() if item["execution_eligibility"]}
        self.assertEqual(selected, {"physio", "exercise_activity", "nutrition", "recovery", "behaviour"})

    def test_insufficient_profile_does_not_select_or_execute_specialists(self):
        decisions = _selections(_state())
        self.assertFalse(any(item["execution_eligibility"] for item in decisions.values()))
        self.assertTrue(all(item["selection_status"] == "NOT SELECTED" for item in decisions.values()))

    def test_adequate_profile_has_no_unnecessary_specialist_selection(self):
        state = _state(
            profile={"daily_steps": 7000, "daily_sitting_hours": 4, "daily_screen_hours": 4,
                     "exercise_days": 4, "exercise_minutes": 40, "sleep_hours": 7.5,
                     "sleep_quality": "good", "meal_pattern": "regular",
                     "fruit_vegetable_servings": 5, "water_glasses_per_day": 8,
                     "processed_food_frequency": "rarely"},
            assessment=_assessment(),
        )
        self.assertFalse(any(item["execution_eligibility"] for item in _selections(state).values()))

    def test_historical_ftsst_does_not_select_current_physio(self):
        state = _state(assessment={"tests": {"ftsst": {"status": "completed",
                                                          "measurements": {"completionTimeSeconds": 40}}}})
        decisions = _selections(state)
        self.assertEqual(decisions["physio"]["selection_status"], "NOT SELECTED")

    def test_supported_progress_event_selects_progress_and_unknown_event_does_not(self):
        state = _state()
        baseline = _assessment(balance=5)
        current = _assessment(balance=20)
        self.assertEqual(
            _selections(
                state, {"reason": "reassessment completed"},
                progress_context={"baseline_assessment": baseline, "current_assessment": current},
            )["progress"]["selection_status"],
            "SELECTED",
        )
        self.assertEqual(
            _selections(state, {"reason": "unrelated request"})["progress"]["selection_status"],
            "NOT SELECTED",
        )

    def test_progress_event_without_comparable_history_is_context_required(self):
        decision = _selections(
            _state(), {"reason": "exercise activity recorded"}
        )["progress"]
        self.assertIn("CONTEXT REQUIRED", decision["selection_status"])
        self.assertFalse(decision["execution_eligibility"])


if __name__ == "__main__":
    unittest.main()
