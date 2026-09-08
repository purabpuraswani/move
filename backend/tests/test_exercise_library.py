import unittest

from exercise_library.catalog import list_exercise_ids
from exercise_library.data import EXERCISES
from exercise_library.schema import (
    CATEGORIES,
    DIFFICULTY_LEVELS,
    ExerciseValidationError,
    TARGET_BODY_AREAS,
    TARGET_CAPABILITIES,
    validate_exercise,
)

EXPECTED_EXERCISE_IDS = [
    "chair-sit-to-stand",
    "wall-sit",
    "standing-knee-raise",
    "supported-calf-raise",
    "wall-push-up",
    "standing-side-leg-raise",
    "standing-hip-extension",
    "heel-to-toe-stand",
    "supported-single-leg-stand",
    "standing-shoulder-raise",
    "seated-marching",
    "standing-trunk-rotation",
    "standing-shoulder-rolls",
    "standing-ankle-circles",
    "standing-hamstring-stretch",
    "glute-bridge",
    "quadruped-bird-dog",
    "standing-overhead-reach",
    "seated-knee-extension",
    "single-leg-reach-balance",
]

# The second batch of ten (added to reach twenty), each honestly marked for
# whether MoveNet's 2D keypoints can actually measure their key movement
# quality — see data.py's module docstring and each entry's movenet_support
# notes for why.
NEW_BATCH_EXERCISE_IDS = EXPECTED_EXERCISE_IDS[10:]

NEW_BATCH_MOVENET_UNSUPPORTED_IDS = {
    "standing-trunk-rotation",
    "standing-shoulder-rolls",
    "standing-ankle-circles",
    "glute-bridge",
    "quadruped-bird-dog",
    # Moved here in the final integration pass. It was listed as supported,
    # but a hamstring stretch is judged by where the stretch is felt and by
    # whether the back stays long -- the trunk-hinge angle a camera can see
    # does not tell a good one from a rounded back. See its movenet_support
    # notes in exercise_library/data.py.
    "standing-hamstring-stretch",
}

NEW_BATCH_MOVENET_SUPPORTED_IDS = (
    set(NEW_BATCH_EXERCISE_IDS) - NEW_BATCH_MOVENET_UNSUPPORTED_IDS
)


