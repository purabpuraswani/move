"""Tests for the check applied to everything a model produces.

The rules in agents/guardrails.py are the last thing between a model's output and
a person reading it, so both directions matter: a sentence this application has
promised never to produce must be caught, and an ordinary sentence must not be.
The second half is what keeps the check usable — a guardrail that rejects
harmless writing gets loosened, and a loosened guardrail catches nothing.

Runs without FastAPI, pymongo or a database.

    python -m unittest discover -s tests -t .
"""

import unittest

from agents.guardrails import (
    DISCLAIMER,
    SAFETY_NOTE,
    GuardrailViolation,
    check_payload,
    check_text,
    correction_instruction,
    enforce,
)

CLEAN_RESPONSE = {
    "opening": "Here is what the recording showed, and what it does not tell us.",
    "observations": [
        {
            "heading": "Both arms raised out to the side",
            "detail": (
                "In the recording your right arm looked like it lifted a little "
                "further than your left. Some difference between sides is "
                "ordinary, and the camera angle alone can produce it."
            ),
        }
    ],
    "focusAreas": [
        {
            "title": "Breaking up long stretches of sitting",
            "whyThisCameUp": (
                "You told us you sit for about nine hours on a typical day."
            ),
            "suggestions": [
                "Stand up and walk for a couple of minutes each hour.",
                "Take calls on your feet where you can.",
            ],
        }
    ],
    "habits": ["A short walk after meals.", "A consistent bedtime."],
    "missingInformation": [
        "No seat height was recorded, so the chair timing cannot be compared "
        "with another session."
    ],
    "closing": (
        "Anything that concerns you belongs with a professional who can examine "
        "you."
    ),
}


class CaughtTests(unittest.TestCase):
    """Sentences this application has promised never to show anyone."""

    def assert_caught(self, text):
        broken = check_text(text)

        self.assertTrue(broken, f"not caught: {text!r}")

        return broken

    def test_a_diagnosis(self):
        self.assert_caught("This is a diagnosis of the underlying problem.")

    def test_telling_the_reader_they_have_a_condition(self):
        self.assert_caught("Based on this, you have anaemia.")
        self.assert_caught("You may have a thyroid problem.")

    def test_a_suspected_condition(self):
        self.assert_caught("These findings are suggestive of a deficiency.")

    def test_medication_advice(self):
        self.assert_caught("You should take a supplement with your evening meal.")

    def test_a_dose_even_when_it_is_being_discouraged(self):
        # Not excusable by negation. A sentence about an amount of a substance is
        # a sentence about an amount of a substance whichever way it leans.
        self.assert_caught("Do not take more than 500 mg of anything.")

    def test_saying_treatment_is_needed(self):
        self.assert_caught("You need treatment for this.")

    def test_a_cure_claim(self):
        self.assert_caught("Daily stretching will cure this.")

    def test_an_invented_normal_range(self):
        self.assert_caught("That sits comfortably inside the normal range.")
        self.assert_caught("That reading is abnormal.")

    def test_calling_a_value_high_or_low(self):
        self.assert_caught("Your haemoglobin level is low.")
        self.assert_caught("Your completion time is quite poor.")

    def test_an_invented_score(self):
        self.assert_caught("Your overall score is 72 out of 100.")
        self.assert_caught("Your mobility score suggests room to improve.")

    def test_calling_a_webcam_observation_a_measurement(self):
        self.assert_caught("Your range of motion has improved since last time.")
        self.assert_caught("Your fall risk looks acceptable.")

    def test_a_verdict_on_urgency_in_either_direction(self):
        # Both ways round. False reassurance is the more likely failure and the
        # more damaging one, so neither is excusable by negation.
        self.assert_caught("You are fine.")
        self.assert_caught("This is not an emergency.")
        self.assert_caught("There is nothing to worry about here.")

    def test_a_personal_risk_figure(self):
        self.assert_caught("This increases your risk of falls.")

    def test_the_description_does_not_repeat_the_sentence(self):
        broken = self.assert_caught("You have diabetes.")

        for description in broken:
            self.assertNotIn("diabetes", description)


