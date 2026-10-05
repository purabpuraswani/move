"""The Nutrition & Lifestyle check-in, end to end through the real modules.

What these tests are for: the nutrition specialist could only ever report
NOT_ASSESSED because nothing in the product asked the questions. A check-in is
only useful if its answers actually change that, if a stated goal is not
mistaken for a finding, and if an unanswered check-in still reports itself as
unanswered rather than as a bad diet.
"""

import unittest

from bson import ObjectId

from need_assessment.rules import assess_nutrition_need
from nutrition_agent.evidence import build_nutrition_evidence_view
from nutrition_library import check_in
from routes import profile as profile_routes
from tests._fake_mongo import FakeReportsCollection


class CheckInDefinitionTests(unittest.TestCase):
    def test_there_are_six_questions_each_with_options(self):
        questions = check_in.describe()

        self.assertEqual(len(questions), 6)

        for question in questions:
            self.assertTrue(question["label"])
            self.assertTrue(question["prompt"])
            self.assertGreaterEqual(len(question["options"]), 2)

            for option in question["options"]:
                self.assertIn("value", option)
                self.assertTrue(option["label"])

    def test_exactly_one_question_is_a_preference(self):
        # The stated goal. Counting it as a nutrition finding would turn "I
        # want to hydrate more" into evidence about somebody's diet.
        self.assertEqual(check_in.PREFERENCE_KEYS, (check_in.NUTRITION_GOAL,))
        self.assertNotIn(check_in.NUTRITION_GOAL, check_in.FACTOR_KEYS)
        self.assertEqual(len(check_in.FACTOR_KEYS), 5)

    def test_only_the_questions_own_options_are_accepted(self):
        self.assertEqual(check_in.normalise_answer("meals_per_day", 3), 3)

        with self.assertRaises(check_in.CheckInAnswerError):
            check_in.normalise_answer("meals_per_day", 9)

        with self.assertRaises(check_in.CheckInAnswerError):
            check_in.normalise_answer("nutrient_deficiency", "yes")

    def test_a_number_arriving_as_a_float_is_still_its_own_option(self):
        self.assertEqual(check_in.normalise_answer("meals_per_day", 3.0), 3)
        self.assertEqual(
            check_in.normalise_answer("water_glasses_per_day", 9.0), 9
        )

    def test_completeness_needs_every_question(self):
        answers = {
            "meals_per_day": 3,
            "fruit_vegetable_servings": 3,
            "water_glasses_per_day": 6,
            "processed_food_frequency": "rarely",
            "eating_out_frequency": "rarely",
            "nutrition_goal": "hydration",
        }

        self.assertTrue(check_in.is_complete(answers))
        self.assertEqual(check_in.unanswered_keys(answers), [])

        partial = {key: value for key, value in answers.items() if key != "water_glasses_per_day"}

        self.assertFalse(check_in.is_complete(partial))
        self.assertEqual(check_in.unanswered_keys(partial), ["water_glasses_per_day"])

    def test_a_stored_value_this_build_does_not_recognise_reads_as_unanswered(self):
        stored = {"meals_per_day": 3, "processed_food_frequency": "fortnightly"}

        self.assertEqual(
            check_in.unanswered_keys(stored),
            [key for key in check_in.QUESTION_KEYS if key != "meals_per_day"],
        )


class NutritionNeedFromCheckInTests(unittest.TestCase):
    def _state(self, **answers):
        return {
            "nutrition": {
                "available": bool(answers),
                "data": dict(answers),
            }
        }

    def test_unanswered_questions_are_not_assessed_rather_than_a_bad_diet(self):
        entry = assess_nutrition_need({"nutrition": {"available": False}})

        self.assertEqual(entry["level"], "NOT_ASSESSED")
        self.assertEqual(entry["confidence"], "NONE")

    def test_answers_that_all_trigger_produce_a_high_need(self):
        entry = assess_nutrition_need(
            self._state(
                meals_per_day=2,
                fruit_vegetable_servings=1,
                water_glasses_per_day=3,
                processed_food_frequency="daily",
                eating_out_frequency="almost_daily",
            )
        )

        self.assertEqual(entry["level"], "HIGH")
        self.assertTrue(any("meals per day" in line for line in entry["evidence"]))

    def test_answers_that_trigger_nothing_produce_a_low_need(self):
        entry = assess_nutrition_need(
            self._state(
                meals_per_day=3,
                fruit_vegetable_servings=5,
                water_glasses_per_day=9,
                processed_food_frequency="rarely",
                eating_out_frequency="rarely",
            )
        )

        self.assertEqual(entry["level"], "LOW")

    def test_eating_out_often_is_counted_as_a_real_factor(self):
        # One triggered factor out of five is not a pattern on its own, so the
        # level stays LOW — what this checks is that the answer is counted at
        # all, and named in the evidence.
        quiet = self._state(
            meals_per_day=3,
            fruit_vegetable_servings=5,
            water_glasses_per_day=9,
            processed_food_frequency="rarely",
            eating_out_frequency="rarely",
        )
        eating_out = {
            "nutrition": {
                "available": True,
                "data": {
                    **quiet["nutrition"]["data"],
                    "eating_out_frequency": "almost_daily",
                },
            }
        }

        quiet_entry = assess_nutrition_need(quiet)
        eating_out_entry = assess_nutrition_need(eating_out)

        self.assertEqual(quiet_entry["score"], 0.0)
        self.assertEqual(eating_out_entry["score"], 0.2)
        self.assertTrue(
            any("eating out" in line for line in eating_out_entry["evidence"]),
            eating_out_entry["evidence"],
        )

    def test_a_stated_goal_alone_establishes_no_need(self):
        entry = assess_nutrition_need(self._state(nutrition_goal="hydration"))

        self.assertEqual(entry["level"], "NOT_ASSESSED")
        self.assertTrue(
            any("preference" in line for line in entry["evidence"]),
            entry["evidence"],
        )

    def test_a_stated_goal_does_not_change_the_level(self):
        without_goal = self._state(meals_per_day=2, water_glasses_per_day=3)

        with_goal = self._state(
            meals_per_day=2, water_glasses_per_day=3, nutrition_goal="weight_management"
        )

        self.assertEqual(
            assess_nutrition_need(without_goal)["level"],
            assess_nutrition_need(with_goal)["level"],
        )