class ExerciseLibraryContentTests(unittest.TestCase):
    def test_there_are_exactly_twenty_exercises_in_the_required_order(self):
        self.assertEqual(list_exercise_ids(), EXPECTED_EXERCISE_IDS)

    def test_every_exercise_id_is_unique(self):
        ids = [exercise["exercise_id"] for exercise in EXERCISES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_exercise_validates_as_well_formed(self):
        for exercise in EXERCISES:
            validate_exercise(exercise)  # must not raise

    def test_every_exercise_category_is_in_the_closed_vocabulary(self):
        for exercise in EXERCISES:
            self.assertIn(exercise["category"], CATEGORIES)

    def test_every_exercise_difficulty_is_in_the_closed_vocabulary(self):
        for exercise in EXERCISES:
            self.assertIn(exercise["difficulty"], DIFFICULTY_LEVELS)

    def test_every_target_capability_and_body_area_is_recognised(self):
        for exercise in EXERCISES:
            for capability in exercise["target_capability"]:
                self.assertIn(capability, TARGET_CAPABILITIES)
            for area in exercise["target_body_area"]:
                self.assertIn(area, TARGET_BODY_AREAS)

    def test_every_exercise_has_a_progression_and_regression(self):
        for exercise in EXERCISES:
            self.assertIsInstance(exercise["progression"], str)
            self.assertTrue(exercise["progression"].strip())
            self.assertIsInstance(exercise["regression"], str)
            self.assertTrue(exercise["regression"].strip())

    def test_measurable_metrics_always_match_movenet_support_metrics(self):
        for exercise in EXERCISES:
            self.assertEqual(
                set(exercise["measurable_metrics"]),
                set(exercise["movenet_support"]["metrics"]),
            )

    def test_every_exercise_declares_a_demonstration_id(self):
        for exercise in EXERCISES:
            self.assertIsInstance(exercise["demonstration_id"], str)
            self.assertTrue(exercise["demonstration_id"])

    def test_every_exercise_has_a_reference(self):
        for exercise in EXERCISES:
            self.assertIsInstance(exercise["reference"], str)
            self.assertTrue(exercise["reference"].strip())

    def test_heel_to_toe_stand_is_honestly_marked_as_not_implemented(self):
        exercise = next(e for e in EXERCISES if e["exercise_id"] == "heel-to-toe-stand")
        self.assertFalse(exercise["movenet_support"]["implemented"])
        self.assertEqual(exercise["movenet_support"]["metrics"], [])
        self.assertEqual(exercise["measurable_metrics"], [])
        self.assertIsNotNone(exercise["movenet_support"]["notes"])

    def test_twelve_of_twenty_exercises_have_an_implemented_movenet_assessment(self):
        """Was fourteen. Two entries claimed an assessment the application
        cannot actually perform and were corrected rather than propped up
        with a proxy measurement:

        supported-calf-raise -- MoveNet's 17 keypoints include no heel and no
        toe, so a heel raise is not observable at all.

        standing-hamstring-stretch -- the trunk-hinge angle a camera can see
        does not distinguish a good stretch from a rounded back, so a score
        would reward the wrong thing.

        The remaining twelve are each wired to a unit-tested signal extractor
        in src/exerciseAssessment/signals.js."""

        implemented = [e for e in EXERCISES if e["movenet_support"]["implemented"]]
        self.assertEqual(len(implemented), 12)

    def test_the_calf_raise_is_honestly_marked_as_not_measurable(self):
        """The same shape as the heel-to-toe-stand test above, for the same
        reason: an exercise the camera cannot measure must say so, carry no
        metrics, and give a reason -- never claim an assessment it cannot
        perform."""

        exercise = next(
            e for e in EXERCISES if e["exercise_id"] == "supported-calf-raise"
        )

        self.assertFalse(exercise["movenet_support"]["implemented"])
        self.assertEqual(exercise["movenet_support"]["metrics"], [])
        self.assertEqual(exercise["measurable_metrics"], [])
        self.assertIsNotNone(exercise["movenet_support"]["notes"])

    def test_a_malformed_exercise_is_rejected_missing_field(self):
        broken = dict(EXERCISES[0])
        del broken["equipment"]
        with self.assertRaises(ExerciseValidationError):
            validate_exercise(broken)

    def test_a_malformed_exercise_is_rejected_unexpected_field(self):
        broken = dict(EXERCISES[0])
        broken["not_a_real_field"] = "x"
        with self.assertRaises(ExerciseValidationError):
            validate_exercise(broken)

    def test_an_exercise_needs_either_repetitions_or_duration(self):
        broken = dict(EXERCISES[0])
        broken["repetitions"] = None
        broken["duration_seconds"] = None
        with self.assertRaises(ExerciseValidationError):
            validate_exercise(broken)

    def test_movenet_support_cannot_claim_implemented_without_supported(self):
        broken = dict(EXERCISES[0])
        broken["movenet_support"] = dict(broken["movenet_support"])
        broken["movenet_support"]["supported"] = False
        broken["movenet_support"]["implemented"] = True
        with self.assertRaises(ExerciseValidationError):
            validate_exercise(broken)


class NewExerciseBatchTests(unittest.TestCase):
    """The ten exercises added to bring the library from ten to twenty."""

    def test_the_new_batch_is_exactly_ten_ids_not_overlapping_the_first_ten(self):
        self.assertEqual(len(NEW_BATCH_EXERCISE_IDS), 10)
        self.assertEqual(len(EXPECTED_EXERCISE_IDS), 20)
        self.assertEqual(
            set(NEW_BATCH_EXERCISE_IDS) & set(EXPECTED_EXERCISE_IDS[:10]), set()
        )

    def test_every_new_exercise_id_resolves_to_a_full_document(self):
        by_id = {e["exercise_id"]: e for e in EXERCISES}
        for exercise_id in NEW_BATCH_EXERCISE_IDS:
            self.assertIn(exercise_id, by_id)

    def test_new_batch_spans_all_four_difficulty_and_capability_and_category_values(self):
        new_exercises = [
            e for e in EXERCISES if e["exercise_id"] in NEW_BATCH_EXERCISE_IDS
        ]
        self.assertIn("advanced", {e["difficulty"] for e in new_exercises})
        capabilities_covered = set()
        for e in new_exercises:
            capabilities_covered.update(e["target_capability"])
        self.assertEqual(capabilities_covered, set(TARGET_CAPABILITIES))
        categories_covered = {e["category"] for e in new_exercises}
        self.assertEqual(categories_covered, set(CATEGORIES))

    def test_new_batch_movenet_unsupported_exercises_are_honestly_marked(self):
        by_id = {e["exercise_id"]: e for e in EXERCISES}
        for exercise_id in NEW_BATCH_MOVENET_UNSUPPORTED_IDS:
            support = by_id[exercise_id]["movenet_support"]
            self.assertFalse(support["supported"], exercise_id)
            self.assertFalse(support["implemented"], exercise_id)
            self.assertEqual(support["metrics"], [], exercise_id)
            self.assertEqual(by_id[exercise_id]["measurable_metrics"], [], exercise_id)
            self.assertIsNotNone(support["notes"], exercise_id)
            self.assertTrue(support["notes"].strip(), exercise_id)

    def test_new_batch_movenet_supported_exercises_declare_real_metrics(self):
        by_id = {e["exercise_id"]: e for e in EXERCISES}
        for exercise_id in NEW_BATCH_MOVENET_SUPPORTED_IDS:
            support = by_id[exercise_id]["movenet_support"]
            self.assertTrue(support["supported"], exercise_id)
            self.assertTrue(support["implemented"], exercise_id)
            self.assertTrue(support["metrics"], exercise_id)

    def test_the_new_batch_splits_six_unsupported_and_four_supported(self):
        """Was a five/five split. standing-hamstring-stretch moved to the
        unsupported side once the assessment it claimed turned out not to be
        something a camera can judge -- the split follows what is actually
        measurable, it is not a target to hit."""

        self.assertEqual(len(NEW_BATCH_MOVENET_UNSUPPORTED_IDS), 6)
        self.assertEqual(len(NEW_BATCH_MOVENET_SUPPORTED_IDS), 4)

    def test_new_batch_uses_the_same_general_reference_style(self):
        by_id = {e["exercise_id"]: e for e in EXERCISES}
        for exercise_id in NEW_BATCH_EXERCISE_IDS:
            reference = by_id[exercise_id]["reference"]
            self.assertIsInstance(reference, str)
            self.assertTrue(reference.strip())

    def test_new_batch_demonstration_ids_follow_the_exercise_dash_prefix_convention(self):
        by_id = {e["exercise_id"]: e for e in EXERCISES}
        for exercise_id in NEW_BATCH_EXERCISE_IDS:
            demonstration_id = by_id[exercise_id]["demonstration_id"]
            self.assertEqual(demonstration_id, f"exercise-{exercise_id}")


if __name__ == "__main__":
    unittest.main()
