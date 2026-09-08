"""Food-log adherence: the four outcomes, and the rule that protects the user.

The rule this file exists to defend: NO FOOD LOG IS NOT EVIDENCE THAT THE
USER DID NOT EAT. An absent log must come back as NOT_LOGGED or
INSUFFICIENT_DATA, and never as NOT_ADHERED.
"""

import unittest
from datetime import datetime, timezone

from nutrition_agent.adherence import (
    ADHERED,
    ADHERENCE_THRESHOLD,
    INSUFFICIENT_DATA,
    MIN_OBSERVATION_DAYS,
    NOT_ADHERED,
    NOT_LOGGED,
    FoodLogAdherenceError,
    compute_food_log_adherence,
)

PLAN = {
    "plan_id": "nutrition_plan_1",
    "created_at": "2026-01-01T00:00:00+00:00",
    "goal": "fixture goal",
    "topic_ids": ["build_a_hydration_habit"],
}

WEEK_START = "2026-01-01"
WEEK_END = "2026-01-07"


def entry(day, meal="lunch", plan_id="nutrition_plan_1", hour=12):
    return {
        "meal": meal,
        "food_id": "poha",
        "plan_id": plan_id,
        "recorded_at": datetime(2026, 1, day, hour, tzinfo=timezone.utc),
    }


class FullLoggingTests(unittest.TestCase):
    def test_every_day_logged_is_adhered_with_a_real_rate_of_one(self):
        entries = [entry(day) for day in range(1, 8)]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], ADHERED)
        self.assertEqual(result["completion_rate"], 1.0)
        self.assertEqual(result["observation_days"], 7)
        self.assertEqual(result["logged_days"], 7)
        self.assertEqual(result["entries_considered"], 7)

    def test_at_the_threshold_is_adhered(self):
        # 6 of 7 days = 0.857, at or above the 0.8 threshold.
        entries = [entry(day) for day in range(1, 7)]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertGreaterEqual(result["completion_rate"], ADHERENCE_THRESHOLD)
        self.assertEqual(result["status"], ADHERED)

    def test_breakdowns_are_produced_per_day_and_per_meal_type(self):
        entries = [
            entry(1, meal="breakfast"),
            entry(1, meal="lunch"),
            entry(2, meal="dinner"),
            entry(3, meal="snack"),
        ]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["per_day"]["2026-01-01"]["entries"], 2)
        self.assertEqual(
            result["per_day"]["2026-01-01"]["meals"], ["breakfast", "lunch"]
        )
        self.assertEqual(
            result["per_meal_type"],
            {"breakfast": 1, "lunch": 1, "dinner": 1, "snack": 1},
        )


class NoLoggingTests(unittest.TestCase):
    def test_zero_logs_is_not_logged_never_not_adhered(self):
        result = compute_food_log_adherence(
            PLAN, [], period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], NOT_LOGGED)
        self.assertNotEqual(result["status"], NOT_ADHERED)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["logged_days"], 0)
        self.assertTrue(
            any("not evidence that the user did not eat" in note
                for note in result["notes"])
        )

    def test_none_entries_is_treated_the_same_as_an_empty_list(self):
        result = compute_food_log_adherence(
            PLAN, None, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], NOT_LOGGED)
        self.assertIsNone(result["completion_rate"])

    def test_logs_belonging_only_to_another_plan_are_not_logged_for_this_plan(self):
        entries = [entry(day, plan_id="nutrition_plan_0") for day in range(1, 8)]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], NOT_LOGGED)
        self.assertEqual(result["entries_excluded_other_plan"], 7)
        self.assertIsNone(result["completion_rate"])

    def test_no_observation_period_is_insufficient_data_not_a_zero_rate(self):
        result = compute_food_log_adherence(PLAN, [entry(1)])

        self.assertEqual(result["status"], INSUFFICIENT_DATA)
        self.assertIsNone(result["completion_rate"])


