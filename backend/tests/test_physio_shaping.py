"""The Physiotherapy & Movement agent's personalisation, under test.

The agent chooses WHICH capabilities to work on from measured need
levels (unchanged, Phase 3). What these tests cover is the shaping added
on top of that: severity deciding order and slot share, the user's own
activity answers deciding plan size, and the guarantees that must hold
however a plan is shaped — every id real, nothing invented from absent
evidence, the Safety Gate still final, and the same evidence always
producing the same plan.

Every input here is built through the project's real schemas
(user_state.build_user_state + the Need Assessment), so a test fixture
cannot assert behaviour the production path would never see.
"""

import unittest

from behaviour_agent.tool_client import InProcessBehaviourToolClient
from exercise_library.catalog import list_exercise_ids
from need_assessment.assessment import apply_need_profile, assemble_need_profile
from nutrition_agent.tool_client import InProcessNutritionToolClient
from orchestrator.orchestrator import run_workflow
from physio_agent.shaping import (
    REDUCED_MAX_EXERCISES,
    SLOTS_FOR_HIGH,
    SLOTS_FOR_MEDIUM,
    activity_context,
    plan_shape,
)
from physio_agent.tool_client import InProcessExerciseToolClient
from safety.gate import evaluate_safety
from user_state.schema import build_user_state

LIBRARY_IDS = set(list_exercise_ids())

# --------------------------------------------------------------------------
# Fixtures, in the shapes the application really stores.
# --------------------------------------------------------------------------

ACTIVE_PROFILE = {
    "age": 54,
    "sex": "female",
    "daily_sitting_hours": 4,
    "daily_screen_hours": 3,
    "daily_steps": 9000,
    "exercise_days": 4,
    "exercise_minutes": 40,
    "sleep_hours": 8,
    "sleep_quality": "good",
    "work_type": "active",
}

SEDENTARY_PROFILE = {
    "age": 33,
    "sex": "male",
    "daily_sitting_hours": 10,
    "daily_screen_hours": 9,
    "daily_steps": 2800,
    "exercise_days": 1,
    "exercise_minutes": 15,
    "sleep_hours": 7,
    "sleep_quality": "good",
    "work_type": "desk",
}


def _assessment(*, shoulder=None, ftsst=None, balance=None, skipped=()):
    """One stored assessment session. A test named in `skipped` is stored
    as skipped with null measurements -- the state a user's own choice
    produces -- and never as a zero."""

    def block(test_id, measurements):
        if test_id in skipped:
            return {"status": "skipped", "measurements": None}

        if measurements is None:
            return {"status": "not_started", "measurements": None}

        return {"status": "completed", "measurements": measurements}

    return {
        "protocol_version": "1.0.0",
        "completed_at": "2026-10-02T09:00:00Z",
        "tests": {
            "shoulder": block(
                "shoulder",
                None
                if shoulder is None
                else {
                    "left": {"finalElevationDeg": shoulder[0]},
                    "right": {"finalElevationDeg": shoulder[1]},
                    "observableDifferenceDeg": abs(shoulder[0] - shoulder[1]),
                },
            ),
            "ftsst": block(
                "ftsst",
                None
                if ftsst is None
                else {
                    "completionTimeSeconds": ftsst,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                },
            ),
            "balance": block(
                "balance",
                None
                if balance is None
                else {
                    "left": {"attempted": True, "valid": True, "holdDurationSeconds": balance[0]},
                    "right": {"attempted": True, "valid": True, "holdDurationSeconds": balance[1]},
                    "observableDifferenceMs": abs(balance[0] - balance[1]) * 1000,
                },
            ),
        },
    }


def _state(profile, assessment=None):
    state = build_user_state(profile_doc=profile, assessment_doc=assessment)

    return apply_need_profile(state, assemble_need_profile(state))


def _clients(tag):
    return {
        "tool_client": InProcessExerciseToolClient(workflow_id=f"wf_{tag}", request_id=f"req_{tag}"),
        "behaviour_tool_client": InProcessBehaviourToolClient(
            workflow_id=f"wf_{tag}", request_id=f"req_{tag}"
        ),
        "nutrition_tool_client": InProcessNutritionToolClient(
            workflow_id=f"wf_{tag}", request_id=f"req_{tag}"
        ),
    }


def _physio(result):
    for entry in result["agent_results"]:
        if entry["agent"] == "physio":
            return entry["findings"]

    return None


def _plan_ids(findings):
    if not findings or not findings.get("plan"):
        return []

    return [entry["exercise_id"] for entry in findings["plan"]["exercises"]]


