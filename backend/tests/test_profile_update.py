import unittest
from unittest.mock import patch


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    def find_one(self, query):
        return self.rows.get(query["user_id"])

    def update_one(self, query, update, upsert=False):
        row = self.rows.setdefault(query["user_id"], {})
        row.update(update["$set"])


class ProfileUpdateTests(unittest.TestCase):
    def setUp(self):
        from routes import profile
        self.profile = profile
        self.rows = {"user-1": {"user_id": "user-1", "age": 40, "meal_pattern": "irregular", "food_allergies": ["peanut"], "health": {"diabetes": "no", "joint_pain": "yes"}}}
        self.collection = _Collection(self.rows)
        self.db = {"health_profiles": self.collection}
        self.patcher = patch.object(profile, "db", self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_partial_edit_preserves_unrelated_fields_and_explicit_none(self):
        result = self.profile.update_profile_fields(
            {"food_allergies": [], "nutrition_goals": ["more produce"]},
            current_user={"_id": "user-1"},
        )
        self.assertEqual(result["message"], "Profile updated")
        self.assertEqual(self.rows["user-1"]["food_allergies"], [])
        self.assertEqual(self.rows["user-1"]["age"], 40)
        self.assertEqual(self.rows["user-1"]["meal_pattern"], "irregular")

    def test_edit_is_scoped_to_authenticated_user(self):
        self.profile.update_profile_fields(
            {"daily_routines": ["after lunch"]}, current_user={"_id": "user-2"}
        )
        self.assertEqual(self.rows["user-1"]["food_allergies"], ["peanut"])
        self.assertEqual(self.rows["user-2"]["daily_routines"], ["after lunch"])

    def test_health_screen_patch_preserves_other_answers(self):
        self.profile.update_profile_fields(
            {"health": {"joint_pain": "no"}}, current_user={"_id": "user-1"}
        )
        self.assertEqual(self.rows["user-1"]["health"]["joint_pain"], "no")
        self.assertEqual(self.rows["user-1"]["health"]["diabetes"], "no")

    def test_activity_and_recovery_answers_are_editable_for_the_next_workflow(self):
        self.profile.update_profile_fields(
            {
                "daily_steps": 6961,
                "sleep_hours": 7.5,
                "sleep_quality": "average",
                "stress_level": "moderate",
                "recovery_difficulties": ["late bedtime"],
            },
            current_user={"_id": "user-1"},
        )
        self.assertEqual(self.rows["user-1"]["daily_steps"], 6961)
        self.assertEqual(self.rows["user-1"]["sleep_hours"], 7.5)
        self.assertEqual(self.rows["user-1"]["sleep_quality"], "average")
        self.assertEqual(self.rows["user-1"]["stress_level"], "moderate")
        self.assertEqual(self.rows["user-1"]["recovery_difficulties"], ["late bedtime"])


if __name__ == "__main__":
    unittest.main()
