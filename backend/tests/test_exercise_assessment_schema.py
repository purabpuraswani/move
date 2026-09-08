import unittest

from exercise_assessment.schema import (
    ExerciseResultValidationError,
    record_exercise_result,
    validate_exercise_result,
)
from exercise_library.catalog import ExerciseNotFoundError


class ValidExerciseResultTests(unittest.TestCase):
    def test_a_completed_result_with_valid_measurements_is_accepted(self):
        result = validate_exercise_result(
            {
                "exerciseId": "wall-sit",
                "status": "completed",
                "measurements": {"durationSeconds": 18, "completion": 0.9},
            }
        )
        self.assertEqual(result["exerciseId"], "wall-sit")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["measurements"]["durationSeconds"], 18)
        self.assertEqual(result["errors"], [])

    def test_an_invalid_result_carries_no_measurements(self):
        result = validate_exercise_result(
            {"exerciseId": "wall-sit", "status": "invalid", "measurements": None}
        )
        self.assertEqual(result["measurements"], {})

    def test_timestamps_round_trip(self):
        result = validate_exercise_result(
            {
                "exerciseId": "chair-sit-to-stand",
                "status": "completed",
                "measurements": {"repetitions": 5, "durationSeconds": 12.3, "completion": 1},
                "startedAt": "2026-01-01T10:00:00Z",
                "completedAt": "2026-01-01T10:00:12Z",
            }
        )
        self.assertEqual(result["startedAt"], "2026-01-01T10:00:00Z")

    def test_errors_list_is_preserved(self):
        result = validate_exercise_result(
            {
                "exerciseId": "wall-sit",
                "status": "incomplete",
                "measurements": {"durationSeconds": 4},
                "errors": ["pose_lost", "user_left_frame"],
            }
        )
        self.assertEqual(result["errors"], ["pose_lost", "user_left_frame"])

    def test_record_exercise_result_is_equivalent_to_validate(self):
        payload = {
            "exerciseId": "wall-sit",
            "status": "completed",
            "measurements": {"durationSeconds": 18, "completion": 0.9},
        }
        self.assertEqual(record_exercise_result(payload), validate_exercise_result(payload))


class RejectedExerciseResultTests(unittest.TestCase):
    def test_unknown_exercise_id_raises_exercise_not_found(self):
        with self.assertRaises(ExerciseNotFoundError):
            validate_exercise_result(
                {"exerciseId": "not-real", "status": "completed", "measurements": {"repetitions": 1}}
            )

    def test_missing_exercise_id_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result({"status": "completed", "measurements": {}})

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "bogus", "measurements": {"durationSeconds": 1}}
            )

    def test_completed_result_with_no_measurements_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result({"exerciseId": "wall-sit", "status": "completed", "measurements": {}})

    def test_invalid_result_with_measurements_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "invalid", "measurements": {"durationSeconds": 1}}
            )

    def test_a_metric_not_declared_by_the_exercise_is_rejected(self):
        # wall-sit does not declare "repetitions" as a measurable metric.
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "completed", "measurements": {"repetitions": 3}}
            )

    def test_an_unrecognised_metric_name_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "completed", "measurements": {"totallyMadeUp": 1}}
            )

    def test_negative_repetitions_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "chair-sit-to-stand",
                    "status": "completed",
                    "measurements": {"repetitions": -1},
                }
            )

    def test_completion_out_of_range_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "completed", "measurements": {"completion": 1.5}}
            )

    def test_unexpected_top_level_field_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "completed",
                    "measurements": {"durationSeconds": 1},
                    "notAField": True,
                }
            )

    def test_malformed_timestamp_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "completed",
                    "measurements": {"durationSeconds": 1},
                    "startedAt": "not-a-timestamp",
                }
            )

    def test_a_field_naming_video_data_is_rejected_outright(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "completed",
                    "measurements": {"durationSeconds": 1, "rawFrameData": "abc"},
                }
            )

    def test_a_field_naming_pose_data_holding_a_list_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "completed",
                    "measurements": {"durationSeconds": 1, "keypointSequence": [1, 2, 3]},
                }
            )

    def test_too_many_error_codes_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "incomplete",
                    "measurements": {"durationSeconds": 1},
                    "errors": [f"code-{i}" for i in range(20)],
                }
            )

    def test_non_dict_input_is_rejected(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result("not a dict")


if __name__ == "__main__":
    unittest.main()
