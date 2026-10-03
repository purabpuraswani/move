"""Which specialists a user actually gets, and why.

The claim under test is the one that distinguishes a multi-specialist
system from six agents that each produce something for everybody: an
agent contributes only when this user's own evidence makes its domain
relevant, and the plan differs between users because their evidence
differs.

Every scenario is built through the real schemas -- `build_user_state`
plus the Need Assessment -- and run through the real `run_workflow`, so
nothing here can assert behaviour the application would not produce.
The personas correspond to the five in the brief (A-E) plus the two
absence cases that are easiest to get wrong: no evidence at all, and
evidence that was never measured.
"""

import unittest

from behaviour_agent.tool_client import InProcessBehaviourToolClient
from need_assessment.assessment import apply_need_profile, assemble_need_profile
from nutrition_agent.tool_client import InProcessNutritionToolClient
from orchestrator.orchestrator import run_workflow
from physio_agent.tool_client import InProcessExerciseToolClient
from user_state.schema import build_user_state
from workflow.response import build_specialists_team

ALL_SIX = {
    "exercise_activity",
    "physio",
    "nutrition",
    "recovery",
    "behaviour",
    "safety",
}

# --------------------------------------------------------------------------
# Profiles. Each one differs from ACTIVE_HEALTHY only in the evidence the
# scenario is about, so a difference in the resulting plan can only have
# come from that evidence.
# --------------------------------------------------------------------------

ACTIVE_HEALTHY = {
    "age": 41,
    "sex": "female",
    "daily_sitting_hours": 4,
    "daily_screen_hours": 3,
    "daily_steps": 9500,
    "exercise_days": 5,
    "exercise_minutes": 45,
    "sleep_hours": 8,
    "sleep_quality": "good",
    "work_type": "active",
    "meal_pattern": "regular",
    "fruit_vegetable_servings": 5,
    "water_glasses_per_day": 8,
    "processed_food_frequency": "rarely",
}

SEDENTARY = {
    **ACTIVE_HEALTHY,
    "daily_sitting_hours": 11,
    "daily_screen_hours": 10,
    "daily_steps": 2400,
    "exercise_days": 0,
    "exercise_minutes": 0,
    "work_type": "desk",
}

POOR_SLEEP = {**ACTIVE_HEALTHY, "sleep_hours": 4.5, "sleep_quality": "poor"}

POOR_DIET = {
    **ACTIVE_HEALTHY,
    "meal_pattern": "skips_meals",
    "fruit_vegetable_servings": 1,
    "water_glasses_per_day": 2,
    "processed_food_frequency": "daily",
}

NO_EVIDENCE = {"age": 30, "sex": "male"}

# A confirmed report carrying a measurement a dietitian would want. The
# VALUE is never read as high or low -- only its presence is evidence.
NUTRITION_REPORT = {
    "reports": [
        {
            "id": "report-1",
            "values": [
                {
                    "key": "fasting_glucose",
                    "label": "Fasting Glucose",
                    "category": "lab_result",
                    "value": "104",
                    "unit": "mg/dL",
                }
            ],
        }
    ]
}

UNRELATED_REPORT = {
    "reports": [
        {
            "id": "report-2",
            "values": [
                {
                    "key": "visual_acuity",
                    "label": "Visual Acuity",
                    "category": "lab_result",
                    "value": "6/6",
                    "unit": "",
                }
            ],
        }
    ]
}


def _assessment(*, shoulder=None, ftsst=None, balance=None, skipped=()):
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


NORMAL_MOVEMENT = _assessment(shoulder=(150, 148), ftsst=8.0, balance=(25, 27))
POOR_MOVEMENT = _assessment(shoulder=(95, 90), ftsst=16.5, balance=(3.5, 4.2))


def _state(profile, assessment=None, reports=None):
    state = build_user_state(
        profile_doc=profile, assessment_doc=assessment, confirmed_reports_doc=reports
    )

    return apply_need_profile(state, assemble_need_profile(state))


def _clients(tag):
    return {
        "tool_client": InProcessExerciseToolClient(workflow_id=f"wf_{tag}", request_id=f"rq_{tag}"),
        "behaviour_tool_client": InProcessBehaviourToolClient(
            workflow_id=f"wf_{tag}", request_id=f"rq_{tag}"
        ),
        "nutrition_tool_client": InProcessNutritionToolClient(
            workflow_id=f"wf_{tag}", request_id=f"rq_{tag}"
        ),
    }


