import unittest

from activity_agent.evidence import build_activity_view
from activity_agent.reasoning import assess_activity


class ActivityScoreTests(unittest.TestCase):
    def test_indicator_uses_known_dimensions_and_keeps_breaks_unknown(self):
        state = {"questionnaire": {"available": True, "data": {
            "daily_steps": 6961,
            "exercise_days": 6,
            "exercise_minutes": 60,
            "daily_sitting_hours": 7,
        }}}
        findings = assess_activity(build_activity_view(state, exercise_results=[]))
        score = findings["activity_score"]
        self.assertEqual(score["value"], 75.0)
        self.assertIsNone(score["inputs"]["movement_breaks_per_day"])
        breaks = next(item for item in score["components"] if item["metric"] == "movement_breaks_per_day")
        self.assertEqual(breaks["status"], "UNKNOWN")
        self.assertIsNone(breaks["score"])
        self.assertIn("not a medically validated", score["interpretation"])
        self.assertEqual(len(findings["activity_recommendations"]), 2)
        self.assertIn("interrupt_sitting", {item["id"] for item in findings["activity_recommendations"]})

    def test_no_known_activity_inputs_does_not_return_zero_score(self):
        state = {"questionnaire": {"available": True, "data": {}}}
        findings = assess_activity(build_activity_view(state, exercise_results=[]))
        self.assertIsNone(findings["activity_score"]["value"])

    def test_recorded_movement_breaks_use_only_values_the_user_logged(self):
        state = {"questionnaire": {"available": True, "data": {"daily_steps": 5000}}}
        view = build_activity_view(state, daily_checkins=[
            {"date": "2026-10-31", "movement_breaks": 0},
            {"date": "2026-10-30", "movement_breaks": 4},
            {"date": "2026-10-29", "sleep_hours": 7},
        ], exercise_results=[])
        findings = assess_activity(view)
        score = findings["activity_score"]
        component = next(item for item in score["components"] if item["metric"] == "movement_breaks_per_day")
        self.assertEqual(component["input_value"], 2)
        self.assertAlmostEqual(component["score"], 66.7)
        self.assertEqual(score["movement_breaks_observation"]["days_observed"], 2)
        self.assertEqual(score["movement_breaks_observation"]["dates"], ["2026-10-31", "2026-10-30"])


if __name__ == "__main__":
    unittest.main()
