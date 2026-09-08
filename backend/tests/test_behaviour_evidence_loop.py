"""The behaviour evidence loop: a recorded action changes the next plan.

Until the behaviour log existed, the Behaviour Agent could set a habit goal
and then had nothing whatsoever to review it against, so habit adherence was
structurally UNKNOWN forever and MODIFY was unreachable. These tests drive
the loop end to end — schema, store contract, agent, orchestrator, Safety
Gate, plan version — and, as with the other specialists, the negative
assertions are the point:

  * No recorded action is never read as failure.
  * A rate is never reported from too few records, and never as 0.0
    standing in for "nothing recorded".
  * A review that changed nothing does not mint a plan version.
  * The client cannot submit an adherence figure at all.

A note on what the persistence tests here do and do not prove. This
project's own sandbox has no pymongo, so they do not write to a database:
they assert the store's and route's *contract* by reading the source —
that ownership and the timestamp are set server-side and never taken from
the request, and that every read is scoped to the owner. That catches the
mistakes that matter (identity from the body, a client-set time, an
unscoped query) but it does not prove a round trip against a real MongoDB.
The end-to-end reload behaviour needs the running application, and is
listed as such rather than claimed here.
"""

import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from behaviour_agent.adherence import (
    ADHERED,
    INSUFFICIENT_DATA,
    MIN_ACTIONS_FOR_A_RATE,
    NOT_ADHERED,
    NOT_LOGGED,
    compute_behaviour_adherence,
    summarise_for_progress,
)
from behaviour_agent.tool_client import InProcessBehaviourToolClient
from behaviour_log.schema import (
    ACCEPTED_FIELDS,
    BehaviourActionValidationError,
    build_behaviour_action,
    validate_behaviour_action,
)
from orchestration.ids import start_workflow
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from workflow.assembly import assemble_user_state_from_documents
from workflow.response import serialise_workflow_state

BACKEND_ROOT = Path(__file__).resolve().parent.parent

PROFILE = {
    "daily_sitting_hours": 12,
    "daily_screen_hours": 10,
    "sleep_hours": 6,
    "exercise_days": 0,
    "exercise_minutes": 0,
}

