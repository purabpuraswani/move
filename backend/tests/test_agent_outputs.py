"""Tests for reading what a model sent back.

Two properties matter here. Nothing arrives in the response that the model did
not actually produce — no filled-in default, no salvaged fragment, no role
guessed from a near miss. And nothing arrives changed: an over-long sentence is
dropped whole rather than cut, because a sentence that stops early can mean
something its author did not intend.

Runs without FastAPI, pymongo or a database.

    python -m unittest discover -s tests -t .
"""

import unittest

from agents.outputs import (
    MAX_PARAGRAPH,
    MAX_SENTENCE,
    NAVIGATION_TOOL,
    PROFESSIONAL_TYPES,
    WELLNESS_TOOL,
    AgentOutputError,
    parse_navigation,
    parse_wellness,
    professional_type_options,
)

WELLNESS = {
    "opening": "This is based on your setup answers and one movement session.",
    "observations": [
        {"heading": "Both arms", "detail": "Your right arm looked like it "
                                          "lifted a little further."}
    ],
    "focusAreas": [
        {
            "title": "Sitting less",
            "whyThisCameUp": "You said you sit for about nine hours a day.",
            "suggestions": ["Stand up once an hour."],
        }
    ],
    "habits": ["A short walk after meals."],
    "missingInformation": ["No report has been confirmed yet."],
    "closing": "Small changes, kept up, are worth more than big ones dropped.",
}

NAVIGATION = {
    "opening": "These are options you may wish to consider.",
    "considerations": [
        {
            "professionalType": "physiotherapist",
            "whatTheyCouldLookAt": "How your shoulder moves, in person.",
            "whyItCameUp": "The two sides looked different on camera.",
        }
    ],
    "questionsToAsk": ["Is the difference between my arms worth looking at?"],
    "limitations": ["This tool cannot tell whether anything is urgent."],
}


