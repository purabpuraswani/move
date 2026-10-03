"""The Progress page's data, and the line it must not cross.

The page exists to show what the user recorded. The failure mode worth
testing for is the flattering one: inventing a trend, carrying a skipped
check forward as a zero, or counting a self-reported tick as a measured
session. Each of those would make the chart say something the data does
not.

The movement figures are not re-derived here -- series.py calls
comparison.py's existing extractors, the same ones the Progress Agent
and the Need Assessment use -- so these tests also pin that a figure
plotted and a figure reasoned about cannot diverge.
"""

import unittest

from progress_agent.series import (
    MIN_POINTS_FOR_TREND,
    build_progress_series,
    completions_by_day,
    movement_metric_series,
    plan_version_history,
    recent_completions,
)


def _result(day, *, source="camera", exercise_id="wall-sit", status="completed"):
    return {
        "exerciseId": exercise_id,
        "completedAt": f"{day}T10:00:00+00:00",
        "status": status,
        "source": source,
    }


def _assessment_doc(completed_at, *, shoulder=None, ftsst=None, balance=None, skipped=()):
    def block(test_id, measurements):
        if test_id in skipped:
            return {"status": "skipped", "measurements": None}

        if measurements is None:
            return {"status": "not_started", "measurements": None}

        return {"status": "completed", "measurements": measurements}

    return {
        "completed_at": completed_at,
        "tests": {
            "shoulder": block(
                "shoulder",
                None
                if shoulder is None
                else {
                    "left": {"finalElevationDeg": shoulder[0]},
                    "right": {"finalElevationDeg": shoulder[1]},
                },
            ),
            "ftsst": block(
                "ftsst", None if ftsst is None else {"completionTimeSeconds": ftsst}
            ),
            "balance": block(
                "balance",
                None
                if balance is None
                else {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": balance[0]},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": balance[1]},
                },
            ),
        },
    }


class CompletionsByDayTests(unittest.TestCase):
    def test_completions_are_grouped_by_the_day_they_happened(self):
        series = completions_by_day(
            [_result("2026-09-01"), _result("2026-09-01"), _result("2026-09-03")]
        )

        self.assertEqual([point["date"] for point in series["points"]], ["2026-09-01", "2026-09-03"])
        self.assertEqual([point["total"] for point in series["points"]], [2, 1])
        self.assertEqual(series["total_completions"], 3)

    def test_days_come_out_in_chronological_order(self):
        series = completions_by_day(
            [_result("2026-09-05"), _result("2026-09-01"), _result("2026-09-03")]
        )

        dates = [point["date"] for point in series["points"]]

        self.assertEqual(dates, sorted(dates))

    def test_measured_and_self_reported_are_counted_separately(self):
        series = completions_by_day(
            [
                _result("2026-09-01"),
                _result("2026-09-01", source="manual_confirmation"),
            ]
        )

        point = series["points"][0]

        self.assertEqual(point["total"], 2)
        self.assertEqual(point["measured"], 1)
        self.assertEqual(point["self_reported"], 1)

    def test_one_day_is_not_a_trend(self):
        series = completions_by_day([_result("2026-09-01"), _result("2026-09-01")])

        self.assertEqual(series["point_count"], 1)
        self.assertFalse(series["plottable"])

    def test_two_days_is(self):
        series = completions_by_day([_result("2026-09-01"), _result("2026-09-02")])

        self.assertEqual(series["point_count"], MIN_POINTS_FOR_TREND)
        self.assertTrue(series["plottable"])

    def test_nothing_recorded_is_an_empty_series_not_a_zero(self):
        series = completions_by_day([])

        self.assertEqual(series["points"], [])
        self.assertFalse(series["plottable"])
        self.assertEqual(series["total_completions"], 0)

    def test_a_result_with_no_date_is_skipped_rather_than_guessed(self):
        series = completions_by_day([{"exerciseId": "wall-sit"}, _result("2026-09-01")])

        self.assertEqual(series["point_count"], 1)


class MovementMetricSeriesTests(unittest.TestCase):
    def test_each_metric_gets_its_own_series_in_date_order(self):
        series = {
            entry["metric"]: entry
            for entry in movement_metric_series(
                [
                    _assessment_doc("2026-09-10T09:00:00Z", ftsst=14.0),
                    _assessment_doc("2026-08-01T09:00:00Z", ftsst=17.0),
                ]
            )
        }

        points = series["functional_movement_ftsst_seconds"]["points"]

        self.assertEqual([point["value"] for point in points], [17.0, 14.0])
        self.assertEqual([point["date"] for point in points], ["2026-08-01", "2026-09-10"])

    def test_a_skipped_check_contributes_no_point_rather_than_a_zero(self):
        series = {
            entry["metric"]: entry
            for entry in movement_metric_series(
                [
                    _assessment_doc("2026-08-01T09:00:00Z", balance=(20, 22)),
                    _assessment_doc("2026-09-01T09:00:00Z", skipped=("balance",)),
                ]
            )
        }

        balance = series["stability_balance_hold_seconds"]

        self.assertEqual(len(balance["points"]), 1)
        self.assertEqual(balance["points"][0]["value"], 20)
        self.assertFalse(balance["plottable"])

    def test_a_single_assessment_is_never_plottable(self):
        for entry in movement_metric_series(
            [_assessment_doc("2026-09-01T09:00:00Z", shoulder=(150, 148), ftsst=9.0)]
        ):
            self.assertFalse(entry["plottable"], f"{entry['metric']} claimed a trend")

    def test_the_direction_of_improvement_is_carried_not_assumed(self):
        series = {entry["metric"]: entry for entry in movement_metric_series([])}

        # Lower is better for sit-to-stand time; higher for the other two.
        self.assertFalse(series["functional_movement_ftsst_seconds"]["higherIsBetter"])
        self.assertTrue(series["stability_balance_hold_seconds"]["higherIsBetter"])
        self.assertTrue(series["mobility_shoulder_elevation_deg"]["higherIsBetter"])

    def test_the_values_are_the_extractors_own_values(self):
        from progress_agent.comparison import extract_shoulder_metric

        document = _assessment_doc("2026-09-01T09:00:00Z", shoulder=(132, 147))

        series = {entry["metric"]: entry for entry in movement_metric_series([document])}
        plotted = series["mobility_shoulder_elevation_deg"]["points"][0]["value"]

        self.assertEqual(plotted, extract_shoulder_metric(document["tests"]))


