"""End-to-end tests for the Medical Report Reader pipeline.

Every other file in this test directory tests one module in isolation.
Nothing, before this file, exercised the actual sequence a report goes
through: upload -> store the file -> extract candidate values -> save them
as needs_review -> the user reviews them -> the user confirms them -> the
confirmed values reach the shape user_state.schema.build_user_state()
reads as medical_context.data.confirmed_reports. That gap is exactly where
a wiring mistake between two individually-correct modules would go
unnoticed, so this file exists to close it.

Two things are faked, and both are faked the same way the rest of this
project fakes an external dependency (see physio_agent/tool_client.py's
InProcessProgressToolClient, and reports/extraction.py's own transport=
parameter, built for exactly this purpose): the MongoDB collection
(tests/_fake_mongo.py) and the OpenRouter HTTP transport. Nothing about
reports/schema.py, reports/store.py, reports/extraction.py or
reports/storage.py is modified or reimplemented to make these tests pass;
they run the real modules.

No live network call is made anywhere in this file, and none of the AI
extraction it exercises is faked to produce a value that was not present in
the input: the fake transport below returns literally the same three
values (diagnosis, medication, allergy) that are printed in the synthetic
fixture PDF built by synthetic_report_pdf(), and the assertions check that
those values, and only those values, survive the pipeline.
"""

import importlib.util
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from reports import extraction, storage
from reports.schema import (
    STATUS_CONFIRMED,
    STATUS_NEEDS_REVIEW,
    STATUS_PROCESSING,
    STATUS_UPLOADED,
    SOURCE_AI_EXTRACTION,
    apply_review,
    build_report_document,
)
from user_state.schema import build_user_state

# reports/store.py (and tests/_fake_mongo.py, which mirrors its ObjectId
# usage) needs pymongo/bson and a reachable `database.db` handle — none of
# which is installed in this sandbox (no PyPI network access, the same,
# already-documented constraint as the `mcp` package since Phase 2). The
# module-level import below is therefore guarded exactly like every real
# MCP-transport integration test in this suite
# (tests/test_physio_agent_mcp_integration.py, tests/test_progress_mcp_integration.py):
# skip honestly, never silently, and never by faking a passing result.
REPORT_STORE_AVAILABLE = (
    importlib.util.find_spec("pymongo") is not None
    and importlib.util.find_spec("bson") is not None
)

REPORT_STORE_SKIP_REASON = (
    "pymongo/bson are not installed in this environment (no PyPI network "
    "access in this sandbox); install them in the project's real .venv "
    "(where reports/store.py already runs against a real MongoDB) to run "
    "these full-chain tests instead of skipping them"
)

if REPORT_STORE_AVAILABLE:
    from reports import store as report_store
    from tests._fake_mongo import FakeReportsCollection

USER_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_USER_ID = "bbbbbbbbbbbbbbbbbbbbbbbb"

# The three facts the whole test file is built around. Every assertion below
# traces back to these three literal strings so a test that passes for the
# wrong reason (a hard-coded field somewhere) is easy to notice.
DIAGNOSIS_TEXT = "Diagnosis: Type 2 Diabetes."
MEDICATION_TEXT = "Medications: Metformin."
ALLERGY_TEXT = "Allergies: Penicillin."


