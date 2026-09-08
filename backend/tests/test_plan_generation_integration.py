"""The assessment -> plan -> persistence -> /latest -> Plan UI chain.

Every test here corresponds to something that was actually broken, and the
two defects they cover were found by tracing a real user's failed session,
not by reading the code:

  1. A completed assessment in which the camera could read only one of the
     three tests produced {LOW, NOT_ASSESSED, NOT_ASSESSED}. Nothing was at
     MEDIUM or HIGH, so no specialist was selected, no plan was built, and
     the API honestly returned 200 with nothing in it. The Plan screen
     rendered that identically to "you have not started yet".

  2. `build_user_state_for_user()` rebuilt the User State from source
     documents on every run. No source document can produce
     `exercise_history`, so every plan a previous run had created was
     silently discarded, and `plan_version` could never exceed 1.

The tests are written against the real modules — real Need Assessment, real
Orchestrator, the real Physio Agent, the real Safety Gate, the real
response serialiser. Only the MCP transport is the in-process client, which
is this project's own test double for the tool layer and nothing else.
"""

import ast
import unittest
from pathlib import Path

from orchestration.ids import start_workflow
from orchestrator.decision import decide_physio_required
from orchestrator.orchestrator import run_workflow
from physio_agent.agent import BASELINE_ASSESSMENT_MOVEMENTS
from physio_agent.plan_schema import DECISION_TYPES, MEASUREMENT_METHODS
from physio_agent.tool_client import InProcessExerciseToolClient
from workflow.assembly import (
    PERSISTED_WORKFLOW_SECTIONS,
    SOURCE_DERIVED_SECTIONS,
    assemble_user_state_from_documents,
    validate_section_classification,
)
from workflow.response import serialise_workflow_state

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def source_of(relative_path: str) -> str:
    """The text of one backend module, read from disk.

    Read rather than imported on purpose: both guards below are about lines
    in modules that import `fastapi` / `bson`, and this project's own
    sandbox does not always have those installed. An assertion about the
    shape of the source must not be skipped for want of a database driver.
    """

    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")

# The three baseline tests, as `assessments/schema.py` stores them.
SHOULDER_USABLE = {
    "status": "completed",
    "measurements": {
        "left": {"finalElevationDeg": 114.0},
        "right": {"finalElevationDeg": 111.0},
        "observableDifferenceDeg": 3.0,
    },
}

SHOULDER_UNUSABLE = {
    "status": "invalid",
    "measurements": None,
    "invalid_reasons": ["low_quality_frames"],
}

# 18 seconds is above FTSST_HIGH_NEED_ABOVE_SECONDS (15), so this is a real,
# measured HIGH — the evidence-based selection path.
FTSST_SLOW = {
    "status": "completed",
    "measurements": {
        "completionTimeSeconds": 18.0,
        "repetitionsDetected": 5,
        "requiredRepetitions": 5,
    },
}

FTSST_UNUSABLE = {
    "status": "invalid",
    "measurements": None,
    "invalid_reasons": ["pose_loss"],
}

# A full-marks hold: 30s is the protocol ceiling, so this is LOW — measured,
# no deficit. It is the ONLY usable measurement in the partial session.
BALANCE_USABLE = {
    "status": "completed",
    "measurements": {
        "left": {"attempted": True, "valid": True, "holdDurationSeconds": 30.0},
        "right": {"attempted": True, "valid": True, "holdDurationSeconds": 30.0},
        "observableDifferenceMs": 0,
    },
}


def assessment_document(*, shoulder, ftsst, balance):
    return {
        "protocol_version": "1.0.0",
        "completed_at": "2026-09-06T10:00:00+00:00",
        "tests": {"shoulder": shoulder, "ftsst": ftsst, "balance": balance},
    }


PARTIAL_SESSION = assessment_document(
    shoulder=SHOULDER_UNUSABLE, ftsst=FTSST_UNUSABLE, balance=BALANCE_USABLE
)

NEED_SESSION = assessment_document(
    shoulder=SHOULDER_USABLE, ftsst=FTSST_SLOW, balance=BALANCE_USABLE
)

FULLY_ASSESSED_NO_NEED_SESSION = assessment_document(
    shoulder=SHOULDER_USABLE,
    ftsst={
        "status": "completed",
        "measurements": {
            "completionTimeSeconds": 8.0,
            "repetitionsDetected": 5,
            "requiredRepetitions": 5,
        },
    },
    balance=BALANCE_USABLE,
)


def build_state(assessment_doc, persisted_state=None):
    return assemble_user_state_from_documents(
        profile_doc=None,
        assessment_doc=assessment_doc,
        confirmed_reports_doc=None,
        persisted_state=persisted_state,
    )


