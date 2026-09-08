"""Tests for the decision made before anything is run.

The distinction under test is between a blocker and a note. A blocker means an
agent cannot produce anything honest and must not be called; a note means it can
run but something about the basis is worth saying. Collapsing the two either
refuses to help somebody who could be helped, or produces guidance that quietly
rests on less than it appears to.

Runs without FastAPI, pymongo or a database.

    python -m unittest discover -s tests -t .
"""

import unittest

from agents.context import build_context
from agents.plan import (
    ACTION_ADD_REPORT,
    ACTION_COMPLETE_PROFILE,
    ACTION_CONFIRM_REPORT,
    ACTION_RECORD_ASSESSMENT,
    guidance_plan,
    report_stage_state,
)

PROFILE = {"age": 40, "sex": "male", "daily_sitting_hours": 8}

SESSION = {
    "completedAt": "2026-08-25T18:30:00+00:00",
    "tests": {
        "shoulder": {
            "status": "completed",
            "measurements": {"left": {"finalElevationDeg": 140.0},
                             "right": {"finalElevationDeg": 138.0},
                             "observableDifferenceDeg": 2.0},
        }
    },
}

CONFIRMED = {
    "hasConfirmedReports": True,
    "reportCount": 1,
    "reports": [{
        "title": "Blood panel",
        "values": [{"key": "haemoglobin", "label": "Haemoglobin",
                    "value": "13.2", "unit": "g/dL",
                    "printedReferenceRange": "13.0 - 17.0"}],
    }],
}


def plan(*, profile=None, assessment=None, confirmed=None, totals=None,
         model_available=True, model_reason=None, extraction_available=True):
    context = build_context(profile_summary=profile, assessment=assessment,
                            confirmed_reports=confirmed, report_totals=totals)

    return guidance_plan(context, model_available=model_available,
                         model_reason=model_reason,
                         extraction_available=extraction_available)


class BlockerTests(unittest.TestCase):
    def test_a_user_with_nothing_recorded_cannot_be_given_guidance(self):
        result = plan()

        self.assertFalse(result["canRun"])
        self.assertTrue(any("nothing to work from" in blocker
                            for blocker in result["blockers"]))

    def test_no_model_is_a_blocker_with_the_reason_given(self):
        result = plan(assessment=SESSION, model_available=False,
                      model_reason="No API key is configured on this server.")

        self.assertFalse(result["canRun"])
        self.assertIn("No API key is configured on this server.",
                      result["blockers"])

    def test_no_model_still_has_a_reason_when_none_was_supplied(self):
        result = plan(assessment=SESSION, model_available=False)

        self.assertTrue(result["blockers"][0])

    def test_both_problems_are_reported_not_just_the_first(self):
        result = plan(model_available=False, model_reason="Not configured.")

        self.assertEqual(len(result["blockers"]), 2)

    def test_one_source_and_a_model_is_enough_to_run(self):
        result = plan(assessment=SESSION)

        self.assertTrue(result["canRun"])
        self.assertEqual(result["blockers"], [])


class NoteTests(unittest.TestCase):
    def test_unconfirmed_reports_are_a_note_not_a_blocker(self):
        # The user can still be helped from what they have confirmed. They just
        # need to know why their readings are not being mentioned.
        result = plan(assessment=SESSION, totals={"total": 2})

        self.assertTrue(result["canRun"])
        self.assertTrue(any("not been confirmed" in note
                            for note in result["notes"]))

    def test_the_note_reads_correctly_for_a_single_report(self):
        result = plan(assessment=SESSION, totals={"total": 1})

        note = next(note for note in result["notes"] if "confirmed" in note)

        self.assertIn("1 report has not been confirmed", note)

    def test_a_session_with_nothing_usable_is_explained(self):
        session = {"tests": {"shoulder": {"status": "invalid",
                                          "measurements": {}}}}

        result = plan(profile=PROFILE, assessment=session)

        self.assertTrue(result["canRun"])
        self.assertTrue(any("did not produce a usable measurement" in note
                            for note in result["notes"]))

    def test_tests_that_produced_nothing_are_named_as_absent(self):
        session = {
            "tests": {
                "shoulder": SESSION["tests"]["shoulder"],
                "ftsst": {"status": "skipped", "measurements": {}},
            }
        }

        result = plan(profile=PROFILE, assessment=session)

        note = next(note for note in result["notes"] if "treated as absent" in note)

        self.assertIn("Standing up from a chair five times", note)
        self.assertIn("Standing on one leg with eyes open", note)

    def test_a_single_source_is_flagged_as_general(self):
        result = plan(assessment=SESSION)

        self.assertTrue(any("Only one kind of information" in note
                            for note in result["notes"]))

    def test_two_sources_are_not_flagged(self):
        result = plan(profile=PROFILE, assessment=SESSION)

        self.assertFalse(any("Only one kind of information" in note
                             for note in result["notes"]))

    def test_a_blocked_plan_does_not_add_the_thinness_note(self):
        # Nothing can be produced, so how general it would have been is not the
        # thing to tell the user about.
        result = plan(assessment=SESSION, model_available=False)

        self.assertFalse(any("Only one kind of information" in note
                             for note in result["notes"]))