class WellnessParsingTests(unittest.TestCase):
    def test_a_complete_response_survives_intact(self):
        parsed = parse_wellness(WELLNESS)

        self.assertEqual(parsed["opening"], WELLNESS["opening"])
        self.assertEqual(len(parsed["observations"]), 1)
        self.assertEqual(parsed["focusAreas"][0]["title"], "Sitting less")
        self.assertEqual(parsed["habits"], ["A short walk after meals."])
        self.assertEqual(parsed["closing"], WELLNESS["closing"])

    def test_whitespace_is_collapsed_not_content(self):
        parsed = parse_wellness(
            {**WELLNESS, "opening": "  Two   spaces\nand a newline.  "}
        )

        self.assertEqual(parsed["opening"], "Two spaces and a newline.")

    def test_an_over_long_sentence_is_dropped_whole(self):
        # Not truncated. "your result is normal for someone of your age" cut at
        # the wrong point becomes "your result is normal", which is a claim this
        # application has promised never to make.
        parsed = parse_wellness({**WELLNESS, "closing": "x" * (MAX_PARAGRAPH + 1)})

        self.assertIsNone(parsed["closing"])

    def test_an_over_long_list_item_is_dropped_and_the_rest_kept(self):
        parsed = parse_wellness({
            **WELLNESS,
            "habits": ["Keep this one.", "y" * (MAX_SENTENCE + 1),
                       "Keep this one too."],
        })

        self.assertEqual(parsed["habits"], ["Keep this one.",
                                            "Keep this one too."])

    def test_an_observation_missing_its_detail_is_dropped(self):
        parsed = parse_wellness({
            **WELLNESS,
            "observations": [{"heading": "Only a heading"}],
            "focusAreas": [],
            "habits": ["Something to keep the response usable."],
        })

        self.assertEqual(parsed["observations"], [])

    def test_a_focus_area_with_no_suggestions_is_dropped(self):
        # A heading with nothing under it reads as an unfinished thought rather
        # than as restraint.
        parsed = parse_wellness({
            **WELLNESS,
            "focusAreas": [{"title": "Sleep", "whyThisCameUp": "You said six "
                                                               "hours."}],
        })

        self.assertEqual(parsed["focusAreas"], [])

    def test_a_focus_area_keeps_its_suggestions_without_a_reason(self):
        parsed = parse_wellness({
            **WELLNESS,
            "focusAreas": [{"title": "Sleep", "suggestions": ["A fixed "
                                                              "bedtime."]}],
        })

        self.assertEqual(parsed["focusAreas"][0]["title"], "Sleep")
        self.assertIsNone(parsed["focusAreas"][0]["whyThisCameUp"])

    def test_duplicates_are_removed(self):
        parsed = parse_wellness({
            **WELLNESS,
            "habits": ["Walk daily.", "Walk daily.", "Sleep at the same time."],
        })

        self.assertEqual(len(parsed["habits"]), 2)

    def test_the_limits_hold(self):
        parsed = parse_wellness({
            **WELLNESS,
            "observations": [{"heading": f"H{n}", "detail": f"D{n}"}
                             for n in range(9)],
            "habits": [f"Habit {n}." for n in range(9)],
            "missingInformation": [f"Gap {n}." for n in range(9)],
            "focusAreas": [
                {"title": f"Area {n}", "whyThisCameUp": "Because.",
                 "suggestions": [f"S{n}-{m}." for m in range(7)]}
                for n in range(7)
            ],
        })

        self.assertEqual(len(parsed["observations"]), 6)
        self.assertEqual(len(parsed["habits"]), 6)
        self.assertEqual(len(parsed["missingInformation"]), 6)
        self.assertEqual(len(parsed["focusAreas"]), 4)
        self.assertEqual(len(parsed["focusAreas"][0]["suggestions"]), 4)

    def test_a_response_with_nothing_to_show_raises(self):
        with self.assertRaises(AgentOutputError):
            parse_wellness({"opening": "Here you go.", "closing": "Good luck."})

    def test_a_response_that_is_not_a_structure_raises(self):
        for raw in ("some prose", None, [], 7):
            with self.subTest(raw=raw):
                with self.assertRaises(AgentOutputError):
                    parse_wellness(raw)

    def test_habits_alone_are_enough_to_be_worth_showing(self):
        parsed = parse_wellness({"habits": ["Move every hour."]})

        self.assertEqual(parsed["habits"], ["Move every hour."])
        self.assertEqual(parsed["observations"], [])


