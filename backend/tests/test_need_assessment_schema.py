import unittest

from need_assessment.schema import (
    NEED_DIMENSIONS,
    NEED_PROFILE_SCHEMA_VERSION,
    NeedAssessmentValidationError,
    TOP_LEVEL_SECTIONS,
    build_need_entry,
    validate_need_entry,
    validate_need_profile,
)


class BuildNeedEntryTests(unittest.TestCase):
    def test_a_high_entry_with_evidence_and_score_is_valid(self):
        entry = build_need_entry(
            level="HIGH", score=0.821, evidence=["some reason"], confidence="HIGH"
        )

        validate_need_entry(entry)
        # Rounded to 2 decimal places, not left at full float precision.
        self.assertEqual(entry["score"], 0.82)

    def test_a_not_assessed_entry_needs_no_score(self):
        entry = build_need_entry(
            level="NOT_ASSESSED", evidence=["no data"], confidence="NONE"
        )

        validate_need_entry(entry)
        self.assertIsNone(entry["score"])

    def test_a_not_assessed_entry_with_a_score_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(
                level="NOT_ASSESSED", score=0.5, evidence=["no data"], confidence="NONE"
            )

    def test_a_not_assessed_entry_must_have_confidence_none(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(
                level="NOT_ASSESSED", evidence=["no data"], confidence="LOW"
            )

    def test_a_not_assessed_entry_with_no_evidence_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(level="NOT_ASSESSED", evidence=[], confidence="NONE")

    def test_an_assessed_entry_with_no_evidence_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(level="LOW", evidence=[], confidence="LOW")

    def test_an_assessed_entry_cannot_have_confidence_none(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(level="LOW", evidence=["reason"], confidence="NONE")

    def test_an_out_of_range_score_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            build_need_entry(
                level="HIGH", score=1.5, evidence=["reason"], confidence="HIGH"
            )

    def test_an_unknown_level_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            validate_need_entry(
                {
                    "level": "SEVERE",
                    "score": None,
                    "evidence": ["x"],
                    "confidence": "HIGH",
                }
            )


class ValidateNeedProfileTests(unittest.TestCase):
    def _minimal_entry(self, level="LOW"):
        if level == "NOT_ASSESSED":
            return build_need_entry(level=level, evidence=["no data"], confidence="NONE")

        return build_need_entry(
            level=level, score=0.1, evidence=["reason"], confidence="LOW"
        )

    def _minimal_profile(self):
        profile = {
            name: self._minimal_entry() for name in TOP_LEVEL_SECTIONS
        }
        profile["assessmentVersion"] = NEED_PROFILE_SCHEMA_VERSION
        profile["overallSummary"] = {"headline": "test"}
        profile["metadata"] = {
            "assessmentVersion": NEED_PROFILE_SCHEMA_VERSION,
            "generatedAt": "2026-01-01T00:00:00+00:00",
            "workflowId": "wf_test",
            "requestId": "req_test",
        }

        return profile

    def test_a_well_formed_profile_passes(self):
        validate_need_profile(self._minimal_profile())

    def test_all_six_dimensions_are_in_the_schema(self):
        self.assertEqual(len(NEED_DIMENSIONS), 6)

    def test_a_missing_dimension_is_rejected(self):
        profile = self._minimal_profile()
        del profile["nutrition_need"]

        with self.assertRaises(NeedAssessmentValidationError):
            validate_need_profile(profile)

    def test_a_wrong_assessment_version_is_rejected(self):
        profile = self._minimal_profile()
        profile["assessmentVersion"] = "9.9.9"

        with self.assertRaises(NeedAssessmentValidationError):
            validate_need_profile(profile)

    def test_missing_metadata_field_is_rejected(self):
        profile = self._minimal_profile()
        del profile["metadata"]["requestId"]

        with self.assertRaises(NeedAssessmentValidationError):
            validate_need_profile(profile)

    def test_not_a_dict_is_rejected(self):
        with self.assertRaises(NeedAssessmentValidationError):
            validate_need_profile(["not", "a", "profile"])


if __name__ == "__main__":
    unittest.main()