class PlanHistoryTests(unittest.TestCase):
    def test_versions_are_read_from_the_stored_plan_section(self):
        state = {
            "exercise_history": {
                "available": True,
                "data": {
                    "plans": [
                        {"plan_version": 1, "created_at": "2026-08-01T00:00:00Z", "changes": []},
                        {
                            "plan_version": 2,
                            "created_at": "2026-09-01T00:00:00Z",
                            "changes": [{"a": 1}, {"b": 2}],
                        },
                    ]
                },
            }
        }

        history = plan_version_history(state)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["domain"], "Movement")
        self.assertEqual(history[0]["version_count"], 2)
        self.assertEqual(history[0]["versions"][1]["changeCount"], 2)

    def test_an_unavailable_section_contributes_nothing(self):
        state = {"exercise_history": {"available": False, "data": {"plans": [{"plan_version": 1}]}}}

        self.assertEqual(plan_version_history(state), [])

    def test_a_domain_with_no_plan_is_absent_rather_than_empty(self):
        self.assertEqual(plan_version_history({}), [])


class RecentCompletionsTests(unittest.TestCase):
    def test_newest_first(self):
        recent = recent_completions(
            [_result("2026-09-01"), _result("2026-09-09"), _result("2026-09-05")]
        )

        self.assertEqual(
            [entry["completedAt"][:10] for entry in recent],
            ["2026-09-09", "2026-09-05", "2026-09-01"],
        )

    def test_the_source_is_preserved_so_a_tick_is_not_shown_as_measured(self):
        recent = recent_completions([_result("2026-09-01", source="manual_confirmation")])

        self.assertEqual(recent[0]["source"], "manual_confirmation")

    def test_a_datetime_completion_is_read_rather_than_discarded(self):
        from datetime import datetime

        recent = recent_completions(
            [{"exerciseId": "wall-sit", "completedAt": datetime(2026, 9, 7, 8, 30)}]
        )

        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["completedAt"], "2026-09-07")

    def test_an_unreadable_completion_falls_back_to_when_it_was_recorded(self):
        # Rather than dropping a session the user actually did.
        recent = recent_completions(
            [{"exerciseId": "wall-sit", "completedAt": None, "recordedAt": "2026-09-08T11:00:00Z"}]
        )

        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["completedAt"], "2026-09-08")

    def test_a_result_without_a_source_is_treated_as_a_camera_result(self):
        recent = recent_completions([{"exerciseId": "wall-sit", "completedAt": "2026-09-01T10:00:00Z"}])

        self.assertEqual(recent[0]["source"], "camera")


class BuildProgressSeriesTests(unittest.TestCase):
    def test_an_empty_account_claims_no_trend(self):
        series = build_progress_series()

        self.assertFalse(series["hasAnyTrend"])
        self.assertEqual(series["completions"]["points"], [])
        self.assertEqual(series["recentCompletions"], [])

    def test_two_recorded_days_is_a_trend(self):
        series = build_progress_series(
            exercise_results=[_result("2026-09-01"), _result("2026-09-02")]
        )

        self.assertTrue(series["hasAnyTrend"])

    def test_two_assessments_are_a_trend_even_with_no_exercise_results(self):
        series = build_progress_series(
            assessment_documents=[
                _assessment_doc("2026-08-01T09:00:00Z", ftsst=17.0),
                _assessment_doc("2026-09-01T09:00:00Z", ftsst=14.0),
            ]
        )

        self.assertTrue(series["hasAnyTrend"])

    def test_the_threshold_is_published_so_the_interface_cannot_invent_its_own(self):
        self.assertEqual(build_progress_series()["minPointsForTrend"], MIN_POINTS_FOR_TREND)

    def test_it_is_deterministic(self):
        results = [_result("2026-09-01"), _result("2026-09-02")]
        documents = [_assessment_doc("2026-09-01T09:00:00Z", ftsst=14.0)]

        self.assertEqual(
            build_progress_series(exercise_results=results, assessment_documents=documents),
            build_progress_series(exercise_results=results, assessment_documents=documents),
        )


if __name__ == "__main__":
    unittest.main()
