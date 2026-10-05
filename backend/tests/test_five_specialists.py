"""The five user-facing specialists, and the domain decisions behind them.

MoveWell's internal domain modules are not its user-facing specialists. The
product presents exactly five — Exercise & Movement, Nutrition & Lifestyle,
Behaviour & Adherence, Recovery & Care, and Safety & Practitioner
Recommendation — and this module checks both halves of that: the selection
rules still behave as the domain logic says they should, and the team the
API returns is exactly those five, in that order, with the two removed
specialists (Exercise & Physical Activity, Physiotherapy & Movement) and the
renamed Safety card gone from the user-facing surface.
"""

import unittest

from orchestration.specialists import (
    BEHAVIOUR_ADHERENCE,
    EXERCISE_MOVEMENT,
    NUTRITION_LIFESTYLE,
    RECOVERY_CARE,
    SAFETY_PRACTITIONER,
    SPECIALIST_ORDER,
    canonical_id,
)
from orchestrator.decision import (
    decide_behaviour_required,
    decide_exercise_activity_required,
    decide_nutrition_required,
    decide_physio_required,
    decide_recovery_required,
)
from workflow.response import (
    build_specialists_team,
    never_run_response,
    serialise_workflow_state,
)


class DomainSelectionTests(unittest.TestCase):
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

    def test_movement_decision_is_evidence_driven_not_plan_driven(self):
        decision = decide_physio_required(
            {
                "mobility_need": {"level": "LOW"},
                "stability_need": {"level": "LOW"},
                "functional_movement_need": {"level": "LOW"},
            },
            exercise_plan_exists=True,
        )

        self.assertFalse(decision["physio_required"])
        self.assertEqual(decision["selection_mode"], None)


class FiveSpecialistTeamTests(unittest.TestCase):
    def test_team_structure(self):
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
                            "exercises": [
                                {"name": "Wall Slide", "exercise_id": "wall_slide"}
                            ],
                        }
                    ]
                },
            },
        }

        team = build_specialists_team(
            user_state, safety_status="ALLOW", safety_result={"status": "ALLOW"}
        )
        self.assertEqual(len(team), 5)
        self.assertEqual([card["id"] for card in team], list(SPECIALIST_ORDER))

        ids = [card["id"] for card in team]
        self.assertEqual(
            ids,
            [
                EXERCISE_MOVEMENT,
                NUTRITION_LIFESTYLE,
                BEHAVIOUR_ADHERENCE,
                RECOVERY_CARE,
                SAFETY_PRACTITIONER,
            ],
        )

        # A historical plan alone is not current movement evidence, and no
        # physical need dimension was measured here at all — so the honest
        # state is "not assessed", not "assessed and fine".
        movement = next(card for card in team if card["id"] == EXERCISE_MOVEMENT)
        self.assertEqual(movement["status"], "NOT_ASSESSED")
        self.assertFalse(movement["active"])
        self.assertTrue(movement["plan_included"])

        # Safety should be ALLOW because the gate passed.
        safety = next(card for card in team if card["id"] == SAFETY_PRACTITIONER)
        self.assertEqual(safety["status"], "ALLOW")
        self.assertTrue(safety["active"])

    def test_persisted_plan_does_not_activate_movement_without_current_need(self):
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

        movement = next(
            specialist
            for specialist in build_specialists_team(user_state)
            if specialist["id"] == EXERCISE_MOVEMENT
        )

        self.assertEqual(movement["status"], "EVALUATED_NOT_REQUIRED")
        self.assertFalse(movement["active"])
        # The plan is still shown; only the selection status says otherwise.
        self.assertTrue(movement["plan_included"])

    def test_serialise_workflow_state_contains_the_five_specialists(self):
        user_state = {
            "physical_assessment": {"available": True, "data": {"status": "COMPLETE"}},
        }
        response = serialise_workflow_state(user_state)
        self.assertIn("specialists_team", response)
        self.assertEqual(len(response["specialists_team"]), 5)
        self.assertEqual(len(response["unified_plan"]["specialists"]), 5)

    def test_never_run_response_contains_the_five_specialists(self):
        response = never_run_response()
        self.assertIn("specialists_team", response)
        self.assertEqual(len(response["specialists_team"]), 5)
        # All should be NOT_ASSESSED initially.
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

        team = build_specialists_team(
            user_state, safety_status="ALLOW", safety_result={"status": "ALLOW"}
        )
        behaviour = next(card for card in team if card["id"] == BEHAVIOUR_ADHERENCE)
        recovery = next(card for card in team if card["id"] == RECOVERY_CARE)

        self.assertEqual(behaviour["status"], "NOT_ASSESSED")
        self.assertNotIn("standard guidelines", (behaviour["reason"] or "").lower())
        self.assertNotIn(
            "no habit intervention needed", (behaviour["reason"] or "").lower()
        )

        self.assertIn(recovery["status"], ("NOT_ASSESSED", "EVALUATED_NOT_REQUIRED"))
        self.assertNotIn("standard guidelines", (recovery["reason"] or "").lower())
        self.assertNotIn(
            "no specific recommendations are currently available",
            (recovery["reason"] or "").lower(),
        )


class LegacyIdTests(unittest.TestCase):
    def test_every_retired_id_resolves_to_one_of_the_five(self):
        for legacy, expected in (
            ("physio", EXERCISE_MOVEMENT),
            ("exercise_activity", EXERCISE_MOVEMENT),
            ("exercise", EXERCISE_MOVEMENT),
            ("nutrition", NUTRITION_LIFESTYLE),
            ("behaviour", BEHAVIOUR_ADHERENCE),
            ("behavior", BEHAVIOUR_ADHERENCE),
            ("recovery", RECOVERY_CARE),
            ("safety", SAFETY_PRACTITIONER),
        ):
            self.assertEqual(canonical_id(legacy), expected)

    def test_an_unknown_id_is_not_guessed_at(self):
        self.assertIsNone(canonical_id("cardiologist"))
        self.assertIsNone(canonical_id(None))
        self.assertIsNone(canonical_id(""))


if __name__ == "__main__":
    unittest.main()
