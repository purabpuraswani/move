"""Tests for the report field model and the trust boundary.

Runs without FastAPI, pymongo or a database: reports/schema.py deliberately
depends on nothing but the standard library, because the rule it encodes — that
a value is not usable until the user has confirmed it — is the part that most
needs to be testable.

    python -m unittest discover -s tests -t .
"""

import unittest
from datetime import datetime, timezone

from reports.schema import (
    CATEGORY_LAB_RESULT,
    DECISION_ACCEPTED,
    DECISION_CORRECTED,
    DECISION_PENDING,
    DECISION_REJECTED,
    SOURCE_AI_EXTRACTION,
    SOURCE_USER_ENTRY,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_PROCESSING,
    STATUS_UPLOADED,
    ReportValidationError,
    apply_review,
    build_candidate_field,
    build_candidate_fields,
    build_report_document,
    can_confirm,
    check_transition,
    confirmed_values,
    is_trusted,
    review_progress,
)

NOW = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)

PROVENANCE = {
    "source": SOURCE_AI_EXTRACTION,
    "provider": "openrouter",
    "model": "test-model",
    "extracted_at": NOW,
}


def candidate(**overrides):
    raw = {
        "key": "haemoglobin",
        "label": "Haemoglobin",
        "value": "13.2",
        "unit": "g/dL",
        "printed_reference_range": "13.0 - 17.0",
        "quoted_text": "Haemoglobin 13.2 g/dL (13.0 - 17.0)",
        "page": 1,
        "confidence": 0.88,
    }
    raw.update(overrides)

    return raw


def glucose_candidate(**overrides):
    """A second, unrelated field.

    Given its own unit and range rather than inheriting haemoglobin's, because
    a submission that silently drops a unit counts as a correction — which is
    correct behaviour, but makes for a confusing fixture.
    """
    raw = candidate(
        key="glucose",
        label="Glucose",
        value="5.4",
        unit="mmol/L",
        printed_reference_range="3.9 - 5.6",
        quoted_text="Fasting glucose 5.4 mmol/L (3.9 - 5.6)",
    )
    raw.update(overrides)

    return raw


# What the user submits when they change nothing at all. Every part of the
# comparison has to be echoed back, otherwise the omission is itself an edit.
UNCHANGED_HAEMOGLOBIN = {
    "key": "haemoglobin",
    "value": "13.2",
    "unit": "g/dL",
    "printed_reference_range": "13.0 - 17.0",
}

UNCHANGED_GLUCOSE = {
    "key": "glucose",
    "value": "5.4",
    "unit": "mmol/L",
    "printed_reference_range": "3.9 - 5.6",
}


class CandidateFieldTests(unittest.TestCase):
    def test_a_candidate_starts_unreviewed(self):
        field = build_candidate_field(candidate(), provenance=PROVENANCE)

        self.assertEqual(field["review"]["decision"], DECISION_PENDING)
        self.assertIsNone(field["review"]["value"])

    def test_the_candidate_keeps_what_was_read(self):
        field = build_candidate_field(candidate(), provenance=PROVENANCE)

        self.assertEqual(field["candidate"]["value"], "13.2")
        self.assertEqual(field["candidate"]["quoted_text"][:11], "Haemoglobin")

    def test_provenance_comes_from_the_caller_not_the_payload(self):
        # A model claiming its own source must not be able to set it.
        field = build_candidate_field(
            candidate(provenance={"source": "user_entry"}),
            provenance=PROVENANCE,
        )

        self.assertEqual(field["provenance"]["source"], SOURCE_AI_EXTRACTION)
        self.assertEqual(field["provenance"]["provider"], "openrouter")

    def test_values_stay_as_text(self):
        # "<0.01" and "Not detected" appear in the same column as "13.2".
        # Parsing to a number would mean deciding what the others mean.
        field = build_candidate_field(
            candidate(value="Not detected", unit=None), provenance=PROVENANCE
        )

        self.assertEqual(field["candidate"]["value"], "Not detected")
        self.assertIsNone(field["candidate"]["unit"])

    def test_missing_confidence_stays_missing(self):
        field = build_candidate_field(
            candidate(confidence=None), provenance=PROVENANCE
        )

        self.assertIsNone(field["candidate"]["confidence"])

    def test_confidence_outside_zero_to_one_is_refused(self):
        for value in (-0.1, 1.5, "high", True):
            with self.subTest(value=value):
                with self.assertRaises(ReportValidationError):
                    build_candidate_field(
                        candidate(confidence=value), provenance=PROVENANCE
                    )

    def test_a_bad_key_is_refused(self):
        for key in ("Has Spaces", "UPPER", "", None, "x" * 80):
            with self.subTest(key=key):
                with self.assertRaises(ReportValidationError):
                    build_candidate_field(
                        candidate(key=key), provenance=PROVENANCE
                    )

    def test_an_unknown_category_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_candidate_field(
                candidate(category="diagnosis"), provenance=PROVENANCE
            )

    def test_an_over_long_value_is_refused_not_truncated(self):
        with self.assertRaises(ReportValidationError):
            build_candidate_field(
                candidate(value="9" * 600), provenance=PROVENANCE
            )


