"""Comprehensive verification of the MoveWell-AI Physio intervention selection architecture.

Verifies:
1. Baseline physical assessments remain pure measurement records and distinct from intervention exercises.
2. The Physio Agent selects exercises outside the 2 baseline tests when appropriate, drawing from the active 19-exercise library.
3. Non-MoveNet exercises (e.g. standing-shoulder-rolls, heel-to-toe-stand) can be selected with measurement_method == "manual_completion".
4. Adaptation operates on intervention exercises (exercise_results), not baseline assessment records (physical_assessment).
5. All generated exercise IDs strictly belong to the 20-exercise library (no invalid or synthetic IDs).
"""

import unittest

from exercise_library.catalog import list_exercise_ids, get_exercise_details
from exercise_assessment.schema import validate_exercise_result
from orchestration.ids import start_workflow
from orchestration.starter_plan import STARTER_EXERCISE_IDS, build_maintenance_starter_plan
from orchestrator.orchestrator import run_workflow
from physio_agent.agent import (
    BASELINE_ASSESSMENT_MOVEMENTS,
    run_physio_agent,
)
from physio_agent.adaptation import decide_for_exercise, DECISION_PROGRESS, DECISION_REGRESS
from physio_agent.tool_client import InProcessExerciseToolClient
from user_state.schema import build_user_state, validate_user_state
from workflow.response import serialise_workflow_state


from need_assessment.assessment import run_need_assessment


def _state_with_health_screen():
    return build_user_state(profile_doc={
        "diabetes": "no", "hypertension": "no", "heart_condition": "no",
        "previous_injury": "no", "joint_pain": "no", "back_neck_pain": "no",
        "other_conditions": "",
    })


def _assessment_state(*, shoulder_elevation=110.0, balance_hold=30.0):
    state = _state_with_health_screen()
    state["physical_assessment"] = {
        "available": True,
        "reason": None,
        "data": {
            "schemaVersion": "1.0.0",
            "completed_at": "2026-09-01T10:00:00Z",
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {
                        "left": {"finalElevationDeg": shoulder_elevation},
                        "right": {"finalElevationDeg": shoulder_elevation - 30.0 if shoulder_elevation < 80 else shoulder_elevation},
                        "observableDifferenceDeg": 30.0 if shoulder_elevation < 80 else 0.0,
                    },
                },
                "balance": {
                    "status": "completed",
                    "measurements": {
                        "left": {"attempted": True, "valid": True, "holdDurationSeconds": balance_hold},
                        "right": {"attempted": True, "valid": True, "holdDurationSeconds": balance_hold},
                    },
                },
            },
        },
    }
    return run_need_assessment(state, workflow_id="wf_assess", request_id="req_assess")


class BaselineVsInterventionSeparationTests(unittest.TestCase):
    """Point 1: Baseline assessments remain distinct from intervention exercises."""

    def test_baseline_assessment_keys_are_separate_from_intervention_exercises(self):
        baseline_test_keys = {"shoulder", "balance"}
        library_exercise_ids = set(list_exercise_ids())

        # The 2 active assessment identifiers are NOT exercise IDs in the library
        for test_key in baseline_test_keys:
            self.assertNotIn(test_key, library_exercise_ids)

        # The active library has exactly 19 exercises
        self.assertEqual(len(library_exercise_ids), 19)

    def test_baseline_assessment_data_structure_never_stores_workout_prescriptions(self):
        state = _assessment_state()
        tests = state["physical_assessment"]["data"]["tests"]

        for test_name, test_data in tests.items():
            self.assertIn("measurements", test_data)
            # Baseline test data must never contain workout prescription fields
            self.assertNotIn("sets", test_data)
            self.assertNotIn("prescription", test_data)
            self.assertNotIn("progression", test_data)
            self.assertNotIn("regression", test_data)

    def test_running_workflow_preserves_baseline_assessment_unmodified(self):
        state = _assessment_state(shoulder_elevation=50.0)  # HIGH mobility need
        before_tests = dict(state["physical_assessment"]["data"]["tests"])

        tool_client = InProcessExerciseToolClient(workflow_id="wf_sep", request_id="req_sep")
        result = run_workflow(state, tool_client=tool_client, workflow_id="wf_sep", request_id="req_sep")

        after_state = result["updated_user_state"]
        after_tests = after_state["physical_assessment"]["data"]["tests"]

        # Baseline physical assessment is completely preserved and untouched
        self.assertEqual(before_tests, after_tests)


