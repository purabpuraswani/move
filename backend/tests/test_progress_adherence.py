"""Progress Agent — deterministic adherence/completion-rate engine (Phase 5).

Covers: full completion, partial completion, zero planned sessions,
missing planned/completed values, invalid (negative/non-numeric) values,
and compute_plan_adherence's real-data grounding (only counts a result
against the matching plan_id and exercise_id, with status "completed").
"""

import unittest

from progress_agent.adherence import (
    NOT_ENOUGH_DATA,
    AdherenceCalculationError,
    calculate_completion_rate,
    compute_plan_adherence,
)


class CalculateCompletionRateTests(unittest.TestCase):
    def test_full_completion(self):
        result = calculate_completion_rate(4, 4)
        self.assertEqual(result["completion_rate"], 1.0)
        self.assertEqual(result["status"], "completed")

    def test_partial_completion(self):
        result = calculate_completion_rate(4, 2)
        self.assertEqual(result["completion_rate"], 0.5)
        self.assertEqual(result["status"], "completed")

    def test_zero_completion_is_a_real_zero_not_missing(self):
        result = calculate_completion_rate(4, 0)
        self.assertEqual(result["completion_rate"], 0.0)
        self.assertEqual(result["status"], "completed")

    def test_zero_planned_sessions_is_not_enough_data(self):
        result = calculate_completion_rate(0, 0)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["status"], NOT_ENOUGH_DATA)

    def test_missing_planned_is_not_enough_data(self):
        result = calculate_completion_rate(None, 2)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["status"], NOT_ENOUGH_DATA)

    def test_missing_completed_is_not_enough_data(self):
        result = calculate_completion_rate(4, None)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["status"], NOT_ENOUGH_DATA)

    def test_both_missing_is_not_enough_data(self):
        result = calculate_completion_rate(None, None)
        self.assertEqual(result["status"], NOT_ENOUGH_DATA)

    def test_negative_planned_raises(self):
        with self.assertRaises(AdherenceCalculationError):
            calculate_completion_rate(-1, 2)

    def test_negative_completed_raises(self):
        with self.assertRaises(AdherenceCalculationError):
            calculate_completion_rate(4, -1)

    def test_non_numeric_raises(self):
        with self.assertRaises(AdherenceCalculationError):
            calculate_completion_rate("four", 2)

    def test_boolean_is_rejected_even_though_bool_is_an_int_subclass(self):
        with self.assertRaises(AdherenceCalculationError):
            calculate_completion_rate(True, 2)

    def test_completed_never_fabricated_above_planned(self):
        # 5 completed against 4 planned should not produce a >100% rate —
        # clamped to the planned count, never a fabricated over-completion.
        result = calculate_completion_rate(4, 5)
        self.assertEqual(result["completion_rate"], 1.0)

    def test_deterministic(self):
        r1 = calculate_completion_rate(4, 3)
        r2 = calculate_completion_rate(4, 3)
        self.assertEqual(r1, r2)


class ComputePlanAdherenceTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "plan_id": "plan_123",
            "exercise_ids": ["ex_a", "ex_b", "ex_c", "ex_d"],
        }

    def test_requires_plan_id(self):
        with self.assertRaises(AdherenceCalculationError):
            compute_plan_adherence({"exercise_ids": ["ex_a"]}, [])

    def test_requires_dict_plan_record(self):
        with self.assertRaises(AdherenceCalculationError):
            compute_plan_adherence(None, [])

    def test_no_results_is_zero_not_missing(self):
        result = compute_plan_adherence(self.plan, [])
        self.assertEqual(result["completed_sessions"], 0)
        self.assertEqual(result["completion_rate"], 0.0)
        self.assertEqual(result["plan_id"], "plan_123")

    def test_counts_only_completed_status(self):
        results = [
            {"exerciseId": "ex_a", "plan_id": "plan_123", "status": "completed"},
            {"exerciseId": "ex_b", "plan_id": "plan_123", "status": "in_progress"},
        ]
        result = compute_plan_adherence(self.plan, results)
        self.assertEqual(result["completed_sessions"], 1)

    def test_ignores_results_for_a_different_plan(self):
        results = [
            {"exerciseId": "ex_a", "plan_id": "plan_OTHER", "status": "completed"},
        ]
        result = compute_plan_adherence(self.plan, results)
        self.assertEqual(result["completed_sessions"], 0)

    def test_ignores_results_for_an_exercise_not_in_the_plan(self):
        results = [
            {"exerciseId": "ex_not_in_plan", "plan_id": "plan_123", "status": "completed"},
        ]
        result = compute_plan_adherence(self.plan, results)
        self.assertEqual(result["completed_sessions"], 0)

    def test_deduplicates_multiple_completions_of_the_same_exercise(self):
        results = [
            {"exerciseId": "ex_a", "plan_id": "plan_123", "status": "completed"},
            {"exerciseId": "ex_a", "plan_id": "plan_123", "status": "completed"},
        ]
        result = compute_plan_adherence(self.plan, results)
        self.assertEqual(result["completed_sessions"], 1)

    def test_full_realistic_mix(self):
        results = [
            {"exerciseId": "ex_a", "plan_id": "plan_123", "status": "completed"},
            {"exerciseId": "ex_b", "plan_id": "plan_123", "status": "completed"},
            {"exerciseId": "ex_c", "plan_id": "plan_OTHER", "status": "completed"},
            {"exerciseId": "ex_d", "plan_id": "plan_123", "status": "in_progress"},
        ]
        result = compute_plan_adherence(self.plan, results)
        self.assertEqual(result["planned_sessions"], 4)
        self.assertEqual(result["completed_sessions"], 2)
        self.assertEqual(result["completion_rate"], 0.5)

    def test_none_exercise_results_treated_as_empty(self):
        result = compute_plan_adherence(self.plan, None)
        self.assertEqual(result["completed_sessions"], 0)


if __name__ == "__main__":
    unittest.main()
