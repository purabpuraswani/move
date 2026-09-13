"""Unit tests for the genuine 6-specialist agent system in MoveWell-AI:
1. Exercise & Physical Activity
2. Physiotherapy & Movement
3. Nutrition & Lifestyle
4. Recovery & Care
5. Behaviour & Adherence
6. Safety & Clinical Escalation
"""

import unittest
from orchestrator.decision import (
    decide_exercise_activity_required,
    decide_recovery_required,
    decide_physio_required,
    decide_behaviour_required,
    decide_nutrition_required,
)
from workflow.response import (
    build_specialists_team,
    serialise_workflow_state,
    never_run_response,
)


class TestSixSpecialistsSystem(unittest.TestCase):
    def test_exercise_activity_decision_low_steps(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "daily_steps": 3500,
                    "daily_sitting_hours": 6,
                    "exercise_days": 2,
                }
            }
        }
        decision = decide_exercise_activity_required(user_state)
        self.assertTrue(decision["exercise_activity_required"])
        self.assertTrue(decision["evaluated"])
        self.assertIn("Daily steps: 3500", decision["evidence"])
        self.assertIn("5,000 steps", decision["reason"])

    def test_exercise_activity_decision_high_sitting(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "daily_steps": 7000,
                    "daily_sitting_hours": 9,
                    "exercise_days": 3,
                }
            }
        }
        decision = decide_exercise_activity_required(user_state)
        self.assertTrue(decision["exercise_activity_required"])
        self.assertTrue(decision["evaluated"])
        self.assertIn("Daily sitting: 9 hours", decision["evidence"])

    def test_exercise_activity_decision_active_lifestyle(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "daily_steps": 8500,
                    "daily_sitting_hours": 5,
                    "exercise_days": 4,
                }
            }
        }
        decision = decide_exercise_activity_required(user_state)
        self.assertFalse(decision["exercise_activity_required"])
        self.assertTrue(decision["evaluated"])

    def test_recovery_decision_low_sleep(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "sleep_duration_hours": 5.0,
                    "sleep_quality": "poor",
                }
            }
        }
        decision = decide_recovery_required(user_state)
        self.assertTrue(decision["recovery_required"])
        self.assertTrue(decision["evaluated"])
        self.assertIn("recommended 7-9 hours", decision["reason"])

    def test_recovery_decision_good_sleep(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "sleep_duration_hours": 7.5,
                    "sleep_quality": "good",
                }
            }
        }
        decision = decide_recovery_required(user_state)
        self.assertFalse(decision["recovery_required"])
        self.assertTrue(decision["evaluated"])

    def test_build_specialists_team_structure(self):
        user_state = {
            "physical_assessment": {"available": True, "data": {"status": "COMPLETE"}},
            "current_needs": {
                "available": True,
                "data": {
                    "exercise_need": {"level": "HIGH"},
                    "nutrition_need": {"level": "LOW"},
                    "behaviour_need": {"level": "NOT_ASSESSED"},
                },
            },
            "exercise_history": {
                "available": True,
                "data": {
                    "plans": [
                        {
                            "exercises": [{"name": "Wall Slide", "exercise_id": "wall_slide"}],
                        }
                    ]
                },
            },
        }

        team = build_specialists_team(user_state, safety_status="ALLOW", safety_result={"status": "ALLOW"})
        self.assertEqual(len(team), 6)

        ids = [s["id"] for s in team]
        self.assertIn("exercise_activity", ids)
        self.assertIn("physio", ids)
        self.assertIn("nutrition", ids)
        self.assertIn("recovery", ids)
        self.assertIn("behaviour", ids)
        self.assertIn("safety", ids)

        # Physio should be ACTIVE because plan is available
        physio = next(s for s in team if s["id"] == "physio")
        self.assertEqual(physio["status"], "ACTIVE")
        self.assertTrue(physio["active"])

        # Safety should be ALLOW because safety gate passed
        safety = next(s for s in team if s["id"] == "safety")
        self.assertEqual(safety["status"], "ALLOW")
        self.assertTrue(safety["active"])

    def test_serialise_workflow_state_contains_specialists_team(self):
        user_state = {
            "physical_assessment": {"available": True, "data": {"status": "COMPLETE"}},
        }
        response = serialise_workflow_state(user_state)
        self.assertIn("specialists_team", response)
        self.assertEqual(len(response["specialists_team"]), 6)

    def test_never_run_response_contains_specialists_team(self):
        response = never_run_response()
        self.assertIn("specialists_team", response)
        self.assertEqual(len(response["specialists_team"]), 6)
        # All should be NOT_ASSESSED initially
        for spec in response["specialists_team"]:
            self.assertEqual(spec["status"], "NOT_ASSESSED")


if __name__ == "__main__":
    unittest.main()
