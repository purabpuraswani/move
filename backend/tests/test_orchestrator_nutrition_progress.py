"""Phase 6: nutrition-specific progress, dispatch, and a full nutrition
closed-loop integration test — kept in its own file, separate from
tests/test_orchestrator_progress.py's Phase 5 physical-progress coverage,
mirroring that file's fixtures and discipline exactly.

    Need (HIGH) -> Orchestrator -> Nutrition Agent -> Nutrition MCP ->
    Personalized Plan -> User Food Log -> Nutrition Adherence ->
    Progress Agent -> Orchestrator -> Nutrition Agent -> Updated Plan ->
    Safety Gate

Also covers the explicit "Low Need vs Progress Trigger" requirement: a
current LOW physical need must not prevent a legitimate Progress-triggered
specialist review, while the specialist retains sole authority over
whether a new plan actually results.
"""

import unittest
from datetime import datetime, timedelta, timezone

from behaviour_agent.tool_client import InProcessBehaviourToolClient
from nutrition_agent.tool_client import InProcessNutritionToolClient
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from progress_agent.tool_client import InProcessProgressToolClient
from user_state.schema import build_user_state

# A completion timestamp that is genuinely recent, relative to whatever
# "now" is when this suite runs. These tests are about what the Progress
# Agent concludes from a *current* assessment; a hard-coded calendar date
# silently became a "stale assessment" case once enough real time passed,
# which is not what any of them is testing.
RECENT_COMPLETED_AT = (
    datetime.now(timezone.utc) - timedelta(days=3)
).strftime("%Y-%m-%dT%H:%M:%SZ")



def _need_entry(level):
    return {
        "level": level,
        "score": 0.5,
        "evidence": ["fixture"],
        "confidence": "HIGH" if level != "NOT_ASSESSED" else "NONE",
    }


def _needs(mobility="LOW", stability="LOW", functional_movement="LOW", behaviour="LOW", nutrition="LOW"):
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


def _daily_food_log_entries(plan_id, start_date, days_logged):
    """One entry per day, starting at start_date, for `days_logged` days."""

    return [
        {
            "plan_id": plan_id,
            "meal": "lunch",
            "recorded_at": f"{(start_date + timedelta(days=i)).isoformat()}T09:00:00+00:00",
        }
        for i in range(days_logged)
    ]


