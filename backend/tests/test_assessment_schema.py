"""Tests for assessment payload validation.

These run on the standard library alone (python -m unittest), because
assessments/schema.py deliberately imports nothing outside it. That keeps the
rules that protect the database testable without a database, a web framework,
or a network connection to install either.
"""

import copy
import sys
import unittest
from pathlib import Path

# Allows running as "python -m unittest discover" from either backend/ or the
# repository root.
BACKEND_ROOT = Path(__file__).resolve().parent.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from assessments.schema import (  # noqa: E402
    MAX_ARRAY_LENGTH,
    AssessmentValidationError,
    validate_assessment_payload,
)


def valid_payload(**overrides) -> dict:
    """A payload shaped exactly like toStoredPayload() in the browser."""

    payload = {
        "sessionId": "b1b0f2f4-1f1e-4a1e-9c6d-2f5c7a0d9e11",
        "protocolVersion": "1.0.0",
        "startedAt": "2026-08-26T09:15:00.000Z",
        "completedAt": "2026-08-26T09:19:42.000Z",
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
                    "left": {
                        "finalElevationDeg": 148.2,
                        "repetitionCount": 3,
                        "repetitionElevationsDeg": [147.1, 148.2, 149.0],
                    },
                    "right": {
                        "finalElevationDeg": 141.6,
                        "repetitionCount": 3,
                        "repetitionElevationsDeg": [140.2, 141.6, 142.4],
                    },
                    "observableDifferenceDeg": 6.6,
                },
                "quality": {
                    "framesSeen": 188,
                    "framesUsable": 181,
                    "usableFrameRatio": 0.963,
                    "fps": 27.4,
                    "lowFps": False,
                    "longestPoseLossMs": 132,
                    "meanKeypointScore": 0.71,
                },
                "invalidReasons": [],
                "attempts": 1,
            },
            "ftsst": {
                "status": "completed",
                "measurements": {
                    "completionTimeMs": 9420,
                    "completionTimeSeconds": 9.42,
                    "repetitionsDetected": 5,
                    "requiredRepetitions": 5,
                    "standTimestampsMs": [1200, 3010, 4820, 6640, 8460],
                },
                "quality": {"framesSeen": 300, "usableFrameRatio": 0.98},
                "invalidReasons": [],
                "attempts": 1,
                "setup": {
                    "chairSeatHeightCm": 45,
                    "chairSeatHeightPlausible": True,
                    "measuredSide": "right",
                    "cameraView": "side",
                    "armsPosition": "crossed",
                    "warnings": [],
                },
            },
            "balance": {
                "status": "skipped",
                "measurements": None,
                "quality": None,
                "invalidReasons": [],
                "attempts": 0,
            },
        },
    }

    payload.update(overrides)

    return payload


class ValidPayloadTests(unittest.TestCase):
    def test_a_well_formed_payload_is_accepted(self):
        document = validate_assessment_payload(valid_payload())

        self.assertEqual(document["session_id"], "b1b0f2f4-1f1e-4a1e-9c6d-2f5c7a0d9e11")
        self.assertEqual(document["protocol_version"], "1.0.0")
        self.assertEqual(document["tests"]["shoulder"]["status"], "completed")
        self.assertAlmostEqual(
            document["tests"]["shoulder"]["measurements"]["left"]["finalElevationDeg"],
            148.2,
        )

    def test_the_protocol_version_is_stored_so_a_result_stays_interpretable(self):
        document = validate_assessment_payload(
            valid_payload(protocolVersion="2.3.1-beta")
        )

        self.assertEqual(document["protocol_version"], "2.3.1-beta")

    def test_frame_counts_in_quality_metadata_are_kept(self):
        # framesSeen and framesUsable are counts, not frames. An over-broad
        # privacy filter would reject them and quietly lose the only record of
        # how good the recording conditions were.
        document = validate_assessment_payload(valid_payload())
        quality = document["tests"]["shoulder"]["quality"]

        self.assertEqual(quality["framesSeen"], 188)
        self.assertEqual(quality["framesUsable"], 181)

    def test_setup_metadata_survives_validation(self):
        document = validate_assessment_payload(valid_payload())

        self.assertEqual(document["tests"]["ftsst"]["setup"]["chairSeatHeightCm"], 45)

    def test_a_test_without_setup_does_not_gain_an_empty_one(self):
        document = validate_assessment_payload(valid_payload())

        self.assertNotIn("setup", document["tests"]["shoulder"])

    def test_timestamps_become_datetimes(self):
        document = validate_assessment_payload(valid_payload())

        self.assertEqual(document["started_at"].year, 2026)
        self.assertEqual(document["started_at"].hour, 9)
        self.assertIsNotNone(document["started_at"].tzinfo)

    def test_an_unfinished_session_may_have_no_completed_at(self):
        document = validate_assessment_payload(valid_payload(completedAt=None))

        self.assertIsNone(document["completed_at"])

    def test_optional_client_notes_are_accepted(self):
        document = validate_assessment_payload(
            valid_payload(client={"viewportWidth": 1440, "cameraLabel": "FaceTime HD"})
        )

        self.assertEqual(document["client"]["viewportWidth"], 1440)


