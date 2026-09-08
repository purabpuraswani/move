"""The closed loop: recorded performance changes the next plan version.

Before this, the Physio Agent could build a plan and nothing else. A
progress-triggered run called it with the same User State it had the first
time, so it produced another first draft, every entry was an ADD, and five
of `plan_schema.DECISION_TYPES`' six values were unreachable by any code
path. "Plan V2" existed as a version number with no decision behind it.

These tests drive the real chain — real Orchestrator, real Progress Agent,
real Physio Agent, real Safety Gate, real state update — and assert on what
comes out the far end, not on the internals of any one step.

The negative assertions matter as much as the positive ones. An exercise
the user never recorded must not move. A session the camera could not
measure must never be read as the user struggling. And a review that
decided nothing must not mint a plan version, because a version the user
can see should mean something changed.
"""

import unittest

from orchestration.ids import start_workflow
from orchestrator.orchestrator import run_workflow
from physio_agent.adaptation import decide_for_exercise
from physio_agent.tool_client import InProcessExerciseToolClient
from progress_agent.tool_client import InProcessProgressToolClient
from workflow.assembly import assemble_user_state_from_documents
from workflow.response import serialise_workflow_state

# A session with a genuine, measured need: five sit-to-stands in 18 seconds
# is above this project's HIGH threshold, so Physio is selected on evidence
# rather than through the conservative starter pathway.
SESSION = {
    "protocol_version": "1.0.0",
    "completed_at": "2026-09-06T10:00:00+00:00",
    "tests": {
        "shoulder": {
            "status": "completed",
            "measurements": {
                "left": {"finalElevationDeg": 114.0},
                "right": {"finalElevationDeg": 111.0},
                "observableDifferenceDeg": 3.0,
            },
        },
        "ftsst": {
            "status": "completed",
            "measurements": {
                "completionTimeSeconds": 18.0,
                "repetitionsDetected": 5,
                "requiredRepetitions": 5,
            },
        },
        "balance": {
            "status": "completed",
            "measurements": {
                "left": {"attempted": True, "valid": True, "holdDurationSeconds": 30.0},
                "right": {
                    "attempted": True,
                    "valid": True,
                    "holdDurationSeconds": 30.0,
                },
                "observableDifferenceMs": 0,
            },
        },
    },
}


def state_for(persisted=None):
    return assemble_user_state_from_documents(
        profile_doc=None,
        assessment_doc=SESSION,
        confirmed_reports_doc=None,
        persisted_state=persisted,
    )


def run(user_state, **kwargs):
    trace = start_workflow()

    return run_workflow(
        user_state,
        tool_client=InProcessExerciseToolClient(
            workflow_id=trace.workflow_id, request_id=trace.request_id
        ),
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        **kwargs,
    )


def result_for(exercise_id, status, measurements=None):
    return {
        "exerciseId": exercise_id,
        "status": status,
        "measurements": measurements or {},
    }


def decisions_of(workflow_result):
    physio = next(
        entry for entry in workflow_result["agent_results"] if entry["agent"] == "physio"
    )

    return {
        decision["exercise_id"]: decision["decision_type"]
        for decision in physio["findings"]["decisions"]
    }