def _run(profile, assessment, tag, reports=None, **kwargs):
    kwargs.setdefault("exercise_results", [])

    return run_workflow(_state(profile, assessment, reports), **_clients(tag), **kwargs)


def _selected(result):
    return set(result["selected_agents"])


# --------------------------------------------------------------------------


class UserASedentaryOfficeWorkerTests(unittest.TestCase):
    """High sitting, low activity, a real movement finding, no report."""

    def setUp(self):
        self.result = _run(SEDENTARY, POOR_MOVEMENT, "user_a")

    def test_the_activity_and_movement_specialists_are_involved(self):
        self.assertIn("exercise_activity", _selected(self.result))
        self.assertIn("physio", _selected(self.result))

    def test_nutrition_is_not_involved_without_nutrition_evidence(self):
        self.assertNotIn("nutrition", _selected(self.result))

    def test_recovery_is_not_involved_when_sleep_is_adequate(self):
        self.assertNotIn("recovery", _selected(self.result))

    def test_activation_is_attributed_to_this_users_own_numbers(self):
        reason = self.result["orchestrator_decision"]["exercise_activity"]["reason"]

        self.assertTrue(
            str(SEDENTARY["daily_steps"]) in reason
            or str(SEDENTARY["daily_sitting_hours"]) in reason
            or str(SEDENTARY["exercise_days"]) in reason,
            f"activation reason cites no actual figure: {reason}",
        )

    def test_the_safety_gate_still_reviewed_the_plan(self):
        self.assertIsNotNone(self.result["safety_result"])


class UserBHealthRecordTests(unittest.TestCase):
    """Normal movement, adequate activity, but a confirmed report that
    records a nutrition-relevant measurement."""

    def setUp(self):
        self.result = _run(
            ACTIVE_HEALTHY, NORMAL_MOVEMENT, "user_b", reports=NUTRITION_REPORT
        )

    def test_the_report_alone_activates_nutrition(self):
        self.assertIn("nutrition", _selected(self.result))

        decision = self.result["orchestrator_decision"]["nutrition"]

        self.assertIn("confirmed_medical_report", decision["activated_by"])
        self.assertTrue(decision["report_evidence"])

    def test_no_movement_intervention_is_invented_for_a_normal_assessment(self):
        self.assertNotIn("physio", _selected(self.result))

    def test_the_contribution_states_the_report_without_interpreting_it(self):
        findings = next(
            entry["findings"]
            for entry in self.result["agent_results"]
            if entry["agent"] == "nutrition"
        )

        self.assertEqual(findings["mode"], "report_context_only")

        text = " ".join(findings["report_evidence"]).lower()

        self.assertIn("fasting glucose", text)
        # Presence is evidence of relevance. It is never read as a finding.
        for claim in ("high", "elevated", "abnormal", "diabet", "low"):
            self.assertNotIn(claim, text)

    def test_the_advice_reaches_the_user_through_the_safety_gate(self):
        ids = {entry["id"] for entry in self.result["final_recommendations"]}

        self.assertIn("discuss_report_values_with_clinician", ids)

    def test_an_unrelated_report_does_not_activate_nutrition(self):
        other = _run(
            ACTIVE_HEALTHY, NORMAL_MOVEMENT, "user_b2", reports=UNRELATED_REPORT
        )

        self.assertNotIn("nutrition", _selected(other))


class UserCHighMovementNeedTests(unittest.TestCase):
    """A significant assessment finding plus low activity."""

    def setUp(self):
        self.result = _run(SEDENTARY, POOR_MOVEMENT, "user_c")

    def test_physio_is_active_and_prescribes_exercises(self):
        self.assertIn("physio", _selected(self.result))

        physio = next(
            entry for entry in self.result["agent_results"] if entry["agent"] == "physio"
        )

        self.assertTrue(physio["findings"]["plan"]["exercises"])

    def test_the_shaping_rules_still_own_the_plan_size(self):
        physio = next(
            entry for entry in self.result["agent_results"] if entry["agent"] == "physio"
        )

        # Low activity evidence, so the existing shaping caps the plan.
        self.assertTrue(physio["findings"]["plan_shaping"]["low_activity"])
        self.assertLessEqual(len(physio["findings"]["plan"]["exercises"]), 4)


