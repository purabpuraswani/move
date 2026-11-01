import unittest
from unittest import mock

from database import SQLiteClient
from daily_checkins import store


class DailyCheckinStoreTests(unittest.TestCase):
    def setUp(self):
        self.client = SQLiteClient(":memory:")
        self.collection = self.client["daily_checkins_test"]
        self.patch = mock.patch.object(store, "daily_checkins_collection", self.collection)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.client.close)

    def test_same_day_updates_merge_and_users_remain_isolated(self):
        store.save_daily_checkin("user-a", "2026-11-01", {"steps": 4200})
        store.save_daily_checkin("user-a", "2026-11-01", {"sleep_hours": 7})
        store.save_daily_checkin("user-b", "2026-11-01", {"steps": 900})

        mine = store.list_daily_checkins("user-a")
        theirs = store.list_daily_checkins("user-b")
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["steps"], 4200)
        self.assertEqual(mine[0]["sleep_hours"], 7)
        self.assertEqual(len(theirs), 1)
        self.assertEqual(theirs[0]["steps"], 900)


if __name__ == "__main__":
    unittest.main()