def _run(profile, assessment, tag, **kwargs):
    return run_workflow(_state(profile, assessment), **_clients(tag), **kwargs)


# --------------------------------------------------------------------------


class LowActivityShapingTests(unittest.TestCase):
    """TEST 1 -- a low starting point makes the plan smaller, not easier
    to dismiss. The need itself is untouched."""

    def setUp(self):
        self.result = _run(
            SEDENTARY_PROFILE,
            _assessment(shoulder=(150, 146), ftsst=13.0, balance=(28, 26)),
            "low_activity",
            exercise_results=[],
        )
        self.findings = _physio(self.result)

    def test_the_users_own_answers_mark_this_as_a_low_starting_point(self):
        shaping = self.findings["plan_shaping"]

        self.assertTrue(shaping["low_activity"])
        self.assertEqual(shaping["max_exercises"], REDUCED_MAX_EXERCISES)
        # The evidence is the user's own reported numbers, quoted back.
        self.assertTrue(shaping["activity_evidence"])
        self.assertTrue(
            any("sitting" in line or "exercise frequency" in line for line in shaping["activity_evidence"])
        )

    def test_the_plan_is_capped_at_the_reduced_size(self):
        self.assertLessEqual(len(_plan_ids(self.findings)), REDUCED_MAX_EXERCISES)
        self.assertTrue(_plan_ids(self.findings), "a medium need should still produce a plan")

    def test_the_same_findings_produce_a_smaller_plan_for_a_sedentary_user(self):
        # Held against the constants: identical measured evidence, only
        # the activity answers differ, and the plan is strictly shorter.
        assessment = _assessment(shoulder=(110, 100), ftsst=16.5, balance=(4.2, 6.0))

        sedentary = _physio(_run(SEDENTARY_PROFILE, assessment, "size_sed", exercise_results=[]))
        active = _physio(_run(ACTIVE_PROFILE, assessment, "size_act", exercise_results=[]))

        self.assertEqual(sedentary["need_levels"], active["need_levels"])
        self.assertLess(len(_plan_ids(sedentary)), len(_plan_ids(active)))
        # The shorter plan is a prefix of the longer one: the same
        # priorities, fewer of them -- not a different, easier programme.
        self.assertEqual(
            _plan_ids(sedentary), _plan_ids(active)[: len(_plan_ids(sedentary))]
        )

    def test_every_recommended_exercise_is_a_real_library_exercise(self):
        for exercise_id in _plan_ids(self.findings):
            self.assertIn(exercise_id, LIBRARY_IDS)

    def test_each_rationale_quotes_the_measurement_behind_it(self):
        for entry in self.findings["plan"]["exercises"]:
            self.assertIn("Selected because", entry["rationale"])
            # The Need Assessment's own evidence sentence is carried into
            # the reason, so the plan can be explained from the data.
            self.assertIn("seconds", entry["rationale"])


class SeverityChangesTheShapeTests(unittest.TestCase):
    """TEST 2 -- HIGH and MEDIUM are no longer interchangeable."""

    def test_a_high_need_is_allocated_more_of_the_plan_than_a_medium_one(self):
        high = plan_shape(
            {"stability": [{"dimension": "stability_need", "level": "HIGH", "evidence": []}]},
            {"low_activity": False, "evidence": []},
        )
        medium = plan_shape(
            {"stability": [{"dimension": "stability_need", "level": "MEDIUM", "evidence": []}]},
            {"low_activity": False, "evidence": []},
        )

        self.assertEqual(high["slots"]["stability"], SLOTS_FOR_HIGH)
        self.assertEqual(medium["slots"]["stability"], SLOTS_FOR_MEDIUM)
        self.assertGreater(high["slots"]["stability"], medium["slots"]["stability"])

    def test_the_strongest_evidence_is_filled_first(self):
        shape = plan_shape(
            {
                "mobility": [{"dimension": "mobility_need", "level": "MEDIUM", "evidence": []}],
                "stability": [{"dimension": "stability_need", "level": "HIGH", "evidence": []}],
            },
            {"low_activity": False, "evidence": []},
        )

        self.assertEqual(shape["ordered_capabilities"][0], "stability")

    def test_the_same_levels_through_the_real_pipeline_differ_in_plan(self):
        high = _run(ACTIVE_PROFILE, _assessment(shoulder=(150, 148), ftsst=8.0, balance=(3.0, 3.5)), "sev_high")
        medium = _run(ACTIVE_PROFILE, _assessment(shoulder=(150, 148), ftsst=8.0, balance=(9.0, 9.5)), "sev_med")

        self.assertEqual(_physio(high)["need_levels"]["stability_need"], "HIGH")
        self.assertEqual(_physio(medium)["need_levels"]["stability_need"], "MEDIUM")

        self.assertEqual(
            _physio(high)["plan_shaping"]["slots"]["stability"], SLOTS_FOR_HIGH
        )
        self.assertEqual(
            _physio(medium)["plan_shaping"]["slots"]["stability"], SLOTS_FOR_MEDIUM
        )


