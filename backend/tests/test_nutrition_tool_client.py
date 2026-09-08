"""The Nutrition Agent's tool seam, for the food tools added in this phase.

Every call goes through InProcessNutritionToolClient — the TEST-ONLY
double that calls the same underlying functions the Nutrition MCP Server's
tools wrap. Both a success and a failure path is exercised for each new
tool, because a client that only ever gets happy answers proves nothing
about how a real MCP error would surface.

The MCP transport itself is NOT exercised here and cannot be in this
environment: the `mcp` package cannot be installed (no PyPI network
access), so mcp_servers/nutrition_server.py and
nutrition_agent/mcp_client.py are verified by compilation and by testing
the functions underneath them, exactly as every earlier phase's MCP work
was.
"""

import importlib.util
import unittest
from unittest import mock

from nutrition_agent.tool_client import (
    InProcessNutritionToolClient,
    NutritionToolClient,
)

FOOD_LOG_STORE_AVAILABLE = (
    importlib.util.find_spec("pymongo") is not None
    and importlib.util.find_spec("bson") is not None
)

FOOD_LOG_STORE_SKIP_REASON = (
    "pymongo/bson are not installed in this environment (no PyPI network "
    "access in this sandbox); the persistence half of record_food_log "
    "cannot run here, so it is skipped rather than faked"
)


class GuidanceOnlyClient(NutritionToolClient):
    """A client implementing only the two guidance tools — the shape every
    pre-existing test double in this suite already has."""

    def search_nutrition_guidance(self, **kwargs):
        return {"topics": [], "count": 0, "metadata": {}}

    def get_nutrition_topic_details(self, topic_id):
        return {"error": "not implemented in this double", "metadata": {}}


class ClientContractTests(unittest.TestCase):
    def test_the_interface_declares_every_new_tool(self):
        for name in (
            "search_food",
            "get_food_details",
            "record_food_log",
            "calculate_food_adherence",
        ):
            self.assertTrue(hasattr(NutritionToolClient, name))

    def test_the_two_guidance_tools_remain_the_only_required_ones(self):
        self.assertEqual(
            NutritionToolClient.__abstractmethods__,
            frozenset({"search_nutrition_guidance", "get_nutrition_topic_details"}),
        )

        # A pre-existing guidance-only double must still be constructible;
        # adding the food tools must not retroactively break it.
        GuidanceOnlyClient()

    def test_an_unimplemented_food_tool_refuses_explicitly_rather_than_returning_empty(self):
        client = GuidanceOnlyClient()

        with self.assertRaises(NotImplementedError):
            client.search_food("poha")

        with self.assertRaises(NotImplementedError):
            client.record_food_log({"meal": "lunch", "food_id": "poha"}, user_id="u1")


class InProcessFoodToolTests(unittest.TestCase):
    def setUp(self):
        self.client = InProcessNutritionToolClient(
            workflow_id="wf_test", request_id="req_test"
        )

    def _assert_traced(self, result):
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["workflow_id"], "wf_test")

    def test_search_food_returns_real_curated_results_with_source_honesty(self):
        result = self.client.search_food("poha")

        self._assert_traced(result)
        self.assertEqual([r["food_id"] for r in result["results"]], ["poha"])
        self.assertFalse(
            result["secondary_sources_consulted"]["usda_fdc"]["available"]
        )

    def test_search_food_for_an_unknown_food_returns_no_results_not_an_invention(self):
        result = self.client.search_food("zzzz_not_a_food")

        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)
        self.assertFalse(
            result["secondary_sources_consulted"]["open_food_facts"]["available"]
        )

    def test_get_food_details_returns_the_record(self):
        result = self.client.get_food_details("dal_toor_cooked")

        self._assert_traced(result)
        self.assertEqual(result["food"]["category"], "pulse_legume")

    def test_get_food_details_for_an_unknown_id_returns_null_food_with_a_reason(self):
        result = self.client.get_food_details("no_such_food")

        self.assertIsNone(result["food"])
        self.assertIn("not in this project's curated", result["reason"])

    def test_calculate_food_adherence_returns_a_real_computed_result(self):
        plan = {"plan_id": "p1", "created_at": "2026-01-01T00:00:00+00:00"}
        entries = [
            {
                "meal": "lunch",
                "plan_id": "p1",
                "recorded_at": f"2026-01-0{day}T12:00:00+00:00",
            }
            for day in range(1, 8)
        ]

        result = self.client.calculate_food_adherence(
            plan, entries, period_start="2026-01-01", period_end="2026-01-07"
        )

        self._assert_traced(result)
        self.assertEqual(result["adherence"]["status"], "ADHERED")
        self.assertEqual(result["adherence"]["completion_rate"], 1.0)

    def test_calculate_food_adherence_with_no_logs_is_not_logged(self):
        result = self.client.calculate_food_adherence(
            {"plan_id": "p1"}, [], period_start="2026-01-01", period_end="2026-01-07"
        )

        self.assertEqual(result["adherence"]["status"], "NOT_LOGGED")
        self.assertIsNone(result["adherence"]["completion_rate"])

    def test_calculate_food_adherence_surfaces_a_bad_input_as_an_error_result(self):
        result = self.client.calculate_food_adherence(
            {}, [], period_start="2026-01-01", period_end="2026-01-07"
        )

        self.assertIn("error", result)
        self.assertNotIn("adherence", result)
        self._assert_traced(result)

    def test_record_food_log_refuses_an_invalid_entry_before_touching_storage(self):
        result = self.client.record_food_log({"meal": "brunch"}, user_id="u1")

        self.assertIn("error", result)
        self.assertIn("breakfast", result["error"])
        self.assertNotIn("entry", result)

    def test_record_food_log_refuses_an_entry_naming_no_food(self):
        result = self.client.record_food_log(
            {"meal": "lunch", "quantity": "1 bowl"}, user_id="u1"
        )

        self.assertIn("must name what was eaten", result["error"])


@unittest.skipUnless(FOOD_LOG_STORE_AVAILABLE, FOOD_LOG_STORE_SKIP_REASON)
class InProcessRecordFoodLogPersistenceTests(unittest.TestCase):
    def setUp(self):
        from food_log import store as food_log_store
        from tests._fake_mongo import FakeFoodLogCollection

        self.client = InProcessNutritionToolClient(
            workflow_id="wf_test", request_id="req_test"
        )
        patch = mock.patch.object(
            food_log_store, "food_log_collection", FakeFoodLogCollection()
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_valid_entry_is_persisted_and_returned_serialised(self):
        result = self.client.record_food_log(
            {"meal": "breakfast", "food_id": "poha", "quantity": "1 bowl"},
            user_id="aaaaaaaaaaaaaaaaaaaaaaaa",
            plan_id="nutrition_plan_1",
        )

        self.assertNotIn("error", result)
        self.assertEqual(result["entry"]["meal"], "breakfast")
        self.assertEqual(result["entry"]["foodId"], "poha")
        self.assertEqual(result["entry"]["planId"], "nutrition_plan_1")
        self.assertNotIn("user_id", result["entry"])

    def test_a_storage_failure_is_reported_rather_than_faked_as_a_success(self):
        with mock.patch(
            "food_log.store.save_food_log_entry",
            side_effect=RuntimeError("database unreachable"),
        ):
            result = self.client.record_food_log(
                {"meal": "lunch", "food_id": "poha"},
                user_id="aaaaaaaaaaaaaaaaaaaaaaaa",
            )

        self.assertIn("error", result)
        self.assertIn("database unreachable", result["error"])
        self.assertNotIn("entry", result)


if __name__ == "__main__":
    unittest.main()