class RecordedPerformanceChangesThePlan(unittest.TestCase):
    def setUp(self):
        first = run(state_for())
        self.state_v1 = first["updated_user_state"]
        self.plan_v1 = self.state_v1["exercise_history"]["data"]["plans"][-1]
        self.ids = self.plan_v1["exercise_ids"]

        self.assertGreaterEqual(
            len(self.ids), 2, "this fixture needs at least two exercises to adapt"
        )

    def _adapt(self, exercise_results):
        trace = start_workflow()

        return run_workflow(
            state_for(persisted=self.state_v1),
            tool_client=InProcessExerciseToolClient(
                workflow_id=trace.workflow_id, request_id=trace.request_id
            ),
            progress_tool_client=InProcessProgressToolClient(
                workflow_id=trace.workflow_id, request_id=trace.request_id
            ),
            progress_trigger={"reason": "exercise_activity_recorded"},
            exercise_results=exercise_results,
            baseline_assessment=SESSION,
            current_assessment=self.state_v1["physical_assessment"]["data"],
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
        )

    def test_the_first_plan_is_all_additions(self):
        kinds = {
            decision["decision_type"] for decision in self.plan_v1["decisions"]
        }

        self.assertEqual(kinds, {"ADD"})

    def test_consistent_success_moves_an_exercise_up(self):
        completed = self.ids[0]
        adapted = self._adapt(
            [
                result_for(completed, "completed", {"repetitions": 10}),
                result_for(completed, "completed", {"repetitions": 10}),
            ]
        )

        self.assertEqual(decisions_of(adapted)[completed], "PROGRESS")

    def test_repeatedly_not_finishing_makes_an_exercise_easier(self):
        struggled = self.ids[1]
        adapted = self._adapt(
            [
                result_for(struggled, "incomplete", {"repetitions": 2}),
                result_for(struggled, "incomplete", {"repetitions": 1}),
            ]
        )

        self.assertIn(decisions_of(adapted)[struggled], ("REGRESS", "REPLACE"))

    def test_both_directions_can_happen_in_one_review(self):
        adapted = self._adapt(
            [
                result_for(self.ids[0], "completed", {"repetitions": 10}),
                result_for(self.ids[0], "completed", {"repetitions": 10}),
                result_for(self.ids[1], "incomplete", {"repetitions": 2}),
                result_for(self.ids[1], "incomplete", {"repetitions": 1}),
            ]
        )
        decisions = decisions_of(adapted)

        self.assertEqual(decisions[self.ids[0]], "PROGRESS")
        self.assertIn(decisions[self.ids[1]], ("REGRESS", "REPLACE"))

    def test_the_new_plan_version_says_what_changed_and_why(self):
        adapted = self._adapt(
            [
                result_for(self.ids[0], "completed", {"repetitions": 10}),
                result_for(self.ids[0], "completed", {"repetitions": 10}),
            ]
        )
        plans = adapted["updated_user_state"]["exercise_history"]["data"]["plans"]

        self.assertEqual([plan["plan_version"] for plan in plans], [1, 2])
        self.assertTrue(plans[-1]["adaptation_reason"])
        self.assertEqual(plans[-1]["adapted_from_plan_id"], self.plan_v1["plan_id"])

    def test_the_safety_gate_still_ran_on_the_adapted_plan(self):
        adapted = self._adapt(
            [
                result_for(self.ids[0], "completed", {"repetitions": 10}),
                result_for(self.ids[0], "completed", {"repetitions": 10}),
            ]
        )

        self.assertIsNotNone(adapted["safety_result"])

    def test_the_change_reaches_the_plan_screen(self):
        adapted = self._adapt(
            [
                result_for(self.ids[0], "completed", {"repetitions": 10}),
                result_for(self.ids[0], "completed", {"repetitions": 10}),
            ]
        )
        response = serialise_workflow_state(
            adapted["updated_user_state"], safety_status="ALLOW"
        )
        movement = response["specialists"][0]

        self.assertEqual(movement["title"], "Movement")
        self.assertEqual(movement["plan_version"], 2)
        self.assertTrue(movement["changes"])
        self.assertTrue(movement["changes"][0]["reason"])