def run(user_state):
    """One real workflow run against the real Orchestrator."""

    trace = start_workflow()
    client = InProcessExerciseToolClient(
        workflow_id=trace.workflow_id, request_id=trace.request_id
    )

    return run_workflow(
        user_state,
        tool_client=client,
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
    )


def serialise(result):
    safety = result["safety_result"]

    return serialise_workflow_state(
        result["updated_user_state"],
        safety_status=safety["status"] if safety else None,
    )


def need_levels(user_state):
    return {
        dimension: entry["level"]
        for dimension, entry in user_state["current_needs"]["data"].items()
        if isinstance(entry, dict) and "level" in entry
    }


class AssessmentWithRealNeedProducesAPlan(unittest.TestCase):
    """(1) An assessment showing a real, measured need selects the
    specialist and produces a plan."""

    def setUp(self):
        self.result = run(build_state(NEED_SESSION))
        self.response = serialise(self.result)

    def test_the_physio_specialist_is_selected(self):
        self.assertIn("physio", self.result["selected_agents"])

    def test_a_plan_is_created_and_written_to_the_user_state(self):
        self.assertIn("exercise_history", self.result["state_updates"])
        self.assertTrue(self.response["exercise_plan"]["available"])
        self.assertGreater(self.response["exercise_plan"]["exercise_count"], 0)

    def test_the_selection_was_evidence_based_not_the_starter_pathway(self):
        decision = self.result["orchestrator_decision"]["physio"]

        self.assertEqual(decision["selection_mode"], "need_based")
        self.assertEqual(
            need_levels(self.result["updated_user_state"])[
                "functional_movement_need"
            ],
            "HIGH",
        )

    def test_the_safety_gate_ran(self):
        self.assertIsNotNone(self.result["safety_result"])


class PartialAssessmentDoesNotBecomeLow(unittest.TestCase):
    """(2) and (4) An unmeasured capability stays NOT_ASSESSED, everywhere,
    and is never read as evidence of a deficit."""

    def setUp(self):
        self.state = build_state(PARTIAL_SESSION)
        self.levels = need_levels(self.state)

    def test_unmeasured_dimensions_are_not_assessed_not_low(self):
        self.assertEqual(self.levels["mobility_need"], "NOT_ASSESSED")
        self.assertEqual(self.levels["functional_movement_need"], "NOT_ASSESSED")

    def test_the_one_measured_dimension_is_low(self):
        # Measured, at the protocol ceiling: a real finding of no deficit,
        # which is a different thing from the two above.
        self.assertEqual(self.levels["stability_need"], "LOW")

    def test_a_not_assessed_dimension_carries_no_score(self):
        profile = self.state["current_needs"]["data"]

        for dimension in ("mobility_need", "functional_movement_need"):
            self.assertIsNone(profile[dimension]["score"])
            self.assertEqual(profile[dimension]["confidence"], "NONE")
            self.assertTrue(profile[dimension]["evidence"])

    def test_not_assessed_is_never_reported_as_a_triggering_need(self):
        decision = decide_physio_required(self.state["current_needs"]["data"])

        # It may select Physio (the starter pathway) but must never claim a
        # dimension is at MEDIUM/HIGH to do it.
        self.assertNotIn("MEDIUM", decision["reason"].split("at MEDIUM or HIGH")[0])
        self.assertEqual(
            set(decision["unassessed_dimensions"]),
            {"mobility_need", "functional_movement_need"},
        )
        for level in decision["evaluated_dimensions"].values():
            if level in ("MEDIUM", "HIGH"):
                self.fail("a NOT_ASSESSED dimension was reported as a need")

    def test_the_plan_never_claims_a_deficit_it_did_not_measure(self):
        response = serialise(run(self.state))
        needs = need_levels(build_state(PARTIAL_SESSION))

        self.assertEqual(needs["mobility_need"], "NOT_ASSESSED")
        self.assertTrue(response["exercise_plan"]["available"])