class NutritionClosedLoopTests(unittest.TestCase):
    """The full nutrition closed loop, end-to-end, exactly as specified."""

    def _create_initial_nutrition_plan(self):
        # A real triggering self-reported signal is required for the
        # Nutrition Agent to actually build a plan (see
        # nutrition_agent/agent.py's _triggered_signals()) — a bare
        # nutrition_need=HIGH with no underlying signal produces a
        # completed-but-planless result, same as physio's own need-gate.
        state = _state(
            profile_doc={
                "meal_pattern": "skips_meals",
                "fruit_vegetable_servings": 1,
                "water_glasses_per_day": 2,
                "processed_food_frequency": "daily",
            },
            nutrition="HIGH",
        )
        result = run_workflow(state, **_clients("nutinit"))
        return result

    def test_full_nutrition_closed_loop_declined_adherence_dispatches_nutrition_and_versions_plan(self):
        # Need (HIGH) -> Orchestrator -> Nutrition Agent -> Plan
        init = self._create_initial_nutrition_plan()
        self.assertEqual(init["selected_agents"], ["nutrition"])
        state_after_plan = init["updated_user_state"]
        plan_v1 = state_after_plan["nutrition_plan"]["data"]["plans"][0]

        plan_created = datetime.fromisoformat(plan_v1["created_at"].replace("Z", "+00:00"))
        previous_start = plan_created.date()
        previous_end = previous_start + timedelta(days=6)
        current_start = previous_end + timedelta(days=1)
        current_end = current_start + timedelta(days=6)

        # User Food Log: high adherence in the previous period, then a
        # real drop-off in the current period — a genuine, computed
        # decline, never a fabricated one.
        previous_entries = _daily_food_log_entries(plan_v1["plan_id"], previous_start, days_logged=7)
        current_entries = _daily_food_log_entries(plan_v1["plan_id"], current_start, days_logged=1)

        # Progress Agent -> Orchestrator -> Decision -> Nutrition -> Safety -> Updated Plan
        progress_client = InProcessProgressToolClient(workflow_id="wf_nutloop", request_id="req_nutloop")
        closed_loop = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "food log activity recorded"},
            nutrition_food_log_previous_period=previous_entries,
            nutrition_food_log_current_period=current_entries,
            nutrition_period_previous={"start": previous_start.isoformat(), "end": previous_end.isoformat()},
            nutrition_period_current={"start": current_start.isoformat(), "end": current_end.isoformat()},
            **_clients("nutloop"),
        )

        progress_result = next(r for r in closed_loop["agent_results"] if r["agent"] == "progress")
        nutrition_progress = progress_result["findings"]["nutrition_progress"]
        self.assertIsNotNone(nutrition_progress)
        self.assertEqual(nutrition_progress["status"], "DECLINED")
        self.assertEqual(nutrition_progress["adaptation_recommendation"], "MODIFY")

        # Nutrition ran (Phase A independently selected it too, since
        # nutrition_need is still HIGH — exactly the Phase 5 precedent for
        # physio's own full closed-loop test) and Safety Gate evaluated it.
        self.assertIn("nutrition", closed_loop["selected_agents"])
        self.assertIsNotNone(closed_loop["safety_result"])

        # Updated User State: new nutrition plan version, with a real,
        # structured, nutrition-specific adaptation reason.
        plans = closed_loop["updated_user_state"]["nutrition_plan"]["data"]["plans"]
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[1]["plan_version"], 2)
        self.assertIsNotNone(plans[1]["adaptation_reason"])
        self.assertIn("MODIFY", plans[1]["adaptation_reason"])
        self.assertIn("nutrition", plans[1]["adaptation_reason"])
        self.assertEqual(plans[1]["triggered_by"], "progress_agent")

        # Baseline preservation: v1 is untouched.
        self.assertEqual(plans[0], plan_v1)

    def test_no_food_log_data_is_not_enough_data_never_a_fabricated_decline(self):
        init = self._create_initial_nutrition_plan()
        state_after_plan = init["updated_user_state"]

        progress_client = InProcessProgressToolClient(workflow_id="wf_nutnodata", request_id="req_nutnodata")
        result = run_workflow(
            state_after_plan,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "periodic check"},
            nutrition_food_log_previous_period=[],
            nutrition_food_log_current_period=[],
            nutrition_period_previous={"start": "2026-01-01", "end": "2026-01-07"},
            nutrition_period_current={"start": "2026-01-08", "end": "2026-01-14"},
            **_clients("nutnodata"),
        )
        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        nutrition_progress = progress_result["findings"]["nutrition_progress"]
        self.assertEqual(nutrition_progress["status"], "NOT_ENOUGH_DATA")
        self.assertEqual(nutrition_progress["adaptation_recommendation"], "REASSESS")
        # The requested period predates the plan's own created_at, so this
        # is INSUFFICIENT_DATA (the plan was not yet in effect) — a
        # different reason than NOT_LOGGED, but the same honest refusal to
        # report a rate that cannot be computed.
        self.assertIn(
            nutrition_progress["current_adherence_status"],
            ("NOT_LOGGED", "INSUFFICIENT_DATA"),
        )

    def test_no_nutrition_plan_yet_produces_no_nutrition_progress_finding(self):
        """Progress runs (a physical trigger fired) but the caller supplied
        no nutrition context at all — nutrition_progress must be None, not
        a fabricated comparison."""

        state = _state(stability="HIGH")
        progress_client = InProcessProgressToolClient(workflow_id="wf_nonutr", request_id="req_nonutr")
        result = run_workflow(
            state,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "periodic check"},
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(40, RECENT_COMPLETED_AT),
            **_clients("nonutr"),
        )
        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertIsNone(progress_result["findings"]["nutrition_progress"])


class LowNeedDoesNotBlockProgressTriggeredReviewTests(unittest.TestCase):
    """Section 15: a current LOW physical need must not prevent a
    legitimate Progress-triggered specialist review, but the specialist
    retains sole authority over whether a plan actually results. This is
    an explicit, tested design decision (see docs/architecture.md), not
    an accident of the dispatch code.
    """

    def test_low_stability_need_still_gets_a_physio_review_on_a_progress_trigger_but_no_plan_results(self):
        # Stability need is LOW: Phase A does NOT select physio at all.
        state = _state(stability="LOW")

        progress_client = InProcessProgressToolClient(workflow_id="wf_lowneed", request_id="req_lowneed")
        result = run_workflow(
            state,
            progress_tool_client=progress_client,
            progress_trigger={"reason": "exercise activity recorded"},
            # A real, computed IMPROVED direction — never fabricated —
            # is what makes Progress recommend PROGRESS (-> physio) here.
            baseline_assessment=_balance_doc(40, "2026-01-01T00:00:00Z"),
            current_assessment=_balance_doc(60, RECENT_COMPLETED_AT),
            exercise_results=[],
            **_clients("lowneed"),
        )

        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["findings"]["overall_direction"], "IMPROVED")
        self.assertEqual(progress_result["findings"]["adaptation_recommendation"], "PROGRESS")

        # The specialist WAS reviewed: it appears in selected_agents and
        # produced a completed Agent Result this cycle, even though its
        # own need level never independently selected it.
        self.assertIn("physio", result["selected_agents"])
        physio_result = next(r for r in result["agent_results"] if r["agent"] == "physio")
        self.assertEqual(physio_result["status"], "completed")

        # But the specialist retains sole authority: its own need-gated
        # logic found no MEDIUM/HIGH physical need dimension, so it
        # produced no plan — and nothing was written to the User State.
        self.assertNotIn("plan", physio_result["findings"])
        self.assertNotIn("exercise_history", result["state_updates"])
        self.assertFalse(result["updated_user_state"].get("exercise_history", {}).get("available"))


if __name__ == "__main__":
    unittest.main()
