"""Proof that the six specialists actually differ.

Not "the prompt changed": every test here runs the real decision
pipeline and asserts on what each specialist *computed* -- which evidence
it read, what it concluded, and what it recommended. A test that only
checked that strings differ would pass just as happily on six copies of
the same agent, so none of these do that.

The three scenarios are representative personas with synthetic inputs.
They are not participants, and nothing here is a clinical finding.
"""

import unittest

from activity_agent.evidence import build_activity_view
from activity_agent.reasoning import assess_activity
from behaviour_agent.tool_client import InProcessBehaviourToolClient
from need_assessment.assessment import apply_need_profile, assemble_need_profile
from nutrition_agent.evidence import build_nutrition_evidence_view
from nutrition_agent.tool_client import InProcessNutritionToolClient
from orchestration.evidence import STATUS_INSUFFICIENT_EVIDENCE
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from recovery_agent.evidence import build_recovery_view
from recovery_agent.reasoning import assess_recovery
from safety.gate import evaluate_safety
from user_state.schema import build_user_state
from workflow.response import build_specialists_team

# --------------------------------------------------------------------------
# Scenario inputs. Every value is synthetic and chosen to represent the
# persona; none was recorded from a person.
# --------------------------------------------------------------------------

OFFICE_WORKER = {
    "age": 32,
    "sex": "female",
    "daily_sitting_hours": 9.5,
    "daily_screen_hours": 10,
    "daily_steps": 3200,
    "exercise_days": 1,
    "exercise_minutes": 20,
    "sleep_hours": 6,
    "sleep_quality": "fair",
    "work_type": "desk",
    "back_neck_pain": "yes",
}

MOBILITY_LIMITED = {
    "age": 41,
    "sex": "male",
    "daily_sitting_hours": 10,
    "daily_screen_hours": 6,
    "daily_steps": 900,
    "exercise_days": 2,
    "exercise_minutes": 30,
    "sleep_hours": 7.5,
    "sleep_quality": "good",
    "work_type": "desk",
    "joint_pain": "yes",
}

OLDER_ADULT = {
    "age": 72,
    "sex": "male",
    "daily_sitting_hours": 6,
    "daily_screen_hours": 3,
    "daily_steps": 4000,
    "exercise_days": 2,
    "exercise_minutes": 20,
    "sleep_hours": 7,
    "sleep_quality": "good",
    "work_type": "retired",
}


def _assessment(*, shoulder=None, ftsst=None, balance=None, completed_at="2026-09-01T09:00:00Z"):
    """A stored assessment session. A test that is not passed is recorded
    as skipped -- the state a user's own decision produces -- never as a
    zero measurement."""

    def test_block(measurements):
        if measurements is None:
            return {"status": "skipped", "measurements": None}

        return {"status": "completed", "measurements": measurements}

    return {
        "protocol_version": "1.0.0",
        "completed_at": completed_at,
        "tests": {
            "shoulder": test_block(
                None
                if shoulder is None
                else {
                    "left": {"finalElevationDeg": shoulder[0]},
                    "right": {"finalElevationDeg": shoulder[1]},
                    "observableDifferenceDeg": abs(shoulder[0] - shoulder[1]),
                }
            ),
            "ftsst": test_block(
                None
                if ftsst is None
                else {
                    "completionTimeSeconds": ftsst,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                }
            ),
            "balance": test_block(
                None
                if balance is None
                else {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": balance[0]},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": balance[1]},
                    "observableDifferenceMs": abs(balance[0] - balance[1]) * 1000,
                }
            ),
        },
    }


def _state(profile, assessment=None):
    state = build_user_state(profile_doc=profile, assessment_doc=assessment)

    return apply_need_profile(state, assemble_need_profile(state))


def _clients(tag="t"):
    return {
        "tool_client": InProcessExerciseToolClient(workflow_id=f"wf_{tag}", request_id=f"req_{tag}"),
        "behaviour_tool_client": InProcessBehaviourToolClient(
            workflow_id=f"wf_{tag}", request_id=f"req_{tag}"
        ),
        "nutrition_tool_client": InProcessNutritionToolClient(
            workflow_id=f"wf_{tag}", request_id=f"req_{tag}"
        ),
    }


def _findings(result, agent_id):
    for entry in result["agent_results"]:
        if entry["agent"] == agent_id:
            return entry["findings"]

    return None