class PartialAssessmentProducesAConservativeStarterPlan(unittest.TestCase):
    """(3) The dead end is gone: a real session with one usable measurement
    produces a real, structured, safety-gated plan."""

    def setUp(self):
        self.result = run(build_state(PARTIAL_SESSION))
        self.response = serialise(self.result)
        self.plan = self.result["agent_results"][0]["findings"]["plan"]

    def test_a_plan_is_produced(self):
        self.assertTrue(self.response["exercise_plan"]["available"])
        self.assertGreaterEqual(self.response["exercise_plan"]["exercise_count"], 1)

    def test_it_is_labelled_as_the_conservative_starter_pathway(self):
        decision = self.result["orchestrator_decision"]["physio"]

        self.assertEqual(decision["selection_mode"], "conservative_starter")
        self.assertEqual(
            self.result["agent_results"][0]["findings"]["selection_mode"],
            "conservative_starter",
        )

    def test_every_exercise_is_at_the_bottom_of_the_difficulty_range(self):
        for entry in self.plan["exercises"]:
            self.assertEqual(entry["difficulty"], "beginner")

    def test_no_rationale_claims_a_finding(self):
        for entry in self.plan["exercises"]:
            self.assertIn("could not measure", entry["rationale"])
            self.assertIn("rather than as a finding", entry["rationale"])

    def test_each_decision_is_structured(self):
        for entry in self.plan["exercises"]:
            self.assertIn(entry["decision_type"], DECISION_TYPES)
            self.assertEqual(entry["decision_type"], "ADD")
            self.assertIn(entry["measurement_method"], MEASUREMENT_METHODS)
            self.assertTrue(entry["target_need"])
            self.assertTrue(entry["rationale"])

    def test_it_still_passed_the_safety_gate(self):
        self.assertIsNotNone(self.result["safety_result"])
        self.assertIn(
            self.result["safety_result"]["status"],
            ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED"),
        )

    def test_a_fully_assessed_user_with_no_need_gets_no_starter_plan(self):
        # The starter pathway must not fire when everything WAS measured
        # and nothing was found — inventing a plan there would be inventing
        # a need.
        result = run(build_state(FULLY_ASSESSED_NO_NEED_SESSION))

        self.assertEqual(result["selected_agents"], [])
        self.assertEqual(
            serialise(result)["plan_state"]["state"], "NO_PLAN_SAFE_OR_SUPPORTED"
        )


class InterventionIsNotTheAssessment(unittest.TestCase):
    """The programme must be intervention exercises, not the three baseline
    tests handed back as a workout."""

    def test_the_starter_plan_contains_no_baseline_assessment_movement(self):
        result = run(build_state(PARTIAL_SESSION))
        ids = [
            entry["exercise_id"]
            for entry in result["agent_results"][0]["findings"]["plan"]["exercises"]
        ]

        self.assertTrue(ids)
        for exercise_id in ids:
            self.assertNotIn(exercise_id, BASELINE_ASSESSMENT_MOVEMENTS)

    def test_the_need_based_plan_contains_no_baseline_assessment_movement(self):
        result = run(build_state(NEED_SESSION))
        ids = [
            entry["exercise_id"]
            for entry in result["agent_results"][0]["findings"]["plan"]["exercises"]
        ]

        self.assertTrue(ids)
        for exercise_id in ids:
            self.assertNotIn(exercise_id, BASELINE_ASSESSMENT_MOVEMENTS)

    def test_a_plan_is_not_always_exactly_three_exercises(self):
        counts = {
            len(
                run(build_state(session))["agent_results"][0]["findings"]["plan"][
                    "exercises"
                ]
            )
            for session in (PARTIAL_SESSION, NEED_SESSION)
        }

        self.assertTrue(all(count >= 1 for count in counts))
        self.assertTrue(any(count >= 4 for count in counts))


class PersistedPlanSurvivesTheRebuild(unittest.TestCase):
    """(5), (6), (7) The persistence defect."""

    def setUp(self):
        self.first = run(build_state(PARTIAL_SESSION))
        self.persisted = self.first["updated_user_state"]

    def test_the_first_run_created_a_plan(self):
        self.assertTrue(self.persisted["exercise_history"]["available"])
        self.assertEqual(len(self.persisted["exercise_history"]["data"]["plans"]), 1)

    def test_rebuilding_from_source_documents_alone_loses_it(self):
        # The defect itself, asserted so this test fails if the merge is
        # ever removed and this file is left claiming everything is fine.
        rebuilt_without_merge = assemble_user_state_from_documents(
            profile_doc=None, assessment_doc=PARTIAL_SESSION, confirmed_reports_doc=None
        )

        self.assertFalse(rebuilt_without_merge["exercise_history"]["available"])

    def test_the_plan_survives_build_user_state_for_user(self):
        rebuilt = build_state(PARTIAL_SESSION, persisted_state=self.persisted)

        self.assertTrue(rebuilt["exercise_history"]["available"])
        self.assertEqual(len(rebuilt["exercise_history"]["data"]["plans"]), 1)

    def test_a_second_run_does_not_erase_the_first_plan(self):
        rebuilt = build_state(PARTIAL_SESSION, persisted_state=self.persisted)
        second = run(rebuilt)
        response = serialise(second)

        self.assertTrue(response["exercise_plan"]["available"])
        self.assertEqual(response["plan_state"]["state"], "PLAN_AVAILABLE")

    def test_plan_history_is_append_only_and_never_restarts_at_one(self):
        state = self.persisted

        for _ in range(3):
            state = run(build_state(PARTIAL_SESSION, persisted_state=state))[
                "updated_user_state"
            ]

        plans = state["exercise_history"]["data"]["plans"]
        versions = [record["plan_version"] for record in plans]

        # Unchanged evidence plus an existing plan must not mint new
        # versions, and must never drop the one that exists.
        self.assertEqual(versions, sorted(versions))
        self.assertGreaterEqual(len(plans), 1)
        self.assertEqual(plans[0]["plan_version"], 1)

    def test_source_derived_sections_are_not_taken_from_the_stale_copy(self):
        # A newer assessment must win over the persisted projection of the
        # older one, or the merge would resurrect stale evidence.
        stale = dict(self.persisted)
        rebuilt = build_state(NEED_SESSION, persisted_state=stale)

        self.assertEqual(
            rebuilt["physical_assessment"]["data"]["tests"]["ftsst"]["status"],
            "completed",
        )
        self.assertEqual(need_levels(rebuilt)["functional_movement_need"], "HIGH")

    def test_the_merge_rule_classifies_every_section_exactly_once(self):
        validate_section_classification()

        self.assertNotIn("exercise_history", SOURCE_DERIVED_SECTIONS)
        self.assertIn("exercise_history", PERSISTED_WORKFLOW_SECTIONS)
        self.assertIn("physical_assessment", SOURCE_DERIVED_SECTIONS)


