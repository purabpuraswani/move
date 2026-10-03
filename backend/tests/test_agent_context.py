"""Tests for what an agent is allowed to know.

agents/context.py is the only route information takes into a prompt, so these
tests are less about formatting than about three properties: that a value keeps
the meaning it had in the database, that a gap stays a gap, and that nothing
which was not asked for comes along with it.

Runs without FastAPI, pymongo or a database.

    python -m unittest discover -s tests -t .
"""

import json
import unittest

from agents.context import (
    build_assessment_context,
    build_context,
    build_profile_context,
    build_report_context,
    context_digest,
    context_signature,
    context_summary,
)

PROFILE_DOCUMENT = {
    "_id": "6510f00000000000000000ff",
    "user_id": "6510f00000000000000000aa",
    "age": 34,
    "sex": "female",
    "bmi": 23.456789,
    "work_type": "desk",
    "daily_sitting_hours": 9,
    "sleep_hours": 6.5,
    "updated_at": "2026-08-20T09:00:00+00:00",
    # Written by the onboarding upload. Nothing here asks for it.
    "health_documents": [{"filename": "scan.pdf", "notes": "private note"}],
}


def assessment(**overrides):
    """A serialised session with all three tests completed."""

    document = {
        "id": "a" * 24,
        "protocolVersion": "1.0.0",
        "completedAt": "2026-08-25T18:30:00+00:00",
        "summary": {
            "testsCompleted": 3,
            "testsInvalid": 0,
            "testsSkipped": 0,
            "testsNotStarted": 0,
            "hasAnyUsableResult": True,
        },
        "tests": {
            "shoulder": {
                "status": "completed",
                "measurements": {
                    "left": {"finalElevationDeg": 148.2},
                    "right": {"finalElevationDeg": 131.7},
                    "observableDifferenceDeg": 16.5,
                },
                "quality": {"meanFps": 24.4, "meanKeypointScore": 0.71},
                "invalidReasons": [],
                "attempts": 1,
            },
            "ftsst": {
                "status": "completed",
                "measurements": {
                    "completionTimeSeconds": 11.84,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                },
                "setup": {"chairSeatHeightCm": 45,
                          "chairSeatHeightPlausible": True},
                "quality": {"meanFps": 25.0},
                "invalidReasons": [],
                "attempts": 1,
            },
            "balance": {
                "status": "completed",
                "measurements": {
                    "left": {"attempted": True, "valid": True,
                             "holdDurationSeconds": 21.4,
                             "reachedMaxDuration": False},
                    "right": {"attempted": True, "valid": True,
                              "holdDurationSeconds": 30.0,
                              "reachedMaxDuration": True},
                    "observableDifferenceMs": 8600,
                },
                "quality": {},
                "invalidReasons": [],
                "attempts": 1,
            },
        },
    }

    document.update(overrides)

    return document


def confirmed(**overrides):
    payload = {
        "hasConfirmedReports": True,
        "reportCount": 1,
        "reports": [
            {
                "id": "b" * 24,
                "title": "Blood panel",
                "reportDate": "2026-08-01T00:00:00+00:00",
                "facility": "City Lab",
                "confirmedAt": "2026-08-02T00:00:00+00:00",
                "values": [
                    {
                        "key": "haemoglobin",
                        "label": "Haemoglobin",
                        "category": "lab_result",
                        "value": "13.2",
                        "unit": "g/dL",
                        "printedReferenceRange": "13.0 - 17.0",
                        "wasCorrectedByUser": False,
                        "originalSource": "ai_extraction",
                    },
                    {
                        "key": "vitamin_d",
                        "label": "Vitamin D",
                        "category": "lab_result",
                        "value": "22",
                        "unit": "ng/mL",
                        "printedReferenceRange": None,
                        "wasCorrectedByUser": True,
                        "originalSource": "user_entry",
                    },
                ],
            }
        ],
    }

    payload.update(overrides)

    return payload


