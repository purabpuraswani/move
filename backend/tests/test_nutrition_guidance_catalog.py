"""The ICMR-NIN guidance set, and how the catalog serves both sets together."""

import unittest

from nutrition_library.catalog import (
    ALL_NUTRITION_TOPICS,
    get_nutrition_topic_details,
    list_topic_ids,
    search_nutrition_guidance,
    topics_for_signal,
)
from nutrition_library.data import NUTRITION_TOPICS, USDA_MYPLATE_REFERENCE
from nutrition_library.guidance_icmr_nin import ICMR_NIN_REFERENCE, ICMR_NIN_TOPICS
from nutrition_library.schema import validate_nutrition_topic


class IcmrNinGuidanceTests(unittest.TestCase):
    def test_every_icmr_topic_validates_against_the_existing_topic_schema(self):
        for topic in ICMR_NIN_TOPICS:
            validate_nutrition_topic(topic)

    def test_there_are_between_four_and_six_general_themes(self):
        self.assertGreaterEqual(len(ICMR_NIN_TOPICS), 4)
        self.assertLessEqual(len(ICMR_NIN_TOPICS), 6)

    def test_every_icmr_topic_cites_the_icmr_nin_reference_and_says_it_is_adapted(self):
        for topic in ICMR_NIN_TOPICS:
            self.assertEqual(topic["reference"], ICMR_NIN_REFERENCE)

        self.assertIn("ICMR-NIN Dietary Guidelines for Indians (2024)", ICMR_NIN_REFERENCE)
        self.assertIn("not a verbatim quotation", ICMR_NIN_REFERENCE)

    def test_the_two_guidance_sets_do_not_share_a_topic_id(self):
        usda_ids = {topic["topic_id"] for topic in NUTRITION_TOPICS}
        icmr_ids = {topic["topic_id"] for topic in ICMR_NIN_TOPICS}

        self.assertEqual(usda_ids & icmr_ids, set())


class CombinedCatalogTests(unittest.TestCase):
    def test_search_includes_both_sets_by_default(self):
        results = search_nutrition_guidance()

        self.assertEqual(len(results), len(ALL_NUTRITION_TOPICS))
        references = {topic["reference"] for topic in results}
        self.assertIn(USDA_MYPLATE_REFERENCE, references)
        self.assertIn(ICMR_NIN_REFERENCE, references)

    def test_include_icmr_false_returns_only_the_original_set(self):
        results = search_nutrition_guidance(include_icmr=False)

        self.assertEqual([t["topic_id"] for t in results],
                         [t["topic_id"] for t in NUTRITION_TOPICS])

    def test_the_original_topics_still_come_first_so_results_zero_is_unchanged(self):
        for signal in ("meal_pattern", "fruit_vegetable_servings",
                       "water_glasses_per_day", "processed_food_frequency"):
            with_icmr = search_nutrition_guidance(target_signal=signal)
            without = search_nutrition_guidance(target_signal=signal, include_icmr=False)

            self.assertEqual(with_icmr[0]["topic_id"], without[0]["topic_id"])

    def test_details_lookup_resolves_topics_from_both_sets(self):
        self.assertEqual(
            get_nutrition_topic_details("build_a_hydration_habit")["reference"],
            USDA_MYPLATE_REFERENCE,
        )
        self.assertEqual(
            get_nutrition_topic_details("drink_enough_safe_water")["reference"],
            ICMR_NIN_REFERENCE,
        )

    def test_list_topic_ids_covers_both_sets(self):
        ids = list_topic_ids()

        self.assertIn("increase_fruit_vegetable_intake", ids)
        self.assertIn("moderate_salt_sugar_and_fat", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_topics_for_signal_returns_both_sets_original_first(self):
        topics = topics_for_signal("water_glasses_per_day")

        self.assertEqual(topics[0]["reference"], USDA_MYPLATE_REFERENCE)
        self.assertIn(ICMR_NIN_REFERENCE, {t["reference"] for t in topics})


if __name__ == "__main__":
    unittest.main()
