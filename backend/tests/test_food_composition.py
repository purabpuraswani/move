"""Real behaviour tests for the curated Indian food composition dataset.

These assert what the data actually does — lookup, search, category
spread, and above all that the two secondary sources are reported as
honestly unavailable rather than answered with invented records.
"""

import unittest

from nutrition_library import food_composition as fc
from nutrition_library.catalog import get_food, search_foods


class FoodCompositionLookupTests(unittest.TestCase):
    def test_get_food_composition_returns_the_full_record(self):
        record = fc.get_food_composition("poha")

        self.assertIsNotNone(record)
        self.assertEqual(record["food_id"], "poha")
        self.assertEqual(record["category"], "prepared_dish")
        self.assertIn("energy_kcal", record["nutrients"])
        self.assertGreater(record["nutrients"]["energy_kcal"], 0)

    def test_unknown_food_id_returns_none_not_a_guess(self):
        self.assertIsNone(fc.get_food_composition("definitely_not_a_food"))
        self.assertIsNone(fc.get_food_composition(None))
        self.assertIsNone(fc.get_food_composition(42))

    def test_provenance_is_marked_as_curated_and_approximate_on_every_record(self):
        for record in fc.FOOD_COMPOSITION:
            self.assertEqual(record["source"], "IFCT_ADAPTED")
            self.assertEqual(record["source_version"], "curated-approximate-v1")

        # The version string must not read as the real, licensed dataset.
        self.assertIn("curated", fc.SOURCE_VERSION)
        self.assertIn("approximate", fc.SOURCE_VERSION)

    def test_every_record_validates_against_the_declared_shape(self):
        for record in fc.FOOD_COMPOSITION:
            fc.validate_food_record(record)

    def test_a_malformed_record_is_refused(self):
        with self.assertRaises(fc.FoodCompositionValidationError):
            fc.validate_food_record({"food_id": "x"})

        with self.assertRaises(fc.FoodCompositionValidationError):
            fc.validate_food_record(
                {
                    "food_id": "x",
                    "food_name": "X",
                    "category": "not_a_category",
                    "serving_basis": "1",
                    "nutrients": {k: 0 for k in fc.NUTRIENT_FIELDS},
                    "source": fc.SOURCE,
                    "source_version": fc.SOURCE_VERSION,
                }
            )


class FoodCompositionSearchTests(unittest.TestCase):
    def test_search_by_name_is_case_insensitive_substring(self):
        results = fc.search_food_composition("POHA")

        self.assertEqual([r["food_id"] for r in results], ["poha"])

    def test_search_by_category_returns_every_food_in_it(self):
        results = fc.search_food_composition("fruit")
        ids = {r["food_id"] for r in results}

        self.assertIn("banana", ids)
        self.assertIn("guava", ids)
        self.assertTrue(all(r["category"] == "fruit" for r in results))

    def test_search_with_no_match_returns_empty_not_a_nearest_guess(self):
        self.assertEqual(fc.search_food_composition("zzzzz_no_such_food"), [])

    def test_blank_query_returns_the_whole_dataset_deterministically(self):
        first = fc.search_food_composition("")
        second = fc.search_food_composition(None)

        self.assertEqual(len(first), len(fc.FOOD_COMPOSITION))
        self.assertEqual(
            [r["food_id"] for r in first], [r["food_id"] for r in second]
        )


class CuratedDatasetCoverageTests(unittest.TestCase):
    def test_dataset_is_a_reasonable_size(self):
        self.assertGreaterEqual(len(fc.FOOD_COMPOSITION), 40)

    def test_every_declared_category_is_actually_represented(self):
        represented = {record["category"] for record in fc.FOOD_COMPOSITION}

        self.assertEqual(represented, set(fc.CATEGORIES))

    def test_common_indian_staples_are_present(self):
        ids = set(fc.list_food_ids())

        for staple in ("roti_wheat", "dal_toor_cooked", "idli", "poha", "curd_dahi"):
            self.assertIn(staple, ids)

    def test_food_ids_are_unique(self):
        ids = fc.list_food_ids()

        self.assertEqual(len(ids), len(set(ids)))


class SecondarySourceHonestyTests(unittest.TestCase):
    def test_both_secondary_sources_are_declared_unavailable_with_a_reason(self):
        for name in ("open_food_facts", "usda_fdc"):
            source = fc.SECONDARY_SOURCES[name]

            self.assertFalse(source["available"])
            self.assertIn("no network egress", source["reason"])

    def test_all_sources_search_reports_unavailability_and_never_fakes_a_result(self):
        result = fc.search_foods_all_sources("dal")

        self.assertTrue(result["primary_source"]["available"])
        self.assertEqual(result["count"], len(result["results"]))
        self.assertEqual(result["secondary_sources_consulted"], fc.SECONDARY_SOURCES)

        # Every returned record came from the curated primary dataset.
        for record in result["results"]:
            self.assertIs(record, fc.get_food_composition(record["food_id"]))

    def test_a_food_only_a_secondary_source_would_know_returns_no_results(self):
        result = fc.search_foods_all_sources("branded packaged protein bar")

        self.assertEqual(result["results"], [])
        self.assertFalse(
            result["secondary_sources_consulted"]["open_food_facts"]["available"]
        )


class CatalogWrapperTests(unittest.TestCase):
    def test_catalog_search_foods_delegates_to_all_sources_search(self):
        self.assertEqual(search_foods("idli"), fc.search_foods_all_sources("idli"))

    def test_catalog_get_food_delegates_to_get_food_composition(self):
        self.assertEqual(get_food("idli"), fc.get_food_composition("idli"))
        self.assertIsNone(get_food("no_such_food"))


if __name__ == "__main__":
    unittest.main()