class HighStabilityAndFunctionalTests(unittest.TestCase):
    """TEST 3 -- the capability the evidence shouts about leads."""

    def setUp(self):
        self.result = _run(
            ACTIVE_PROFILE,
            _assessment(shoulder=(150, 148), ftsst=16.5, balance=(4.2, 6.0)),
            "high_two",
            exercise_results=[],
        )
        self.findings = _physio(self.result)

    def test_both_needs_are_high_and_both_are_targeted(self):
        self.assertEqual(self.findings["need_levels"]["stability_need"], "HIGH")
        self.assertEqual(self.findings["need_levels"]["functional_movement_need"], "HIGH")
        self.assertIn("stability", self.findings["capabilities_targeted"])

    def test_the_plan_fits_the_full_size_for_an_active_user(self):
        shaping = self.findings["plan_shaping"]

        self.assertFalse(shaping["low_activity"])
        self.assertGreater(len(_plan_ids(self.findings)), REDUCED_MAX_EXERCISES)

    def test_no_exercise_exceeds_the_difficulty_ceiling(self):
        for entry in self.findings["plan"]["exercises"]:
            self.assertIn(entry["difficulty"], ("beginner", "intermediate"))

    def test_the_safety_gate_ran_over_this_plan(self):
        self.assertIsNotNone(self.result["safety_result"])


class ShoulderOnlyTests(unittest.TestCase):
    """TEST 4 -- a shoulder finding produces shoulder work, not a
    general-purpose corrective programme."""

    def setUp(self):
        self.findings = _physio(
            _run(
                ACTIVE_PROFILE,
                _assessment(shoulder=(55, 58), ftsst=8.0, balance=(25, 27)),
                "shoulder_only",
                exercise_results=[],
            )
        )

    def test_only_the_mobility_capability_is_targeted(self):
        self.assertEqual(self.findings["capabilities_targeted"], ["mobility"])
        self.assertEqual(self.findings["need_levels"]["mobility_need"], "HIGH")
        self.assertEqual(self.findings["need_levels"]["stability_need"], "LOW")
        self.assertEqual(self.findings["need_levels"]["functional_movement_need"], "LOW")

    def test_every_selected_exercise_claims_the_mobility_capability(self):
        from exercise_library.catalog import get_exercise_details

        for exercise_id in _plan_ids(self.findings):
            exercise = get_exercise_details(exercise_id)
            self.assertIn(
                "mobility",
                exercise["target_capability"],
                f"{exercise_id} was selected for a mobility need but does not train mobility",
            )

    def test_the_plan_is_attributed_to_the_shoulder_measurement(self):
        for entry in self.findings["plan"]["exercises"]:
            self.assertIn("upper-body mobility", entry["rationale"])


class BalanceSelectionTests(unittest.TestCase):
    """Balance evidence must prefer balance interventions over generic leg work."""

    def test_balance_need_prioritises_balance_training_exercises(self):
        findings = _physio(
            _run(
                ACTIVE_PROFILE,
                _assessment(shoulder=(150, 148), ftsst=8.0, balance=(3.5, 4.0)),
                "balance_specific",
                exercise_results=[],
            )
        )

        self.assertEqual(findings["capabilities_targeted"], ["stability"])
        self.assertTrue(findings["plan"]["exercises"])

        for entry in findings["plan"]["exercises"]:
            self.assertIn(entry["exercise_id"], {
                "heel-to-toe-stand",
                "supported-single-leg-stand",
                "quadruped-bird-dog",
                "single-leg-reach-balance",
            })


class NormalAssessmentTests(unittest.TestCase):
    """TEST 5 -- nothing measured as a deficit means no plan. The agent
    does not manufacture a reason to prescribe."""

    def setUp(self):
        self.result = _run(
            ACTIVE_PROFILE,
            _assessment(shoulder=(150, 148), ftsst=8.0, balance=(25, 27)),
            "normal",
            exercise_results=[],
        )

    def test_physio_is_not_selected_at_all(self):
        self.assertNotIn("physio", self.result["selected_agents"])
        self.assertIsNone(_physio(self.result))

    def test_the_decision_names_the_measured_levels(self):
        decision = self.result["orchestrator_decision"]["physio"]

        self.assertFalse(decision["physio_required"])
        self.assertEqual(
            set(decision["evaluated_dimensions"].values()),
            {"LOW"},
        )

    def test_no_exercise_history_is_written(self):
        self.assertNotIn("exercise_history", self.result["state_updates"])


