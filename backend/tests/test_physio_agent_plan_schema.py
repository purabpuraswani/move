import unittest

from physio_agent.plan_schema import (
    ExercisePlanValidationError,
    build_exercise_plan,
    build_exercise_plan_entry,
    validate_exercise_plan,
    validate_exercise_plan_entry,
)


def valid_entry(**overrides):
    base = dict(
        exercise_id="wall-sit",
        sets=None,
        repetitions=None,
        duration_seconds=30,
        difficulty="beginner",
        progression="Hold longer.",
        regression="Hold for less time.",
        rationale="Supports stability training at the beginner level.",
        safety_notes=["Keep your back flat against the wall."],
    )
    base.update(overrides)
    return base


class ExercisePlanEntryTests(unittest.TestCase):
    def test_a_well_formed_entry_validates(self):
        entry = build_exercise_plan_entry(**valid_entry())
        validate_exercise_plan_entry(entry)

    def test_missing_field_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            validate_exercise_plan_entry({"exercise_id": "wall-sit"})

    def test_unexpected_field_is_rejected(self):
        entry = valid_entry()
        entry["extra"] = 1
        with self.assertRaises(ExercisePlanValidationError):
            validate_exercise_plan_entry(entry)

    def test_negative_repetitions_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            build_exercise_plan_entry(**valid_entry(repetitions=-1))

    def test_empty_rationale_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            build_exercise_plan_entry(**valid_entry(rationale="   "))

    def test_diagnostic_language_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            build_exercise_plan_entry(
                **valid_entry(rationale="This exercise treats your balance disorder.")
            )

    def test_a_non_diagnostic_rationale_using_the_good_example_is_accepted(self):
        entry = build_exercise_plan_entry(
            **valid_entry(
                rationale=(
                    "Selected because the current stability need is HIGH and "
                    "the exercise supports balance training at a beginner level."
                )
            )
        )
        validate_exercise_plan_entry(entry)

    def test_safety_notes_must_be_strings(self):
        with self.assertRaises(ExercisePlanValidationError):
            build_exercise_plan_entry(**valid_entry(safety_notes=[1, 2]))


class ExercisePlanTests(unittest.TestCase):
    def test_a_well_formed_plan_validates_and_has_a_generated_id(self):
        plan = build_exercise_plan(goal="Support balance.", exercises=[build_exercise_plan_entry(**valid_entry())])
        validate_exercise_plan(plan)
        self.assertTrue(plan["plan_id"].startswith("plan_"))
        self.assertTrue(plan["created_at"])

    def test_an_empty_exercises_list_is_a_valid_plan(self):
        plan = build_exercise_plan(goal="No suitable exercise found.", exercises=[])
        validate_exercise_plan(plan)

    def test_two_plans_get_different_ids(self):
        plan1 = build_exercise_plan(goal="g", exercises=[])
        plan2 = build_exercise_plan(goal="g", exercises=[])
        self.assertNotEqual(plan1["plan_id"], plan2["plan_id"])

    def test_a_malformed_entry_inside_the_plan_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            validate_exercise_plan({"plan_id": "p", "created_at": "t", "goal": "g", "exercises": [{"bad": True}]})

    def test_missing_top_level_field_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            validate_exercise_plan({"plan_id": "p", "goal": "g", "exercises": []})

    def test_blank_goal_is_rejected(self):
        with self.assertRaises(ExercisePlanValidationError):
            build_exercise_plan(goal="   ", exercises=[])


if __name__ == "__main__":
    unittest.main()
