"""Confirmed medical reports as nutrition evidence -- and its limits.

The rule being protected: a confirmed report can make the Nutrition
specialist RELEVANT, and can never make it diagnostic. These tests pin
both halves, because the dangerous failure here is not under-activation
-- it is a system that reads a number off a lab report and starts
talking about a condition.

Three boundaries in particular:

* unconfirmed extraction must not activate anything;
* the printed value and reference range must not change the decision;
* the evidence sentences must quote the report and interpret nothing.
"""

import unittest

from nutrition_agent.report_relevance import (
    nutrition_relevant_values,
    report_nutrition_evidence,
)
from orchestrator.decision import decide_nutrition_required


def _report(values, report_id="r1"):
    return [{"id": report_id, "values": values}]


def _value(key, label, category="lab_result", value="100", unit="mg/dL", **extra):
    return {
        "key": key,
        "label": label,
        "category": category,
        "value": value,
        "unit": unit,
        **extra,
    }


def _state_with(reports):
    return {
        "medical_context": {
            "available": True,
            "data": {"confirmed_reports": {"reports": reports}},
        }
    }


class RelevanceMatchingTests(unittest.TestCase):
    def test_a_metabolic_lab_result_is_relevant(self):
        matched = nutrition_relevant_values(
            _report([_value("fasting_glucose", "Fasting Glucose")])
        )

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["key"], "fasting_glucose")

    def test_the_key_matches_even_when_the_token_is_a_prefix(self):
        # The extractor emits free-form keys, so `fasting_glucose` and
        # `glucose_fasting` must both match on the `glucose` token.
        for key in ("glucose", "fasting_glucose", "glucose_fasting", "random_glucose"):
            self.assertTrue(
                nutrition_relevant_values(_report([_value(key, key)])), f"{key} did not match"
            )

    def test_the_printed_label_can_match_when_the_key_does_not(self):
        matched = nutrition_relevant_values(
            _report([_value("test_17", "Total Cholesterol")])
        )

        self.assertEqual(len(matched), 1)

    def test_an_unrelated_result_is_not_relevant(self):
        for key, label in (
            ("visual_acuity", "Visual Acuity"),
            ("hearing_threshold", "Hearing Threshold"),
            ("bone_density", "Bone Density"),
        ):
            self.assertEqual(nutrition_relevant_values(_report([_value(key, label)])), [])

    def test_medication_and_free_text_never_activate_nutrition(self):
        # Acting on these would mean interpreting a prescription or
        # clinical prose, which this system does not do -- even when the
        # text happens to contain a matching word.
        for category in ("medication", "clinical_note_text", "report_metadata"):
            self.assertEqual(
                nutrition_relevant_values(
                    _report([_value("metformin", "Metformin for diabetes", category=category)])
                ),
                [],
                f"{category} should not activate nutrition",
            )

    def test_relevance_does_not_depend_on_the_value(self):
        # The same field is equally relevant whatever the number says.
        # Anything else would be inferring a condition from one figure.
        low = report_nutrition_evidence(
            _report([_value("fasting_glucose", "Fasting Glucose", value="70")])
        )
        high = report_nutrition_evidence(
            _report([_value("fasting_glucose", "Fasting Glucose", value="260")])
        )

        self.assertEqual(low["relevant"], high["relevant"])
        self.assertEqual(low["evidence"], high["evidence"])

    def test_a_printed_reference_range_does_not_change_the_decision(self):
        with_range = report_nutrition_evidence(
            _report(
                [
                    _value(
                        "fasting_glucose",
                        "Fasting Glucose",
                        printedReferenceRange="70-99",
                    )
                ]
            )
        )
        without = report_nutrition_evidence(
            _report([_value("fasting_glucose", "Fasting Glucose")])
        )

        self.assertEqual(with_range["evidence"], without["evidence"])