class RawAssessmentEvidenceReachesPhysioTests(unittest.TestCase):
    def test_agent_findings_retain_the_exact_domain_parameters(self):
        assessment = _assessment(
            shoulder=(55, 58),
            ftsst=13.84,
            balance=(5.97, 3.5),
        )
        findings = _physio(_run(ACTIVE_PROFILE, assessment, "raw_trace", exercise_results=[]))

        movement = findings["movement_evidence"]
        self.assertEqual(movement["shoulder"]["left_elevation_deg"], 55)
        self.assertEqual(movement["shoulder"]["right_elevation_deg"], 58)
        self.assertEqual(movement["shoulder"]["side_difference_deg"], 3)
        self.assertEqual(movement["sit_to_stand"]["time_seconds"], 13.84)
        self.assertEqual(movement["balance"]["left_hold_seconds"], 5.97)
        self.assertEqual(movement["balance"]["right_hold_seconds"], 3.5)

        self.assertTrue(
            any("left_elevation_deg=55" in entry["rationale"] for entry in findings["plan"]["exercises"])
        )


class NotAssessedIsNotAnImpairmentTests(unittest.TestCase):
    """TEST 6 and 7 -- an unmeasured check is an absence of evidence."""

    def setUp(self):
        # Two checks skipped by the user; the arm check completed well.
        self.result = _run(
            SEDENTARY_PROFILE,
            _assessment(shoulder=(130, 126), skipped=("ftsst", "balance")),
            "skipped_two",
            exercise_results=[],
        )
        self.findings = _physio(self.result)
        self.needs = _state(
            SEDENTARY_PROFILE, _assessment(shoulder=(130, 126), skipped=("ftsst", "balance"))
        )["current_needs"]["data"]

    def test_a_skipped_check_never_becomes_a_medium_or_high_need(self):
        for dimension in ("stability_need", "functional_movement_need"):
            self.assertEqual(self.needs[dimension]["level"], "NOT_ASSESSED")
            self.assertIsNone(self.needs[dimension]["score"])
            self.assertEqual(self.needs[dimension]["confidence"], "NONE")

    def test_the_evidence_says_it_could_not_be_measured_not_that_it_was_poor(self):
        for dimension in ("stability_need", "functional_movement_need"):
            evidence = " ".join(self.needs[dimension]["evidence"]).lower()

            self.assertIn("has not produced a usable result", evidence)
            for word in ("poor", "impair", "deficit", "reduced"):
                self.assertNotIn(word, evidence)

    def test_missing_movement_evidence_does_not_activate_physio(self):
        self.assertIsNone(self.findings)

    def test_nothing_in_the_run_asserts_poor_balance_or_mobility(self):
        text = str(self.result["agent_results"]).lower()

        for claim in ("poor balance", "poor mobility", "impair", "deficit"):
            self.assertNotIn(claim, text)

    def test_missing_movement_evidence_does_not_run_shaping(self):
        self.assertIsNone(self.findings)


class SafetyGateRemainsAuthoritativeTests(unittest.TestCase):
    """TEST 8 -- physio cannot put a blocked exercise in front of a user."""

    def _state_with_report(self):
        state = build_user_state(
            profile_doc=ACTIVE_PROFILE,
            assessment_doc=_assessment(shoulder=(150, 148), ftsst=16.5, balance=(4.2, 6.0)),
            confirmed_reports_doc={"reports": [{"report_id": "r1", "values": []}]},
        )

        return apply_need_profile(state, assemble_need_profile(state))

    def setUp(self):
        self.result = run_workflow(
            self._state_with_report(), exercise_results=[], **_clients("safety")
        )

    def test_the_gate_paused_the_exercise_above_the_reduced_ceiling(self):
        safety = self.result["safety_result"]

        self.assertEqual(safety["status"], "PAUSE")
        self.assertTrue(safety["blocked_recommendation_ids"])

    def test_a_blocked_exercise_never_reaches_the_final_recommendations(self):
        blocked = set(self.result["safety_result"]["blocked_recommendation_ids"])
        final = {entry["id"] for entry in self.result["final_recommendations"]}

        self.assertTrue(blocked)
        self.assertFalse(blocked & final)

    def test_the_rest_of_the_plan_survives(self):
        physio_final = [
            entry for entry in self.result["final_recommendations"] if entry["agent"] == "physio"
        ]

        self.assertTrue(physio_final, "a pause on one exercise must not empty the plan")

    def test_the_agent_still_proposed_it_so_the_audit_trail_is_intact(self):
        blocked = set(self.result["safety_result"]["blocked_recommendation_ids"])

        self.assertTrue(blocked & set(_plan_ids(_physio(self.result))))

    def test_the_gate_is_not_reimplemented_inside_the_agent(self):
        decision = evaluate_safety(
            candidate_recommendations=[
                {"id": "wall-sit", "agent": "physio", "type": "exercise", "difficulty": "intermediate"}
            ],
            confirmed_medical_context={"reports": [{"report_id": "r1"}]},
        )

        self.assertEqual(decision["status"], "PAUSE")
        self.assertIn("wall-sit", decision["blocked_recommendation_ids"])