class PartialLoggingTests(unittest.TestCase):
    def test_partial_logging_below_the_threshold_is_not_adhered(self):
        entries = [entry(1), entry(2)]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], NOT_ADHERED)
        self.assertAlmostEqual(result["completion_rate"], 2 / 7)
        self.assertEqual(result["logged_days"], 2)

    def test_several_entries_on_one_day_count_as_one_logged_day(self):
        entries = [entry(1, meal="breakfast"), entry(1, meal="lunch"), entry(1, meal="dinner")]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["logged_days"], 1)
        self.assertEqual(result["entries_considered"], 3)
        self.assertAlmostEqual(result["completion_rate"], 1 / 7)

    def test_not_adhered_says_plainly_that_it_measures_logging_not_diet_quality(self):
        result = compute_food_log_adherence(
            PLAN, [entry(1)], period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertTrue(
            any("LOGGING coverage" in note for note in result["notes"])
        )


class ShortAndChangedPeriodTests(unittest.TestCase):
    def test_a_period_shorter_than_the_minimum_is_insufficient_data(self):
        result = compute_food_log_adherence(
            PLAN, [entry(1)], period_start="2026-01-01", period_end="2026-01-02"
        )

        self.assertEqual(result["status"], INSUFFICIENT_DATA)
        self.assertIsNone(result["completion_rate"])
        self.assertLess(result["observation_days"], MIN_OBSERVATION_DAYS)

    def test_a_plan_created_mid_period_is_only_judged_from_its_own_start(self):
        plan = {**PLAN, "created_at": "2026-01-05T00:00:00+00:00"}
        entries = [entry(day) for day in (5, 6, 7)]

        result = compute_food_log_adherence(
            plan, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        # 3 in-effect days, all logged — not 3 of 7.
        self.assertEqual(result["observation_days"], 3)
        self.assertEqual(result["completion_rate"], 1.0)
        self.assertEqual(result["status"], ADHERED)
        self.assertTrue(
            any("created part-way through" in note for note in result["notes"])
        )

    def test_a_plan_not_yet_in_effect_is_insufficient_data(self):
        plan = {**PLAN, "created_at": "2026-02-01T00:00:00+00:00"}

        result = compute_food_log_adherence(
            plan, [], period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["status"], INSUFFICIENT_DATA)
        self.assertIsNone(result["completion_rate"])

    def test_entries_outside_the_period_are_ignored(self):
        entries = [entry(1), entry(20)]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["entries_considered"], 1)


class InputAndDeterminismTests(unittest.TestCase):
    def test_the_same_input_always_produces_the_same_output(self):
        entries = [entry(3), entry(1, meal="snack"), entry(5)]

        first = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )
        second = compute_food_log_adherence(
            PLAN, list(reversed(entries)), period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(first, second)
        self.assertEqual(list(first["per_day"]), sorted(first["per_day"]))

    def test_a_plan_record_without_a_plan_id_is_refused(self):
        with self.assertRaises(FoodLogAdherenceError):
            compute_food_log_adherence({}, [], period_start=WEEK_START, period_end=WEEK_END)

    def test_a_reversed_period_is_refused_not_silently_swapped(self):
        with self.assertRaises(FoodLogAdherenceError):
            compute_food_log_adherence(
                PLAN, [], period_start=WEEK_END, period_end=WEEK_START
            )

    def test_an_undated_entry_is_counted_but_not_attributed_to_a_day(self):
        entries = [entry(1), {"meal": "lunch", "plan_id": PLAN["plan_id"]}]

        result = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )

        self.assertEqual(result["entries_considered"], 2)
        self.assertEqual(result["entries_without_date"], 1)
        self.assertEqual(result["logged_days"], 1)

    def test_datetime_and_string_periods_are_equivalent(self):
        entries = [entry(day) for day in range(1, 8)]

        by_string = compute_food_log_adherence(
            PLAN, entries, period_start=WEEK_START, period_end=WEEK_END
        )
        by_datetime = compute_food_log_adherence(
            PLAN,
            entries,
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 7, 23, 59, tzinfo=timezone.utc),
        )

        self.assertEqual(by_string, by_datetime)


if __name__ == "__main__":
    unittest.main()
