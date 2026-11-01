import unittest

from assessments.store import _serialise_summary


class LegacyAssessmentSummaryTests(unittest.TestCase):
    def test_retired_ftsst_does_not_inflate_legacy_session_summary(self):
        summary = _serialise_summary(
            {
                "tests_completed": 3,
                "tests_invalid": 0,
                "tests_skipped": 0,
                "tests_not_started": 0,
                "has_any_usable_result": True,
                "status": "COMPLETE",
            },
            {
                "shoulder": {"status": "completed"},
                "ftsst": {"status": "completed"},
                "balance": {"status": "skipped"},
            },
        )

        self.assertEqual(summary["testsCompleted"], 1)
        self.assertEqual(summary["testsSkipped"], 1)
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertTrue(summary["hasAnyUsableResult"])


if __name__ == "__main__":
    unittest.main()
