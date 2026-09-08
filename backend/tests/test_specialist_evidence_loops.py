"""Nutrition and Behaviour as evidence-driven specialists.

Both agents could already decide what to work on — they read real
self-reported signals and only target the ones that crossed this project's
own thresholds. What neither could do was look at what happened next: a
user could log food for three weeks and the plan would still be rebuilt
from the same questionnaire answers.

These tests cover the loop that was added, and — more importantly — the
lines it must not cross. The negative assertions are the point of the file:

  * Nothing logged is NOT poor adherence. It is a fact about logging, and
    the only honest response is to ask for some.
  * Exercise adherence is not quietly reused as habit adherence. Missing a
    squat is not evidence about taking a break from sitting.
  * A review that changed nothing does not mint a plan version, but it does
    still record what it learned.
"""

import unittest

from behaviour_agent.adaptation import (
    completed_session_count,
    decide_for_goal as decide_habit,
)
from nutrition_agent.adaptation import (
    decide_for_goal as decide_nutrition,
    evidence_status_of,
)
from orchestration.ids import start_workflow
from orchestrator.orchestrator import run_workflow
from behaviour_agent.tool_client import InProcessBehaviourToolClient
from nutrition_agent.tool_client import InProcessNutritionToolClient
from physio_agent.tool_client import InProcessExerciseToolClient
from workflow.assembly import assemble_user_state_from_documents
from workflow.response import serialise_workflow_state

from datetime import datetime, timedelta, timezone