class EvidenceWordingTests(unittest.TestCase):
    def setUp(self):
        self.evidence = report_nutrition_evidence(
            _report([_value("hba1c", "HbA1c", value="7.4", unit="%")])
        )["evidence"]

    def test_the_sentence_names_what_the_report_records(self):
        self.assertEqual(len(self.evidence), 1)
        self.assertIn("HbA1c", self.evidence[0])
        self.assertIn("confirmed", self.evidence[0].lower())

    def test_the_sentence_never_states_a_finding(self):
        text = " ".join(self.evidence).lower()

        for claim in (
            "high", "low", "elevated", "abnormal", "raised",
            "diabet", "risk", "indicates", "suggests", "poor",
        ):
            self.assertNotIn(claim, text, f"evidence interprets the report: {claim!r}")

    def test_the_value_itself_is_not_quoted_back_as_a_finding(self):
        self.assertNotIn("7.4", " ".join(self.evidence))

    def test_duplicate_fields_are_stated_once(self):
        evidence = report_nutrition_evidence(
            _report(
                [
                    _value("fasting_glucose", "Fasting Glucose"),
                    _value("fasting_glucose", "Fasting Glucose"),
                ]
            )
        )["evidence"]

        self.assertEqual(len(evidence), 1)


class ActivationTests(unittest.TestCase):
    """The decision function's second activation route."""

    NOT_ASSESSED = {"nutrition_need": {"level": "NOT_ASSESSED"}}
    LOW = {"nutrition_need": {"level": "LOW"}}
    HIGH = {"nutrition_need": {"level": "HIGH"}}

    def test_a_relevant_report_activates_nutrition_with_no_dietary_answers(self):
        decision = decide_nutrition_required(
            self.NOT_ASSESSED,
            _state_with(_report([_value("fasting_glucose", "Fasting Glucose")])),
        )

        self.assertTrue(decision["nutrition_required"])
        self.assertEqual(decision["activated_by"], ["confirmed_medical_report"])

    def test_dietary_evidence_still_activates_it_on_its_own(self):
        decision = decide_nutrition_required(self.HIGH, None)

        self.assertTrue(decision["nutrition_required"])
        self.assertEqual(decision["activated_by"], ["dietary_questionnaire"])

    def test_both_routes_are_recorded_when_both_apply(self):
        decision = decide_nutrition_required(
            self.HIGH, _state_with(_report([_value("hba1c", "HbA1c")]))
        )

        self.assertEqual(
            decision["activated_by"], ["dietary_questionnaire", "confirmed_medical_report"]
        )

    def test_an_irrelevant_report_leaves_the_decision_alone(self):
        decision = decide_nutrition_required(
            self.LOW, _state_with(_report([_value("visual_acuity", "Visual Acuity")]))
        )

        self.assertFalse(decision["nutrition_required"])
        self.assertEqual(decision["activated_by"], [])
        self.assertEqual(decision["report_evidence"], [])

    def test_an_unavailable_medical_section_activates_nothing(self):
        decision = decide_nutrition_required(
            self.NOT_ASSESSED,
            {"medical_context": {"available": False, "data": {"confirmed_reports": {
                "reports": _report([_value("hba1c", "HbA1c")])
            }}}},
        )

        self.assertFalse(decision["nutrition_required"])

    def test_the_reason_explains_which_evidence_brought_it_in(self):
        decision = decide_nutrition_required(
            self.NOT_ASSESSED, _state_with(_report([_value("hba1c", "HbA1c")]))
        )

        self.assertIn("confirmed medical report", decision["reason"])

    def test_calling_without_a_user_state_behaves_exactly_as_before(self):
        self.assertEqual(
            decide_nutrition_required(self.LOW)["nutrition_required"],
            decide_nutrition_required(self.LOW, None)["nutrition_required"],
        )


class MalformedInputTests(unittest.TestCase):
    """A broken record must not activate a specialist, or crash one."""

    def test_nothing_at_all(self):
        self.assertEqual(report_nutrition_evidence(None)["relevant"], False)
        self.assertEqual(report_nutrition_evidence([])["relevant"], False)

    def test_a_report_that_is_not_a_dict(self):
        self.assertEqual(nutrition_relevant_values(["not a report", 7, None]), [])

    def test_a_report_with_no_values(self):
        self.assertEqual(nutrition_relevant_values([{"id": "r1"}]), [])

    def test_a_value_that_is_not_a_dict(self):
        self.assertEqual(nutrition_relevant_values([{"id": "r1", "values": ["x", None]}]), [])

    def test_a_value_with_no_category(self):
        self.assertEqual(
            nutrition_relevant_values([{"id": "r1", "values": [{"key": "glucose"}]}]), []
        )


if __name__ == "__main__":
    unittest.main()