class ScenarioAOfficeWorkerTests(unittest.TestCase):
    """32-year-old desk worker: long sitting, low activity, short sleep,
    inconsistent adherence, discomfort after sitting."""

    def setUp(self):
        self.state = _state(
            OFFICE_WORKER,
            _assessment(shoulder=(150, 146), ftsst=9.0, balance=(28, 26)),
        )
        self.result = run_workflow(
            self.state,
            exercise_results=[],
            behaviour_actions=[
                {"goal_id": "take_regular_movement_breaks", "status": "missed"},
                {"goal_id": "take_regular_movement_breaks", "status": "missed"},
                {"goal_id": "build_screen_time_boundaries", "status": "missed"},
            ],
            **_clients("a"),
        )

    def test_the_specialists_this_evidence_warrants_are_the_ones_that_run(self):
        selected = set(self.result["selected_agents"])

        self.assertIn("behaviour", selected)
        self.assertIn("exercise_activity", selected)
        self.assertIn("recovery", selected)
        # Nothing nutrition-related was ever collected, so Nutrition is not
        # selected -- an unanswered question is not a need.
        self.assertNotIn("nutrition", selected)

    def test_each_specialist_reasoned_from_its_own_domain_evidence(self):
        activity = _findings(self.result, "exercise_activity")
        recovery = _findings(self.result, "recovery")
        behaviour = _findings(self.result, "behaviour")

        activity_signals = {f["signal"] for f in activity["activity_findings"]}
        recovery_signals = {f["signal"] for f in recovery["recovery_findings"]}

        # Different domains, different evidence -- not the same profile
        # restated three times.
        self.assertTrue({"daily_steps", "daily_sitting_hours"} & activity_signals)
        self.assertTrue({"sleep_hours", "sleep_quality"} & recovery_signals)
        self.assertFalse(activity_signals & recovery_signals)
        self.assertEqual(behaviour["behaviour_adherence"]["status"], "NOT_ADHERED")

    def test_behaviour_addresses_adherence_rather_than_repeating_exercise_advice(self):
        behaviour = _findings(self.result, "behaviour")
        activity = _findings(self.result, "exercise_activity")

        barriers = {entry["barrier"] for entry in behaviour["barriers"]}
        self.assertIn("inconsistent_adherence", barriers)

        intervention_ids = {entry["id"] for entry in behaviour["behaviour_interventions"]}
        self.assertTrue({"shrink_first_action", "attach_habit_trigger"} & intervention_ids)

        # The behavioural answer to missed sessions is never "do more
        # exercise": no behaviour intervention may duplicate an activity
        # recommendation.
        activity_ids = {item["id"] for item in activity["activity_recommendations"]}
        self.assertFalse(intervention_ids & activity_ids)

    def test_recovery_constrains_the_activity_progression_it_does_not_own(self):
        recovery = _findings(self.result, "recovery")
        activity = _findings(self.result, "exercise_activity")

        self.assertTrue(recovery["constraint"]["limit_progression"])

        step_progression = [p for p in activity["progression"] if p["metric"] == "daily_steps"]
        self.assertEqual(step_progression[0]["rate"], "constrained")

        # The constraint is visible to the user, not just internal.
        self.assertTrue(
            any("Recovery & Care reported a constraint" in note for note in self.result["coordination_notes"])
        )

    def test_self_reported_discomfort_reaches_safety_and_nothing_else(self):
        # Safety is the only specialist that reads the health checklist,
        # and its response is a discussion note -- never a diagnosis.
        self.assertEqual(self.result["safety_result"]["status"], "MODIFY")
        self.assertEqual(self.result["safety_result"]["level"], "CAUTION")
        self.assertIn(
            "self_reported_health_context_present", self.result["safety_result"]["flags"]
        )

        activity_text = str(_findings(self.result, "exercise_activity"))
        self.assertNotIn("back_neck_pain", activity_text)
        self.assertNotIn("back pain", activity_text.lower())