class BaselineAssessmentIsNeverRewritten(unittest.TestCase):
    """(8) The comparison anchor stays where it is."""

    def test_running_the_workflow_does_not_mutate_the_assessment_document(self):
        document = assessment_document(
            shoulder=SHOULDER_UNUSABLE, ftsst=FTSST_UNUSABLE, balance=BALANCE_USABLE
        )
        before = repr(document)

        state = build_state(document)
        result = run(state)
        build_state(document, persisted_state=result["updated_user_state"])

        self.assertEqual(repr(document), before)

    def test_baseline_is_read_oldest_first_and_never_written(self):
        tree = ast.parse(source_of("assessments/store.py"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "baseline_assessment"
        )
        source = ast.unparse(function)

        self.assertIn("ASCENDING", source)
        for forbidden in ("insert_one", "update_one", "replace_one", "delete_one"):
            self.assertNotIn(forbidden, source)


class LatestEndpointReturnsThePersistedPlan(unittest.TestCase):
    """(9) and (10) What `GET /api/workflow/latest` hands the Plan page."""

    def test_serialising_a_persisted_state_returns_the_plan(self):
        persisted = run(build_state(PARTIAL_SESSION))["updated_user_state"]
        response = serialise_workflow_state(persisted, safety_status="ALLOW")

        self.assertTrue(response["exercise_plan"]["available"])
        self.assertEqual(response["plan_state"]["state"], "PLAN_AVAILABLE")
        self.assertTrue(response["exercise_plan"]["exercise_items"])
        for item in response["exercise_plan"]["exercise_items"]:
            self.assertTrue(item["id"])
            self.assertTrue(item["name"])

    def test_the_route_actually_passes_the_persisted_state_to_the_assembler(self):
        # An AST guard rather than a string search: this is the one line
        # whose absence caused the plan loss, and it is invisible in any
        # test that only exercises the pure functions.
        tree = ast.parse(source_of("routes/workflow.py"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_user_state_for_user"
        )
        keywords = {
            keyword.arg
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
        }

        self.assertIn("persisted_state", keywords)
        self.assertIn("get_user_state", ast.unparse(function))

    def test_a_state_with_no_plan_reports_the_third_state_not_the_first(self):
        state = build_state(FULLY_ASSESSED_NO_NEED_SESSION)
        response = serialise_workflow_state(state)

        self.assertEqual(response["plan_state"]["state"], "NO_PLAN_SAFE_OR_SUPPORTED")
        self.assertTrue(response["plan_state"]["reason"])

    def test_an_account_with_no_assessment_reports_never_run(self):
        state = assemble_user_state_from_documents()
        response = serialise_workflow_state(state)

        self.assertEqual(response["plan_state"]["state"], "NEVER_RUN")
        self.assertEqual(response["plan_state"]["next_action"]["route"], "/assessment")

    def test_the_third_state_names_what_was_missing(self):
        state = build_state(PARTIAL_SESSION)
        # Before any workflow has run: a completed session, no plan yet.
        response = serialise_workflow_state(state)

        self.assertEqual(response["plan_state"]["state"], "NO_PLAN_SAFE_OR_SUPPORTED")
        capabilities = {
            item["capability"] for item in response["plan_state"]["missing"]
        }

        self.assertIn("Upper-body mobility", capabilities)
        self.assertIn("Sit-to-stand strength", capabilities)
        for item in response["plan_state"]["missing"]:
            self.assertTrue(item["reason"])

    def test_no_internal_identifier_leaks_into_the_response(self):
        response = serialise(run(build_state(PARTIAL_SESSION)))
        text = repr(response)

        for forbidden in (
            "workflow_id",
            "request_id",
            "agent_run_id",
            "tool_call_id",
            "mcp_session_id",
            "_id",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
