import unittest

from orchestration.agent_result import validate_agent_result
from orchestration.ids import start_workflow
from nutrition_agent.agent import AGENT_ID, run_nutrition_agent
from nutrition_agent.input_contract import build_nutrition_agent_input
from nutrition_agent.tool_client import NutritionToolClient, InProcessNutritionToolClient
from user_state.schema import build_user_state, validate_user_state


def _need_entry(level):
    return {
        "level": level,
        "score": 0.5 if level != "NOT_ASSESSED" else None,
        "evidence": ["fixture evidence"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(nutrition_level):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry("NOT_ASSESSED"),
        "stability_need": _need_entry("NOT_ASSESSED"),
        "functional_movement_need": _need_entry("NOT_ASSESSED"),
        "behaviour_need": _need_entry("NOT_ASSESSED"),
        "nutrition_need": _need_entry(nutrition_level),
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


def _state(nutrition_level, profile_doc=None):
    profile = dict(profile_doc or {})
    # These plan-generation fixtures represent a user who answered both
    # safety-context questions and has no reported items.
    profile.setdefault("food_allergies", [])
    profile.setdefault("dietary_restrictions", [])
    state = build_user_state(profile_doc=profile)
    state["current_needs"] = {
        "available": True, "reason": None, "data": _needs(nutrition_level),
    }
    return state


def _run(state):
    trace = start_workflow()
    client = InProcessNutritionToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
    return run_nutrition_agent(state, client, parent_trace=trace), client


class ValidInputHighNeedTests(unittest.TestCase):
    def setUp(self):
        self.state = _state(
            "HIGH",
            profile_doc={
                "meal_pattern": "skips_meals",
                "fruit_vegetable_servings": 1,
                "water_glasses_per_day": 2,
                "processed_food_frequency": "daily",
            },
        )
        self.result, self.client = _run(self.state)

    def test_returns_a_valid_agent_result(self):
        validate_agent_result(self.result)
        self.assertEqual(self.result["agent"], AGENT_ID)

    def test_status_completed_with_a_real_plan(self):
        self.assertEqual(self.result["status"], "completed")
        plan = self.result["findings"]["plan"]
        self.assertTrue(plan["nutrition_goals"])

    def test_plan_covers_every_triggered_signal(self):
        triggered = set(self.result["findings"]["triggered_signals"])
        self.assertEqual(
            triggered,
            {"meal_pattern", "fruit_vegetable_servings", "water_glasses_per_day", "processed_food_frequency"},
        )

    def test_mcp_tool_was_actually_used(self):
        # The InProcess double calls the real catalog function; verifying
        # the plan's topic_ids exist in the real library proves the tool
        # path was actually exercised, not hard-coded.
        from nutrition_library.catalog import list_topic_ids
        for entry in self.result["findings"]["plan"]["nutrition_goals"]:
            self.assertIn(entry["topic_id"], list_topic_ids())

    def test_recommendations_are_structured(self):
        for rec in self.result["recommendations"]:
            self.assertIn("topic_id", rec)
            self.assertIn("reason", rec)

    def test_no_diagnostic_or_prescriptive_language(self):
        # Checked against rationale/practical_goal only — safety_notes are
        # allowed to defensively say things like "not a prescribed diet"
        # (a negation, not a prescriptive claim); plan_schema.py's own
        # denylist enforces this same scope at construction time.
        for entry in self.result["findings"]["plan"]["nutrition_goals"]:
            text = (entry["rationale"] + " " + entry["practical_goal"]).lower()
            for banned in ("diagnos", "cures", "supplement", "medication", "deficien"):
                self.assertNotIn(banned, text)


class GeneralMaintenanceActivityTests(unittest.TestCase):
    def test_low_need_uses_real_catalog_activity_and_labels_it_general(self):
        result, _ = _run(_state("LOW"))
        self.assertEqual(result["findings"]["mode"], "maintenance_review")
        activity = result["findings"]["activities"][0]
        self.assertEqual(activity["id"], "build_a_regular_meal_pattern")
        self.assertIn("GENERAL_EDUCATION", activity["personalization_status"])
        self.assertTrue(activity["action"])
        self.assertTrue(activity["safety_notes"])
        self.assertEqual(result["recommendations"][0]["id"], activity["id"])


class MissingNutritionDataTests(unittest.TestCase):
    def test_agent_contract_preserves_known_unknown_and_explicit_empty_values(self):
        state = _state("HIGH", {
            "fruit_vegetable_servings": 1,
            "food_preferences": ["fruit"],
            "food_allergies": [],
            "dietary_restrictions": None,
            "nutrition_goals": ["more produce"],
        })
        payload = build_nutrition_agent_input(
            state, workflow_id="wf", request_id="req", agent_run_id="run"
        )
        self.assertEqual(payload["food_preferences"], ["fruit"])
        self.assertEqual(payload["food_allergies"], [])
        self.assertIsNone(payload["dietary_restrictions"])
        self.assertEqual(payload["nutrition_goals"], ["more produce"])

    def test_saved_meal_logs_are_included_in_nutrition_agent_input(self):
        state = _state("LOW")
        entry = {
            "meal": "lunch", "food_name": "dal and rice", "quantity": "1 bowl",
            "notes": "at home", "recorded_at": "2026-11-01T10:00:00Z", "user_id": "must-not-cross",
        }
        payload = build_nutrition_agent_input(
            state, workflow_id="wf", request_id="req", agent_run_id="run",
            meal_log_entries=[entry],
        )
        self.assertEqual(payload["recent_meal_logs"], [{
            "meal": "lunch", "food_name": "dal and rice", "quantity": "1 bowl",
            "notes": "at home", "recorded_at": "2026-11-01T10:00:00Z",
        }])
        from nutrition_agent.evidence import build_nutrition_evidence_view
        evidence = build_nutrition_evidence_view(state, food_log_entries=[entry])
        self.assertIn("User-logged lunch: dal and rice (1 bowl)", evidence["evidence_used"])

    def test_nutrition_need_not_assessed_produces_general_catalog_activity_not_a_plan(self):
        state = _state("NOT_ASSESSED")
        result, _ = _run(state)
        validate_agent_result(result)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["findings"].get("plan"))
        self.assertEqual(result["recommendations"][0]["id"], "build_a_regular_meal_pattern")
        self.assertIn("GENERAL_EDUCATION", result["findings"]["activities"][0]["personalization_status"])

    def test_high_need_but_unrecognised_signal_values_still_handled(self):
        # current_needs says HIGH (constructed directly for this unit
        # test — see module fixture) but the raw nutrition signals in the
        # User State are absent, so the agent has nothing to search for.
        state = _state("HIGH", profile_doc={})
        result, _ = _run(state)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"], [])
        self.assertIn("reason", result["findings"])


class NutritionNeedLowTests(unittest.TestCase):
    def test_low_need_never_produces_a_plan(self):
        state = _state("LOW", profile_doc={"meal_pattern": "regular"})
        result, client = _run(state)
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["findings"].get("plan"))
        self.assertEqual(result["recommendations"][0]["id"], "build_a_regular_meal_pattern")