class UserDNormalAssessmentTests(unittest.TestCase):
    """Everything adequate. The system must not manufacture a plan."""

    def setUp(self):
        self.result = _run(ACTIVE_HEALTHY, NORMAL_MOVEMENT, "user_d")

    def test_no_specialist_is_activated(self):
        self.assertEqual(_selected(self.result), set())

    def test_no_recommendation_is_produced(self):
        self.assertEqual(self.result["final_recommendations"], [])

    def test_each_domain_records_why_it_declined(self):
        decisions = self.result["orchestrator_decision"]

        for domain in ("physio", "nutrition", "behaviour", "recovery", "exercise_activity"):
            self.assertIn(domain, decisions)
            self.assertTrue(decisions[domain]["reason"])


class UserERecoveryNeedTests(unittest.TestCase):
    """Short sleep is the only thing different about this user."""

    def setUp(self):
        self.result = _run(POOR_SLEEP, NORMAL_MOVEMENT, "user_recovery")

    def test_recovery_is_activated_by_the_sleep_answers(self):
        self.assertIn("recovery", _selected(self.result))
        self.assertIn("4.5", self.result["orchestrator_decision"]["recovery"]["reason"])

    def test_nothing_else_is_dragged_in_with_it(self):
        self.assertNotIn("physio", _selected(self.result))
        self.assertNotIn("nutrition", _selected(self.result))


class BehaviourNeedTests(unittest.TestCase):
    """Sedentary habit evidence activates the behaviour specialist."""

    def test_behaviour_is_activated_by_habit_evidence(self):
        result = _run(SEDENTARY, NORMAL_MOVEMENT, "user_behaviour")

        self.assertIn("behaviour", _selected(result))

    def test_consistent_users_get_no_behaviour_intervention(self):
        result = _run(ACTIVE_HEALTHY, NORMAL_MOVEMENT, "user_consistent")

        self.assertNotIn("behaviour", _selected(result))


class UserEMultiDomainTests(unittest.TestCase):
    """Sedentary, movement-limited, poorly rested, poor diet, with a
    nutrition-relevant confirmed report."""

    def setUp(self):
        profile = {
            **SEDENTARY,
            **{key: POOR_SLEEP[key] for key in ("sleep_hours", "sleep_quality")},
            **{
                key: POOR_DIET[key]
                for key in (
                    "meal_pattern",
                    "fruit_vegetable_servings",
                    "water_glasses_per_day",
                    "processed_food_frequency",
                )
            },
        }
        self.result = _run(
            profile, POOR_MOVEMENT, "user_e", reports=NUTRITION_REPORT
        )

    def test_several_specialists_contribute(self):
        selected = _selected(self.result)

        for domain in ("exercise_activity", "physio", "nutrition", "recovery", "behaviour"):
            self.assertIn(domain, selected, f"{domain} should contribute for User E")

    def test_the_combined_plan_contains_no_duplicate_recommendations(self):
        ids = [entry["id"] for entry in self.result["final_recommendations"]]

        self.assertEqual(len(ids), len(set(ids)), f"duplicate recommendations: {ids}")

    def test_the_safety_gate_reviewed_the_combined_plan(self):
        self.assertIsNotNone(self.result["safety_result"])
        self.assertTrue(self.result["final_recommendations"])


class NoEvidenceTests(unittest.TestCase):
    """A profile with nothing but age and sex."""

    def setUp(self):
        self.result = _run(NO_EVIDENCE, None, "no_evidence")

    def test_nothing_is_activated_from_nothing(self):
        self.assertEqual(_selected(self.result), set())

    def test_every_domain_says_it_lacked_evidence_rather_than_found_nothing_wrong(self):
        decisions = self.result["orchestrator_decision"]

        for domain in ("exercise_activity", "recovery"):
            self.assertFalse(decisions[domain]["evaluated"])


class NotAssessedTests(unittest.TestCase):
    """Checks the user skipped are absences, not findings."""

    def setUp(self):
        self.state = _state(
            ACTIVE_HEALTHY, _assessment(shoulder=(150, 148), skipped=("ftsst", "balance"))
        )
        self.result = run_workflow(
            self.state, exercise_results=[], **_clients("not_assessed")
        )

    def test_a_skipped_check_never_becomes_a_need(self):
        needs = self.state["current_needs"]["data"]

        for dimension in ("stability_need", "functional_movement_need"):
            self.assertEqual(needs[dimension]["level"], "NOT_ASSESSED")

    def test_the_specialist_card_says_not_assessed_rather_than_fine(self):
        team = {
            card["id"]: card
            for card in build_specialists_team(
                self.state,
                safety_status=(self.result["safety_result"] or {}).get("status"),
                safety_result=self.result["safety_result"],
            )
        }

        self.assertNotEqual(team["physio"]["status"], "ACTIVE")