def synthetic_report_pdf() -> bytes:
    """A minimal, clearly-synthetic one-page PDF for pipeline tests.

    Built by hand rather than with a PDF library (none is a project
    dependency, and adding one only to generate a test fixture is not
    justified). It is a real, structurally valid single-page PDF with an
    uncompressed content stream, so the three lines of text below are
    present as literal bytes in the file — this is fabricated test data
    about a fabricated patient, not any real person's report.
    """

    lines = [DIAGNOSIS_TEXT, MEDICATION_TEXT, ALLERGY_TEXT]
    stream_ops = ["BT", "/F1 12 Tf", "72 720 Td"]

    for index, line in enumerate(lines):
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

        if index > 0:
            stream_ops.append("0 -18 Td")

        stream_ops.append(f"({escaped}) Tj")

    stream_ops.append("ET")
    stream = "\n".join(stream_ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("latin-1")
        out += body
        out += b"\nendobj\n"

    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"

    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")

    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode("latin-1")

    return bytes(out)


def fake_openrouter_response(fields: list) -> tuple:
    """A (status, body) pair shaped like a real OpenRouter tool-call reply."""

    body = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "record_transcribed_fields",
                                "arguments": json.dumps(
                                    {
                                        "document_readable": True,
                                        "document_note": "",
                                        "fields": fields,
                                    }
                                ),
                            },
                        }
                    ],
                },
            }
        ]
    }

    return 200, json.dumps(body)


def synthetic_extraction_transport(_url, _headers, _payload, _timeout):
    """Stands in for the OpenRouter HTTP call.

    This is the one point in the whole test file that decides what "the AI
    read off the document" was, and it is fixed to transcribe exactly the
    three lines synthetic_report_pdf() prints — nothing more, nothing
    invented — the same discipline reports/extraction.py's own SYSTEM_PROMPT
    asks of the real model.
    """

    return fake_openrouter_response(
        [
            {
                "key": "diagnosis",
                "label": "Diagnosis",
                "category": "diagnosis_listed_on_report",
                "value": "Type 2 Diabetes",
                "quoted_text": DIAGNOSIS_TEXT,
                "page": 1,
                "confidence": 0.97,
            },
            {
                "key": "medications",
                "label": "Medications",
                "category": "medication",
                "value": "Metformin",
                "quoted_text": MEDICATION_TEXT,
                "page": 1,
                "confidence": 0.95,
            },
            {
                "key": "allergies",
                "label": "Allergies",
                "category": "clinical_note_text",
                "value": "Penicillin",
                "quoted_text": ALLERGY_TEXT,
                "page": 1,
                "confidence": 0.9,
            },
        ]
    )


@unittest.skipUnless(REPORT_STORE_AVAILABLE, REPORT_STORE_SKIP_REASON)
class ReportPipelineTestCase(unittest.TestCase):
    """Common fixture: a fake collection standing in for MongoDB, and a
    real LocalReportStorage pointed at a throwaway directory standing in
    for the uploads folder.

    skipUnless is on this base class only — unittest still discovers and
    correctly skips every subclass (FullChainTests, NoConfirmationNoTrustTests)
    since they inherit setUp from here and never override the decorator away.
    """

    def setUp(self):
        self.fake_collection = FakeReportsCollection()

        self._collection_patch = mock.patch.object(
            report_store, "reports_collection", self.fake_collection
        )
        self._collection_patch.start()
        self.addCleanup(self._collection_patch.stop)

        self.storage_dir = tempfile.mkdtemp(prefix="movewell_reports_test_")
        self.addCleanup(shutil.rmtree, self.storage_dir, ignore_errors=True)
        self.storage = storage.LocalReportStorage(root=self.storage_dir)

    def _upload(self, user_id=USER_ID):
        pdf_bytes = synthetic_report_pdf()

        stream = mock.Mock()
        stream.read = mock.Mock(side_effect=[pdf_bytes, b""])

        stored_file = self.storage.save(user_id, "blood_test.pdf", stream)

        now = datetime.now(timezone.utc)
        document = build_report_document(
            user_id=user_id,
            title="Blood test",
            report_date=None,
            facility="Synthetic Test Clinic",
            file_record=stored_file.as_record(),
            source="upload",
            now=now,
        )

        return report_store.create_report(document), pdf_bytes


