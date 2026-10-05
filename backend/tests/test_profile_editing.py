"""The editable profile: validation, persistence, and its effect on planning.

The point of these tests is the last one. An editable profile is only real if a
change reaches the User State the Orchestrator reads — otherwise the editor
persists a number that nothing downstream ever sees, which is a worse outcome
than having no editor at all.
"""

import unittest

from bson import ObjectId

from routes import profile as profile_routes
from routes.profile_spec import (
    ProfileValidationError,
    calculate_bmi,
    describe,
    validate_changes,
    validate_value,
)
from tests._fake_mongo import FakeReportsCollection
from user_state.schema import build_user_state


class _FakeDatabase:
    """Just enough of a database for the profile routes: `db["name"]` and
    `db.name` both returning an in-memory collection."""

    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeReportsCollection())

    def __getattr__(self, name):
        # Only reached for names not set on the instance, and the routes use
        # both `db["health_profiles"]` and `db.users`.
        if name.startswith("_"):
            raise AttributeError(name)

        return self[name]


class ProfileValidationTests(unittest.TestCase):
    def test_a_number_outside_its_range_is_refused_not_clamped(self):
        with self.assertRaises(ProfileValidationError):
            validate_value("daily_steps", 999999)

        with self.assertRaises(ProfileValidationError):
            validate_value("age", 3)

        with self.assertRaises(ProfileValidationError):
            validate_value("height_cm", -170)

    def test_a_whole_number_field_refuses_a_fraction(self):
        with self.assertRaises(ProfileValidationError):
            validate_value("exercise_days", 3.5)

        self.assertEqual(validate_value("exercise_days", 3), 3)

    def test_a_boolean_is_not_a_number(self):
        with self.assertRaises(ProfileValidationError):
            validate_value("daily_steps", True)

    def test_a_select_only_accepts_its_own_options(self):
        self.assertEqual(validate_value("work_type", "mixed"), "mixed")

        with self.assertRaises(ProfileValidationError):
            validate_value("work_type", "astronaut")

        with self.assertRaises(ProfileValidationError):
            validate_value("sex", "unspecified")

    def test_an_unknown_field_is_refused_outright(self):
        # This is the guard that keeps the endpoint from being a general-purpose
        # write into the profile document.
        with self.assertRaises(ProfileValidationError):
            validate_value("password_hash", "x")

        with self.assertRaises(ProfileValidationError):
            validate_value("health", {"diabetes": "yes"})

    def test_clearing_a_field_stores_null(self):
        self.assertIsNone(validate_value("sleep_quality", ""))
        self.assertIsNone(validate_value("daily_steps", None))

    def test_a_whole_update_is_refused_when_any_field_is_bad(self):
        with self.assertRaises(ProfileValidationError):
            validate_changes({"daily_steps": 6000, "work_type": "nope"})

    def test_bmi_is_computed_from_the_two_stored_values(self):
        self.assertEqual(calculate_bmi(180, 81), 25.0)
        self.assertIsNone(calculate_bmi(None, 81))
        self.assertIsNone(calculate_bmi(180, None))

    def test_the_health_answers_are_not_editable_anywhere(self):
        keys = {
            field["key"]
            for section in describe({})
            for field in section["fields"]
        }

        for health_key in (
            "diabetes",
            "hypertension",
            "heart_condition",
            "joint_pain",
            "back_neck_pain",
            "previous_injury",
        ):
            self.assertNotIn(health_key, keys)

    def test_every_section_the_profile_screen_shows_is_present(self):
        titles = [section["title"] for section in describe({})]

        self.assertEqual(
            titles,
            ["Basic information", "Body", "Lifestyle", "Goals & preferences"],
        )