class DeterminismTests(unittest.TestCase):
    """TEST 9 -- the same evidence always produces the same plan."""

    def test_two_identical_runs_produce_an_identical_plan(self):
        assessment = _assessment(shoulder=(150, 148), ftsst=16.5, balance=(4.2, 6.0))

        first = _physio(_run(ACTIVE_PROFILE, assessment, "det_a", exercise_results=[]))
        second = _physio(_run(ACTIVE_PROFILE, assessment, "det_b", exercise_results=[]))

        self.assertEqual(_plan_ids(first), _plan_ids(second))
        self.assertEqual(first["plan_shaping"], second["plan_shaping"])
        self.assertEqual(first["capabilities_targeted"], second["capabilities_targeted"])

    def test_the_shaping_function_itself_is_pure(self):
        triggers = {
            "stability": [{"dimension": "stability_need", "level": "HIGH", "evidence": ["x"]}],
            "mobility": [{"dimension": "mobility_need", "level": "MEDIUM", "evidence": ["y"]}],
        }
        context = activity_context({"daily_sitting_hours": 10, "exercise_days": 1})

        self.assertEqual(plan_shape(triggers, context), plan_shape(triggers, context))


class DifferentEvidenceDifferentPlanTests(unittest.TestCase):
    """TEST 10 -- two users, two different plans, each explainable."""

    def setUp(self):
        # A: sedentary, slow sit-to-stand (functional movement).
        self.a = _physio(
            _run(
                SEDENTARY_PROFILE,
                _assessment(shoulder=(150, 148), ftsst=13.0, balance=(25, 27)),
                "diff_a",
                exercise_results=[],
            )
        )
        # B: active, short one-leg hold (balance).
        self.b = _physio(
            _run(
                ACTIVE_PROFILE,
                _assessment(shoulder=(150, 148), ftsst=8.0, balance=(3.5, 4.0)),
                "diff_b",
                exercise_results=[],
            )
        )

    def test_the_two_plans_are_not_the_same(self):
        self.assertNotEqual(_plan_ids(self.a), _plan_ids(self.b))

    def test_each_plan_follows_its_own_evidence(self):
        self.assertEqual(self.a["capabilities_targeted"], ["functional_movement", "strength"])
        self.assertEqual(self.b["capabilities_targeted"], ["stability"])

    def test_the_sedentary_user_gets_the_smaller_plan(self):
        self.assertTrue(self.a["plan_shaping"]["low_activity"])
        self.assertFalse(self.b["plan_shaping"]["low_activity"])
        self.assertLessEqual(len(_plan_ids(self.a)), REDUCED_MAX_EXERCISES)


class EveryRecommendationIsRealTests(unittest.TestCase):
    """TEST 11 (backend half) -- no plan may name an exercise that does
    not exist. The image mapping is tested on the frontend side."""

    def test_no_scenario_produces_an_unknown_exercise_id(self):
        scenarios = [
            (SEDENTARY_PROFILE, _assessment(shoulder=(150, 146), ftsst=13.0, balance=(28, 26))),
            (ACTIVE_PROFILE, _assessment(shoulder=(110, 100), ftsst=16.5, balance=(4.2, 6.0))),
            (ACTIVE_PROFILE, _assessment(shoulder=(55, 58), ftsst=8.0, balance=(25, 27))),
            (SEDENTARY_PROFILE, _assessment(shoulder=(130, 126), skipped=("ftsst", "balance"))),
        ]

        for index, (profile, assessment) in enumerate(scenarios):
            findings = _physio(_run(profile, assessment, f"real_{index}", exercise_results=[]))

            if findings is None:
                continue

            for exercise_id in _plan_ids(findings):
                self.assertIn(exercise_id, LIBRARY_IDS, f"scenario {index} invented {exercise_id}")


if __name__ == "__main__":
    unittest.main()