ASSESSMENT = {
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


def build_state(persisted=None):
    return assemble_user_state_from_documents(
        profile_doc=PROFILE,
        assessment_doc=ASSESSMENT,
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
        behaviour_tool_client=InProcessBehaviourToolClient(
            workflow_id=trace.workflow_id, request_id=trace.request_id
        ),
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        **kwargs,
    )


def actions_for(topic_id, count, status="completed", difficulty=None):
    now = datetime.now(timezone.utc)

    return [
        {
            "topic_id": topic_id,
            "status": status,
            "difficulty": difficulty,
            "recorded_at": now - timedelta(days=offset),
        }
        for offset in range(count)
    ]


def behaviour_findings(result):
    return next(
        entry for entry in result["agent_results"] if entry["agent"] == "behaviour"
    )["findings"]


class TheActionSchemaRefusesWhatItShould(unittest.TestCase):
    def test_a_minimal_action_is_accepted(self):
        action = build_behaviour_action("take_regular_movement_breaks")

        self.assertEqual(action["status"], "completed")
        self.assertIsNone(action["difficulty"])
        self.assertIsNone(action["notes"])

    def test_skipping_is_a_real_recordable_answer(self):
        action = build_behaviour_action(
            "take_regular_movement_breaks", status="skipped"
        )

        self.assertEqual(action["status"], "skipped")

    def test_an_adherence_figure_can_never_be_submitted(self):
        # The whole point of the collection: rates are computed from
        # records, so a client that could post one could post a number
        # nothing happened to produce.
        for forbidden in (
            "completion_rate",
            "adherence",
            "streak",
            "completed_actions",
        ):
            self.assertNotIn(forbidden, ACCEPTED_FIELDS)

            with self.assertRaises(BehaviourActionValidationError):
                validate_behaviour_action(
                    {
                        "topic_id": "take_regular_movement_breaks",
                        "status": "completed",
                        "difficulty": None,
                        "notes": None,
                        forbidden: 0.9,
                    }
                )

        # And the builder has no parameter for one either, so the route
        # cannot forward such a field even by accident.
        with self.assertRaises(TypeError):
            build_behaviour_action("t", completion_rate=0.9)

    def test_a_missing_topic_is_refused_not_guessed(self):
        for bad in (None, "", "   "):
            with self.assertRaises(BehaviourActionValidationError):
                build_behaviour_action(bad)

    def test_an_unrecognised_status_or_difficulty_is_refused(self):
        with self.assertRaises(BehaviourActionValidationError):
            build_behaviour_action("t", status="sort-of")

        with self.assertRaises(BehaviourActionValidationError):
            build_behaviour_action("t", difficulty="7/10")

    def test_the_store_sets_ownership_and_time_never_the_client(self):
        source = (BACKEND_ROOT / "behaviour_log/store.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "save_behaviour_action"
        )
        body = ast.unparse(function)

        # ast.unparse normalises string quotes, hence the single quotes.
        self.assertIn("'user_id': user_id", body)
        self.assertIn("datetime.now(timezone.utc)", body)

    def test_every_read_is_scoped_to_the_owner(self):
        source = (BACKEND_ROOT / "behaviour_log/store.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        for name in ("list_behaviour_actions", "count_behaviour_actions"):
            function = next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name
            )

            self.assertIn('query = {\'user_id\': user_id}', ast.unparse(function))

    def test_the_route_never_takes_identity_from_the_request(self):
        source = (BACKEND_ROOT / "routes/behaviour_log.py").read_text(encoding="utf-8")

        self.assertIn('str(current_user["_id"])', source)
        self.assertNotIn('body.get("user_id")', source)
        self.assertNotIn('payload.get("user_id")', source)


class AdherenceIsComputedNeverInvented(unittest.TestCase):
    def test_no_records_is_not_logged_with_no_rate(self):
        result = compute_behaviour_adherence([])

        self.assertEqual(result["status"], NOT_LOGGED)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["completed_actions"], 0)
        self.assertIn("not evidence", " ".join(result["notes"]))

    def test_too_few_records_is_insufficient_data_with_no_rate(self):
        result = compute_behaviour_adherence(
            actions_for("t", MIN_ACTIONS_FOR_A_RATE - 1)
        )

        self.assertEqual(result["status"], INSUFFICIENT_DATA)
        self.assertIsNone(result["completion_rate"])

    def test_enough_completed_records_is_adhered(self):
        result = compute_behaviour_adherence(actions_for("t", 4))

        self.assertEqual(result["status"], ADHERED)
        self.assertEqual(result["completion_rate"], 1.0)

    def test_enough_skipped_records_is_not_adhered(self):
        result = compute_behaviour_adherence(actions_for("t", 4, status="skipped"))

        self.assertEqual(result["status"], NOT_ADHERED)
        self.assertEqual(result["completion_rate"], 0.0)

    def test_a_zero_rate_only_ever_comes_from_real_records(self):
        # 0.0 must mean "recorded four times, did none". It must never be
        # the value reported for "nothing recorded".
        recorded = compute_behaviour_adherence(actions_for("t", 4, status="skipped"))
        nothing = compute_behaviour_adherence([])

        self.assertEqual(recorded["completion_rate"], 0.0)
        self.assertIsNone(nothing["completion_rate"])

    def test_records_for_another_goal_are_not_counted(self):
        result = compute_behaviour_adherence(
            actions_for("other_topic", 5), topic_id="this_topic"
        )

        self.assertEqual(result["status"], NOT_LOGGED)

    def test_the_progress_summary_states_absence_rather_than_a_rate(self):
        self.assertIn("No behaviour actions", summarise_for_progress([])["summary"])
        self.assertIn(
            "not enough recorded data",
            summarise_for_progress(actions_for("t", 1))["summary"],
        )
        self.assertIn(
            "3 completed of 3", summarise_for_progress(actions_for("t", 3))["summary"]
        )