class ProfileContextTests(unittest.TestCase):
    def test_no_profile_is_stated_not_guessed(self):
        context = build_profile_context(None)

        self.assertFalse(context["available"])
        self.assertIn("has not filled in the setup questions", context["reason"])
        self.assertEqual(context["values"], [])
        self.assertTrue(context["missingFields"])

    def test_the_api_wrapper_is_understood(self):
        context = build_profile_context(
            {"complete": True, "profile": {"age": 41},
             "updatedAt": "2026-08-01T00:00:00+00:00"}
        )

        self.assertTrue(context["available"])
        self.assertEqual(context["values"][0]["value"], 41)
        self.assertEqual(context["updatedAt"], "2026-08-01T00:00:00+00:00")

    def test_the_stored_document_is_understood_too(self):
        context = build_profile_context(PROFILE_DOCUMENT)

        labels = {entry["key"]: entry["value"] for entry in context["values"]}

        self.assertEqual(labels["age"], 34)
        self.assertEqual(labels["daily_sitting_hours"], 9)

    def test_only_the_named_fields_travel(self):
        # The profile document holds an id, the owner's id and an uploaded file
        # list. None of it was asked for, so none of it may arrive.
        context = build_profile_context(PROFILE_DOCUMENT)

        encoded = json.dumps(context)

        self.assertNotIn("6510f00000000000000000aa", encoded)
        self.assertNotIn("scan.pdf", encoded)
        self.assertNotIn("private note", encoded)

    def test_unanswered_questions_are_listed(self):
        context = build_profile_context(PROFILE_DOCUMENT)

        self.assertIn("Steps on a typical day", context["missingFields"])

    def test_a_long_float_is_shortened_without_being_changed(self):
        context = build_profile_context(PROFILE_DOCUMENT)

        bmi = next(entry for entry in context["values"] if entry["key"] == "bmi")

        self.assertEqual(bmi["value"], 23.46)


class AssessmentContextTests(unittest.TestCase):
    def test_no_session_is_stated(self):
        context = build_assessment_context(None)

        self.assertFalse(context["available"])
        self.assertIn("has not completed a movement assessment", context["reason"])
        self.assertEqual(context["tests"], [])

    def test_a_completed_test_is_described_with_its_numbers(self):
        context = build_assessment_context(assessment())

        shoulder = next(t for t in context["tests"] if t["id"] == "shoulder")

        joined = " ".join(shoulder["observations"])

        self.assertIn("148.2", joined)
        self.assertIn("131.7", joined)

    def test_a_skipped_test_produces_no_observations(self):
        session = assessment()
        session["tests"]["balance"] = {"status": "skipped", "measurements": {},
                                      "quality": {}, "invalidReasons": [],
                                      "attempts": 0}

        context = build_assessment_context(session)

        balance = next(t for t in context["tests"] if t["id"] == "balance")

        self.assertEqual(balance["status"], "skipped")
        self.assertEqual(balance["observations"], [])
        self.assertIn("no measurement exists", balance["statusExplanation"])

    def test_an_invalid_test_keeps_its_numbers_to_itself(self):
        # An invalid test can still carry measurements from the attempt. They
        # are not describable, because the conditions the measurement depends on
        # were not met, and describing them anyway is how an unusable number
        # becomes a finding.
        session = assessment()
        session["tests"]["ftsst"]["status"] = "invalid"
        session["tests"]["ftsst"]["invalidReasons"] = ["excessive_trunk_lean"]

        context = build_assessment_context(session)

        ftsst = next(t for t in context["tests"] if t["id"] == "ftsst")

        self.assertEqual(ftsst["observations"], [])
        self.assertIn("did not meet", ftsst["statusExplanation"])

        digest = context_digest(build_context(assessment=session))

        self.assertNotIn("11.84", digest)

    def test_a_missing_test_is_not_started_rather_than_absent(self):
        session = assessment()
        del session["tests"]["balance"]

        context = build_assessment_context(session)

        balance = next(t for t in context["tests"] if t["id"] == "balance")

        self.assertEqual(balance["status"], "not_started")

    def test_a_session_with_nothing_usable_is_unavailable(self):
        session = assessment()

        for test_id in ("shoulder", "ftsst", "balance"):
            session["tests"][test_id]["status"] = "invalid"

        context = build_assessment_context(session)

        self.assertFalse(context["available"])
        self.assertIn("no test in it produced a usable measurement",
                      context["reason"])

    def test_every_test_carries_what_it_is_not(self):
        context = build_assessment_context(assessment())

        for test in context["tests"]:
            with self.subTest(test=test["id"]):
                self.assertTrue(test["isNot"])

    def test_a_recording_problem_is_kept_apart_from_the_observations(self):
        session = assessment()
        session["tests"]["shoulder"]["invalidReasons"] = ["low_confidence"]

        context = build_assessment_context(session)

        shoulder = next(t for t in context["tests"] if t["id"] == "shoulder")

        self.assertTrue(any("low confidence" in note
                            for note in shoulder["reliabilityNotes"]))

        self.assertFalse(any("low confidence" in observation
                             for observation in shoulder["observations"]))

    def test_a_missing_seat_height_makes_the_time_incomparable(self):
        session = assessment()
        session["tests"]["ftsst"]["setup"] = {"chairSeatHeightCm": None}

        context = build_assessment_context(session)

        ftsst = next(t for t in context["tests"] if t["id"] == "ftsst")

        self.assertTrue(any("cannot be compared" in line
                            for line in ftsst["observations"]))

    def test_an_unattempted_balance_side_has_no_duration(self):
        session = assessment()
        session["tests"]["balance"]["measurements"]["right"] = {
            "attempted": False, "valid": False, "holdDurationSeconds": None
        }

        context = build_assessment_context(session)

        balance = next(t for t in context["tests"] if t["id"] == "balance")

        joined = " ".join(balance["observations"])

        self.assertIn("not attempted", joined)