class SkippedIsNotZeroTests(unittest.TestCase):
    def test_a_skipped_test_is_stored_as_skipped_with_no_measurements(self):
        document = validate_assessment_payload(valid_payload())
        balance = document["tests"]["balance"]

        self.assertEqual(balance["status"], "skipped")
        self.assertIsNone(balance["measurements"])
        self.assertNotEqual(balance["measurements"], 0)

    def test_a_skipped_test_carrying_measurements_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["balance"]["measurements"] = {"holdDurationMs": 0}

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("never be stored as zero", str(caught.exception))

    def test_a_not_started_test_carrying_measurements_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["balance"]["status"] = "not_started"
        payload["tests"]["balance"]["measurements"] = {"holdDurationMs": 0}

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_a_completed_test_must_actually_carry_measurements(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["measurements"] = None

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_an_invalid_test_keeps_its_numbers_but_not_its_status(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["status"] = "invalid"
        payload["tests"]["shoulder"]["invalidReasons"] = ["insufficient_repetitions"]

        document = validate_assessment_payload(payload)

        self.assertEqual(document["tests"]["shoulder"]["status"], "invalid")
        self.assertIsNotNone(document["tests"]["shoulder"]["measurements"])
        self.assertEqual(
            document["tests"]["shoulder"]["invalid_reasons"],
            ["insufficient_repetitions"],
        )


class PoseDataIsRejectedTests(unittest.TestCase):
    def test_a_keypoint_field_is_rejected_however_it_is_nested(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["measurements"]["left"]["keypoints"] = [
            {"x": 1, "y": 2}
        ]

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("never stored", str(caught.exception))

    def test_media_and_encoded_payload_fields_are_rejected(self):
        # These names have no legitimate scalar meaning, so they are refused
        # whatever they hold.
        for field in ("videoUrl", "imageData", "base64Frame", "blobId", "thumbnailSrc"):
            payload = valid_payload()
            payload["tests"]["shoulder"]["quality"][field] = "anything"

            with self.assertRaises(AssessmentValidationError, msg=field):
                validate_assessment_payload(payload)

    def test_fields_named_as_collections_of_pose_data_are_rejected(self):
        for field in ("keypoints", "landmarks", "poses", "skeleton", "frames"):
            payload = valid_payload()
            payload["tests"]["shoulder"]["quality"][field] = 3

            with self.assertRaises(AssessmentValidationError, msg=field):
                validate_assessment_payload(payload)

    def test_a_pose_named_field_may_not_hold_a_list_or_object(self):
        # This is the rule that enforces "no sequences" independently of the
        # exact name chosen.
        for field, value in (
            ("poseLandmarkTrack", [[0.1, 0.2], [0.3, 0.4]]),
            ("keypointSeries", {"left_wrist": [1, 2, 3]}),
            ("framePoses", [{"x": 1}]),
        ):
            payload = valid_payload()
            payload["tests"]["shoulder"]["quality"][field] = value

            with self.assertRaises(AssessmentValidationError, msg=field):
                validate_assessment_payload(payload)

    def test_scalar_summaries_of_pose_quality_are_kept(self):
        # The counterpart to the rule above: a single number describing how well
        # the pose was tracked is quality metadata, and losing it would leave no
        # record of the recording conditions.
        payload = valid_payload()
        payload["tests"]["shoulder"]["quality"]["meanKeypointScore"] = 0.71
        payload["tests"]["shoulder"]["quality"]["longestPoseLossMs"] = 132
        payload["tests"]["shoulder"]["quality"]["framesSeen"] = 188

        quality = validate_assessment_payload(payload)["tests"]["shoulder"]["quality"]

        self.assertAlmostEqual(quality["meanKeypointScore"], 0.71)
        self.assertEqual(quality["longestPoseLossMs"], 132)
        self.assertEqual(quality["framesSeen"], 188)

    def test_an_array_long_enough_to_be_a_pose_sequence_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["measurements"]["series"] = list(
            range(MAX_ARRAY_LENGTH + 1)
        )

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("never stored", str(caught.exception))

    def test_a_sequence_hidden_under_an_innocuous_name_is_still_rejected(self):
        # The key-name filter can be side-stepped by choosing another name; the
        # length limit is what actually makes storing a sequence impossible.
        payload = valid_payload()
        payload["tests"]["balance"]["quality"] = {
            "notes": [[0.1, 0.2]] * (MAX_ARRAY_LENGTH + 5)
        }

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_binary_values_cannot_be_stored(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["quality"]["extra"] = b"\x89PNG\r\n"

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_a_payload_with_too_many_fields_overall_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["balance"]["status"] = "invalid"
        payload["tests"]["balance"]["measurements"] = {
            f"field{outer}": {f"inner{inner}": inner for inner in range(40)}
            for outer in range(40)
        }

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_deeply_nested_structures_are_rejected(self):
        payload = valid_payload()

        nested = {"value": 1}

        for _ in range(12):
            nested = {"level": nested}

        payload["tests"]["shoulder"]["measurements"]["deep"] = nested

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)


class StructureTests(unittest.TestCase):
    def test_an_unknown_test_id_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["grip_strength"] = {"status": "completed", "measurements": {}}

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("unknown test ids", str(caught.exception))

    def test_a_missing_test_is_rejected(self):
        payload = valid_payload()
        del payload["tests"]["ftsst"]

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("missing", str(caught.exception))

    def test_an_unknown_status_is_rejected(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["status"] = "excellent"

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_a_client_supplied_user_id_is_rejected_rather_than_ignored(self):
        # Identity comes from the token. A payload trying to set it is a bug or
        # an attack, and either way should not be silently dropped.
        payload = valid_payload()
        payload["user_id"] = "68b0f2f41f1e4a1e9c6d2f5c"

        with self.assertRaises(AssessmentValidationError) as caught:
            validate_assessment_payload(payload)

        self.assertIn("unexpected fields", str(caught.exception))

    def test_a_missing_started_at_is_rejected(self):
        payload = valid_payload()
        del payload["startedAt"]

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_a_completed_at_before_started_at_is_rejected(self):
        payload = valid_payload(
            startedAt="2026-08-26T09:19:00.000Z",
            completedAt="2026-08-26T09:15:00.000Z",
        )

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_a_malformed_timestamp_is_rejected(self):
        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(valid_payload(startedAt="yesterday"))

    def test_a_missing_session_id_is_rejected(self):
        payload = valid_payload()
        payload["sessionId"] = "   "

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_non_finite_numbers_are_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            payload = valid_payload()
            payload["tests"]["shoulder"]["measurements"]["left"][
                "finalElevationDeg"
            ] = bad

            with self.assertRaises(AssessmentValidationError, msg=repr(bad)):
                validate_assessment_payload(payload)

    def test_reason_codes_must_be_short_strings(self):
        payload = valid_payload()
        payload["tests"]["shoulder"]["invalidReasons"] = [{"code": "nope"}]

        with self.assertRaises(AssessmentValidationError):
            validate_assessment_payload(payload)

    def test_the_input_payload_is_not_mutated(self):
        payload = valid_payload()
        before = copy.deepcopy(payload)

        validate_assessment_payload(payload)

        self.assertEqual(payload, before)


class SummaryTests(unittest.TestCase):
    def test_the_summary_is_recounted_and_not_trusted(self):
        payload = valid_payload()

        # A client claiming three usable results when one was skipped.
        payload["summary"] = {
            "testsCompleted": 3,
            "testsInvalid": 0,
            "testsSkipped": 0,
            "testsNotStarted": 0,
            "hasAnyUsableResult": True,
        }

        document = validate_assessment_payload(payload)

        self.assertEqual(document["summary"]["tests_completed"], 2)
        self.assertEqual(document["summary"]["tests_skipped"], 1)

    def test_a_session_with_nothing_usable_says_so(self):
        payload = valid_payload()

        for test_id in ("shoulder", "ftsst", "balance"):
            payload["tests"][test_id] = {
                "status": "skipped",
                "measurements": None,
                "quality": None,
                "invalidReasons": [],
                "attempts": 0,
            }

        document = validate_assessment_payload(payload)

        self.assertFalse(document["summary"]["has_any_usable_result"])
        self.assertEqual(document["summary"]["tests_skipped"], 3)

    def test_the_summary_contains_no_score_or_rating(self):
        document = validate_assessment_payload(valid_payload())
        keys = " ".join(document["summary"]).lower()

        for forbidden in ("score", "rating", "grade", "index", "percentile", "risk"):
            self.assertNotIn(forbidden, keys)

    def test_a_missing_summary_is_computed_rather_than_refused(self):
        document = validate_assessment_payload(valid_payload(summary=None))

        self.assertEqual(document["summary"]["tests_completed"], 2)

    def test_summary_status_distinguishes_partial_complete_insufficient_none(self):
        # Case 1: Partial (2 completed)
        doc_partial = validate_assessment_payload(valid_payload())
        self.assertEqual(doc_partial["summary"]["status"], "PARTIAL")

        # Case 2: Complete (all 3 completed)
        payload_complete = valid_payload()
        payload_complete["tests"]["balance"] = {
            "status": "completed",
            "measurements": {"left": {"holdDurationMs": 15000, "attempted": True}, "right": {"holdDurationMs": 14000, "attempted": True}},
            "quality": {"fps": 28.5, "usableFrameRatio": 0.95},
            "invalidReasons": [],
            "attempts": 1,
        }
        doc_complete = validate_assessment_payload(payload_complete)
        self.assertEqual(doc_complete["summary"]["status"], "COMPLETE")

        # Case 3: Insufficient data (0 completed, at least 1 invalid)
        payload_insufficient = valid_payload()
        for t in ("shoulder", "ftsst", "balance"):
            payload_insufficient["tests"][t] = {
                "status": "invalid",
                "measurements": None,
                "quality": None,
                "invalidReasons": ["low_confidence"],
                "attempts": 1,
            }
        doc_insufficient = validate_assessment_payload(payload_insufficient)
        self.assertEqual(doc_insufficient["summary"]["status"], "INSUFFICIENT_DATA")

        # Case 4: None completed (all skipped/not started, none invalid)
        payload_none = valid_payload()
        for t in ("shoulder", "ftsst", "balance"):
            payload_none["tests"][t] = {
                "status": "skipped",
                "measurements": None,
                "quality": None,
                "invalidReasons": [],
                "attempts": 0,
            }
        doc_none = validate_assessment_payload(payload_none)
        self.assertEqual(doc_none["summary"]["status"], "NONE_COMPLETED")


if __name__ == "__main__":
    unittest.main()