# Answers that trigger both the nutrition and the behaviour need, so the
# Orchestrator selects both specialists on real evidence.
PROFILE = {
    "daily_sitting_hours": 12,
    "daily_screen_hours": 10,
    "sleep_hours": 6,
    "exercise_days": 0,
    "exercise_minutes": 0,
    "meal_pattern": "irregular",
    "fruit_vegetable_servings": 1,
    "water_glasses_per_day": 2,
    "processed_food_frequency": "daily",
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


def build_state(profile=None, persisted=None):
    return assemble_user_state_from_documents(
        profile_doc=profile if profile is not None else PROFILE,
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
        nutrition_tool_client=InProcessNutritionToolClient(
            workflow_id=trace.workflow_id, request_id=trace.request_id
        ),
        behaviour_tool_client=InProcessBehaviourToolClient(
            workflow_id=trace.workflow_id, request_id=trace.request_id
        ),
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        **kwargs,
    )


def specialist(response, title):
    return next(
        entry for entry in response["specialists"] if entry["title"] == title
    )


def food_log_for(plan_record, days):
    now = datetime.now(timezone.utc)

    return [
        {
            "meal": "lunch",
            "plan_id": plan_record["plan_id"],
            "recorded_at": (now - timedelta(days=offset)).isoformat(),
        }
        for offset in range(days)
    ]


class NutritionUsesRealFoodEvidence(unittest.TestCase):
    def setUp(self):
        first = run(build_state())
        self.state = first["updated_user_state"]
        self.plan = self.state["nutrition_plan"]["data"]["plans"][-1]

        # Age the plan so there is a period to observe over. The plan's own
        # created_at is what bounds the observation window.
        now = datetime.now(timezone.utc)
        self.plan = dict(self.plan, created_at=(now - timedelta(days=10)).isoformat())
        self.state["nutrition_plan"]["data"]["plans"][-1] = self.plan
        self.period = {"start": now - timedelta(days=9), "end": now}

    def _review(self, entries):
        return run(
            build_state(persisted=self.state),
            nutrition_food_log_current_period=entries,
            nutrition_period_current=self.period,
        )

    def test_the_first_plan_targets_only_signals_the_user_actually_reported(self):
        goals = self.plan["goals"]

        self.assertTrue(goals)
        for goal in goals:
            self.assertIn(
                goal["target_signal"],
                (
                    "meal_pattern",
                    "fruit_vegetable_servings",
                    "water_glasses_per_day",
                    "processed_food_frequency",
                ),
            )
            self.assertEqual(goal["decision_type"], "ADD")

    def test_a_real_food_log_is_consumed_and_reported_back(self):
        reviewed = self._review(food_log_for(self.plan, 9))
        response = serialise_workflow_state(reviewed["updated_user_state"])
        nutrition = specialist(response, "Nutrition")

        self.assertTrue(nutrition["learning"])
        self.assertTrue(
            any("logged food on" in line for line in nutrition["learning"]),
            nutrition["learning"],
        )

    def test_no_food_log_stays_not_logged_and_asks_for_one(self):
        reviewed = self._review([])
        response = serialise_workflow_state(reviewed["updated_user_state"])
        nutrition = specialist(response, "Nutrition")
        statuses = {item["adherence"] for item in nutrition["focus_items"]}

        self.assertIn("Nothing recorded for this yet", statuses)
        self.assertTrue(nutrition["need_from_you"])

    def test_no_food_log_never_becomes_poor_adherence(self):
        reviewed = self._review([])
        decisions = next(
            entry
            for entry in reviewed["agent_results"]
            if entry["agent"] == "nutrition"
        )["findings"]["decisions"]

        for decision in decisions:
            # Never a change made *because* they logged nothing...
            self.assertNotEqual(decision["decision_type"], "MODIFY")
            self.assertEqual(decision["adherence_status"], "NOT_LOGGED")

            # ...and the evidence recorded must say, in words, that an
            # absence of logging is not evidence about their eating. The
            # adherence tool writes that note itself; this asserts it
            # survives to the decision rather than being dropped.
            self.assertTrue(
                any(
                    "not evidence" in line or "absence of tracking" in line
                    for line in decision["evidence_used"]
                ),
                decision["evidence_used"],
            )

    def test_adherence_is_never_invented_when_there_is_no_period(self):
        # No period means no denominator. The tool reports INSUFFICIENT_DATA
        # and the agent must read that as UNKNOWN, not as zero.
        self.assertEqual(evidence_status_of(None), "UNKNOWN")
        self.assertEqual(evidence_status_of({"status": "INSUFFICIENT_DATA"}), "UNKNOWN")
        self.assertEqual(evidence_status_of({"status": "NOT_LOGGED"}), "NOT_LOGGED")
        self.assertEqual(evidence_status_of({"status": "ADHERED"}), "KNOWN")

    def test_consistent_logging_maintains_rather_than_churns_the_plan(self):
        reviewed = self._review(food_log_for(self.plan, 9))
        plans = reviewed["updated_user_state"]["nutrition_plan"]["data"]["plans"]

        self.assertEqual([plan["plan_version"] for plan in plans], [1])

    def test_a_review_that_changed_nothing_still_records_what_it_learned(self):
        reviewed = self._review(food_log_for(self.plan, 9))
        latest = reviewed["updated_user_state"]["nutrition_plan"]["data"]["plans"][-1]

        self.assertEqual(latest["plan_version"], 1)
        self.assertEqual(latest["plan_id"], self.plan["plan_id"])
        self.assertTrue(
            any(goal.get("evidence_used") for goal in latest["goals"]),
            "the refreshed record should carry this review's evidence",
        )

    def test_difficulty_following_the_plan_modifies_it(self):
        decision = decide_nutrition(
            topic_id="regular_meal_timing",
            target_signal="meal_pattern",
            adherence={
                "status": "NOT_ADHERED",
                "completion_rate": 0.2,
                "logged_days": 2,
                "observation_days": 10,
            },
            still_triggered=True,
        )

        self.assertEqual(decision["decision_type"], "MODIFY")
        self.assertEqual(decision["adherence_status"], "KNOWN")
        self.assertTrue(decision["evidence_used"])

    def test_a_signal_that_no_longer_triggers_is_removed(self):
        decision = decide_nutrition(
            topic_id="regular_meal_timing",
            target_signal="meal_pattern",
            adherence={"status": "ADHERED"},
            still_triggered=False,
        )

        self.assertEqual(decision["decision_type"], "REMOVE")


class BehaviourUsesRealBehaviouralEvidence(unittest.TestCase):
    def setUp(self):
        first = run(build_state())
        self.state = first["updated_user_state"]
        self.plan = self.state["behaviour"]["data"]["plans"][-1]

    def test_the_first_plan_targets_only_signals_the_user_actually_reported(self):
        for goal in self.plan["goals"]:
            self.assertIn(
                goal["target_signal"],
                (
                    "daily_sitting_hours",
                    "daily_screen_hours",
                    "exercise_days",
                    "weekly_exercise_minutes",
                ),
            )

    def test_it_is_not_the_same_advice_for_everyone(self):
        """Two users with different answers must not end up with the same
        habit goals — the failure this guards against is one hard-coded
        piece of advice handed to everybody."""

        def topics_for(profile):
            section = run(build_state(profile))["updated_user_state"]["behaviour"]

            if not section.get("available"):
                # No behaviour plan at all is a legitimate outcome, and it
                # is also a different outcome, which is what this test is
                # about.
                return None

            return set(section["data"]["plans"][-1]["topic_ids"])

        sedentary = topics_for(
            {
                **PROFILE,
                "daily_sitting_hours": 12,
                "daily_screen_hours": 10,
                "exercise_days": 5,
                "exercise_minutes": 45,
            }
        )
        inactive = topics_for(
            {
                **PROFILE,
                "daily_sitting_hours": 3,
                "daily_screen_hours": 1,
                "exercise_days": 0,
                "exercise_minutes": 0,
            }
        )

        self.assertNotEqual(sedentary, inactive)

    def test_habit_adherence_is_never_invented(self):
        for goal in self.plan["goals"]:
            self.assertIn(goal["adherence_status"], ("UNKNOWN", "NOT_LOGGED"))

    def test_exercise_adherence_is_not_reused_as_habit_adherence(self):
        # A sitting goal must stay UNKNOWN however many exercise sessions
        # were recorded: they are evidence about something else.
        decision = decide_habit(
            topic_id="take_regular_movement_breaks",
            target_signal="daily_sitting_hours",
            previous_value=12,
            current_value=12,
            still_triggered=True,
            completed_sessions=25,
            actions=[],
        )

        # NOT_LOGGED rather than KNOWN: 25 workouts say nothing about
        # whether this person took a break from sitting. Now that the
        # behaviour log exists, "not logged" is the precise word for it.
        self.assertEqual(decision["adherence_status"], "NOT_LOGGED")
        self.assertNotEqual(decision["adherence_status"], "KNOWN")
        self.assertEqual(decision["decision_type"], "MAINTAIN")
        self.assertTrue(decision["evidence_needed"])

    def test_recorded_sessions_are_evidence_for_the_activity_signals_only(self):
        decision = decide_habit(
            topic_id="build_up_weekly_activity",
            target_signal="exercise_days",
            previous_value=0,
            current_value=0,
            still_triggered=True,
            completed_sessions=4,
        )

        self.assertEqual(decision["adherence_status"], "KNOWN")
        self.assertTrue(
            any("recorded exercise" in line for line in decision["evidence_used"])
        )

    def test_no_recorded_sessions_is_not_logged_not_failure(self):
        decision = decide_habit(
            topic_id="build_up_weekly_activity",
            target_signal="exercise_days",
            previous_value=0,
            current_value=0,
            still_triggered=True,
            completed_sessions=0,
        )

        self.assertEqual(decision["adherence_status"], "NOT_LOGGED")
        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_only_completed_sessions_count_as_evidence(self):
        results = [
            {"exerciseId": "wall-sit", "status": "completed"},
            {"exerciseId": "wall-sit", "status": "incomplete"},
            {"exerciseId": "wall-sit", "status": "invalid"},
        ]

        self.assertEqual(completed_session_count(results), 1)
        self.assertEqual(completed_session_count(None), 0)

    def test_a_re_answer_that_got_worse_modifies_the_intervention(self):
        decision = decide_habit(
            topic_id="take_regular_movement_breaks",
            target_signal="daily_sitting_hours",
            previous_value=10,
            current_value=14,
            still_triggered=True,
        )

        self.assertEqual(decision["decision_type"], "MODIFY")

    def test_a_re_answer_that_improved_does_not_modify(self):
        decision = decide_habit(
            topic_id="take_regular_movement_breaks",
            target_signal="daily_sitting_hours",
            previous_value=14,
            current_value=10,
            still_triggered=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_with_nothing_to_compare_against_nothing_changes(self):
        decision = decide_habit(
            topic_id="take_regular_movement_breaks",
            target_signal="daily_sitting_hours",
            previous_value=None,
            current_value=14,
            still_triggered=True,
        )

        self.assertEqual(decision["decision_type"], "MAINTAIN")

    def test_a_signal_that_no_longer_triggers_is_removed(self):
        decision = decide_habit(
            topic_id="take_regular_movement_breaks",
            target_signal="daily_sitting_hours",
            previous_value=12,
            current_value=3,
            still_triggered=False,
        )

        self.assertEqual(decision["decision_type"], "REMOVE")

    def test_re_running_with_unchanged_answers_creates_no_new_version(self):
        state = self.state

        for _ in range(3):
            state = run(build_state(persisted=state))["updated_user_state"]

        plans = state["behaviour"]["data"]["plans"]

        self.assertEqual([plan["plan_version"] for plan in plans], [1])


class TheWholePlanReadsAsOneSystem(unittest.TestCase):
    def setUp(self):
        result = run(build_state())
        self.result = result
        self.response = serialise_workflow_state(
            result["updated_user_state"],
            safety_status=(result["safety_result"] or {})["status"],
        )

    def test_all_three_specialists_are_involved_for_this_user(self):
        titles = [entry["title"] for entry in self.response["specialists"]]

        self.assertEqual(titles, ["Movement", "Nutrition", "Daily habits"])

    def test_each_specialist_says_what_it_found_why_and_what_it_needs(self):
        for entry in self.response["specialists"]:
            self.assertTrue(entry["what_i_found"])
            self.assertTrue(entry["next_review"])
            self.assertIn("plan_version", entry)
            self.assertTrue(entry.get("need_from_you") or entry.get("watching"))

    def test_the_safety_gate_ran_over_every_specialists_output(self):
        self.assertIsNotNone(self.result["safety_result"])
        self.assertIn(
            self.result["safety_result"]["status"],
            ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED"),
        )

    def test_no_internal_identifier_reaches_the_specialist_view(self):
        text = repr(self.response["specialists"])

        for forbidden in (
            "workflow_id",
            "request_id",
            "agent_run_id",
            "tool_call_id",
            "mcp_session_id",
        ):
            self.assertNotIn(forbidden, text)

    def test_the_baseline_tests_are_not_prescribed_as_the_programme(self):
        movement = specialist(self.response, "Movement")
        ids = [exercise["id"] for exercise in movement["programme"]]

        self.assertTrue(ids)
        for baseline in ("chair-sit-to-stand", "standing-shoulder-raise"):
            self.assertNotIn(baseline, ids)


if __name__ == "__main__":
    unittest.main()