class NavigationParsingTests(unittest.TestCase):
    def test_a_complete_response_survives_intact(self):
        parsed = parse_navigation(NAVIGATION)

        self.assertEqual(len(parsed["considerations"]), 1)
        self.assertEqual(parsed["questionsToAsk"], NAVIGATION["questionsToAsk"])

    def test_the_wording_for_a_role_is_ours_not_the_models(self):
        # The model chooses a key. Everything the reader sees about that role is
        # written in outputs.py, so a model cannot relabel "a doctor or GP" as
        # something more specific.
        parsed = parse_navigation({
            **NAVIGATION,
            "considerations": [{
                "professionalType": "physiotherapist",
                "label": "A musculoskeletal specialist",
                "note": "For your shoulder condition.",
                "whatTheyCouldLookAt": "How your shoulder moves.",
            }],
        })

        consideration = parsed["considerations"][0]

        self.assertEqual(consideration["label"],
                         PROFESSIONAL_TYPES["physiotherapist"]["label"])
        self.assertEqual(consideration["note"],
                         PROFESSIONAL_TYPES["physiotherapist"]["note"])

    def test_a_role_outside_the_list_is_dropped_not_mapped(self):
        # Guessing what a model meant by "rheumatologist" would put back exactly
        # the implication the fixed list exists to prevent.
        parsed = parse_navigation({
            **NAVIGATION,
            "considerations": [
                {"professionalType": "rheumatologist",
                 "whatTheyCouldLookAt": "Your joints."},
                {"professionalType": "doctor_or_gp",
                 "whatTheyCouldLookAt": "Anything you want to raise."},
            ],
        })

        roles = [item["professionalType"] for item in parsed["considerations"]]

        self.assertEqual(roles, ["doctor_or_gp"])

    def test_the_same_role_is_only_suggested_once(self):
        parsed = parse_navigation({
            **NAVIGATION,
            "considerations": [
                {"professionalType": "doctor_or_gp",
                 "whatTheyCouldLookAt": "The first thing."},
                {"professionalType": "doctor_or_gp",
                 "whatTheyCouldLookAt": "The second thing."},
            ],
        })

        self.assertEqual(len(parsed["considerations"]), 1)
        self.assertEqual(parsed["considerations"][0]["whatTheyCouldLookAt"],
                         "The first thing.")

    def test_a_consideration_with_nothing_to_look_at_is_dropped(self):
        parsed = parse_navigation({
            **NAVIGATION,
            "considerations": [{"professionalType": "pharmacist"}],
            "questionsToAsk": ["Something worth asking?"],
        })

        self.assertEqual(parsed["considerations"], [])

    def test_questions_alone_are_enough(self):
        parsed = parse_navigation({
            "questionsToAsk": ["Is this difference worth looking at?"],
        })

        self.assertEqual(len(parsed["questionsToAsk"]), 1)
        self.assertEqual(parsed["considerations"], [])

    def test_the_limits_hold(self):
        parsed = parse_navigation({
            **NAVIGATION,
            "considerations": [
                {"professionalType": role, "whatTheyCouldLookAt": f"Thing {n}."}
                for n, role in enumerate(PROFESSIONAL_TYPES)
            ],
            "questionsToAsk": [f"Question {n}?" for n in range(9)],
            "limitations": [f"Limit {n}." for n in range(9)],
        })

        self.assertEqual(len(parsed["considerations"]), 5)
        self.assertEqual(len(parsed["questionsToAsk"]), 6)
        self.assertEqual(len(parsed["limitations"]), 6)

    def test_a_response_with_nothing_to_show_raises(self):
        with self.assertRaises(AgentOutputError):
            parse_navigation({"opening": "Here are some options.",
                              "limitations": ["This is not advice."]})

    def test_a_response_that_is_not_a_structure_raises(self):
        with self.assertRaises(AgentOutputError):
            parse_navigation("see a specialist")


class SchemaTests(unittest.TestCase):
    def test_the_role_enum_cannot_drift_from_the_parser(self):
        # The schema tells the model what to choose from and the parser decides
        # what to accept. If those two lists ever differ, valid responses start
        # being discarded silently.
        enum = (NAVIGATION_TOOL["input_schema"]["properties"]
                ["considerations"]["items"]["properties"]
                ["professionalType"]["enum"])

        self.assertEqual(list(enum), list(PROFESSIONAL_TYPES))

    def test_every_role_has_wording_of_its_own(self):
        for option in professional_type_options():
            with self.subTest(role=option["id"]):
                self.assertIn(option["id"], PROFESSIONAL_TYPES)
                self.assertTrue(option["label"])
                self.assertTrue(option["note"])

    def test_no_role_names_a_medical_specialty(self):
        # A specialty is a diagnosis by implication: "see a rheumatologist" tells
        # the reader they have arthritis without using the word.
        forbidden = ("cardiolog", "neurolog", "rheumatolog", "endocrinolog",
                     "orthopaed", "orthoped", "oncolog", "psychiatr",
                     "dermatolog", "gastroenterolog", "urolog", "nephrolog")

        for option in professional_type_options():
            wording = f"{option['id']} {option['label']} {option['note']}".lower()

            for word in forbidden:
                with self.subTest(role=option["id"], word=word):
                    self.assertNotIn(word, wording)

    def test_both_tools_name_the_fields_they_require(self):
        for tool in (WELLNESS_TOOL, NAVIGATION_TOOL):
            with self.subTest(tool=tool["name"]):
                schema = tool["input_schema"]

                self.assertTrue(schema["required"])

                for field in schema["required"]:
                    self.assertIn(field, schema["properties"])


if __name__ == "__main__":
    unittest.main()