class ExtractionResultTests(unittest.TestCase):
    def test_a_malformed_field_is_dropped_and_reported(self):
        fields, rejected = build_candidate_fields(
            [candidate(), candidate(key="Bad Key")], provenance=PROVENANCE
        )

        self.assertEqual(len(fields), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn("Bad Key", rejected[0])

    def test_repeated_keys_are_kept_separately(self):
        # Reports repeat panel names. Overwriting would silently lose a reading.
        fields, _ = build_candidate_fields(
            [candidate(), candidate(value="13.9")], provenance=PROVENANCE
        )

        self.assertEqual([field["key"] for field in fields],
                         ["haemoglobin", "haemoglobin_2"])
        self.assertEqual(fields[1]["candidate"]["value"], "13.9")

    def test_an_empty_extraction_is_not_an_error(self):
        fields, rejected = build_candidate_fields([], provenance=PROVENANCE)

        self.assertEqual(fields, [])
        self.assertEqual(rejected, [])

    def test_too_many_fields_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_candidate_fields(
                [candidate(key=f"k{i}") for i in range(300)],
                provenance=PROVENANCE,
            )


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.fields, _ = build_candidate_fields(
            [candidate(), glucose_candidate()], provenance=PROVENANCE
        )

    def test_an_unchanged_value_is_an_acceptance(self):
        reviewed = apply_review(
            self.fields, [dict(UNCHANGED_HAEMOGLOBIN)], now=NOW
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["review"]["decision"], DECISION_ACCEPTED)

    def test_dropping_the_unit_is_a_correction(self):
        # Omitting part of the value is an edit, not a no-op: "13.2" without
        # "g/dL" is a different claim from "13.2 g/dL".
        reviewed = apply_review(
            self.fields, [{"key": "haemoglobin", "value": "13.2"}], now=NOW
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["review"]["decision"], DECISION_CORRECTED)

    def test_a_changed_value_is_a_correction(self):
        reviewed = apply_review(
            self.fields,
            [{"key": "haemoglobin", "value": "13.7", "unit": "g/dL"}],
            now=NOW,
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["review"]["decision"], DECISION_CORRECTED)
        self.assertEqual(haemoglobin["review"]["value"], "13.7")

    def test_the_candidate_survives_a_correction(self):
        # The machine's original reading has to stay visible, otherwise a wrong
        # extraction quietly becomes the record.
        reviewed = apply_review(
            self.fields,
            [{"key": "haemoglobin", "value": "13.7"}],
            now=NOW,
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["candidate"]["value"], "13.2")

    def test_excluding_a_field_rejects_it(self):
        reviewed = apply_review(
            self.fields,
            [{"key": "haemoglobin", "value": "13.2", "include": False}],
            now=NOW,
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["review"]["decision"], DECISION_REJECTED)

    def test_a_field_the_user_did_not_mention_is_left_alone(self):
        reviewed = apply_review(
            self.fields,
            [{"key": "haemoglobin", "value": "13.2"}],
            now=NOW,
        )

        glucose = next(f for f in reviewed if f["key"] == "glucose")

        self.assertEqual(glucose["review"]["decision"], DECISION_PENDING)
        self.assertEqual(len(reviewed), 2)

    def test_a_user_added_field_is_recorded_as_their_own(self):
        reviewed = apply_review(
            self.fields,
            [{"key": "vitamin_d", "label": "Vitamin D", "value": "22", "unit": "ng/mL"}],
            now=NOW,
        )

        added = next(f for f in reviewed if f["key"] == "vitamin_d")

        self.assertEqual(added["provenance"]["source"], SOURCE_USER_ENTRY)
        self.assertIsNone(added["candidate"]["value"])
        self.assertEqual(added["review"]["decision"], DECISION_CORRECTED)

    def test_a_user_added_field_needs_a_label(self):
        with self.assertRaises(ReportValidationError):
            apply_review(
                self.fields, [{"key": "mystery", "value": "1"}], now=NOW
            )

    def test_a_duplicate_key_in_one_submission_is_refused(self):
        with self.assertRaises(ReportValidationError):
            apply_review(
                self.fields,
                [
                    {"key": "haemoglobin", "value": "13.2"},
                    {"key": "haemoglobin", "value": "13.4"},
                ],
                now=NOW,
            )

    def test_whitespace_alone_is_not_a_correction(self):
        reviewed = apply_review(
            self.fields,
            [dict(UNCHANGED_HAEMOGLOBIN, value="  13.2  ")],
            now=NOW,
        )

        haemoglobin = next(f for f in reviewed if f["key"] == "haemoglobin")

        self.assertEqual(haemoglobin["review"]["decision"], DECISION_ACCEPTED)


class TrustBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fields, _ = build_candidate_fields(
            [candidate(), glucose_candidate()], provenance=PROVENANCE
        )

    def review_everything(self, include_glucose=True):
        return apply_review(
            self.fields,
            [
                dict(UNCHANGED_HAEMOGLOBIN),
                dict(UNCHANGED_GLUCOSE, include=include_glucose),
            ],
            now=NOW,
        )

    def test_nothing_is_confirmed_before_review(self):
        self.assertEqual(confirmed_values(self.fields), [])

    def test_an_unreviewed_report_cannot_be_confirmed(self):
        ready, reason = can_confirm(self.fields)

        self.assertFalse(ready)
        self.assertIn("still need to be checked", reason)

    def test_a_fully_reviewed_report_can_be_confirmed(self):
        ready, reason = can_confirm(self.review_everything())

        self.assertTrue(ready)
        self.assertIsNone(reason)

    def test_a_partly_reviewed_report_cannot_be_confirmed(self):
        partial = apply_review(
            self.fields, [dict(UNCHANGED_HAEMOGLOBIN)], now=NOW
        )

        ready, reason = can_confirm(partial)

        self.assertFalse(ready)
        self.assertIn("1 of 2", reason)

    def test_a_report_with_everything_rejected_cannot_be_confirmed(self):
        emptied = apply_review(
            self.fields,
            [
                dict(UNCHANGED_HAEMOGLOBIN, include=False),
                dict(UNCHANGED_GLUCOSE, include=False),
            ],
            now=NOW,
        )

        ready, reason = can_confirm(emptied)

        self.assertFalse(ready)
        self.assertIn("nothing left", reason)

    def test_an_empty_report_cannot_be_confirmed(self):
        ready, reason = can_confirm([])

        self.assertFalse(ready)
        self.assertIn("nothing to confirm", reason)

    def test_rejected_values_are_absent_from_the_confirmed_set(self):
        values = confirmed_values(self.review_everything(include_glucose=False))

        self.assertEqual([value["key"] for value in values], ["haemoglobin"])

    def test_a_confirmed_value_says_whether_it_was_corrected(self):
        reviewed = apply_review(
            self.fields,
            [
                dict(UNCHANGED_HAEMOGLOBIN, value="13.9"),
                dict(UNCHANGED_GLUCOSE),
            ],
            now=NOW,
        )

        values = {value["key"]: value for value in confirmed_values(reviewed)}

        self.assertTrue(values["haemoglobin"]["was_corrected"])
        self.assertEqual(values["haemoglobin"]["value"], "13.9")
        self.assertEqual(values["haemoglobin"]["candidate_value"], "13.2")
        self.assertFalse(values["glucose"]["was_corrected"])

    def test_progress_counts_every_decision(self):
        progress = review_progress(self.review_everything(include_glucose=False))

        self.assertEqual(progress["total"], 2)
        self.assertEqual(progress["pending"], 0)
        self.assertEqual(progress["accepted"], 1)
        self.assertEqual(progress["rejected"], 1)
        self.assertEqual(progress["included"], 1)


class StatusTests(unittest.TestCase):
    def test_only_confirmed_is_trusted(self):
        self.assertTrue(is_trusted(STATUS_CONFIRMED))

        for status in (
            STATUS_UPLOADED,
            STATUS_PROCESSING,
            STATUS_NEEDS_REVIEW,
            STATUS_FAILED,
            "extracted",
        ):
            with self.subTest(status=status):
                self.assertFalse(is_trusted(status))

    def test_a_report_cannot_jump_straight_to_confirmed(self):
        for status in (STATUS_UPLOADED, STATUS_PROCESSING, STATUS_FAILED):
            with self.subTest(status=status):
                with self.assertRaises(ReportValidationError):
                    check_transition(status, STATUS_CONFIRMED)

    def test_review_can_lead_to_confirmed(self):
        check_transition(STATUS_NEEDS_REVIEW, STATUS_CONFIRMED)

    def test_a_confirmed_report_can_be_reopened(self):
        check_transition(STATUS_CONFIRMED, STATUS_NEEDS_REVIEW)

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(ReportValidationError):
            check_transition(STATUS_NEEDS_REVIEW, "verified")


class DocumentTests(unittest.TestCase):
    def file_record(self):
        return {"key": "a" * 24 + "/" + "b" * 32 + ".pdf",
                "size_bytes": 2048, "extension": ".pdf"}

    def test_an_uploaded_report_starts_uploaded_with_no_fields(self):
        document = build_report_document(
            user_id="a" * 24,
            title="Blood test",
            report_date="2026-08-01T00:00:00.000Z",
            facility="City Lab",
            file_record=self.file_record(),
            source="upload",
            now=NOW,
        )

        self.assertEqual(document["status"], STATUS_UPLOADED)
        self.assertEqual(document["fields"], [])
        self.assertIsNone(document["confirmed_at"])
        self.assertIsNone(document["review_submitted_at"])

    def test_a_manual_report_starts_in_review_and_needs_no_file(self):
        document = build_report_document(
            user_id="a" * 24,
            title=None,
            report_date=None,
            facility=None,
            file_record=None,
            source="manual_entry",
            now=NOW,
        )

        self.assertEqual(document["status"], STATUS_NEEDS_REVIEW)
        self.assertIsNone(document["file"])

    def test_an_uploaded_report_without_a_file_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_report_document(
                user_id="a" * 24,
                title=None,
                report_date=None,
                facility=None,
                file_record=None,
                source="upload",
                now=NOW,
            )

    def test_a_report_keeps_the_condition_it_was_uploaded_against(self):
        document = build_report_document(
            user_id="a" * 24,
            title=None,
            report_date=None,
            facility=None,
            file_record=self.file_record(),
            source="upload",
            now=NOW,
            condition="diabetes",
        )

        self.assertEqual(document["condition"], "diabetes")

    def test_a_report_without_a_condition_stores_none(self):
        document = build_report_document(
            user_id="a" * 24,
            title=None,
            report_date=None,
            facility=None,
            file_record=self.file_record(),
            source="upload",
            now=NOW,
            condition="  ",
        )

        self.assertIsNone(document["condition"])

    def test_an_unknown_condition_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_report_document(
                user_id="a" * 24,
                title=None,
                report_date=None,
                facility=None,
                file_record=self.file_record(),
                source="upload",
                now=NOW,
                condition="cancer",
            )

    def test_a_trailing_z_date_is_accepted(self):
        # What JavaScript's toISOString produces; Python 3.10 will not parse it
        # without help.
        document = build_report_document(
            user_id="a" * 24,
            title=None,
            report_date="2026-08-01T00:00:00.000Z",
            facility=None,
            file_record=self.file_record(),
            source="upload",
            now=NOW,
        )

        self.assertEqual(document["report_date"].year, 2026)
        self.assertIsNotNone(document["report_date"].tzinfo)

    def test_an_unparseable_date_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_report_document(
                user_id="a" * 24,
                title=None,
                report_date="last tuesday",
                facility=None,
                file_record=self.file_record(),
                source="upload",
                now=NOW,
            )

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(ReportValidationError):
            build_report_document(
                user_id="a" * 24,
                title=None,
                report_date=None,
                facility=None,
                file_record=None,
                source="imported",
                now=NOW,
            )

    def test_a_default_category_is_applied(self):
        field = build_candidate_field(
            candidate(category=None), provenance=PROVENANCE
        )

        self.assertEqual(field["category"], CATEGORY_LAB_RESULT)


if __name__ == "__main__":
    unittest.main()
