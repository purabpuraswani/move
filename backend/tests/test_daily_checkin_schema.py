import unittest

from daily_checkins.schema import DailyCheckinValidationError, validate_checkin


class DailyCheckinSchemaTests(unittest.TestCase):
    def test_partial_real_values_are_accepted_without_filling_missing_fields(self):
        self.assertEqual(validate_checkin({"steps": 4200, "sleep_hours": 7.5}), {"steps": 4200, "sleep_hours": 7.5})

    def test_explicit_zero_is_kept_distinct_from_missing(self):
        self.assertEqual(validate_checkin({"movement_breaks": 0}), {"movement_breaks": 0})

    def test_missing_or_out_of_range_values_are_rejected(self):
        with self.assertRaises(DailyCheckinValidationError):
            validate_checkin({})
        with self.assertRaises(DailyCheckinValidationError):
            validate_checkin({"sleep_hours": 25})

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(DailyCheckinValidationError):
            validate_checkin({"stress_guess": 4})


if __name__ == "__main__":
    unittest.main()