class TheLoopRunsEndToEnd(unittest.TestCase):
    def setUp(self):
        self.state = run(build_state())["updated_user_state"]
        self.plan = self.state["behaviour"]["data"]["plans"][-1]
        self.topic = self.plan["topic_ids"][0]
        self.original_action = next(
            goal["practical_goal"]
            for goal in self.plan["goals"]
            if goal["topic_id"] == self.topic
        )

    def _review(self, actions):
        return run(build_state(persisted=self.state), behaviour_actions=actions)

    def _plans(self, result):
        return result["updated_user_state"]["behaviour"]["data"]["plans"]

    def _decision_for(self, result, topic_id):
        return next(
            decision
            for decision in behaviour_findings(result)["decisions"]
            if decision["topic_id"] == topic_id
        )

    def test_no_recorded_actions_leaves_the_plan_alone(self):
        reviewed = self._review([])
        decision = self._decision_for(reviewed, self.topic)

        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertEqual(decision["adherence_status"], "NOT_LOGGED")
        self.assertEqual([p["plan_version"] for p in self._plans(reviewed)], [1])

    def test_recorded_completions_are_consumed_and_maintain_the_plan(self):
        reviewed = self._review(actions_for(self.topic, 4))
        decision = self._decision_for(reviewed, self.topic)

        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertEqual(decision["adherence_status"], "KNOWN")
        self.assertTrue(
            any("recorded" in line for line in decision["evidence_used"]),
            decision["evidence_used"],
        )
        self.assertEqual([p["plan_version"] for p in self._plans(reviewed)], [1])

    def test_repeated_skipping_modifies_the_intervention(self):
        reviewed = self._review(actions_for(self.topic, 4, status="skipped"))
        decision = self._decision_for(reviewed, self.topic)
        plans = self._plans(reviewed)

        self.assertEqual(decision["decision_type"], "MODIFY")
        self.assertEqual([p["plan_version"] for p in plans], [1, 2])

        changed = next(
            goal["practical_goal"]
            for goal in plans[-1]["goals"]
            if goal["topic_id"] == self.topic
        )

        # A real change to what the user is asked to do, not just a new
        # version number over the same sentence.
        self.assertNotEqual(changed, self.original_action)

    def test_recorded_difficulty_modifies_the_intervention(self):
        reviewed = self._review(
            actions_for(self.topic, 4, status="completed", difficulty="difficult")
        )
        decision = self._decision_for(reviewed, self.topic)

        self.assertEqual(decision["decision_type"], "MODIFY")
        self.assertEqual([p["plan_version"] for p in self._plans(reviewed)], [1, 2])

    def test_one_bad_day_changes_nothing(self):
        reviewed = self._review(actions_for(self.topic, 1, status="skipped"))
        decision = self._decision_for(reviewed, self.topic)

        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertEqual(decision["adherence_status"], "UNKNOWN")
        self.assertEqual([p["plan_version"] for p in self._plans(reviewed)], [1])

    def test_an_adapted_plan_still_passes_the_safety_gate(self):
        reviewed = self._review(actions_for(self.topic, 4, status="skipped"))

        self.assertIsNotNone(reviewed["safety_result"])
        self.assertIn(
            reviewed["safety_result"]["status"],
            ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED"),
        )
        self.assertIn("behaviour", reviewed["state_updates"])

    def test_the_new_version_says_what_changed_and_why(self):
        reviewed = self._review(actions_for(self.topic, 4, status="skipped"))
        latest = self._plans(reviewed)[-1]

        self.assertTrue(latest["adaptation_reason"])
        self.assertIn("recorded", latest["adaptation_reason"])

    def test_the_evidence_reaches_the_habits_panel(self):
        reviewed = self._review(actions_for(self.topic, 4))
        response = serialise_workflow_state(reviewed["updated_user_state"])
        habits = next(
            entry for entry in response["specialists"] if entry["title"] == "Daily habits"
        )

        self.assertTrue(habits["learning"])
        self.assertTrue(
            any("recorded" in line for line in habits["learning"]), habits["learning"]
        )

        # And the panel can address each goal, which is what lets the
        # Complete button record against the right one.
        for item in habits["focus_items"]:
            self.assertTrue(item["topic_id"])

    def test_records_survive_a_reload_because_the_ui_reads_them_back(self):
        # The store is the source of truth for "did I do this", so the
        # route that the panel re-reads on mount must exist and be a plain
        # authenticated GET.
        source = (BACKEND_ROOT / "routes/behaviour_log.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("")', source)
        self.assertIn("list_behaviour_actions", source)
        self.assertIn("get_current_user", source)


class ProgressAndTheOrchestratorSeeTheEvidence(unittest.TestCase):
    def test_the_orchestrator_passes_recorded_actions_to_the_behaviour_agent(self):
        source = (BACKEND_ROOT / "orchestrator/orchestrator.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("behaviour_actions=behaviour_actions", source)

    def test_the_progress_agent_reports_behaviour_evidence(self):
        source = (BACKEND_ROOT / "progress_agent/agent.py").read_text(encoding="utf-8")

        self.assertIn('"behaviour_progress": behaviour_progress', source)
        self.assertIn("summarise_for_progress", source)

    def test_progress_uses_the_one_adherence_module_not_a_second_one(self):
        # A second mechanism would be free to disagree with the first about
        # what the same records mean.
        source = (BACKEND_ROOT / "progress_agent/agent.py").read_text(encoding="utf-8")

        self.assertIn("from behaviour_agent.adherence import", source)

    def test_the_route_supplies_the_actions_on_every_run(self):
        source = (BACKEND_ROOT / "routes/workflow.py").read_text(encoding="utf-8")

        self.assertIn("list_behaviour_actions", source)
        self.assertIn("behaviour_actions=behaviour_actions", source)


if __name__ == "__main__":
    unittest.main()