class FullChainTests(ReportPipelineTestCase):
    """Upload -> extract -> review -> confirm -> User State."""

    def test_the_full_chain_from_upload_to_confirmed_user_state(self):
        stored, pdf_bytes = self._upload()
        report_id = stored["_id"]

        self.assertEqual(stored["status"], STATUS_UPLOADED)
        self.assertIn(DIAGNOSIS_TEXT.encode("latin-1"), pdf_bytes)

        # The extraction step: read the file back off storage (the same
        # bytes that were uploaded), and transcribe it with a fake transport
        # standing in for the network call to OpenRouter.
        report_store.mark_extraction_started(USER_ID, report_id, STATUS_PROCESSING)

        read_back = self.storage.read_bytes(stored["file"]["key"])
        self.assertEqual(read_back, pdf_bytes)

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=synthetic_extraction_transport
        )
        result = extraction.extract_candidates(read_back, ".pdf", provider=provider)

        self.assertEqual(len(result["fields"]), 3)
        self.assertEqual(result["rejected"], [])

        extracted = report_store.save_extraction_result(USER_ID, report_id, result)

        self.assertEqual(extracted["status"], STATUS_NEEDS_REVIEW)
        self.assertEqual(len(extracted["fields"]), 3)

        for field in extracted["fields"]:
            self.assertEqual(field["review"]["decision"], "pending")
            self.assertEqual(
                field["provenance"]["source"], SOURCE_AI_EXTRACTION
            )

        # Nothing is confirmed yet, at any layer.
        self.assertEqual(
            report_store.confirmed_values_for_user(USER_ID),
            {"hasConfirmedReports": False, "reportCount": 0, "reports": []},
        )

        with self.assertRaises(report_store.ReportStateError):
            report_store.confirm_report(USER_ID, report_id)

        # The user reviews every value and accepts it unchanged.
        submitted = [
            {"key": field["key"], "label": field["label"], "value": field["candidate"]["value"], "include": True}
            for field in extracted["fields"]
        ]
        reviewed_fields = apply_review(extracted["fields"], submitted, now=datetime.now(timezone.utc))
        reviewed = report_store.save_review(USER_ID, report_id, reviewed_fields)

        self.assertEqual(reviewed["status"], STATUS_NEEDS_REVIEW)
        self.assertIsNotNone(reviewed["review_submitted_at"])

        for field in reviewed["fields"]:
            self.assertEqual(field["review"]["decision"], "accepted")

        # Confirmation: the only place a report crosses the trust boundary.
        confirmed = report_store.confirm_report(USER_ID, report_id)

        self.assertEqual(confirmed["status"], STATUS_CONFIRMED)
        self.assertIsNotNone(confirmed["confirmed_at"])

        # What anything downstream (Physio/Nutrition/Behaviour input
        # contracts, via User State) is allowed to read.
        confirmed_values = report_store.confirmed_values_for_user(USER_ID)

        self.assertTrue(confirmed_values["hasConfirmedReports"])
        self.assertEqual(confirmed_values["reportCount"], 1)

        values_by_label = {
            value["label"]: value["value"]
            for value in confirmed_values["reports"][0]["values"]
        }
        self.assertEqual(
            values_by_label,
            {
                "Diagnosis": "Type 2 Diabetes",
                "Medications": "Metformin",
                "Allergies": "Penicillin",
            },
        )
        self.assertTrue(
            all(
                value["originalSource"] == SOURCE_AI_EXTRACTION
                and value["wasCorrectedByUser"] is False
                for value in confirmed_values["reports"][0]["values"]
            )
        )

        # The exact wiring other Phase 3/4 agents rely on: User State's
        # medical_context.data.confirmed_reports, built from this same
        # confirmed_values_for_user() shape (see user_state/schema.py's
        # _build_medical_context, and physio_agent/input_contract.py's
        # docstring, which reads confirmed_medical_context from exactly
        # this path).
        user_state = build_user_state(
            profile_doc=None, confirmed_reports_doc=confirmed_values
        )
        medical_context = user_state["medical_context"]

        self.assertTrue(medical_context["available"])
        reports_in_state = medical_context["data"]["confirmed_reports"]["reports"]
        self.assertEqual(len(reports_in_state), 1)

        state_values_by_label = {
            value["label"]: value["value"] for value in reports_in_state[0]["values"]
        }
        self.assertEqual(
            state_values_by_label,
            {
                "Diagnosis": "Type 2 Diabetes",
                "Medications": "Metformin",
                "Allergies": "Penicillin",
            },
        )

    def test_a_correction_during_review_overrides_the_candidate_in_confirmed_values(self):
        stored, pdf_bytes = self._upload()
        report_id = stored["_id"]

        report_store.mark_extraction_started(USER_ID, report_id, STATUS_PROCESSING)

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=synthetic_extraction_transport
        )
        result = extraction.extract_candidates(pdf_bytes, ".pdf", provider=provider)
        extracted = report_store.save_extraction_result(USER_ID, report_id, result)

        # The user corrects the medication field (a misread drug name) and
        # rejects the allergy field (not actually on their copy).
        submitted = [
            {"key": "diagnosis", "label": "Diagnosis", "value": "Type 2 Diabetes", "include": True},
            {"key": "medications", "label": "Medications", "value": "Metformin XR", "include": True},
            {"key": "allergies", "label": "Allergies", "value": "Penicillin", "include": False},
        ]
        reviewed_fields = apply_review(extracted["fields"], submitted, now=datetime.now(timezone.utc))
        report_store.save_review(USER_ID, report_id, reviewed_fields)
        report_store.confirm_report(USER_ID, report_id)

        confirmed_values = report_store.confirmed_values_for_user(USER_ID)
        values = confirmed_values["reports"][0]["values"]
        by_label = {value["label"]: value for value in values}

        # The rejected field never crosses the trust boundary at all.
        self.assertNotIn("Allergies", by_label)

        # The corrected field carries the user's value, not the candidate's,
        # and is marked as a correction rather than an acceptance.
        self.assertEqual(by_label["Medications"]["value"], "Metformin XR")
        self.assertTrue(by_label["Medications"]["wasCorrectedByUser"])


