"""Progress Agent — reassessment-required check (Phase 5)."""

import unittest
from datetime import datetime, timezone

from progress_agent.reassessment import REASSESSMENT_STALE_AFTER_DAYS, check_reassessment_required


class ReassessmentTests(unittest.TestCase):
    def test_no_assessment_at_all_requires_reassessment(self):
        result = check_reassessment_required(None)
        self.assertTrue(result["required"])
        self.assertIn("No physical assessment", result["reason"])

    def test_unparseable_timestamp_requires_reassessment(self):
        result = check_reassessment_required("not-a-timestamp")
        self.assertTrue(result["required"])

    def test_recent_assessment_does_not_require_reassessment(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        completed = "2026-06-10T00:00:00Z"
        result = check_reassessment_required(completed, now=now)
        self.assertFalse(result["required"])

    def test_stale_assessment_requires_reassessment(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        completed = "2026-01-01T00:00:00Z"  # far past the threshold
        result = check_reassessment_required(completed, now=now)
        self.assertTrue(result["required"])
        self.assertIn(str(REASSESSMENT_STALE_AFTER_DAYS), result["reason"])

    def test_exactly_at_boundary_is_not_stale(self):
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        completed = "2026-01-01T00:00:00Z"  # 30 days old exactly
        result = check_reassessment_required(completed, now=now)
        self.assertFalse(result["required"])

    def test_deterministic(self):
        now = datetime(2026, 6, 15, tzinfo=timezone.utc)
        r1 = check_reassessment_required("2026-06-01T00:00:00Z", now=now)
        r2 = check_reassessment_required("2026-06-01T00:00:00Z", now=now)
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()