class AllowedTests(unittest.TestCase):
    """Sentences the agents are supposed to be able to write."""

    def assert_allowed(self, text):
        self.assertEqual(check_text(text), [], f"wrongly caught: {text!r}")

    def test_saying_it_is_not_a_diagnosis(self):
        self.assert_allowed(
            "This is not a diagnosis, and it cannot rule anything out."
        )

    def test_declining_to_claim_a_condition(self):
        self.assert_allowed(
            "Nothing here says you have a condition of any kind."
        )

    def test_repeating_a_range_that_was_printed_on_the_report(self):
        self.assert_allowed(
            "The range printed beside it on your report is 13.0 - 17.0 g/dL."
        )

    def test_stating_a_value_without_judging_it(self):
        self.assert_allowed(
            "Your haemoglobin level is 13.2 g/dL, which is what you confirmed "
            "from the report."
        )

    def test_naming_what_a_professional_could_look_at(self):
        # The whole point of the care navigation agent. "your range of motion" is
        # a claim; range of motion as a thing somebody qualified could examine is
        # not, and the rule has to tell them apart.
        self.assert_allowed(
            "A physiotherapist could look at range of motion properly and in "
            "person."
        )

    def test_describing_what_the_camera_saw(self):
        self.assert_allowed(
            "In the recording your left arm looked like it lifted a little "
            "further than your right."
        )

    def test_naming_a_gap(self):
        self.assert_allowed(
            "No balance measurement exists, because that test was skipped."
        )

    def test_a_whole_clean_response(self):
        self.assertEqual(check_payload(CLEAN_RESPONSE), [])

    def test_our_own_authored_text_passes_its_own_check(self):
        # If a future rule made the disclaimer or the safety note unpublishable,
        # that rule is wrong, and this is where it should show up.
        self.assertEqual(check_text(DISCLAIMER), [])
        self.assertEqual(check_text(SAFETY_NOTE), [])


class NegationWindowTests(unittest.TestCase):
    def test_a_negation_in_the_same_sentence_excuses_the_match(self):
        self.assertEqual(
            check_text("There is no suggestion that you have diabetes."), []
        )

    def test_a_negation_in_the_previous_sentence_does_not(self):
        # The window stops at the sentence boundary. Otherwise a denial anywhere
        # nearby would launder the claim that follows it.
        self.assertTrue(
            check_text("This is not a scoring tool. You have diabetes.")
        )

    def test_a_distant_negation_does_not_reach(self):
        far = "not " + "a very long stretch of unrelated wording " * 3

        self.assertTrue(check_text(far + "you have diabetes."))


class PayloadTests(unittest.TestCase):
    def test_nested_strings_are_checked(self):
        payload = {
            "focusAreas": [
                {"title": "Fine", "suggestions": ["You have diabetes."]}
            ]
        }

        self.assertTrue(check_payload(payload))

    def test_each_rule_is_reported_once(self):
        payload = {
            "a": "You have diabetes.",
            "b": "You have diabetes as well.",
        }

        broken = check_payload(payload)

        self.assertEqual(len(broken), len(set(broken)))

    def test_non_strings_are_ignored(self):
        self.assertEqual(check_payload({"n": 5, "flag": True, "empty": None}), [])

    def test_empty_text_passes(self):
        self.assertEqual(check_text(""), [])
        self.assertEqual(check_text("   "), [])
        self.assertEqual(check_text(None), [])


class EnforceTests(unittest.TestCase):
    def test_a_clean_payload_is_returned_unchanged(self):
        self.assertIs(enforce(CLEAN_RESPONSE), CLEAN_RESPONSE)

    def test_a_broken_payload_is_refused_not_edited(self):
        with self.assertRaises(GuardrailViolation) as caught:
            enforce({"opening": "You have diabetes."})

        self.assertTrue(caught.exception.rules)

    def test_the_error_names_the_rules_it_broke(self):
        try:
            enforce({"opening": "Your overall score is 80."})

        except GuardrailViolation as error:
            self.assertIn("score", str(error))

        else:
            self.fail("expected GuardrailViolation")


class CorrectionTests(unittest.TestCase):
    def test_the_retry_names_what_was_wrong(self):
        instruction = correction_instruction(["named or implied a diagnosis"])

        self.assertIn("named or implied a diagnosis", instruction)

    def test_the_retry_asks_for_the_same_content(self):
        # Not for something shorter or vaguer. A response made vague to get past
        # a check is not a safer response, it is a less useful one.
        instruction = correction_instruction(["named or implied a diagnosis"])

        self.assertIn("same helpful content", instruction)
        self.assertIn("same level of", instruction)


if __name__ == "__main__":
    unittest.main()