class NoConfirmationNoTrustTests(ReportPipelineTestCase):
    """Uploading (and even extracting) a report alone must never create
    confirmed medical context. Only an explicit confirm does."""

    def test_upload_and_extraction_alone_create_no_confirmed_context(self):
        stored, pdf_bytes = self._upload()
        report_id = stored["_id"]

        report_store.mark_extraction_started(USER_ID, report_id, STATUS_PROCESSING)

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=synthetic_extraction_transport
        )
        result = extraction.extract_candidates(pdf_bytes, ".pdf", provider=provider)
        extracted = report_store.save_extraction_result(USER_ID, report_id, result)

        self.assertEqual(extracted["status"], STATUS_NEEDS_REVIEW)
        self.assertEqual(len(extracted["fields"]), 3)

        confirmed_values = report_store.confirmed_values_for_user(USER_ID)
        self.assertFalse(confirmed_values["hasConfirmedReports"])
        self.assertEqual(confirmed_values["reportCount"], 0)
        self.assertEqual(confirmed_values["reports"], [])

        user_state = build_user_state(
            profile_doc=None, confirmed_reports_doc=confirmed_values
        )
        # No self-reported checklist and no confirmed report: the section is
        # unavailable, not populated with the unconfirmed candidate values.
        self.assertFalse(user_state["medical_context"]["available"])

    def test_saving_a_review_without_confirming_creates_no_confirmed_context(self):
        stored, pdf_bytes = self._upload()
        report_id = stored["_id"]

        report_store.mark_extraction_started(USER_ID, report_id, STATUS_PROCESSING)

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=synthetic_extraction_transport
        )
        result = extraction.extract_candidates(pdf_bytes, ".pdf", provider=provider)
        extracted = report_store.save_extraction_result(USER_ID, report_id, result)

        submitted = [
            {"key": field["key"], "label": field["label"], "value": field["candidate"]["value"], "include": True}
            for field in extracted["fields"]
        ]
        reviewed_fields = apply_review(extracted["fields"], submitted, now=datetime.now(timezone.utc))
        # Saved, but never confirmed.
        report_store.save_review(USER_ID, report_id, reviewed_fields)

        confirmed_values = report_store.confirmed_values_for_user(USER_ID)
        self.assertFalse(confirmed_values["hasConfirmedReports"])
        self.assertEqual(confirmed_values["reports"], [])

    def test_a_report_belonging_to_another_user_is_invisible(self):
        stored, _pdf_bytes = self._upload(user_id=USER_ID)
        report_id = stored["_id"]

        report_store.mark_extraction_started(USER_ID, report_id, STATUS_PROCESSING)

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=synthetic_extraction_transport
        )
        result = extraction.extract_candidates(
            synthetic_report_pdf(), ".pdf", provider=provider
        )
        extracted = report_store.save_extraction_result(USER_ID, report_id, result)

        submitted = [
            {"key": field["key"], "label": field["label"], "value": field["candidate"]["value"], "include": True}
            for field in extracted["fields"]
        ]
        reviewed_fields = apply_review(extracted["fields"], submitted, now=datetime.now(timezone.utc))
        report_store.save_review(USER_ID, report_id, reviewed_fields)
        report_store.confirm_report(USER_ID, report_id)

        # Confirmed for USER_ID, but a different user reads nothing.
        self.assertTrue(report_store.confirmed_values_for_user(USER_ID)["hasConfirmedReports"])
        self.assertFalse(
            report_store.confirmed_values_for_user(OTHER_USER_ID)["hasConfirmedReports"]
        )

        with self.assertRaises(report_store.ReportNotFoundError):
            report_store.get_report(OTHER_USER_ID, report_id)


