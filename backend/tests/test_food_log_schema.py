"""Validation behaviour for a submitted food log entry.

No database is involved here — food_log/schema.py never touches one, the
same split exercise_assessment/schema.py and store.py already use.
"""

import unittest

from food_log.schema import (
    MEAL_TYPES,
    FoodLogValidationError,
    build_food_log_entry,
    validate_food_log_entry,
)


class ValidEntryTests(unittest.TestCase):
    def test_a_minimal_entry_with_a_food_id_is_accepted(self):
        entry = build_food_log_entry("breakfast", food_id="poha")

        self.assertEqual(entry["meal"], "breakfast")
        self.assertEqual(entry["food_id"], "poha")
        self.assertIsNone(entry["food_name"])
        self.assertIsNone(entry["quantity"])

    def test_free_text_quantity_is_kept_as_written_not_converted_to_grams(self):
        entry = build_food_log_entry(
            "lunch", food_name="Ghar ka dal chawal", quantity="1 bowl and 2 rotis"
        )

        self.assertEqual(entry["quantity"], "1 bowl and 2 rotis")
        self.assertEqual(entry["food_name"], "Ghar ka dal chawal")

    def test_every_meal_type_is_accepted(self):
        for meal in MEAL_TYPES:
            self.assertEqual(build_food_log_entry(meal, food_id="water")["meal"], meal)

    def test_water_intake_and_notes_round_trip(self):
        entry = build_food_log_entry(
            "snack", food_name="Tea", notes="  after work  ", water_intake_ml=250
        )

        self.assertEqual(entry["notes"], "after work")
        self.assertEqual(entry["water_intake_ml"], 250)

    def test_blank_strings_are_normalised_to_none_not_kept_as_empty(self):
        entry = build_food_log_entry("dinner", food_id="idli", quantity="   ")

        self.assertIsNone(entry["quantity"])

    def test_validate_is_the_same_contract_as_build(self):
        built = build_food_log_entry("lunch", food_id="poha", quantity="1 bowl")
        validated = validate_food_log_entry(
            {"meal": "lunch", "food_id": "poha", "quantity": "1 bowl"}
        )

        self.assertEqual(built, validated)


class RefusedEntryTests(unittest.TestCase):
    def test_a_missing_meal_is_refused(self):
        with self.assertRaises(FoodLogValidationError):
            build_food_log_entry(None, food_id="poha")

    def test_an_unrecognised_meal_is_refused_not_coerced(self):
        with self.assertRaises(FoodLogValidationError) as caught:
            build_food_log_entry("brunch", food_id="poha")

        self.assertIn("breakfast", str(caught.exception))

    def test_an_entry_naming_no_food_at_all_is_refused(self):
        with self.assertRaises(FoodLogValidationError) as caught:
            build_food_log_entry("lunch", quantity="1 bowl")

        self.assertIn("must name what was eaten", str(caught.exception))

    def test_a_blank_food_name_does_not_count_as_naming_a_food(self):
        with self.assertRaises(FoodLogValidationError):
            build_food_log_entry("lunch", food_name="   ")

    def test_an_unexpected_field_is_refused(self):
        with self.assertRaises(FoodLogValidationError) as caught:
            validate_food_log_entry(
                {"meal": "lunch", "food_id": "poha", "calories": 250}
            )

        self.assertIn("calories", str(caught.exception))

    def test_a_negative_or_absurd_water_intake_is_refused(self):
        with self.assertRaises(FoodLogValidationError):
            build_food_log_entry("snack", food_id="water", water_intake_ml=-1)

        with self.assertRaises(FoodLogValidationError):
            build_food_log_entry("snack", food_id="water", water_intake_ml=999999)

    def test_a_non_object_entry_is_refused(self):
        with self.assertRaises(FoodLogValidationError):
            validate_food_log_entry("breakfast: poha")


if __name__ == "__main__":
    unittest.main()