class ScenarioBMobilityLimitedTests(unittest.TestCase):
    """41-year-old who uses a wheelchair for most daily mobility: the two
    standing checks are skipped, the arm check is completed."""

    def setUp(self):
        self.state = _state(
            MOBILITY_LIMITED,
            _assessment(shoulder=(118, 122), ftsst=None, balance=None),
        )
        self.result = run_workflow(self.state, exercise_results=[], **_clients("b"))

    def test_a_skipped_check_is_never_read_as_poor_performance(self):
        needs = self.state["current_needs"]["data"]

        self.assertEqual(needs["stability_need"]["level"], "NOT_ASSESSED")
        self.assertEqual(needs["functional_movement_need"]["level"], "NOT_ASSESSED")
        self.assertIsNone(needs["stability_need"]["score"])

        self.assertNotIn("physio", self.result["selected_agents"])

    def test_no_plan_is_offered_for_unmeasured_movement_domains(self):
        self.assertFalse(self.result["updated_user_state"]["exercise_history"]["available"])

    def test_nothing_in_the_run_claims_an_impairment(self):
        text = str(self.result["agent_results"]).lower()

        for word in ("impair", "disorder", "deficit", "abnormal", "disab"):
            self.assertNotIn(word, text)

    def test_activity_reasons_from_reported_volume_not_from_the_skipped_checks(self):
        activity = _findings(self.result, "exercise_activity")
        signals = {f["signal"] for f in activity["activity_findings"]}

        self.assertIn("daily_steps", signals)
        self.assertFalse({"ftsst", "balance", "shoulder"} & signals)


class ScenarioCOlderAdultTests(unittest.TestCase):
    """72-year-old living independently, wanting mobility and balance
    support. Age alone decides nothing."""

    def setUp(self):
        self.state = _state(
            OLDER_ADULT,
            _assessment(shoulder=(110, 100), ftsst=16.5, balance=(4.2, 6.0)),
        )
        self.result = run_workflow(self.state, exercise_results=[], **_clients("c"))

    def test_movement_evidence_selects_physio_and_drives_its_plan(self):
        self.assertIn("physio", self.result["selected_agents"])

        physio = _findings(self.result, "physio")
        self.assertEqual(physio["need_levels"]["stability_need"], "HIGH")
        self.assertEqual(physio["need_levels"]["functional_movement_need"], "HIGH")
        self.assertTrue(physio["plan"]["exercises"])
        self.assertEqual(
            {entry["movement"] for entry in physio["assessed_movements"]},
            {"shoulder", "ftsst", "balance"},
        )

    def test_age_alone_changes_nothing(self):
        younger = _state(
            {**OLDER_ADULT, "age": 34},
            _assessment(shoulder=(110, 100), ftsst=16.5, balance=(4.2, 6.0)),
        )
        younger_result = run_workflow(younger, exercise_results=[], **_clients("c2"))

        def plan_ids(result):
            physio = _findings(result, "physio")

            return [entry["exercise_id"] for entry in physio["plan"]["exercises"]]

        self.assertEqual(plan_ids(self.result), plan_ids(younger_result))

    def test_good_sleep_produces_no_recovery_constraint(self):
        recovery = _findings(self.result, "recovery")

        if recovery is not None:
            self.assertFalse(recovery["constraint"]["limit_progression"])
        else:
            self.assertNotIn("recovery", self.result["selected_agents"])


