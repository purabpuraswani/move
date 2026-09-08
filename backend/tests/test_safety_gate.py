import unittest

from safety.gate import SafetyEvaluationError, evaluate_safety
from safety.schema import validate_safety_result


def _exercise_candidate(id_, difficulty="beginner"):
    return {"id": id_, "agent": "physio", "type": "exercise", "difficulty": difficulty}


def _confirmed_medical_context():
    return {"source": "user_confirmed_medical_report", "reports": [{"report_id": "r1"}]}


class AllowTests(unittest.TestCase):
    def test_no_medical_context_no_high_safety_status_allows(self):
        result = evaluate_safety(candidate_recommendations=[_exercise_candidate("chair-sit-to-stand")])
        validate_safety_result(result)
        self.assertEqual(result["status"], "ALLOW")
        self.assertEqual(result["blocked_recommendation_ids"], [])
        self.assertEqual(result["modified_recommendation_ids"], [])
        self.assertFalse(result["requires_referral"])


class ModifyTests(unittest.TestCase):
    def test_confirmed_medical_context_with_beginner_only_modifies(self):
        result = evaluate_safety(
            confirmed_medical_context=_confirmed_medical_context(),
            candidate_recommendations=[_exercise_candidate("chair-sit-to-stand", "beginner")],
        )
        validate_safety_result(result)
        self.assertEqual(result["status"], "MODIFY")
        self.assertEqual(result["modified_recommendation_ids"], ["chair-sit-to-stand"])
        self.assertIn("add_medical_disclaimer", result["actions"])
        self.assertEqual(result["blocked_recommendation_ids"], [])


class PauseTests(unittest.TestCase):
    def test_confirmed_medical_context_with_above_ceiling_difficulty_pauses(self):
        result = evaluate_safety(
            confirmed_medical_context=_confirmed_medical_context(),
            candidate_recommendations=[
                _exercise_candidate("wall-sit", "intermediate"),
                _exercise_candidate("chair-sit-to-stand", "beginner"),
            ],
        )
        validate_safety_result(result)
        self.assertEqual(result["status"], "PAUSE")
        self.assertEqual(result["blocked_recommendation_ids"], ["wall-sit"])
        self.assertFalse(result["requires_referral"])


class ReferTests(unittest.TestCase):
    def test_safety_status_high_refers_and_blocks_everything(self):
        # This uses the Safety Gate's own supported rule directly — it
        # does not invent a clinical scenario. need_assessment.rules'
        # assess_safety_status() cannot itself produce HIGH today (see
        # safety/rules.py's docstring); this test exercises the gate's
        # real, documented handling of that Need Profile field regardless
        # of how it was populated.
        result = evaluate_safety(
            need_profile={"safety_status": {"level": "HIGH", "evidence": ["fixture evidence"]}},
            candidate_recommendations=[_exercise_candidate("chair-sit-to-stand")],
        )
        validate_safety_result(result)
        self.assertEqual(result["status"], "REFER")
        self.assertTrue(result["requires_referral"])
        self.assertEqual(result["blocked_recommendation_ids"], ["chair-sit-to-stand"])


class NotAssessedTests(unittest.TestCase):
    def test_no_candidates_is_not_assessed_not_allow(self):
        result = evaluate_safety(candidate_recommendations=[])
        validate_safety_result(result)
        self.assertEqual(result["status"], "NOT_ASSESSED")
        self.assertEqual(result["flags"], [])
        self.assertFalse(result["requires_referral"])


class InvalidInputTests(unittest.TestCase):
    def test_malformed_candidate_raises_not_silently_allows(self):
        with self.assertRaises(SafetyEvaluationError):
            evaluate_safety(candidate_recommendations=[{"id": "x"}])  # missing agent/type

    def test_non_list_candidates_raises(self):
        with self.assertRaises(SafetyEvaluationError):
            evaluate_safety(candidate_recommendations="not-a-list")

    def test_non_dict_need_profile_raises(self):
        with self.assertRaises(SafetyEvaluationError):
            evaluate_safety(need_profile="not-a-dict", candidate_recommendations=[])


class MissingMedicalContextTests(unittest.TestCase):
    def test_no_confirmed_medical_context_never_triggers_modify_or_pause(self):
        result = evaluate_safety(
            confirmed_medical_context=None,
            candidate_recommendations=[_exercise_candidate("wall-sit", "intermediate")],
        )
        self.assertEqual(result["status"], "ALLOW")


class UnsafeExerciseConstraintTests(unittest.TestCase):
    def test_advanced_difficulty_with_confirmed_context_is_paused(self):
        result = evaluate_safety(
            confirmed_medical_context=_confirmed_medical_context(),
            candidate_recommendations=[_exercise_candidate("some-advanced-move", "advanced")],
        )
        self.assertEqual(result["status"], "PAUSE")
        self.assertIn("some-advanced-move", result["blocked_recommendation_ids"])


class SpecialistRecommendationBlockedTests(unittest.TestCase):
    def test_a_blocked_recommendation_id_is_named_not_silently_dropped(self):
        result = evaluate_safety(
            confirmed_medical_context=_confirmed_medical_context(),
            candidate_recommendations=[
                _exercise_candidate("wall-sit", "intermediate"),
            ],
        )
        self.assertEqual(result["status"], "PAUSE")
        self.assertIn("wall-sit", result["blocked_recommendation_ids"])
        self.assertNotIn("wall-sit", result["modified_recommendation_ids"])


if __name__ == "__main__":
    unittest.main()