class AdaptationNeverRunsOnAbsence(unittest.TestCase):
    """The rules that stop the loop inventing a reason to act."""

    def setUp(self):
        first = run(state_for())
        self.state_v1 = first["updated_user_state"]
        self.ids = self.state_v1["exercise_history"]["data"]["plans"][-1][
            "exercise_ids"
        ]

    def test_re_running_with_no_new_evidence_creates_no_new_version(self):
        state = self.state_v1

        for _ in range(3):
            state = run(state_for(persisted=state))["updated_user_state"]

        plans = state["exercise_history"]["data"]["plans"]

        self.assertEqual([plan["plan_version"] for plan in plans], [1])

    def test_one_session_is_not_enough_to_change_anything(self):
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[result_for("wall-sit", "completed")],
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_unmeasurable_sessions_are_never_read_as_struggling(self):
        # The camera could not see them. That says nothing about how they
        # did, so it must not make the exercise easier.
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[
                result_for("wall-sit", "invalid"),
                result_for("wall-sit", "invalid"),
            ],
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertIn("could not be measured", decision["reason"])

    def test_an_exercise_with_no_results_is_left_alone(self):
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[],
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertEqual(decision["evidence"]["results_recorded"], 0)

    def test_a_mixed_run_of_sessions_changes_nothing(self):
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[
                result_for("wall-sit", "completed"),
                result_for("wall-sit", "incomplete"),
            ],
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_success_without_a_harder_version_does_not_invent_one(self):
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=False,
            has_regression=True,
            exercise_results=[
                result_for("wall-sit", "completed"),
                result_for("wall-sit", "completed"),
            ],
            still_targeted=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_an_exercise_no_longer_targeted_is_removed(self):
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[],
            still_targeted=False,
        )

        self.assertEqual(decision["decision_type"], "REMOVE")

    def test_the_programme_level_finding_never_overrides_a_specific_one(self):
        # Evidence about this exercise is more specific than evidence about
        # the programme, so it wins.
        decision = decide_for_exercise(
            exercise_id="wall-sit",
            target_need="functional_movement_need",
            has_progression=True,
            has_regression=True,
            exercise_results=[
                result_for("wall-sit", "incomplete"),
                result_for("wall-sit", "incomplete"),
            ],
            still_targeted=True,
            programme_direction="PROGRESS",
        )

        self.assertEqual(decision["decision_type"], "REGRESS")


class TheSpecialistViewIsReadFromTheAgent(unittest.TestCase):
    """What the Movement screen shows must come from persisted agent output,
    not from anything the UI could have written itself."""

    def setUp(self):
        self.state = run(state_for())["updated_user_state"]
        self.response = serialise_workflow_state(self.state, safety_status="ALLOW")
        self.movement = self.response["specialists"][0]

    def test_the_findings_are_need_assessments_own_evidence(self):
        profile = self.state["current_needs"]["data"]
        shown = {
            line
            for finding in self.movement["what_i_found"]
            for line in finding["evidence"]
        }
        recorded = {
            line
            for dimension in (
                "mobility_need",
                "stability_need",
                "functional_movement_need",
            )
            for line in profile[dimension]["evidence"]
        }

        self.assertTrue(shown)
        self.assertTrue(shown.issubset(recorded))

    def test_every_exercise_carries_the_agents_own_reason(self):
        for exercise in self.movement["programme"]:
            self.assertTrue(exercise["why"])
            self.assertTrue(exercise["name"])
            self.assertTrue(exercise["id"])

    def test_an_unmeasured_capability_is_shown_as_unmeasured_not_as_fine(self):
        response = serialise_workflow_state(
            assemble_user_state_from_documents(
                profile_doc=None,
                assessment_doc={
                    **SESSION,
                    "tests": {
                        **SESSION["tests"],
                        "shoulder": {"status": "invalid", "measurements": None},
                    },
                },
                confirmed_reports_doc=None,
                persisted_state=self.state,
            )
        )
        findings = response["specialists"][0]["what_i_found"]
        by_capability = {entry["capability"]: entry for entry in findings}

        self.assertFalse(by_capability["Upper-body mobility"]["measured"])
        self.assertEqual(by_capability["Upper-body mobility"]["finding"], "Not measured")

    def test_what_is_watched_is_said_without_computer_vision_language(self):
        text = repr(self.movement["watching"]) + repr(self.movement["programme"])

        for forbidden in (
            "keypoint",
            "landmark",
            "confidence",
            "frame",
            "tracking coverage",
            "MoveNet",
            "movenet",
        ):
            self.assertNotIn(forbidden, text)

    def test_the_specialist_view_leaks_no_internal_identifier(self):
        text = repr(self.response["specialists"])

        for forbidden in (
            "workflow_id",
            "request_id",
            "agent_run_id",
            "tool_call_id",
            "mcp_session_id",
        ):
            self.assertNotIn(forbidden, text)

    def test_a_specialist_that_was_not_involved_is_absent(self):
        titles = [entry["title"] for entry in self.response["specialists"]]

        self.assertIn("Movement", titles)
        self.assertNotIn("Nutrition", titles)


if __name__ == "__main__":
    unittest.main()