class ExtractionUnavailableTests(unittest.TestCase):
    """The honest path: no provider configured, no invented data."""

    def test_no_api_key_raises_extraction_unavailable_not_a_fake_success(self):
        # BOTH provider keys must be cleared. Nulling only OPENROUTER_API_KEY
        # used to be enough because OpenRouter was the only provider; now a
        # GEMINI_API_KEY in the developer's own .env would leave a working
        # provider in place and this test would assert nothing. Patching both
        # makes it independent of whatever is configured on the machine
        # running the suite, which is what it was always meant to check.
        with mock.patch.object(extraction, "OPENROUTER_API_KEY", None), \
             mock.patch.object(extraction, "GEMINI_API_KEY", None):
            provider = extraction.select_provider()

            self.assertFalse(provider.available)

            with self.assertRaises(extraction.ExtractionUnavailable):
                extraction.extract_candidates(
                    synthetic_report_pdf(), ".pdf", provider=provider
                )

            status = extraction.extraction_status()

        self.assertFalse(status["available"])
        self.assertIsNone(status["provider"])
        self.assertIsNotNone(status["reason"])

    def test_ai_provider_none_is_honestly_unavailable(self):
        with mock.patch.object(extraction, "AI_PROVIDER", "none"):
            provider = extraction.select_provider()

            self.assertFalse(provider.available)

            with self.assertRaises(extraction.ExtractionUnavailable):
                extraction.extract_candidates(
                    synthetic_report_pdf(), ".pdf", provider=provider
                )

    def test_a_provider_http_failure_never_produces_fields_silently(self):
        def failing_transport(_url, _headers, _payload, _timeout):
            return 500, json.dumps({"error": {"message": "upstream is down"}})

        provider = extraction.OpenRouterProvider(
            api_key="sk-or-test-key", transport=failing_transport
        )

        with self.assertRaises(extraction.ExtractionFailed):
            extraction.extract_candidates(
                synthetic_report_pdf(), ".pdf", provider=provider
            )


if __name__ == "__main__":
    unittest.main()