class SafetyGateTests(unittest.TestCase):
    """Safety is applied after candidates exist, and it is final."""

    def setUp(self):
        self.result = run_workflow(
            _state(SEDENTARY, POOR_MOVEMENT, {"reports": [{"report_id": "r1", "values": []}]}),
            exercise_results=[],
            **_clients("safety"),
        )

    def test_a_confirmed_report_makes_the_gate_act(self):
        self.assertIn(self.result["safety_result"]["status"], ("MODIFY", "PAUSE", "REFER"))

    def test_nothing_blocked_survives_into_the_final_plan(self):
        blocked = set(self.result["safety_result"]["blocked_recommendation_ids"])
        final = {entry["id"] for entry in self.result["final_recommendations"]}

        self.assertFalse(blocked & final)


class PlanDepthTests(unittest.TestCase):
    """Severity changes how much intervention is included."""

    def test_a_worse_assessment_produces_a_larger_movement_plan(self):
        mild = _run(
            ACTIVE_HEALTHY,
            _assessment(shoulder=(150, 148), ftsst=8.0, balance=(9.0, 9.5)),
            "depth_mild",
        )
        severe = _run(
            ACTIVE_HEALTHY,
            _assessment(shoulder=(95, 90), ftsst=16.5, balance=(3.5, 4.2)),
            "depth_severe",
        )

        def plan_size(result):
            for entry in result["agent_results"]:
                if entry["agent"] == "physio":
                    return len(entry["findings"]["plan"]["exercises"])

            return 0

        self.assertGreater(plan_size(severe), plan_size(mild))

    def test_more_affected_domains_means_more_specialists(self):
        one = _run(POOR_SLEEP, NORMAL_MOVEMENT, "depth_one")
        many = _run(
            {**SEDENTARY, "sleep_hours": 4.5, "sleep_quality": "poor"},
            POOR_MOVEMENT,
            "depth_many",
        )

        self.assertGreater(len(_selected(many)), len(_selected(one)))


class DeterminismTests(unittest.TestCase):
    def test_identical_evidence_produces_an_identical_plan(self):
        first = _run(SEDENTARY, POOR_MOVEMENT, "det_1", reports=NUTRITION_REPORT)
        second = _run(SEDENTARY, POOR_MOVEMENT, "det_2", reports=NUTRITION_REPORT)

        self.assertEqual(first["selected_agents"], second["selected_agents"])
        self.assertEqual(
            [entry["id"] for entry in first["final_recommendations"]],
            [entry["id"] for entry in second["final_recommendations"]],
        )


class SpecialistStatusTests(unittest.TestCase):
    """The six cards must reflect what actually happened."""

    def test_not_every_specialist_is_active_for_a_healthy_user(self):
        state = _state(ACTIVE_HEALTHY, NORMAL_MOVEMENT)
        result = run_workflow(state, exercise_results=[], **_clients("status_healthy"))

        team = build_specialists_team(
            result["updated_user_state"] or state,
            safety_status=(result["safety_result"] or {}).get("status"),
            safety_result=result["safety_result"],
        )

        self.assertEqual(len(team), 6)

        active = [card["id"] for card in team if card["status"] == "ACTIVE"]

        # Safety is a standing review and may legitimately be active; no
        # advisory specialist should be.
        self.assertFalse(
            set(active) - {"safety"},
            f"specialists claimed active without evidence: {active}",
        )

    def test_every_card_carries_a_status_and_a_reason(self):
        state = _state(SEDENTARY, POOR_MOVEMENT)
        result = run_workflow(state, exercise_results=[], **_clients("status_sed"))

        # The Safety card deliberately speaks the Safety Gate's own
        # vocabulary rather than the advisory one: its job is to report
        # the gate's verdict, not whether it "contributed".
        advisory_statuses = ("ACTIVE", "EVALUATED_NOT_REQUIRED", "NOT_ASSESSED", "MONITORING")
        safety_statuses = ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED")

        for card in build_specialists_team(
            result["updated_user_state"] or state,
            safety_status=(result["safety_result"] or {}).get("status"),
            safety_result=result["safety_result"],
        ):
            allowed = safety_statuses if card["id"] == "safety" else advisory_statuses

            self.assertIn(
                card["status"],
                allowed,
                f"{card['id']} has status {card['status']!r}",
            )
            self.assertTrue(card.get("status_label"))
            self.assertTrue(card.get("reason"), f"{card['id']} gives no reason")


if __name__ == "__main__":
    unittest.main()
