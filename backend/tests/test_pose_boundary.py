"""Tests for the shared pose/media boundary every agent input contract uses.

The bug this module was written to fix is worth stating plainly, because it is
the reason these tests are specific rather than general: the boundary used to
be "if the serialised payload contains the word 'keypoint', refuse it". The
browser sends `quality.meanKeypointScore` with every assessment session — a
single number summarising detector confidence, which
`assessments/schema.py` deliberately stores — so the Physio Agent and the
Progress Agent refused their own legitimate input, and no movement plan and no
progress review could ever be produced from a real recording.

The rule is therefore structural, and these tests pin down both halves of it:
the shapes that must still be refused, and the legitimate data that must not
be.
"""

import unittest

from orchestration.pose_boundary import (
    MAX_SCALAR_STRING_LENGTH,
    find_pose_or_media_violation,
)


class LegitimatePayloadTests(unittest.TestCase):
    """What a real payload carries, and what must pass."""

    def test_the_assessment_quality_summary_passes(self):
        payload = {
            "physical_assessment": {
                "tests": {
                    "shoulder": {
                        "status": "completed",
                        "measurements": {
                            "left": {"finalElevationDeg": 148.2, "repetitionCount": 3},
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
                    }
                }
            }
        }

        self.assertEqual(find_pose_or_media_violation(payload), "")

    def test_projection_geometry_names_are_still_allowed(self):
        # Protocol definition metadata, not pictures.
        payload = {
            "setup": {
                "camera_image_plane_projection": "frontal",
                "downward_vertical_image_plane": True,
            }
        }

        self.assertEqual(find_pose_or_media_violation(payload), "")

    def test_prose_mentioning_pose_data_is_not_a_violation(self):
        payload = {"note": "the keypoint sequence was lost briefly"}

        self.assertEqual(find_pose_or_media_violation(payload), "")

    def test_an_empty_payload_has_no_violation(self):
        self.assertEqual(find_pose_or_media_violation({}), "")
        self.assertEqual(find_pose_or_media_violation(None), "")
        self.assertEqual(find_pose_or_media_violation([]), "")
        self.assertEqual(find_pose_or_media_violation("a short string"), "")
        self.assertEqual(find_pose_or_media_violation(42), "")


class RefusedPayloadTests(unittest.TestCase):
    """What must never cross the boundary."""

    def _assert_refused(self, payload, expected_fragment=""):
        violation = find_pose_or_media_violation(payload)

        self.assertTrue(violation, f"expected a violation for {payload!r}")

        if expected_fragment:
            self.assertIn(expected_fragment, violation)

    def test_a_pose_named_list_is_refused(self):
        self._assert_refused(
            {"keypoints": [[0.1, 0.2, 0.9]]}, "keypoints"
        )

    def test_a_pose_named_object_is_refused(self):
        self._assert_refused(
            {"shoulder": {"poseData": {"left": 1}}}, "poseData"
        )

    def test_a_nested_pose_sequence_is_refused(self):
        self._assert_refused(
            {"physical_assessment": {"tests": {"shoulder": {"landmarks": [1, 2, 3]}}}},
            "landmarks",
        )

    def test_a_media_named_key_is_refused_whatever_its_value(self):
        self._assert_refused({"debugFrameSnapshot": "abc"}, "debugFrameSnapshot")
        self._assert_refused({"rawVideo": "abc"}, "rawVideo")
        self._assert_refused({"imageBase64": 12}, "imageBase64")

    def test_a_data_uri_is_refused(self):
        self._assert_refused({"note": "data:image/png;base64,iVBORw0KGgo="})

    def test_a_long_encoded_string_is_refused(self):
        self._assert_refused({"payload": "A" * 300})

    def test_an_over_long_string_is_refused(self):
        self._assert_refused({"note": "x " * (MAX_SCALAR_STRING_LENGTH)})

    def test_a_violation_reports_where_it_is(self):
        violation = find_pose_or_media_violation(
            {"physical_assessment": {"tests": {"shoulder": {"keypointSeries": [1]}}}}
        )

        self.assertIn("physical_assessment.tests.shoulder.keypointSeries", violation)


class ScalarsVersusContainersTests(unittest.TestCase):
    """The distinction the whole rule rests on."""

    def test_the_same_name_is_allowed_as_a_scalar_and_refused_as_a_container(self):
        self.assertEqual(find_pose_or_media_violation({"keypointCount": 17}), "")
        self.assertEqual(find_pose_or_media_violation({"keypointMeanScore": 0.8}), "")

        self.assertTrue(find_pose_or_media_violation({"keypointCount": [1, 2, 3]}))
        self.assertTrue(find_pose_or_media_violation({"keypointMeanScore": {"a": 1}}))

    def test_a_frame_named_scalar_is_allowed_but_a_frame_list_is_not(self):
        # `framesSeen`/`framesUsable` are real quality counters this project
        # stores; a `frames` list is a frame sequence.
        self.assertEqual(find_pose_or_media_violation({"framesSeen": 188}), "")
        self.assertTrue(find_pose_or_media_violation({"frames": [1, 2, 3]}))


if __name__ == "__main__":
    unittest.main()
