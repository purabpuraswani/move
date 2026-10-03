"""Manually confirmed exercises stay distinguishable from measured ones.

The checkbox on a plan card records a real exercise result, through the
same API and store a camera session uses -- there is no second progress
system. What these tests pin down is the distinction that makes that
safe: a tick says "I did it", a camera session says "here is what was
measured", and the second can never be manufactured from the first.
"""

import unittest

from exercise_assessment.schema import (
    SOURCE_CAMERA,
    SOURCE_MANUAL,
    ExerciseResultValidationError,
    validate_exercise_result,
)
from physio_agent.adaptation import DECISION_MAINTAIN, DECISION_PROGRESS, decide_for_exercise
from progress_agent.adherence import compute_plan_adherence


def _manual(exercise_id="wall-sit"):
    return {"exerciseId": exercise_id, "status": "completed", "source": SOURCE_MANUAL}


def _camera(exercise_id="wall-sit", **measurements):
    return {
        "exerciseId": exercise_id,
        "status": "completed",
        "source": SOURCE_CAMERA,
        "measurements": measurements or {"durationSeconds": 30},
    }


class ManualResultValidationTests(unittest.TestCase):
    def test_a_tick_is_accepted_and_carries_no_measurements(self):
        result = validate_exercise_result(_manual())

        self.assertEqual(result["source"], SOURCE_MANUAL)
        self.assertEqual(result["measurements"], {})

    def test_a_tick_cannot_smuggle_in_a_measurement(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {
                    "exerciseId": "wall-sit",
                    "status": "completed",
                    "source": SOURCE_MANUAL,
                    "measurements": {"durationSeconds": 45},
                }
            )

    def test_a_tick_can_only_say_completed(self):
        for status in ("incomplete", "invalid"):
            with self.assertRaises(ExerciseResultValidationError):
                validate_exercise_result(
                    {"exerciseId": "wall-sit", "status": status, "source": SOURCE_MANUAL}
                )

    def test_an_unknown_source_is_refused_rather_than_defaulted(self):
        with self.assertRaises(ExerciseResultValidationError):
            validate_exercise_result(
                {"exerciseId": "wall-sit", "status": "completed", "source": "assumed"}
            )

    def test_a_result_without_a_source_is_still_a_camera_result(self):
        # Every result stored before this field existed was a camera
        # session, and must keep being read as one.
        result = validate_exercise_result(
            {
                "exerciseId": "wall-sit",
                "status": "completed",
                "measurements": {"durationSeconds": 30},
            }
        )

        self.assertEqual(result["source"], SOURCE_CAMERA)

    def test_the_camera_path_is_unchanged(self):
        result = validate_exercise_result(_camera(durationSeconds=42))

        self.assertEqual(result["source"], SOURCE_CAMERA)
        self.assertEqual(result["measurements"]["durationSeconds"], 42)


class ManualTicksDoNotDrivePrescriptionChangesTests(unittest.TestCase):
    """A tick is not a performance reading, so it cannot progress a plan."""

    def _decide(self, results):
        return decide_for_exercise(
            exercise_id="wall-sit",
            target_need="stability_need",
            has_progression=True,
            has_regression=True,
            exercise_results=results,
            still_targeted=True,
        )

    def test_two_measured_sessions_progress_the_exercise(self):
        decision = self._decide([_camera(), _camera()])

        self.assertEqual(decision["decision_type"], DECISION_PROGRESS)

    def test_the_same_two_as_ticks_do_not(self):
        decision = self._decide([_manual(), _manual()])

        self.assertEqual(decision["decision_type"], DECISION_MAINTAIN)
        self.assertEqual(decision["evidence"]["results_recorded"], 0)

    def test_ticks_do_not_pad_out_the_measured_evidence(self):
        # One real session plus two ticks is still one real session.
        decision = self._decide([_camera(), _manual(), _manual()])

        self.assertEqual(decision["decision_type"], DECISION_MAINTAIN)
        self.assertEqual(decision["evidence"]["results_recorded"], 1)


class ManualTicksStillCountAsDoingItTests(unittest.TestCase):
    """Adherence asks a different question -- did you do it? -- and a tick
    is a legitimate answer to that one."""

    def test_a_ticked_exercise_counts_towards_plan_adherence(self):
        plan = {"plan_id": "plan_1", "exercise_ids": ["wall-sit", "glute-bridge"]}

        adherence = compute_plan_adherence(
            plan,
            [
                {**_manual("wall-sit"), "plan_id": "plan_1"},
                {**_camera("glute-bridge"), "plan_id": "plan_1"},
            ],
        )

        self.assertEqual(adherence["planned_sessions"], 2)
        self.assertEqual(adherence["completed_sessions"], 2)


if __name__ == "__main__":
    unittest.main()