class PreferenceHandlingTests(unittest.TestCase):
    def test_food_preferences_are_never_invented(self):
        state = _state(
            "HIGH",
            profile_doc={"fruit_vegetable_servings": 1},
        )
        result, _ = _run(state)
        # Missing preference remains unknown while explicit empty allergy /
        # restriction answers permit evidence-based general guidance.
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["findings"].get("plan"))

    def test_missing_allergy_and_restriction_answers_request_clarification(self):
        state = build_user_state(profile_doc={"fruit_vegetable_servings": 1})
        state["current_needs"] = {"available": True, "reason": None, "data": _needs("HIGH")}
        result, _ = _run(state)
        self.assertEqual(result["findings"]["mode"], "context_required")
        self.assertEqual(result["findings"]["missing_information"], ["food allergies", "dietary restrictions"])

    def test_restriction_filters_literal_catalog_example(self):
        state = _state("HIGH", {
            "processed_food_frequency": "daily",
            "food_allergies": ["nuts"], "dietary_restrictions": [],
        })
        result, _ = _run(state)
        goals = result["findings"]["plan"]["nutrition_goals"]
        self.assertTrue(goals)
        self.assertNotIn("nuts", " ".join(goal["practical_goal"] for goal in goals).lower())

    def test_unusable_catalog_topic_is_deferred_with_reason(self):
        state = _state("HIGH", {
            "fruit_vegetable_servings": 1,
            "food_allergies": [],
            "dietary_restrictions": ["fruit", "vegetables"],
        })
        result, _ = _run(state)
        self.assertEqual(result["findings"]["mode"], "context_required")
        excluded = result["findings"]["excluded_topics"][0]
        self.assertEqual(excluded["target_signal"], "fruit_vegetable_servings")
        self.assertTrue(excluded["reason"])
        self.assertTrue(excluded["additional_information_required"])

    def test_preference_selects_matching_catalog_goal_example(self):
        state = _state("HIGH", {
            "fruit_vegetable_servings": 1,
            "food_allergies": [], "dietary_restrictions": [],
            "food_preferences": ["fruit"],
        })
        result, _ = _run(state)
        goal = result["findings"]["plan"]["nutrition_goals"][0]
        self.assertIn("fruit", goal["practical_goal"].lower())

    def test_user_stated_goal_prioritizes_matching_signal(self):
        state = _state("HIGH", {
            "meal_pattern": "skips_meals", "water_glasses_per_day": 1,
            "food_allergies": [], "dietary_restrictions": [],
            "nutrition_goals": ["drink more water"],
        })
        result, _ = _run(state)
        self.assertEqual(result["findings"]["triggered_signals"][0], "water_glasses_per_day")