class PhysioInterventionSelectionOutsideBaselineTests(unittest.TestCase):
    """Point 2: Physio selects exercises outside the 3 baseline tests, drawn from the 20-exercise library."""

    def test_high_mobility_need_selects_genuine_mobility_interventions_not_baseline_test(self):
        # Shoulder baseline test showed deficit (elevation < 60 deg -> HIGH mobility need)
        state = _state_with_health_screen()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {
                    "level": "HIGH",
                    "evidence": ["Lowest observed arm elevation across sides: 45 degrees"],
                },
                "functional_movement_need": {"level": "LOW", "evidence": []},
                "stability_need": {"level": "LOW", "evidence": []},
            },
        }

        trace = start_workflow()
        tool_client = InProcessExerciseToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
        result = run_physio_agent(state, tool_client, parent_trace=trace)

        plan = result["findings"]["plan"]
        exercise_ids = [e["exercise_id"] for e in plan["exercises"]]

        # The assessed shoulder movement and retired chair test are excluded.
        self.assertNotIn("standing-shoulder-raise", exercise_ids)
        self.assertNotIn("chair-sit-to-stand", exercise_ids)
        self.assertNotIn("chair-sit-to-stand", list_exercise_ids())

        # Meaningful mobility interventions selected (such as standing-overhead-reach, standing-shoulder-rolls)
        self.assertTrue(any(e in exercise_ids for e in ("standing-overhead-reach", "standing-shoulder-rolls", "standing-trunk-rotation", "standing-knee-raise")))

    def test_high_functional_movement_need_selects_interventions_not_baseline_test(self):
        # FTSST baseline test was slow -> HIGH functional movement need
        state = _state_with_health_screen()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {"level": "LOW", "evidence": []},
                "functional_movement_need": {
                    "level": "HIGH",
                    "evidence": ["FTSST completion time was 22 seconds"],
                },
                "stability_need": {"level": "LOW", "evidence": []},
            },
        }

        trace = start_workflow()
        tool_client = InProcessExerciseToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
        result = run_physio_agent(state, tool_client, parent_trace=trace)

        plan = result["findings"]["plan"]
        exercise_ids = [e["exercise_id"] for e in plan["exercises"]]

        # Chair sit-to-stand (the baseline test movement) is NOT used when alternative functional interventions exist
        self.assertNotIn("chair-sit-to-stand", exercise_ids)
        # Seated marching or wall sit or leg extensions are selected
        self.assertTrue(any(e in exercise_ids for e in ("seated-marching", "wall-sit", "seated-knee-extension", "standing-side-leg-raise")))

    def test_starter_plan_exercises_do_not_mirror_baseline_assessment_tests(self):
        # Starter plan must not just mirror the 3 baseline tests
        self.assertNotIn("chair-sit-to-stand", STARTER_EXERCISE_IDS)
        self.assertNotIn("standing-shoulder-raise", STARTER_EXERCISE_IDS)

        # Starter plan exercises are valid beginner exercises from the 20-exercise library
        library_ids = set(list_exercise_ids())
        for ex_id in STARTER_EXERCISE_IDS:
            self.assertIn(ex_id, library_ids)
            details = get_exercise_details(ex_id)
            self.assertEqual(details["difficulty"], "beginner")

    def test_retired_exercise_in_a_historical_plan_is_not_recommended_again(self):
        state = _state_with_health_screen()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {"level": "LOW", "evidence": []},
                "functional_movement_need": {"level": "LOW", "evidence": []},
                "stability_need": {
                    "level": "HIGH",
                    "evidence": ["Shortest valid one-leg hold was 3 seconds"],
                },
            },
        }

        trace = start_workflow()
        tool_client = InProcessExerciseToolClient(
            workflow_id=trace.workflow_id, request_id=trace.request_id
        )
        result = run_physio_agent(
            state,
            tool_client,
            parent_trace=trace,
            previous_plan={
                "plan_id": "historic",
                "plan_version": 1,
                "exercise_ids": ["chair-sit-to-stand"],
            },
        )

        ids = [item["exercise_id"] for item in result["findings"]["plan"]["exercises"]]
        self.assertNotIn("chair-sit-to-stand", ids)

    def test_retired_historical_plan_entry_is_not_exposed_as_a_current_recommendation(self):
        state = build_user_state()
        state["exercise_history"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [{
                    "plan_id": "legacy-plan",
                    "plan_version": 1,
                    "exercise_ids": ["chair-sit-to-stand", "wall-sit"],
                }],
            },
        }

        response = serialise_workflow_state(state, safety_status="ALLOW")
        active_output = str(response)
        self.assertNotIn("chair-sit-to-stand", active_output)
        self.assertNotIn("Chair Sit-to-Stand", active_output)
        self.assertIn("wall-sit", active_output)
        self.assertIn("chair-sit-to-stand", str(state["exercise_history"]))


