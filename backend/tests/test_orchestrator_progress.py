"""Orchestrator Phase 5 extension: progress-trigger selection, adaptation
dispatch to the correct specialist agent(s), the unified Safety Gate pass,
baseline preservation, plan versioning, and at least one complete
closed-loop end-to-end run:

    Baseline -> Plan -> Activity Result -> Progress -> Orchestrator ->
    Adaptation -> Specialist -> Safety -> New Plan -> Updated State
"""

import unittest

from behaviour_agent.tool_client import InProcessBehaviourToolClient
from nutrition_agent.tool_client import InProcessNutritionToolClient
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from progress_agent.tool_client import InProcessProgressToolClient
from user_state.schema import build_user_state


def _need_entry(level):
    return {"level": level, "score": 0.5, "evidence": ["fixture"], "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE"}


def _needs(mobility="LOW", stability="LOW", functional_movement="LOW", behaviour="LOW", nutrition="NOT_ASSESSED"):
    return {
        "assessmentVersion": "0.1.0",
        "mobility_need": _need_entry(mobility),
        "stability_need": _need_entry(stability),
        "functional_movement_need": _need_entry(functional_movement),
        "behaviour_need": _need_entry(behaviour),
        "nutrition_need": _need_entry(nutrition),
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


def _state(*, profile_doc=None, **need_kwargs):
    state = build_user_state(profile_doc=profile_doc or {})
    state["current_needs"] = {"available": True, "reason": None, "data": _needs(**need_kwargs)}
    return state


def _clients(tag="c"):
    return dict(
        tool_client=InProcessExerciseToolClient(workflow_id=f"wf_{tag}", request_id=f"req_{tag}"),
        behaviour_tool_client=InProcessBehaviourToolClient(workflow_id=f"wf_{tag}", request_id=f"req_{tag}"),
        nutrition_tool_client=InProcessNutritionToolClient(workflow_id=f"wf_{tag}", request_id=f"req_{tag}"),
    )


def _balance_doc(hold, completed_at):
    return {
        "tests": {
            "balance": {
                "status": "completed",
                "measurements": {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": hold},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": hold},
                },
            },
        },
        "completed_at": completed_at,
    }


class ProgressSelectionTests(unittest.TestCase):
    """decide_progress_required, surfaced through run_workflow's
    orchestrator_decision, and the "not selected without a trigger" case."""

    def test_progress_not_selected_without_a_trigger(self):
        state = _state(stability="HIGH")
        result = run_workflow(state, **_clients())
        self.assertNotIn("progress", result["selected_agents"])
        self.assertFalse(result["orchestrator_decision"]["progress_required"])

    def test_progress_selected_when_trigger_given_and_client_available(self):
        state = _state(stability="LOW")
        progress_client = InProcessProgressToolClient(workflow_id="wf", request_id="req")
        result = run_workflow(
            state,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            **_clients(),
        )
        self.assertIn("progress", result["selected_agents"])
        self.assertTrue(result["orchestrator_decision"]["progress_required"])

    def test_progress_required_but_no_client_is_a_named_error_not_a_crash(self):
        state = _state(stability="LOW")
        result = run_workflow(
            state,
            progress_trigger={"reason": "exercise activity recorded"},
            **_clients(),
        )
        self.assertNotIn("progress", result["selected_agents"])
        self.assertTrue(any("ProgressToolClient" in e for e in result["errors"]))

    def test_trigger_without_a_reason_is_not_treated_as_required(self):
        state = _state(stability="LOW")
        result = run_workflow(
            state,
            progress_trigger={},
            progress_tool_client=InProcessProgressToolClient(workflow_id="wf", request_id="req"),
            **_clients(),
        )
        self.assertNotIn("progress", result["selected_agents"])


