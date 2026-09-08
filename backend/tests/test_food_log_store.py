"""Persistence behaviour for food log entries, against a fake collection.

The module under test is the real, unmodified food_log/store.py; only the
MongoDB collection it talks to is swapped out (tests/_fake_mongo.py), the
same way tests/test_report_pipeline_integration.py fakes reports/store.py's
collection.

food_log/store.py (and _fake_mongo, which mirrors its ObjectId usage) needs
pymongo/bson, which are not installed in this development sandbox (no PyPI
network access — the same already-documented constraint as the `mcp`
package). The import below is therefore guarded exactly like every other
dependency-gated test file in this suite: skip honestly and visibly, never
by faking a passing result.
"""

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from food_log.schema import build_food_log_entry

FOOD_LOG_STORE_AVAILABLE = (
    importlib.util.find_spec("pymongo") is not None
    and importlib.util.find_spec("bson") is not None
)

FOOD_LOG_STORE_SKIP_REASON = (
    "pymongo/bson are not installed in this environment (no PyPI network "
    "access in this sandbox); install them in the project's real .venv "
    "(where food_log/store.py already runs against a real MongoDB) to run "
    "these persistence tests instead of skipping them"
)

if FOOD_LOG_STORE_AVAILABLE:
    from food_log import store as food_log_store
    from tests._fake_mongo import FakeFoodLogCollection

USER_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_USER_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"

DAY_ONE = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


@unittest.skipUnless(FOOD_LOG_STORE_AVAILABLE, FOOD_LOG_STORE_SKIP_REASON)
class FoodLogStoreTests(unittest.TestCase):
    def setUp(self):
        self.fake_collection = FakeFoodLogCollection()
        self._patch = mock.patch.object(
            food_log_store, "food_log_collection", self.fake_collection
        )
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _save(self, user_id=USER_ID, meal="breakfast", food_id="poha", plan_id=None,
              recorded_at=None):
        entry = build_food_log_entry(meal, food_id=food_id, quantity="1 bowl")
        saved = food_log_store.save_food_log_entry(user_id, entry, plan_id=plan_id)

        if recorded_at is not None:
            # The store sets recorded_at server-side; a test that needs a
            # specific day rewrites it in the fake collection afterwards
            # rather than passing a client-supplied timestamp in.
            self.fake_collection._docs[str(saved["_id"])]["recorded_at"] = recorded_at
            saved["recorded_at"] = recorded_at

        return saved

    def test_a_saved_entry_gets_ownership_and_a_server_set_timestamp(self):
        saved = self._save(plan_id="nutrition_plan_1")

        self.assertEqual(saved["user_id"], USER_ID)
        self.assertEqual(saved["plan_id"], "nutrition_plan_1")
        self.assertIsInstance(saved["recorded_at"], datetime)
        self.assertEqual(saved["meal"], "breakfast")

    def test_entries_accumulate_and_are_never_overwritten(self):
        self._save(meal="breakfast")
        self._save(meal="lunch")
        self._save(meal="dinner")

        self.assertEqual(food_log_store.count_food_log_entries(USER_ID), 3)

    def test_listing_is_scoped_to_the_owner(self):
        self._save(user_id=USER_ID)
        self._save(user_id=OTHER_USER_ID)

        mine = food_log_store.list_food_log_entries(USER_ID)
        theirs = food_log_store.list_food_log_entries(OTHER_USER_ID)

        self.assertEqual(len(mine), 1)
        self.assertEqual(len(theirs), 1)
        self.assertEqual(mine[0]["user_id"], USER_ID)
        self.assertEqual(food_log_store.count_food_log_entries(USER_ID), 1)

    def test_get_entry_refuses_another_users_entry(self):
        theirs = self._save(user_id=OTHER_USER_ID)

        with self.assertRaises(food_log_store.FoodLogEntryNotFoundError):
            food_log_store.get_food_log_entry(USER_ID, str(theirs["_id"]))

        fetched = food_log_store.get_food_log_entry(OTHER_USER_ID, str(theirs["_id"]))
        self.assertEqual(fetched["user_id"], OTHER_USER_ID)

    def test_a_malformed_entry_id_is_a_not_found_not_a_crash(self):
        with self.assertRaises(food_log_store.FoodLogEntryNotFoundError):
            food_log_store.get_food_log_entry(USER_ID, "not-an-object-id")

    def test_filtering_by_meal(self):
        self._save(meal="breakfast")
        self._save(meal="dinner")

        results = food_log_store.list_food_log_entries(USER_ID, meal="dinner")

        self.assertEqual([r["meal"] for r in results], ["dinner"])

    def test_filtering_by_date_range(self):
        self._save(meal="breakfast", recorded_at=DAY_ONE)
        self._save(meal="lunch", recorded_at=DAY_ONE + timedelta(days=5))

        inside = food_log_store.list_food_log_entries(
            USER_ID,
            date_from=DAY_ONE - timedelta(hours=1),
            date_to=DAY_ONE + timedelta(hours=1),
        )

        self.assertEqual([r["meal"] for r in inside], ["breakfast"])

    def test_filtering_by_plan_id(self):
        self._save(plan_id="plan_a")
        self._save(plan_id="plan_b")

        results = food_log_store.list_food_log_entries(USER_ID, plan_id="plan_a")

        self.assertEqual(len(results), 1)
        self.assertEqual(
            food_log_store.count_food_log_entries(USER_ID, plan_id="plan_b"), 1
        )

    def test_serialisation_never_leaks_the_owner_id(self):
        saved = self._save(plan_id="plan_a")

        serialised = food_log_store.serialise_food_log_entry(saved)

        self.assertNotIn("user_id", serialised)
        self.assertEqual(serialised["foodId"], "poha")
        self.assertEqual(serialised["planId"], "plan_a")
        self.assertEqual(serialised["id"], str(saved["_id"]))
        self.assertTrue(serialised["recordedAt"].startswith("20"))

    def test_ensure_indexes_is_safe_to_run_repeatedly(self):
        food_log_store.ensure_indexes()
        food_log_store.ensure_indexes()


if __name__ == "__main__":
    unittest.main()