class ProfileRouteTests(unittest.TestCase):
    """The routes themselves, over an in-memory stand-in for the database."""

    def setUp(self):
        self.original_db = profile_routes.db
        self.database = _FakeDatabase()
        profile_routes.db = self.database

        self.user_id = ObjectId()
        # The fake collection assigns its own _id, exactly as Mongo does when a
        # document is inserted without one, so the id in use is whatever came
        # back rather than the one this test guessed at.
        inserted = self.database["users"].insert_one(
            {"_id": self.user_id, "name": "Original Name", "email": "a@example.com"}
        )
        self.user_id = inserted.inserted_id
        self.database["health_profiles"].insert_one(
            {
                "user_id": str(self.user_id),
                "age": 54,
                "sex": "female",
                "height_cm": 162.0,
                "weight_kg": 74.0,
                "bmi": 28.2,
                "daily_steps": 3000,
                "work_type": "mostly_sitting",
                "health": {"diabetes": "no", "hypertension": "yes"},
            }
        )

    def tearDown(self):
        profile_routes.db = self.original_db

    def _current_user(self):
        return {"_id": self.user_id, "email": "a@example.com"}

    def test_the_profile_loads_with_its_current_values(self):
        response = profile_routes.read_profile(current_user=self._current_user())

        self.assertTrue(response["complete"])

        values = {
            field["key"]: field["value"]
            for section in response["sections"]
            for field in section["fields"]
        }

        self.assertEqual(values["age"], 54)
        self.assertEqual(values["name"], "Original Name")
        self.assertEqual(values["daily_steps"], 3000)

    def test_a_partial_update_changes_only_what_was_sent(self):
        profile_routes.update_profile(
            payload={"fields": {"daily_steps": 6000, "exercise_days": 5}},
            current_user=self._current_user(),
        )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )

        self.assertEqual(document["daily_steps"], 6000)
        self.assertEqual(document["exercise_days"], 5)
        # Untouched by a save from one section.
        self.assertEqual(document["age"], 54)
        self.assertEqual(document["work_type"], "mostly_sitting")

    def test_a_change_is_reported_back_with_what_happens_next(self):
        response = profile_routes.update_profile(
            payload={"fields": {"daily_steps": 6000}},
            current_user=self._current_user(),
        )

        self.assertIn("Future plan reviews", response["message"])

        values = {
            field["key"]: field["value"]
            for section in response["sections"]
            for field in section["fields"]
        }

        self.assertEqual(values["daily_steps"], 6000)

    def test_height_or_weight_recomputes_bmi(self):
        profile_routes.update_profile(
            payload={"fields": {"height_cm": 180, "weight_kg": 81}},
            current_user=self._current_user(),
        )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )

        self.assertEqual(document["bmi"], 25.0)

    def test_a_bad_field_leaves_the_stored_profile_untouched(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            profile_routes.update_profile(
                payload={"fields": {"daily_steps": 6000, "work_type": "nope"}},
                current_user=self._current_user(),
            )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )

        self.assertEqual(document["daily_steps"], 3000)

    def test_the_name_is_stored_on_the_user_document(self):
        profile_routes.update_profile(
            payload={"fields": {"name": "New Name"}},
            current_user=self._current_user(),
        )

        user = self.database["users"].find_one({"_id": self.user_id})

        self.assertEqual(user["name"], "New Name")

    def test_an_edit_to_the_profile_reaches_the_user_state(self):
        # The acceptance criterion that matters: future orchestration must see
        # the new answer. The User State is built from the profile document, so
        # this asserts the whole chain rather than the write alone.
        profile_routes.update_profile(
            payload={"fields": {"exercise_days": 5, "daily_steps": 8500}},
            current_user=self._current_user(),
        )

        document = self.database["health_profiles"].find_one(
            {"user_id": str(self.user_id)}
        )
        state = build_user_state(profile_doc=document)

        questionnaire = state["questionnaire"]["data"]

        self.assertEqual(questionnaire["exercise_days"], 5)
        self.assertEqual(questionnaire["daily_steps"], 8500)


if __name__ == "__main__":
    unittest.main()