class NutritionEvidenceViewTests(unittest.TestCase):
    def test_the_check_in_answers_reach_the_specialists_own_view(self):
        state = {
            "nutrition": {
                "available": True,
                "data": {
                    "meals_per_day": 2,
                    "eating_out_frequency": "almost_daily",
                    "nutrition_goal": "hydration",
                },
            }
        }

        view = build_nutrition_evidence_view(state)

        self.assertEqual(view["status"], "ASSESSED")

        for key in ("meals_per_day", "eating_out_frequency", "nutrition_goal"):
            self.assertIn(key, view["signals"])

    def test_with_nothing_answered_the_view_reports_what_is_missing(self):
        view = build_nutrition_evidence_view({"nutrition": {"available": False}})

        self.assertEqual(view["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("Meal pattern", view["missing_information"])


class CheckInRouteTests(unittest.TestCase):
    """The endpoints, over an in-memory stand-in for the database."""

    def setUp(self):
        self.original_db = profile_routes.db

        class _FakeDatabase:
            def __init__(self):
                self.collections = {}

            def __getitem__(self, name):
                return self.collections.setdefault(name, FakeReportsCollection())

            def __getattr__(self, name):
                if name.startswith("_"):
                    raise AttributeError(name)

                return self[name]

        self.database = _FakeDatabase()
        profile_routes.db = self.database

        inserted = self.database["users"].insert_one(
            {"name": "Check In", "email": "ci@example.com"}
        )
        self.user_id = inserted.inserted_id

    def tearDown(self):
        profile_routes.db = self.original_db

    def _current_user(self):
        return {"_id": self.user_id}

    def test_an_untouched_account_reports_nothing_answered(self):
        response = profile_routes.read_nutrition_check_in(
            current_user=self._current_user()
        )

        self.assertFalse(response["complete"])
        self.assertEqual(response["answeredCount"], 0)
        self.assertEqual(response["questionCount"], 6)
        self.assertEqual(len(response["questions"]), 6)

    def test_answers_persist_and_make_the_check_in_complete(self):
        answers = {
            "meals_per_day": 3,
            "fruit_vegetable_servings": 3,
            "water_glasses_per_day": 9,
            "processed_food_frequency": "rarely",
            "eating_out_frequency": "one_to_two_a_week",
            "nutrition_goal": "hydration",
        }

        response = profile_routes.update_nutrition_check_in(
            payload={"answers": answers}, current_user=self._current_user()
        )

        self.assertTrue(response["complete"])
        self.assertEqual(response["answeredCount"], 6)
        self.assertIn("saved", response["message"])

        # Read back from the store, not from the response.
        reloaded = profile_routes.read_nutrition_check_in(
            current_user=self._current_user()
        )

        self.assertEqual(reloaded["answers"]["meals_per_day"], 3)
        self.assertEqual(reloaded["answers"]["nutrition_goal"], "hydration")

    def test_an_answer_outside_the_options_is_refused_and_nothing_is_written(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            profile_routes.update_nutrition_check_in(
                payload={"answers": {"meals_per_day": 11}},
                current_user=self._current_user(),
            )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )

        self.assertIsNone(document)

    def test_a_saved_check_in_reaches_the_user_state(self):
        # The chain the brief asks for: check-in -> persist -> nutrition need ->
        # nutrition specialist. This asserts the middle link, which is the one
        # that was missing.
        from user_state.schema import build_user_state

        profile_routes.update_nutrition_check_in(
            payload={
                "answers": {
                    "meals_per_day": 2,
                    "water_glasses_per_day": 3,
                    "nutrition_goal": "hydration",
                }
            },
            current_user=self._current_user(),
        )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )
        state = build_user_state(profile_doc=document)

        self.assertTrue(state["nutrition"]["available"])
        self.assertEqual(state["nutrition"]["data"]["meals_per_day"], 2)

        entry = assess_nutrition_need(state)

        self.assertIn(entry["level"], ("MEDIUM", "HIGH"))


if __name__ == "__main__":
    unittest.main()