class ReportContextTests(unittest.TestCase):
    def test_nothing_confirmed_is_stated_as_nothing(self):
        context = build_report_context({"hasConfirmedReports": False,
                                        "reportCount": 0, "reports": []})

        self.assertFalse(context["available"])
        self.assertIn("has not confirmed any medical report", context["reason"])

    def test_unconfirmed_reports_are_counted_but_withheld(self):
        context = build_report_context(
            {"hasConfirmedReports": False, "reportCount": 0, "reports": []},
            {"total": 2},
        )

        self.assertFalse(context["available"])
        self.assertEqual(context["unconfirmedReportCount"], 2)
        self.assertIn("not been confirmed yet", context["reason"])

    def test_confirmed_values_arrive_with_their_printed_range(self):
        context = build_report_context(confirmed(), {"total": 1})

        values = context["reports"][0]["values"]

        haemoglobin = next(v for v in values if v["label"] == "Haemoglobin")

        self.assertEqual(haemoglobin["value"], "13.2")
        self.assertEqual(haemoglobin["printedReferenceRange"], "13.0 - 17.0")

    def test_a_value_with_no_printed_range_says_so_in_the_digest(self):
        digest = context_digest(build_context(confirmed_reports=confirmed()))

        self.assertIn("no reference range was printed", digest)
        self.assertIn("must not supply one", digest)

    def test_a_corrected_value_is_marked_as_the_users_own(self):
        digest = context_digest(build_context(confirmed_reports=confirmed()))

        self.assertIn("the user corrected this value themselves", digest)


