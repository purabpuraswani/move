import unittest

from exercise_library.catalog import (
    ExerciseNotFoundError,
    check_exercise_constraints,
    get_exercise_details,
    list_exercise_ids,
    search_exercises,
)


class SearchExercisesTests(unittest.TestCase):
    def test_no_filters_returns_the_whole_library(self):
        self.assertEqual(len(search_exercises()), 20)

    def test_filtering_by_target_capability_stability(self):
        results = search_exercises(target_capability="stability")
        self.assertTrue(results)
        for exercise in results:
            self.assertIn("stability", exercise["target_capability"])

    def test_filtering_by_target_body_area(self):
        results = search_exercises(target_body_area="legs")
        self.assertTrue(results)
        for exercise in results:
            self.assertIn("legs", exercise["target_body_area"])

    def test_filtering_by_difficulty(self):
        results = search_exercises(difficulty="beginner")
        for exercise in results:
            self.assertEqual(exercise["difficulty"], "beginner")

    def test_filtering_by_category(self):
        results = search_exercises(category="balance_training")
        for exercise in results:
            self.assertEqual(exercise["category"], "balance_training")

    def test_movenet_implemented_only_excludes_what_cannot_be_measured(self):
        """Twelve, not fourteen. Two entries were corrected in the final
        integration pass because they claimed an assessment this application
        cannot actually perform: supported-calf-raise (MoveNet has no heel or
        toe keypoint) and standing-hamstring-stretch (the visible trunk angle
        does not distinguish a good stretch from a rounded back)."""

        results = search_exercises(movenet_implemented_only=True)
        ids = [e["exercise_id"] for e in results]

        self.assertNotIn("heel-to-toe-stand", ids)
        self.assertNotIn("supported-calf-raise", ids)
        self.assertNotIn("standing-hamstring-stretch", ids)
        self.assertEqual(len(results), 12)

    def test_movenet_implemented_only_excludes_the_new_batchs_unsupported_exercises(self):
        results = search_exercises(movenet_implemented_only=True)
        ids = {e["exercise_id"] for e in results}
        for unsupported_id in (
            "standing-trunk-rotation",
            "standing-shoulder-rolls",
            "standing-ankle-circles",
            "glute-bridge",
            "quadruped-bird-dog",
            "standing-hamstring-stretch",
        ):
            self.assertNotIn(unsupported_id, ids)

    def test_new_batch_exercises_are_found_by_id(self):
        for exercise_id in (
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
        ):
            exercise = get_exercise_details(exercise_id)
            self.assertEqual(exercise["exercise_id"], exercise_id)

    def test_new_advanced_difficulty_exercise_is_found_by_difficulty(self):
        results = search_exercises(difficulty="advanced")
        ids = [e["exercise_id"] for e in results]
        self.assertIn("single-leg-reach-balance", ids)

    def test_new_mobility_training_exercises_are_found_by_category(self):
        results = search_exercises(category="mobility_training")
        ids = {e["exercise_id"] for e in results}
        self.assertIn("standing-knee-raise", ids)  # one of the original ten
        for new_mobility_id in (
            "standing-trunk-rotation",
            "standing-shoulder-rolls",
            "standing-ankle-circles",
            "standing-hamstring-stretch",
        ):
            self.assertIn(new_mobility_id, ids)

    def test_new_functional_movement_exercise_is_found_by_target_capability(self):
        results = search_exercises(target_capability="functional_movement")
        ids = {e["exercise_id"] for e in results}
        self.assertIn("seated-marching", ids)

    def test_combining_filters_narrows_further(self):
        results = search_exercises(target_capability="strength", difficulty="beginner")
        for exercise in results:
            self.assertIn("strength", exercise["target_capability"])
            self.assertEqual(exercise["difficulty"], "beginner")

    def test_an_unrecognised_filter_value_matches_nothing_not_an_error(self):
        results = search_exercises(target_capability="not-a-real-capability")
        self.assertEqual(results, [])

    def test_an_impossible_combination_returns_empty_not_an_error(self):
        results = search_exercises(category="balance_training", target_body_area="ankles-that-do-not-exist")
        self.assertEqual(results, [])


class GetExerciseDetailsTests(unittest.TestCase):
    def test_a_valid_id_returns_the_full_document(self):
        exercise = get_exercise_details("wall-sit")
        self.assertEqual(exercise["name"], "Wall Sit")

    def test_every_listed_id_resolves(self):
        for exercise_id in list_exercise_ids():
            exercise = get_exercise_details(exercise_id)
            self.assertEqual(exercise["exercise_id"], exercise_id)

    def test_an_unknown_id_raises_exercise_not_found(self):
        with self.assertRaises(ExerciseNotFoundError):
            get_exercise_details("not-a-real-exercise")

    def test_an_empty_string_id_raises_exercise_not_found(self):
        with self.assertRaises(ExerciseNotFoundError):
            get_exercise_details("")


class CheckExerciseConstraintsTests(unittest.TestCase):
    def test_a_valid_id_returns_safety_relevant_fields_only(self):
        constraints = check_exercise_constraints("chair-sit-to-stand")
        self.assertEqual(
            set(constraints),
            {"exerciseId", "difficulty", "equipmentRequired", "safetyConstraints", "commonMistakes"},
        )
        self.assertEqual(constraints["exerciseId"], "chair-sit-to-stand")

    def test_an_unknown_id_raises_exercise_not_found(self):
        with self.assertRaises(ExerciseNotFoundError):
            check_exercise_constraints("nonexistent")

    def test_constraints_do_not_leak_full_exercise_document_fields(self):
        constraints = check_exercise_constraints("wall-sit")
        self.assertNotIn("movenet_support", constraints)
        self.assertNotIn("measurable_metrics", constraints)


if __name__ == "__main__":
    unittest.main()