class SpecialistsAreDifferentTests(unittest.TestCase):
    """The ten differentiation checks, each against computed output."""

    def test_1_one_profile_produces_different_reasoning_per_domain(self):
        state = _state(OFFICE_WORKER, _assessment(shoulder=(150, 146), ftsst=9.0, balance=(28, 26)))
        result = run_workflow(state, exercise_results=[], **_clients("d1"))

        shapes = {
            entry["agent"]: set(entry["findings"].keys()) for entry in result["agent_results"]
        }

        # Each specialist reports in its own vocabulary; no two agents
        # return the same finding shape.
        self.assertIn("activity_recommendations", shapes["exercise_activity"])
        self.assertIn("recovery_findings", shapes["recovery"])
        self.assertIn("barriers", shapes["behaviour"])
        self.assertNotEqual(shapes["exercise_activity"], shapes["recovery"])
        self.assertNotEqual(shapes["recovery"], shapes["behaviour"])

    def test_2_different_users_activate_different_specialists(self):
        office = run_workflow(
            _state(OFFICE_WORKER, _assessment(shoulder=(150, 146), ftsst=9.0, balance=(28, 26))),
            exercise_results=[],
            **_clients("d2a"),
        )
        older = run_workflow(
            _state(OLDER_ADULT, _assessment(shoulder=(110, 100), ftsst=16.5, balance=(4.2, 6.0))),
            exercise_results=[],
            **_clients("d2b"),
        )

        self.assertNotEqual(set(office["selected_agents"]), set(older["selected_agents"]))
        self.assertIn("recovery", office["selected_agents"])
        self.assertIn("physio", older["selected_agents"])
        self.assertNotIn("physio", office["selected_agents"])

    def test_3_missing_nutrition_evidence_is_reported_not_papered_over(self):
        view = build_nutrition_evidence_view(build_user_state(profile_doc=OFFICE_WORKER))

        self.assertEqual(view["status"], STATUS_INSUFFICIENT_EVIDENCE)
        self.assertIn("Meal pattern", view["missing_information"])

        card = next(
            c
            for c in build_specialists_team(
                _state(OFFICE_WORKER), safety_result={"status": "ALLOW"}
            )
            if c["id"] == "nutrition_lifestyle"
        )

        self.assertEqual(card["evidence_status"], STATUS_INSUFFICIENT_EVIDENCE)
        self.assertEqual(card["recommendations"], [])

        text = str(card).lower()
        for generic in ("eat healthy", "eat more vegetables", "drink more water"):
            self.assertNotIn(generic, text)

    def test_4_not_assessed_movement_never_becomes_an_impairment(self):
        result = run_workflow(
            _state(MOBILITY_LIMITED, _assessment(shoulder=(118, 122))),
            exercise_results=[],
            **_clients("d4"),
        )
        self.assertNotIn("physio", result["selected_agents"])
        needs = _state(MOBILITY_LIMITED, _assessment(shoulder=(118, 122)))["current_needs"]["data"]
        self.assertEqual(needs["stability_need"]["level"], "NOT_ASSESSED")

    def test_5_behaviour_tracks_adherence_evidence(self):
        state = _state(OFFICE_WORKER)

        missed = run_workflow(
            state,
            # Three recorded actions: behaviour_agent/adherence.py refuses
            # to call anything adherence from fewer, which is the point --
            # two missed days is not yet a pattern.
            behaviour_actions=[
                {"goal_id": "take_regular_movement_breaks", "status": "missed"},
                {"goal_id": "take_regular_movement_breaks", "status": "missed"},
                {"goal_id": "take_regular_movement_breaks", "status": "missed"},
            ],
            **_clients("d5a"),
        )
        done = run_workflow(
            state,
            behaviour_actions=[
                {"goal_id": "take_regular_movement_breaks", "status": "completed"},
                {"goal_id": "take_regular_movement_breaks", "status": "completed"},
                {"goal_id": "take_regular_movement_breaks", "status": "completed"},
            ],
            **_clients("d5b"),
        )

        missed_barriers = {b["barrier"] for b in _findings(missed, "behaviour")["barriers"]}
        done_barriers = {b["barrier"] for b in _findings(done, "behaviour")["barriers"]}

        self.assertIn("inconsistent_adherence", missed_barriers)
        self.assertNotIn("inconsistent_adherence", done_barriers)

    def test_6_recovery_tracks_sleep_evidence(self):
        short_sleep = assess_recovery(
            build_recovery_view(build_user_state(profile_doc={"sleep_hours": 5, "sleep_quality": "poor"}))
        )
        slept_well = assess_recovery(
            build_recovery_view(build_user_state(profile_doc={"sleep_hours": 8, "sleep_quality": "good"}))
        )
        unknown = assess_recovery(build_recovery_view(build_user_state(profile_doc={"daily_steps": 3000})))

        self.assertEqual(short_sleep["recovery_status"], "CONSTRAINED")
        self.assertEqual(slept_well["recovery_status"], "SUPPORTIVE")
        self.assertEqual(unknown["status"], STATUS_INSUFFICIENT_EVIDENCE)
        self.assertIn("Sleep duration", unknown["missing_information"])

    def test_7_safety_responds_to_evidence_and_constrains_other_specialists(self):
        candidates = [
            {"id": "wall-sit", "agent": "physio", "type": "exercise", "difficulty": "intermediate"},
            {"id": "increase_daily_steps", "agent": "exercise_activity", "type": "activity_guidance", "difficulty": None},
        ]

        quiet = evaluate_safety(candidate_recommendations=candidates)
        self.assertEqual(quiet["status"], "ALLOW")
        self.assertEqual(quiet["level"], "SAFE")

        reported = evaluate_safety(
            candidate_recommendations=candidates,
            self_reported_health={"values": {"heart_condition": "yes"}},
        )
        self.assertEqual(reported["status"], "MODIFY")
        self.assertEqual(set(reported["modified_recommendation_ids"]), {"wall-sit", "increase_daily_steps"})

        paused = evaluate_safety(
            candidate_recommendations=candidates,
            confirmed_medical_context={"reports": [{"report_id": "r1"}]},
        )
        self.assertEqual(paused["status"], "PAUSE")
        self.assertIn("wall-sit", paused["blocked_recommendation_ids"])

        # Nothing was invented: with no evidence at all the gate says what
        # it is missing rather than clearing the user.
        self.assertTrue(quiet["missing_safety_information"])

    def test_8_activity_tracks_activity_evidence(self):
        low = assess_activity(build_activity_view(build_user_state(profile_doc={"daily_steps": 2000})))
        high = assess_activity(build_activity_view(build_user_state(profile_doc={"daily_steps": 9000})))

        low_target = next(
            item["target"]["to"]
            for item in low["activity_recommendations"]
            if item["id"] == "increase_daily_steps"
        )
        self.assertEqual(low_target, 2500)
        self.assertEqual(
            [item["id"] for item in high["activity_recommendations"]], ["maintain_daily_steps"]
        )

    def test_9_physio_tracks_movement_evidence(self):
        limited = run_workflow(
            _state(OLDER_ADULT, _assessment(shoulder=(55, 58), ftsst=9.0, balance=(20, 22))),
            exercise_results=[],
            **_clients("d9a"),
        )
        unlimited = run_workflow(
            _state(OLDER_ADULT, _assessment(shoulder=(150, 148), ftsst=16.5, balance=(4.0, 4.5))),
            exercise_results=[],
            **_clients("d9b"),
        )

        self.assertEqual(_findings(limited, "physio")["need_levels"]["mobility_need"], "HIGH")
        self.assertEqual(_findings(unlimited, "physio")["need_levels"]["stability_need"], "HIGH")

        self.assertNotEqual(
            [e["exercise_id"] for e in _findings(limited, "physio")["plan"]["exercises"]],
            [e["exercise_id"] for e in _findings(unlimited, "physio")["plan"]["exercises"]],
        )

    def test_10_the_final_plan_is_built_from_the_specialised_outputs(self):
        result = run_workflow(
            _state(OFFICE_WORKER, _assessment(shoulder=(150, 146), ftsst=12.0, balance=(28, 26))),
            exercise_results=[],
            **_clients("d10"),
        )

        by_agent = {}
        for entry in result["final_recommendations"]:
            by_agent.setdefault(entry["agent"], set()).add(entry["id"])

        # Every specialist that ran contributed to what the user is shown,
        # and each contribution is its own domain's output.
        self.assertIn("physio", by_agent)
        self.assertIn("behaviour", by_agent)
        self.assertIn("exercise_activity", by_agent)

        activity_ids = {
            item["id"] for item in _findings(result, "exercise_activity")["activity_recommendations"]
        }
        self.assertEqual(by_agent["exercise_activity"], activity_ids)

        physio_plan_ids = {
            entry["exercise_id"] for entry in _findings(result, "physio")["plan"]["exercises"]
        }
        self.assertTrue(by_agent["physio"].issubset(physio_plan_ids))