class DigestTests(unittest.TestCase):
    def test_the_digest_labels_where_everything_came_from(self):
        digest = context_digest(
            build_context(profile_summary=PROFILE_DOCUMENT,
                          assessment=assessment(),
                          confirmed_reports=confirmed(),
                          report_totals={"total": 1})
        )

        self.assertIn("Self-reported estimates", digest)
        self.assertIn("not clinical measurements", digest)
        self.assertIn("checked and confirmed by the user themselves", digest)

    def test_the_digest_carries_the_webcam_caveats(self):
        # Every number is preceded by what the number is not. This is the
        # assertion that would fail first if a future edit shortened the prompt
        # by dropping the caveats.
        digest = context_digest(build_context(assessment=assessment()))

        self.assertIn("What it is not: a clinical range of motion", digest)
        self.assertIn("a clinician-timed test", digest)
        self.assertIn("fall risk score", digest)

    def test_the_digest_never_contains_an_identifier(self):
        digest = context_digest(
            build_context(profile_summary=PROFILE_DOCUMENT,
                          assessment=assessment(),
                          confirmed_reports=confirmed())
        )

        self.assertNotIn("6510f00000000000000000aa", digest)
        self.assertNotIn("a" * 24, digest)
        self.assertNotIn("b" * 24, digest)

    def test_missing_sources_are_named_in_the_digest(self):
        digest = context_digest(build_context(assessment=assessment()))

        self.assertIn("MISSING INFORMATION", digest)
        self.assertIn("profile", digest)
        self.assertIn("Do not fill the gap with what is typical", digest)

    def test_a_context_with_nothing_still_renders(self):
        digest = context_digest(build_context())

        self.assertIn("ABOUT THIS PERSON", digest)
        self.assertIn("MOVEMENT OBSERVATIONS", digest)
        self.assertIn("CONFIRMED MEDICAL REPORT VALUES", digest)


class AvailabilityTests(unittest.TestCase):
    def test_nothing_available_is_reported_as_nothing(self):
        context = build_context()

        self.assertFalse(context["availability"]["hasAnything"])
        self.assertEqual(context["availability"]["present"], [])

    def test_one_source_is_thin(self):
        context = build_context(assessment=assessment())

        self.assertTrue(context["availability"]["hasAnything"])
        self.assertTrue(context["availability"]["isThin"])

    def test_two_sources_are_not_thin(self):
        context = build_context(assessment=assessment(),
                                confirmed_reports=confirmed())

        self.assertFalse(context["availability"]["isThin"])


class SignatureTests(unittest.TestCase):
    def test_the_same_data_gives_the_same_fingerprint(self):
        first = build_context(assessment=assessment(),
                             generated_at="2026-08-26T10:00:00+00:00")
        second = build_context(assessment=assessment(),
                               generated_at="2026-08-27T22:00:00+00:00")

        self.assertEqual(first["signature"], second["signature"])

    def test_a_changed_measurement_changes_the_fingerprint(self):
        session = assessment()
        session["tests"]["shoulder"]["measurements"]["left"][
            "finalElevationDeg"] = 120.0

        self.assertNotEqual(
            context_signature(build_context(assessment=assessment())),
            context_signature(build_context(assessment=session)),
        )

    def test_a_newly_confirmed_report_changes_the_fingerprint(self):
        self.assertNotEqual(
            context_signature(build_context(assessment=assessment())),
            context_signature(build_context(assessment=assessment(),
                                            confirmed_reports=confirmed())),
        )


class SummaryTests(unittest.TestCase):
    def test_the_summary_carries_counts_not_readings(self):
        summary = context_summary(
            build_context(profile_summary=PROFILE_DOCUMENT,
                          assessment=assessment(),
                          confirmed_reports=confirmed(),
                          report_totals={"total": 3})
        )

        # `generatedAt` is a wall-clock timestamp and `signature` a hash;
        # neither is derived from a reading, and both can contain a
        # reading's digits by coincidence -- a run at 10:26:13.217462
        # used to fail this on the "13.2" in the timestamp. Searching the
        # fields that actually carry content keeps the check honest
        # without making it depend on the clock.
        encoded = json.dumps(
            {
                key: value
                for key, value in summary.items()
                if key not in ("generatedAt", "signature")
            }
        )

        self.assertNotIn("13.2", encoded)
        self.assertNotIn("Haemoglobin", encoded)
        self.assertNotIn("148.2", encoded)

        self.assertEqual(summary["confirmedReportCount"], 1)
        self.assertEqual(summary["unconfirmedReportCount"], 2)

    def test_the_summary_keeps_every_test_status(self):
        session = assessment()
        session["tests"]["balance"]["status"] = "skipped"

        summary = context_summary(build_context(assessment=session))

        statuses = {test["id"]: test["status"] for test in summary["movementTests"]}

        self.assertEqual(statuses["balance"], "skipped")
        self.assertEqual(statuses["shoulder"], "completed")


if __name__ == "__main__":
    unittest.main()