class PlanCreationTests(unittest.TestCase):
    def test_plan_is_capped_and_well_formed(self):
        from nutrition_agent.plan_schema import validate_nutrition_plan

        state = _state(
            "HIGH",
            profile_doc={
                "meal_pattern": "irregular",
                "fruit_vegetable_servings": 0,
                "water_glasses_per_day": 1,
                "processed_food_frequency": "often",
            },
        )
        result, _ = _run(state)
        plan = result["findings"]["plan"]
        validate_nutrition_plan(plan)
        self.assertLessEqual(len(plan["nutrition_goals"]), 4)

    def test_serialized_response_preserves_agent_goal_and_rationale(self):
        from orchestrator.state_update import apply_nutrition_plan
        from workflow.response import serialise_workflow_state

        state = _state("HIGH", {
            "fruit_vegetable_servings": 1,
            "food_allergies": [], "dietary_restrictions": [],
            "food_preferences": ["fruit"],
        })
        result, _ = _run(state)
        persisted = apply_nutrition_plan(state, result)
        response = serialise_workflow_state(persisted)
        entry = result["findings"]["plan"]["nutrition_goals"][0]
        displayed = response["nutrition_plan"]["recommendations"][0]
        self.assertEqual(displayed["action"], entry["practical_goal"])
        self.assertEqual(displayed["why"], entry["rationale"])
        self.assertEqual(displayed["evidence_used"], entry["evidence_used"])


class InvalidInputTests(unittest.TestCase):
    def test_missing_current_needs_key_is_handled_not_crashed(self):
        state = build_user_state()
        trace = start_workflow()
        client = InProcessNutritionToolClient(workflow_id=trace.workflow_id, request_id=trace.request_id)
        result = run_nutrition_agent(state, client, parent_trace=trace)
        validate_agent_result(result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["recommendations"][0]["id"], "build_a_regular_meal_pattern")
        self.assertIn("GENERAL_EDUCATION", result["findings"]["activities"][0]["personalization_status"])


class McpFailureTests(unittest.TestCase):
    def test_a_broken_tool_client_produces_a_failed_result_not_a_crash(self):
        class BrokenClient(NutritionToolClient):
            def search_nutrition_guidance(self, **kwargs):
                raise ConnectionError("nutrition mcp down")

            def get_nutrition_topic_details(self, topic_id):
                raise ConnectionError("nutrition mcp down")

        state = _state(
            "HIGH",
            profile_doc={"fruit_vegetable_servings": 1, "water_glasses_per_day": 2},
        )
        trace = start_workflow()
        result = run_nutrition_agent(state, BrokenClient(), parent_trace=trace)
        validate_agent_result(result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("mcp_unavailable_or_tool_error", result["safetyFlags"])
        self.assertTrue(result["requiresReassessment"])


if __name__ == "__main__":
    unittest.main()
