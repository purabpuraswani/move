import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from database import SQLiteClient
import assessments.store as store
from assessments.schema import validate_assessment_payload
from routes.assessments import create_assessment
from user_state.schema import build_user_state
from workflow.response import serialise_workflow_state

SUBMISSION_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "assessment"
    / "fixtures"
    / "active-assessment-submission.json"
)


def payload(session_id="f6af5a0d-9f2a-4d2b-97b2-62c9172ac7b9"):
    actual_frontend_payload = json.loads(SUBMISSION_FIXTURE.read_text(encoding="utf-8"))
    actual_frontend_payload["sessionId"] = session_id
    return actual_frontend_payload


class ActiveAssessmentRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.client = SQLiteClient(Path(self.directory.name) / "assessments.sqlite3")
        self.collection = self.client["assessments"]
        self.patcher = patch.object(store, "assessments_collection", self.collection)
        self.patcher.start()
        store.ensure_indexes()

    def tearDown(self):
        self.patcher.stop()
        self.client.close()
        self.directory.cleanup()

    def test_both_measurements_round_trip_history_and_user_state_from_latest_session(self):
        request_payload = payload()
        self.assertEqual(set(request_payload["tests"]), {"shoulder", "balance"})
        self.assertNotIn("ftsst", request_payload["tests"])

        # Exercise the route used by POST /api/assessments with the exact
        # serialized payload emitted by frontend toStoredPayload().
        response = create_assessment(request_payload, current_user={"_id": "user-a"})
        self.assertEqual(response["message"], "Assessment saved")
        latest = store.latest_assessment("user-a")
        listed = store.list_assessments("user-a")
        public = store.serialise_assessment(latest)
        state = build_user_state(assessment_doc=latest)
        plan_readiness = serialise_workflow_state(state)["assessment_summary"]

        self.assertEqual(store.count_assessments("user-a"), 1)
        self.assertEqual(set(public["tests"]), {"shoulder", "balance"})
        self.assertEqual(public["tests"]["shoulder"]["measurements"]["left"]["finalElevationDeg"], 151.5)
        self.assertEqual(public["tests"]["balance"]["measurements"]["left"]["holdDurationSeconds"], 30.0)
        self.assertEqual(listed[0]["tests"]["balance"]["status"], "completed")
        self.assertEqual(state["physical_assessment"]["data"]["session_id"], latest["session_id"])
        self.assertEqual(
            state["physical_assessment"]["data"]["tests"]["balance"]["measurements"]["right"]["holdDurationSeconds"],
            29.7,
        )
        self.assertEqual(plan_readiness["status"], "COMPLETE")
        self.assertEqual(plan_readiness["tests_completed"], 2)
        self.assertEqual(plan_readiness["tests_total"], 2)
        self.assertEqual(set(plan_readiness["completed_tests"]), {"shoulder", "balance"})

    def test_missing_one_leg_measurement_is_rejected(self):
        incomplete = payload()
        del incomplete["tests"]["balance"]

        with self.assertRaisesRegex(ValueError, "tests is missing: balance"):
            validate_assessment_payload(incomplete)

    def test_retry_updates_the_same_session_and_same_session_id_is_user_scoped(self):
        first = store.save_assessment("user-a", validate_assessment_payload(payload()))
        retry = store.save_assessment("user-a", validate_assessment_payload(payload()))
        other_user = store.save_assessment("user-b", validate_assessment_payload(payload()))

        self.assertTrue(first["created"])
        self.assertFalse(retry["created"])
        self.assertNotEqual(first["document"]["_id"], other_user["document"]["_id"])
        self.assertEqual(store.count_assessments("user-a"), 1)
        self.assertEqual(store.count_assessments("user-b"), 1)

    def test_progress_reads_whole_measurement_session_and_skips_newer_invalid_session(self):
        valid_payload = payload(session_id="valid-session")
        valid_payload["startedAt"] = "2026-10-01T09:00:00+00:00"
        valid_payload["completedAt"] = "2026-10-01T10:00:00+00:00"
        store.save_assessment("user-a", validate_assessment_payload(valid_payload))

        invalid_payload = payload(session_id="invalid-session")
        invalid_payload["startedAt"] = "2026-10-02T10:00:00+00:00"
        invalid_payload["completedAt"] = None
        invalid_payload["tests"]["shoulder"] = {"status": "not_started", "measurements": None}
        invalid_payload["tests"]["balance"] = {"status": "not_started", "measurements": None}
        store.save_assessment("user-a", validate_assessment_payload(invalid_payload))

        history = store.list_assessments_with_measurements("user-a")
        self.assertEqual(store.latest_valid_assessment("user-a")["session_id"], "valid-session")
        self.assertIn("measurements", history[0]["tests"]["shoulder"])

        from progress_agent.series import build_progress_series
        series = build_progress_series(assessment_documents=history)
        current = series["latestAssessment"]
        self.assertEqual(current["sessionId"], "valid-session")
        self.assertEqual(current["shoulder"]["measurements"]["left"]["finalElevationDeg"], 151.5)
        self.assertEqual(current["balance"]["measurements"]["right"]["holdDurationSeconds"], 29.7)

        metrics = {item["metric"]: item for item in series["movementMetrics"]}
        self.assertEqual(metrics["mobility_shoulder_elevation_deg"]["points"][0]["sessionId"], "valid-session")
        self.assertEqual(metrics["mobility_shoulder_elevation_deg"]["point_count"], 1)
        self.assertFalse(metrics["mobility_shoulder_elevation_deg"]["plottable"])


if __name__ == "__main__":
    unittest.main()
