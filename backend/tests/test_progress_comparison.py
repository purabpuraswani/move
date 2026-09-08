"""Progress Agent — deterministic comparison engine (Phase 5).

Covers: improvement, stable, decline, missing data (both sides), a
direction-aware metric (functional_movement_ftsst_seconds, where LOWER is
better), and an explicit determinism check (identical input -> identical
output, called twice).
"""

import unittest

from progress_agent.comparison import (
    DECLINED,
    IMPROVED,
    NOT_ENOUGH_DATA,
    STABLE,
    compare_metric,
    compare_physical_assessments,
    extract_balance_metric,
    extract_ftsst_metric,
    extract_shoulder_metric,
    overall_direction,
)


def _shoulder_doc(left_deg, right_deg, status="completed"):
    return {
        "tests": {
            "shoulder": {
                "status": status,
                "measurements": {
                    "left": {"finalElevationDeg": left_deg},
                    "right": {"finalElevationDeg": right_deg},
                },
            },
        },
    }


def _balance_doc(left_hold, right_hold, status="completed", valid=True):
    return {
        "tests": {
            "balance": {
                "status": status,
                "measurements": {
                    "left": {"attempted": True, "valid": valid, "holdDurationSeconds": left_hold},
                    "right": {"attempted": True, "valid": valid, "holdDurationSeconds": right_hold},
                },
            },
        },
    }


def _ftsst_doc(seconds, status="completed"):
    return {"tests": {"ftsst": {"status": status, "measurements": {"completionTimeSeconds": seconds}}}}


class CompareMetricTests(unittest.TestCase):
    def test_unknown_metric_rejected(self):
        with self.assertRaises(ValueError):
            compare_metric(1, 2, "not_a_real_metric")

    def test_missing_baseline_is_not_enough_data(self):
        result = compare_metric(None, 60, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], NOT_ENOUGH_DATA)
        self.assertIsNone(result["change"])

    def test_missing_current_is_not_enough_data(self):
        result = compare_metric(40, None, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], NOT_ENOUGH_DATA)
        self.assertIsNone(result["change"])

    def test_both_missing_is_not_enough_data(self):
        result = compare_metric(None, None, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], NOT_ENOUGH_DATA)

    def test_higher_is_better_improvement(self):
        # 40 -> 60 seconds, tolerance is 2s -> well past it -> IMPROVED
        result = compare_metric(40, 60, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], IMPROVED)
        self.assertEqual(result["change"], 20)

    def test_higher_is_better_decline(self):
        result = compare_metric(60, 40, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], DECLINED)
        self.assertEqual(result["change"], -20)

    def test_higher_is_better_stable_within_tolerance(self):
        # tolerance for stability is 2s; a 1s change stays STABLE
        result = compare_metric(40, 41, "stability_balance_hold_seconds")
        self.assertEqual(result["direction"], STABLE)

    def test_lower_is_better_improvement_is_a_decrease(self):
        # FTSST: 15s -> 10s is an IMPROVEMENT (faster), even though the
        # raw number went down — this is the direction-aware check.
        result = compare_metric(15, 10, "functional_movement_ftsst_seconds")
        self.assertEqual(result["direction"], IMPROVED)
        self.assertEqual(result["change"], -5)

    def test_lower_is_better_decline_is_an_increase(self):
        # FTSST: 10s -> 15s is a DECLINE (slower)
        result = compare_metric(10, 15, "functional_movement_ftsst_seconds")
        self.assertEqual(result["direction"], DECLINED)
        self.assertEqual(result["change"], 5)

    def test_lower_is_better_stable_within_tolerance(self):
        # tolerance for ftsst is 1s
        result = compare_metric(10, 10.5, "functional_movement_ftsst_seconds")
        self.assertEqual(result["direction"], STABLE)

    def test_deterministic(self):
        r1 = compare_metric(40, 65, "mobility_shoulder_elevation_deg")
        r2 = compare_metric(40, 65, "mobility_shoulder_elevation_deg")
        self.assertEqual(r1, r2)


class ExtractorTests(unittest.TestCase):
    def test_shoulder_extractor_uses_lowest_side(self):
        tests = _shoulder_doc(120, 90)["tests"]
        self.assertEqual(extract_shoulder_metric(tests), 90)

    def test_shoulder_extractor_none_when_not_completed(self):
        tests = _shoulder_doc(120, 90, status="in_progress")["tests"]
        self.assertIsNone(extract_shoulder_metric(tests))

    def test_balance_extractor_ignores_invalid_attempts(self):
        tests = _balance_doc(30, 45, valid=False)["tests"]
        self.assertIsNone(extract_balance_metric(tests))

    def test_balance_extractor_uses_shortest_valid_hold(self):
        tests = _balance_doc(30, 45)["tests"]
        self.assertEqual(extract_balance_metric(tests), 30)

    def test_ftsst_extractor_reads_completion_time(self):
        tests = _ftsst_doc(12.5)["tests"]
        self.assertEqual(extract_ftsst_metric(tests), 12.5)

    def test_ftsst_extractor_none_when_missing(self):
        tests = {}
        self.assertIsNone(extract_ftsst_metric(tests))


class ComparePhysicalAssessmentsTests(unittest.TestCase):
    def test_all_documents_none_is_not_enough_data_for_every_metric(self):
        result = compare_physical_assessments(None, None, None)
        for metric_name, entry in result.items():
            self.assertEqual(entry["baseline_vs_current"]["direction"], NOT_ENOUGH_DATA, metric_name)
            self.assertEqual(entry["previous_vs_current"]["direction"], NOT_ENOUGH_DATA, metric_name)

    def test_baseline_and_current_present_previous_missing(self):
        baseline = _balance_doc(40, 40)
        current = _balance_doc(60, 60)
        result = compare_physical_assessments(baseline, None, current)
        stability = result["stability_balance_hold_seconds"]
        self.assertEqual(stability["baseline_vs_current"]["direction"], IMPROVED)
        self.assertEqual(stability["previous_vs_current"]["direction"], NOT_ENOUGH_DATA)

    def test_malformed_document_does_not_crash(self):
        # A document missing "tests" entirely, or holding unexpected types,
        # must degrade to NOT_ENOUGH_DATA per-metric, never raise.
        result = compare_physical_assessments({"unexpected": True}, {}, {"tests": None})
        for entry in result.values():
            self.assertEqual(entry["baseline_vs_current"]["direction"], NOT_ENOUGH_DATA)


class OverallDirectionTests(unittest.TestCase):
    def _comparisons(self, *directions):
        return {
            f"metric_{i}": {"baseline_vs_current": {"direction": d}}
            for i, d in enumerate(directions)
        }

    def test_any_declined_wins(self):
        comparisons = self._comparisons(IMPROVED, DECLINED, STABLE)
        self.assertEqual(overall_direction(comparisons), DECLINED)

    def test_improved_over_stable(self):
        comparisons = self._comparisons(STABLE, IMPROVED, NOT_ENOUGH_DATA)
        self.assertEqual(overall_direction(comparisons), IMPROVED)

    def test_stable_when_no_improvement_or_decline(self):
        comparisons = self._comparisons(STABLE, NOT_ENOUGH_DATA)
        self.assertEqual(overall_direction(comparisons), STABLE)

    def test_not_enough_data_when_nothing_comparable(self):
        comparisons = self._comparisons(NOT_ENOUGH_DATA, NOT_ENOUGH_DATA)
        self.assertEqual(overall_direction(comparisons), NOT_ENOUGH_DATA)


if __name__ == "__main__":
    unittest.main()
