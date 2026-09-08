import unittest

from orchestration.agent_result import validate_agent_result
from orchestration.ids import start_workflow
from behaviour_agent.agent import AGENT_ID, run_behaviour_agent
from behaviour_agent.tool_client import BehaviourToolClient, InProcessBehaviourToolClient
from user_state.schema import build_user_state


def _need_entry(level):
    return {
        "level": level,
        "score": 0.5 if level != "NOT_ASSESSED" else None,
        "evidence": ["fixture evidence"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(behaviour_level):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry("NOT_ASSESSED"),
        "stability_need": _need_entry("NOT_ASSESSED"),
        "functional_movement_need": _need_entry("NOT_ASSESSED"),
        "behaviour_need": _need_entry(behaviour_level),
        "nutrition_need": _need_entry("NOT_ASSESSED"),
        "exercise_need": _need_entry("NOT_ASSESSED"),
        "safety_status": _need_entry("NOT_ASSESSED"),
        "overallSummary": {
            "headline": "x", "dimensionsAtHigh": [], "dimensionsAtMedium": [],
            "dimensionsAtLow": [], "dimensionsNotAssessed": [], "assessedCount": 0,
            "notAssessedCount": 0,
        },
        "metadata": {
            "assessmentVersion": "0.1.0", "generatedAt": "2026-01-01T00:00:00Z",
            "workflowId": "wf_fixture", "requestId": "req_fixture",
        },
    }


def _state(behaviour_level, profile_doc=None):
    state = build_user_state(profile_doc=profile_doc or {})
    state["current_needs"] = {
        "available": True, "reason": None, "data": _needs(behaviour_level),
    }
    return state


def _run(state):
    trace = start_workflow()
    client = InProcessBehaviourToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
    return run_behaviour_agent(state, client, parent_trace=trace), client


class SittingBehaviourTests(unittest.TestCase):
    def test_high_sitting_time_is_targeted(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        result, _ = _run(state)
        self.assertIn("daily_sitting_hours", result["findings"]["triggered_signals"])
        topic_ids = [g["topic_id"] for g in result["findings"]["plan"]["habit_goals"]]
        self.assertIn("take_regular_movement_breaks", topic_ids)


class MovementBreakNeedTests(unittest.TestCase):
    def test_movement_break_goal_has_a_practical_example(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        result, _ = _run(state)
        entry = next(
            g for g in result["findings"]["plan"]["habit_goals"]
            if g["topic_id"] == "take_regular_movement_breaks"
        )
        self.assertTrue(entry["practical_goal"].strip())


class BarrierAwareTests(unittest.TestCase):
    def test_topics_name_common_barriers(self):
        from behaviour_library.catalog import get_behaviour_topic_details
        topic = get_behaviour_topic_details("take_regular_movement_breaks")
        self.assertTrue(topic["common_barriers"])


class RoutineTests(unittest.TestCase):
    def test_low_weekly_volume_is_targeted(self):
        state = _state("HIGH", profile_doc={"exercise_days": 1, "exercise_minutes": 10})
        result, _ = _run(state)
        self.assertIn("weekly_exercise_minutes", result["findings"]["triggered_signals"])


class HabitPlanTests(unittest.TestCase):
    def test_plan_is_well_formed_and_capped(self):
        from behaviour_agent.plan_schema import validate_habit_plan

        state = _state(
            "HIGH",
            profile_doc={
                "daily_sitting_hours": 12, "daily_screen_hours": 10,
                "exercise_days": 0, "exercise_minutes": 0,
            },
        )
        result, _ = _run(state)
        plan = result["findings"]["plan"]
        validate_habit_plan(plan)
        self.assertLessEqual(len(plan["habit_goals"]), 4)


class AdherenceTests(unittest.TestCase):
    """This application records nothing about whether a habit goal was
    actually kept, so the agent must never claim it knows.

    The original form of this test banned the substring "adherence" from
    the findings entirely. That worked while the agent said nothing at all
    about adherence, but it also forbids the agent from stating, in the
    data, that adherence is UNKNOWN — which is the honest thing to say and
    is what the Behaviour panel now reads to tell the user what is missing.
    The intent is unchanged and the check is stricter: no adherence VALUE
    may be claimed, and the only statuses permitted are the two that assert
    an absence.
    """

    def test_no_adherence_data_is_ever_fabricated(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        result, _ = _run(state)
        findings = result["findings"]

        # With nothing recorded, every computed figure must be null and
        # the status must assert the absence. Banning the *word* would also
        # forbid the agent from saying "not logged", which is the honest
        # thing to say -- so this asserts the values instead.
        adherence = findings["behaviour_adherence"]

        self.assertEqual(adherence["status"], "NOT_LOGGED")
        self.assertIsNone(adherence["completion_rate"])
        self.assertIsNone(adherence["difficulty_rate"])
        self.assertEqual(adherence["recorded_actions"], 0)
        self.assertEqual(adherence["completed_actions"], 0)
        self.assertIn("not evidence", " ".join(adherence["notes"]))

        # Every goal and decision must say adherence is not known.
        for entry in findings["plan"]["habit_goals"]:
            self.assertIn(entry.get("adherence_status"), ("UNKNOWN", "NOT_LOGGED"))

        for decision in findings["decisions"]:
            self.assertIn(decision["adherence_status"], ("UNKNOWN", "NOT_LOGGED"))
            self.assertEqual(decision["evidence_used"], [])


class StructuredAgentResultTests(unittest.TestCase):
    def test_returns_a_valid_agent_result(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        result, _ = _run(state)
        validate_agent_result(result)
        self.assertEqual(result["agent"], AGENT_ID)

    def test_recommendations_are_structured(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        result, _ = _run(state)
        for rec in result["recommendations"]:
            self.assertIn("topic_id", rec)
            self.assertIn("reason", rec)


class McpUsageTests(unittest.TestCase):
    def test_topic_ids_exist_in_the_real_library(self):
        from behaviour_library.catalog import list_topic_ids
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12, "daily_screen_hours": 10})
        result, _ = _run(state)
        for entry in result["findings"]["plan"]["habit_goals"]:
            self.assertIn(entry["topic_id"], list_topic_ids())


class InvalidInputTests(unittest.TestCase):
    def test_behaviour_need_not_assessed_is_handled(self):
        state = _state("NOT_ASSESSED")
        result, _ = _run(state)
        validate_agent_result(result)
        self.assertEqual(result["recommendations"], [])

    def test_low_need_never_produces_a_plan(self):
        state = _state("LOW", profile_doc={"daily_sitting_hours": 4})
        result, _ = _run(state)
        self.assertEqual(result["recommendations"], [])

    def test_no_diagnostic_or_psychological_claims(self):
        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12, "daily_screen_hours": 10})
        result, _ = _run(state)
        for entry in result["findings"]["plan"]["habit_goals"]:
            text = (entry["rationale"] + " " + entry["practical_goal"]).lower()
            for banned in ("diagnos", "mental illness", "therapy", "treatment for", "disorder"):
                self.assertNotIn(banned, text)


class McpFailureTests(unittest.TestCase):
    def test_a_broken_tool_client_produces_a_failed_result_not_a_crash(self):
        class BrokenClient(BehaviourToolClient):
            def search_behaviour_guidance(self, **kwargs):
                raise ConnectionError("behaviour mcp down")

            def get_behaviour_topic_details(self, topic_id):
                raise ConnectionError("behaviour mcp down")

        state = _state("HIGH", profile_doc={"daily_sitting_hours": 12})
        trace = start_workflow()
        result = run_behaviour_agent(state, BrokenClient(), parent_trace=trace)
        validate_agent_result(result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("mcp_unavailable_or_tool_error", result["safetyFlags"])


if __name__ == "__main__":
    unittest.main()