class NonMoveNetManualCompletionTests(unittest.TestCase):
    """Point 3: Exercises without MoveNet camera tracking can be selected and recorded as manual_completion."""

    def test_manual_completion_exercise_validation(self):
        # standing-shoulder-rolls has movenet_support["implemented"] == False and measurable_metrics == []
        details = get_exercise_details("standing-shoulder-rolls")
        self.assertFalse(details["movenet_support"]["implemented"])
        self.assertEqual(details["measurable_metrics"], [])

        # Schema accepts manual completion result without requiring camera metrics
        valid_manual_result = validate_exercise_result({
            "exerciseId": "standing-shoulder-rolls",
            "status": "completed",
            "startedAt": "2026-09-01T10:00:00Z",
            "completedAt": "2026-09-01T10:01:00Z",
            "measurements": {},
        })
        self.assertEqual(valid_manual_result["status"], "completed")
        self.assertEqual(valid_manual_result["measurements"], {})

    def test_physio_agent_assigns_correct_measurement_method(self):
        state = build_user_state()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {
                    "level": "HIGH",
                    "evidence": ["Lowest observed arm elevation across sides: 40 degrees"],
                },
                "functional_movement_need": {"level": "LOW", "evidence": []},
                "stability_need": {"level": "LOW", "evidence": []},
            },
        }

        trace = start_workflow()
        tool_client = InProcessExerciseToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
        result = run_physio_agent(state, tool_client, parent_trace=trace)

        plan = result["findings"]["plan"]
        for entry in plan["exercises"]:
            details = get_exercise_details(entry["exercise_id"])
            if details["movenet_support"]["implemented"]:
                self.assertEqual(entry["measurement_method"], "movenet_derived_metrics")
            else:
                self.assertEqual(entry["measurement_method"], "manual_completion")


class AdaptationOperatesOnInterventionResultsTests(unittest.TestCase):
    """Point 4: Adaptation operates on intervention exercise results, not baseline assessment records."""

    def test_adaptation_progresses_based_on_intervention_exercise_results(self):
        # User recorded 2 completed sessions of 'seated-marching' (an intervention exercise)
        exercise_results = [
            {"exerciseId": "seated-marching", "status": "completed"},
            {"exerciseId": "seated-marching", "status": "completed"},
        ]

        decision = decide_for_exercise(
            exercise_id="seated-marching",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=exercise_results,
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], DECISION_PROGRESS)
        self.assertEqual(decision["exercise_id"], "seated-marching")
        self.assertEqual(decision["evidence"]["results_recorded"], 2)

    def test_adaptation_regresses_when_incomplete_sessions_recorded(self):
        exercise_results = [
            {"exerciseId": "seated-marching", "status": "incomplete"},
            {"exerciseId": "seated-marching", "status": "incomplete"},
        ]

        decision = decide_for_exercise(
            exercise_id="seated-marching",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=exercise_results,
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], DECISION_REGRESS)

    def test_baseline_assessment_never_confused_with_exercise_results(self):
        # Baseline assessment tests (shoulder, ftsst, balance) are not exercise result entries
        baseline_tests = [{"testId": "ftsst", "status": "completed"}]
        # Passing baseline tests to decide_for_exercise does NOT count as exercise results
        decision = decide_for_exercise(
            exercise_id="seated-marching",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=baseline_tests,
            still_targeted=True,
        )
        # Because no result matches exerciseId "seated-marching", it MAINTAINs with 0 results recorded
        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertEqual(decision["evidence"]["results_recorded"], 0)


class ExerciseIdIntegrityTests(unittest.TestCase):
    """Point 5: No invalid or synthetic exercise IDs are generated."""

    def test_all_19_exercises_have_valid_ids(self):
        all_ids = list_exercise_ids()
        self.assertEqual(len(all_ids), 19)
        for exercise_id in all_ids:
            details = get_exercise_details(exercise_id)
            self.assertEqual(details["exercise_id"], exercise_id)
            self.assertTrue(details["name"])

    def test_workflow_generated_plan_contains_only_valid_library_exercise_ids(self):
        state = _assessment_state(shoulder_elevation=55.0, balance_hold=4.0)
        tool_client = InProcessExerciseToolClient(workflow_id="wf_valid", request_id="req_valid")
        result = run_workflow(state, tool_client=tool_client, workflow_id="wf_valid", request_id="req_valid")

        all_ids = set(list_exercise_ids())
        plans = result["updated_user_state"]["exercise_history"]["data"]["plans"]
        for plan in plans:
            for ex_id in plan["exercise_ids"]:
                self.assertIn(ex_id, all_ids, f"Exercise ID '{ex_id}' is not in the 19-exercise library!")

    def test_starter_plan_contains_only_valid_library_exercise_ids(self):
        all_ids = set(list_exercise_ids())
        for ex_id in STARTER_EXERCISE_IDS:
            self.assertIn(ex_id, all_ids, f"Starter exercise ID '{ex_id}' is not in the 20-exercise library!")


if __name__ == "__main__":
    unittest.main()
