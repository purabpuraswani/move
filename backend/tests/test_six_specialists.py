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
        # The reason names this project's own marker. It deliberately no
        # longer states a sleep duration as a physiological requirement:
        # that claim had no source in this codebase.
        self.assertIn("6-hour marker", decision["reason"])
        self.assertNotIn("recommended 7-9 hours", decision["reason"])

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

        # A historical plan alone is not current movement evidence.
        physio = next(s for s in team if s["id"] == "physio")
        self.assertEqual(physio["status"], "NOT_ASSESSED")
        self.assertFalse(physio["active"])

        # Safety should be ALLOW because safety gate passed
        safety = next(s for s in team if s["id"] == "safety")
        self.assertEqual(safety["status"], "ALLOW")
        self.assertTrue(safety["active"])

    def test_persisted_plan_does_not_activate_physio_without_current_movement_need(self):
        user_state = {
            "current_needs": {
                "available": True,
                "data": {
                    "mobility_need": {"level": "LOW"},
                    "stability_need": {"level": "LOW"},
                    "functional_movement_need": {"level": "LOW"},
                },
            },
            "exercise_history": {
                "available": True,
                "data": {"plans": [{"exercise_ids": ["wall-sit"]}]},
            },
        }

        physio = next(
            specialist
            for specialist in build_specialists_team(user_state)
            if specialist["id"] == "physio"
        )

        self.assertEqual(physio["status"], "EVALUATED_NOT_REQUIRED")
        self.assertFalse(physio["active"])

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

    def test_inactive_specialists_use_not_activated_state_not_static_clinical_copy(self):
        user_state = {
            "questionnaire": {
                "data": {
                    "daily_steps": 8500,
                    "daily_sitting_hours": 5,
                    "exercise_days": 4,
                    "sleep_duration_hours": 7.5,
                    "sleep_quality": "good",
                    "daily_activity": "active",
                }
            }
        }

        team = build_specialists_team(user_state, safety_status="ALLOW", safety_result={"status": "ALLOW"})
        behaviour = next(s for s in team if s["id"] == "behaviour")
        recovery = next(s for s in team if s["id"] == "recovery")

        self.assertEqual(behaviour["status"], "NOT_ASSESSED")
        self.assertNotIn("standard guidelines", (behaviour["reason"] or "").lower())
        self.assertNotIn("no habit intervention needed", (behaviour["reason"] or "").lower())
        self.assertTrue("not activated" in (behaviour["status_label"] or "").lower() or "not yet evaluated" in (behaviour["status_label"] or "").lower())

        self.assertIn(recovery["status"], ("NOT_ASSESSED", "EVALUATED_NOT_REQUIRED"))
        self.assertNotIn("standard guidelines", (recovery["reason"] or "").lower())
        self.assertNotIn("no specific recommendations are currently available", (recovery["reason"] or "").lower())
        self.assertTrue("not activated" in (recovery["status_label"] or "").lower())


if __name__ == "__main__":
    unittest.main()