class SuggestedActionTests(unittest.TestCase):
    def test_a_new_user_is_pointed_at_everything(self):
        result = plan()

        self.assertEqual(result["suggestedActions"],
                         [ACTION_RECORD_ASSESSMENT, ACTION_COMPLETE_PROFILE,
                          ACTION_ADD_REPORT])

    def test_an_unconfirmed_report_asks_for_confirmation_not_another_upload(self):
        result = plan(assessment=SESSION, profile=PROFILE, totals={"total": 1})

        self.assertEqual(result["suggestedActions"], [ACTION_CONFIRM_REPORT])

    def test_a_user_with_everything_is_asked_for_nothing(self):
        result = plan(profile=PROFILE, assessment=SESSION, confirmed=CONFIRMED,
                      totals={"total": 1})

        self.assertEqual(result["suggestedActions"], [])


class StageTests(unittest.TestCase):
    def test_the_three_stages_are_reported_in_order(self):
        result = plan(profile=PROFILE, assessment=SESSION)

        self.assertEqual([stage["stage"] for stage in result["stages"]],
                         [1, 2, 3])

    def test_care_navigation_waits_for_the_stage_before_it(self):
        result = plan(assessment=SESSION)

        navigation = result["stages"][2]

        self.assertEqual(navigation["state"], "runs_after_wellness_guidance")

    def test_a_blocked_plan_blocks_both_agent_stages_with_the_reason(self):
        result = plan(assessment=SESSION, model_available=False,
                      model_reason="Not configured.")

        for stage in result["stages"][1:]:
            with self.subTest(stage=stage["id"]):
                self.assertEqual(stage["state"], "blocked")
                self.assertEqual(stage["note"], "Not configured.")

    def test_a_runnable_plan_leaves_the_wellness_stage_ready(self):
        result = plan(assessment=SESSION)

        self.assertEqual(result["stages"][1]["state"], "ready")
        self.assertIsNone(result["stages"][1]["note"])


class ReportStageTests(unittest.TestCase):
    def test_a_confirmed_report_completes_the_stage(self):
        stage = report_stage_state(
            {"confirmedReportCount": 2, "unconfirmedReportCount": 0},
            extraction_available=True,
        )

        self.assertEqual(stage["state"], "complete")
        self.assertIn("2 confirmed reports", stage["note"])

    def test_an_unconfirmed_report_waits_for_the_user(self):
        stage = report_stage_state(
            {"confirmedReportCount": 0, "unconfirmedReportCount": 1},
            extraction_available=True,
        )

        self.assertEqual(stage["state"], "waiting_for_your_confirmation")
        self.assertIn("waiting for you to check", stage["note"])
        self.assertIn("until you confirm", stage["note"])

    def test_no_reports_and_no_provider_says_so_without_pretending(self):
        stage = report_stage_state(
            {"confirmedReportCount": 0, "unconfirmedReportCount": 0},
            extraction_available=False,
        )

        self.assertEqual(stage["state"], "not_configured")
        self.assertIn("not set up on this server", stage["note"])
        self.assertIn("by hand", stage["note"])

    def test_no_reports_with_a_provider_is_simply_empty(self):
        stage = report_stage_state(
            {"confirmedReportCount": 0, "unconfirmedReportCount": 0},
            extraction_available=True,
        )

        self.assertEqual(stage["state"], "no_reports")

    def test_a_confirmed_report_outranks_a_missing_provider(self):
        # Values the user has already confirmed stay usable whether or not
        # automatic reading is configured now.
        stage = report_stage_state(
            {"confirmedReportCount": 1, "unconfirmedReportCount": 0},
            extraction_available=False,
        )

        self.assertEqual(stage["state"], "complete")


if __name__ == "__main__":
    unittest.main()