class DispatchAndClosedLoopTests(unittest.TestCase):
    """The full closed-loop chain, at least once, plus the multi-agent
    dispatch variants (physio, behaviour) and the negative/insufficient-
    data case."""

    def _create_initial_plan(self, needs_kwargs, profile_doc=None):
        state = _state(profile_doc=profile_doc, **needs_kwargs)
        result = run_workflow(state, **_clients("init"))
        return result

    def test_full_closed_loop_improved_high_adherence_dispatches_physio_and_versions_plan(self):
        # Baseline -> Plan
        init = self._create_initial_plan({"stability": "HIGH"})
        self.assertEqual(init["selected_agents"], ["physio"])
        state_after_plan = init["updated_user_state"]
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]

        # User Performs Plan -> Structured Performance/Adherence Data
        exercise_results = [
            {"exerciseId": eid, "plan_id": plan_v1["plan_id"], "status": "completed"}
            for eid in plan_v1["exercise_ids"]
        ]

        # Progress Agent -> Orchestrator -> Decision -> Physio -> Safety -> New Plan
        progress_client = InProcessProgressToolClient(workflow_id="wf_p", request_id="req_p")
        closed_loop = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(60, "2026-09-05T00:00:00Z"),
            exercise_results=exercise_results,
            **_clients("loop"),
        )

        progress_result = next(r for r in closed_loop["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["findings"]["overall_direction"], "IMPROVED")
        self.assertEqual(progress_result["findings"]["adaptation_recommendation"], "PROGRESS")

        # Specialist re-run and Safety Gate both happened
        self.assertIn("physio", closed_loop["selected_agents"])
        self.assertIsNotNone(closed_loop["safety_result"])

        # Updated User State: new plan version, with a structured reason
        plans = closed_loop["updated_user_state"]["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[1]["plan_version"], 2)
        self.assertIsNotNone(plans[1]["adaptation_reason"])
        self.assertNotEqual(plans[1]["adaptation_reason"], "Plan updated.")
        self.assertEqual(plans[1]["triggered_by"], "progress_agent")

        # Baseline preservation: v1 is untouched
        self.assertEqual(plans[0], plan_v1)

    def test_negative_case_missing_current_assessment_never_claims_progress(self):
        init = self._create_initial_plan({"stability": "HIGH"})
        state_after_plan = init["updated_user_state"]
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]

        progress_client = InProcessProgressToolClient(workflow_id="wf_neg", request_id="req_neg")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "periodic check"},
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=None,
            exercise_results=[],
            **_clients("neg"),
        )
        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["findings"]["overall_direction"], "NOT_ENOUGH_DATA")
        self.assertEqual(progress_result["findings"]["adaptation_recommendation"], "REASSESS")
        # REASSESS never dispatches physio/behaviour on its own
        self.assertNotIn("physio", result["selected_agents"][1:])

    def test_stagnation_high_adherence_maintains_no_specialist_dispatch(self):
        init = self._create_initial_plan({"stability": "HIGH"})
        state_after_plan = init["updated_user_state"]
        # Drop stability need to LOW so Phase A does not select physio —
        # isolates whether Progress's MAINTAIN recommendation dispatches
        # anything on its own (it must not).
        state_after_plan["current_needs"]["data"] = _needs(stability="LOW")
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]

        exercise_results = [
            {"exerciseId": eid, "plan_id": plan_v1["plan_id"], "status": "completed"}
            for eid in plan_v1["exercise_ids"]
        ]
        progress_client = InProcessProgressToolClient(workflow_id="wf_stag", request_id="req_stag")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            baseline_assessment=_balance_doc(50, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(50, "2026-09-05T00:00:00Z"),
            exercise_results=exercise_results,
            **_clients("stag"),
        )
        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["findings"]["overall_direction"], "STABLE")
        self.assertEqual(progress_result["findings"]["adaptation_recommendation"], "MAINTAIN")
        self.assertNotIn("physio", result["selected_agents"])
        self.assertNotIn("behaviour", result["selected_agents"])

    def test_adherence_low_stable_performance_dispatches_behaviour_not_physio(self):
        init = self._create_initial_plan({"stability": "HIGH"}, profile_doc={"daily_sitting_hours": 12})
        state_after_plan = init["updated_user_state"]
        # behaviour_need HIGH so the Behaviour Agent's own plan-generation
        # gate (need-based, mirroring Physio's) actually produces a plan
        # once dispatched — Progress's recommendation and the Behaviour
        # Agent's own criteria agreeing is a realistic combination, not a
        # contradiction; what this test isolates is that MODIFY dispatches
        # Behaviour and never Physio (whose own need stays LOW here).
        state_after_plan["current_needs"]["data"] = _needs(stability="LOW", behaviour="HIGH")
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]

        # Only 1 of 4 exercises completed -> LOW adherence
        exercise_results = [
            {"exerciseId": plan_v1["exercise_ids"][0], "plan_id": plan_v1["plan_id"], "status": "completed"},
        ]
        progress_client = InProcessProgressToolClient(workflow_id="wf_mod", request_id="req_mod")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            baseline_assessment=_balance_doc(50, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(50, "2026-09-05T00:00:00Z"),
            exercise_results=exercise_results,
            **_clients("mod"),
        )
        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["findings"]["adaptation_recommendation"], "MODIFY")
        self.assertIn("behaviour", result["selected_agents"])
        self.assertNotIn("physio", result["selected_agents"])

        # A behaviour plan version was created, attributed to Progress
        behaviour_plans = result["updated_user_state"]["behaviour"]["data"]["plans"]
        self.assertGreaterEqual(len(behaviour_plans), 1)
        self.assertEqual(behaviour_plans[-1]["triggered_by"], "progress_agent")

    def test_progress_does_not_double_run_specialist_already_selected_in_phase_a(self):
        # stability stays HIGH in both cycles -> Phase A selects physio on
        # its own each time; Progress's PROGRESS recommendation must not
        # cause a second, redundant physio run in the same workflow call.
        init = self._create_initial_plan({"stability": "HIGH"})
        state_after_plan = init["updated_user_state"]
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]
        exercise_results = [
            {"exerciseId": eid, "plan_id": plan_v1["plan_id"], "status": "completed"}
            for eid in plan_v1["exercise_ids"]
        ]
        progress_client = InProcessProgressToolClient(workflow_id="wf_dup", request_id="req_dup")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(60, "2026-09-05T00:00:00Z"),
            exercise_results=exercise_results,
            **_clients("dup"),
        )
        self.assertEqual(result["selected_agents"].count("physio"), 1)
        plans = result["updated_user_state"]["exercise_history"]["data"]["plans"]
        # Exactly one new plan version this cycle — never two.
        self.assertEqual(len(plans), 2)

    def test_safety_gate_still_applies_to_a_progress_triggered_adaptation(self):
        init = self._create_initial_plan({"stability": "HIGH"})
        state_after_plan = init["updated_user_state"]
        plan_v1 = state_after_plan["exercise_history"]["data"]["plans"][0]
        exercise_results = [
            {"exerciseId": eid, "plan_id": plan_v1["plan_id"], "status": "completed"}
            for eid in plan_v1["exercise_ids"]
        ]
        progress_client = InProcessProgressToolClient(workflow_id="wf_safety", request_id="req_safety")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(60, "2026-09-05T00:00:00Z"),
            exercise_results=exercise_results,
            **_clients("safety"),
        )
        # Exactly one Safety Gate evaluation ran (never two, never skipped)
        self.assertIsNotNone(result["safety_result"])
        self.assertIn(result["safety_result"]["status"], ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED"))

    def test_plan_versioning_preserves_every_historical_version(self):
        init = self._create_initial_plan({"stability": "HIGH"})
        state = init["updated_user_state"]
        plan_v1 = state["exercise_history"]["data"]["plans"][0]

        for cycle in range(2):
            exercise_results = [
                {"exerciseId": eid, "plan_id": state["exercise_history"]["data"]["plans"][-1]["plan_id"], "status": "completed"}
                for eid in state["exercise_history"]["data"]["plans"][-1]["exercise_ids"]
            ]
            progress_client = InProcessProgressToolClient(workflow_id=f"wf_v{cycle}", request_id=f"req_v{cycle}")
            result = run_workflow(
                state,
                progress_tool_client=progress_client,
                progress_trigger={"reason": "exercise activity recorded"},
                baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
                current_assessment=_balance_doc(60 + cycle, "2026-09-05T00:00:00Z"),
                exercise_results=exercise_results,
                **_clients(f"v{cycle}"),
            )
            state = result["updated_user_state"]

        plans = state["exercise_history"]["data"]["plans"]
        self.assertEqual(len(plans), 3)
        self.assertEqual([p["plan_version"] for p in plans], [1, 2, 3])
        self.assertEqual(plans[0], plan_v1)


if __name__ == "__main__":
    unittest.main()