class DomainInputIsolationTests(unittest.TestCase):
    """The filtering is in code, not in a comment: each domain view can be
    inspected for what it does and does not contain."""

    def setUp(self):
        self.state = _state(
            OFFICE_WORKER, _assessment(shoulder=(150, 146), ftsst=9.0, balance=(28, 26))
        )

    def test_activity_view_excludes_medical_sleep_and_raw_movement_data(self):
        view = build_activity_view(self.state)
        text = str(view)

        self.assertNotIn("sleep", text.lower())
        self.assertNotIn("back_neck_pain", text)
        self.assertNotIn("finalElevationDeg", text)
        self.assertIn("daily_steps", view["signals"])

    def test_recovery_view_excludes_activity_targets_and_medical_context(self):
        view = build_recovery_view(self.state)

        self.assertIn("sleep_hours", view["signals"])
        self.assertNotIn("daily_steps", view["signals"])
        self.assertNotIn("back_neck_pain", str(view))

    def test_every_view_records_missing_evidence_as_missing(self):
        empty = build_user_state()

        activity = build_activity_view(empty)
        recovery = build_recovery_view(empty)

        self.assertTrue(
            all(entry["state"] == "MISSING" for entry in activity["signals"].values())
        )
        self.assertTrue(
            all(entry["state"] == "MISSING" for entry in recovery["signals"].values())
        )


if __name__ == "__main__":
    unittest.main()
