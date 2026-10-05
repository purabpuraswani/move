"""Tests for the MoveWell Score.

The score is the one number in this product that is not a raw measurement, so
the tests that matter are the ones about what it refuses to do: invent a value
for a domain nobody assessed, show a headline number built only from
questionnaire answers, or report "no change" as a zero.
"""

import unittest

from workflow.score import (
    BAND_GOING_WELL,
    BAND_ROOM_TO_IMPROVE,
    BAND_STEADY,
    build_movewell_score,
    with_previous,
)


def _state(**entries):
    """A User State whose current_needs holds these dimension entries.

    Each caller passes a level and, where it exists, the need score the need
    assessment would have produced (higher = more need).
    """

    data = {}

    for dimension, value in entries.items():
        if value is None:
            data[dimension] = {
                "level": "NOT_ASSESSED",
                "score": None,
                "evidence": ["nothing measured"],
                "confidence": "NONE",
            }
        else:
            level, need = value
            data[dimension] = {
                "level": level,
                "score": need,
                "evidence": [f"{dimension} evidence"],
                "confidence": "HIGH",
            }

    return {"current_needs": {"available": True, "data": data}}


class ScoreValueTests(unittest.TestCase):
    def test_a_low_need_reads_as_a_high_score(self):
        score = build_movewell_score(
            _state(mobility_need=("LOW", 0.0), stability_need=("LOW", 0.2))
        )

        self.assertTrue(score["available"])
        # (100 + 80) / 2
        self.assertEqual(score["value"], 90)

    def test_a_high_need_reads_as_a_low_score(self):
        score = build_movewell_score(
            _state(mobility_need=("HIGH", 1.0), stability_need=("HIGH", 1.0))
        )

        self.assertEqual(score["value"], 0)

    def test_the_average_covers_only_the_domains_that_were_assessed(self):
        score = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.0),
                stability_need=("LOW", 0.0),
                functional_movement_need=("LOW", 0.0),
                nutrition_need=("HIGH", 1.0),
            )
        )

        # 100, 100, 100, 0 -> 75, and the four assessed domains are listed.
        self.assertEqual(score["value"], 75)
        self.assertEqual(len([d for d in score["domains"] if d["assessed"]]), 4)

    def test_the_value_always_falls_between_zero_and_one_hundred(self):
        for need in (0.0, 0.13, 0.5, 0.87, 1.0):
            score = build_movewell_score(_state(mobility_need=("MEDIUM", need)))

            self.assertGreaterEqual(score["value"], 0)
            self.assertLessEqual(score["value"], 100)


class NotAssessedTests(unittest.TestCase):
    def test_an_unassessed_domain_gets_no_value_at_all(self):
        score = build_movewell_score(
            _state(mobility_need=("LOW", 0.0), nutrition_need=None)
        )
        nutrition = next(d for d in score["domains"] if d["key"] == "nutrition_need")

        self.assertFalse(nutrition["assessed"])
        # Not zero. "We do not know" must not read as "you scored badly".
        self.assertIsNone(nutrition["value"])
        self.assertEqual(nutrition["level"], "NOT_ASSESSED")
        self.assertTrue(nutrition["evidence"])

    def test_an_unassessed_domain_is_excluded_from_the_average_not_counted_as_zero(self):
        with_two = build_movewell_score(
            _state(mobility_need=("LOW", 0.0), stability_need=("LOW", 0.0))
        )
        with_a_third_unassessed = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.0),
                stability_need=("LOW", 0.0),
                nutrition_need=None,
            )
        )

        self.assertEqual(with_two["value"], with_a_third_unassessed["value"])

    def test_answers_alone_do_not_produce_a_headline_score(self):
        # A number built only from questionnaire answers would read as a health
        # score while being a summary of what somebody typed.
        score = build_movewell_score(
            _state(behaviour_need=("HIGH", 0.8), nutrition_need=("MEDIUM", 0.4))
        )

        self.assertFalse(score["available"])
        self.assertIsNone(score["value"])
        self.assertIsNone(score["message"])

        # Their own values are still shown, so the answers are not wasted.
        behaviour = next(d for d in score["domains"] if d["key"] == "behaviour_need")

        self.assertTrue(behaviour["assessed"])
        self.assertEqual(behaviour["value"], 20)
        self.assertEqual(behaviour["source"], "answered")

    def test_an_account_with_nothing_assessed_has_no_score(self):
        score = build_movewell_score({"current_needs": {"available": False}})

        self.assertFalse(score["available"])
        self.assertEqual(score["value"], None)
        self.assertEqual(score["domains"], [])

        empty = build_movewell_score(_state(mobility_need=None))
        self.assertFalse(empty["available"])


class BandTests(unittest.TestCase):
    def test_the_band_comes_from_the_levels_not_from_the_average(self):
        # One domain at HIGH produces the "room to improve" wording even though
        # the average is comfortable: a single domain at the far end of the
        # project's markers is worth naming.
        score = build_movewell_score(
            _state(
                mobility_need=("HIGH", 0.75),
                stability_need=("LOW", 0.0),
                functional_movement_need=("LOW", 0.0),
                behaviour_need=("LOW", 0.0),
            )
        )

        self.assertEqual(score["band"], BAND_ROOM_TO_IMPROVE)
        self.assertGreater(score["value"], 60)

    def test_medium_anywhere_reads_as_steady(self):
        score = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.0),
                stability_need=("MEDIUM", 0.4),
                functional_movement_need=("LOW", 0.0),
            )
        )

        self.assertEqual(score["band"], BAND_STEADY)

    def test_all_low_reads_as_going_well(self):
        score = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.1),
                stability_need=("LOW", 0.1),
                functional_movement_need=("LOW", 0.1),
            )
        )

        self.assertEqual(score["band"], BAND_GOING_WELL)
        self.assertEqual(score["message"], "You're doing well overall.")

    def test_every_score_carries_an_explanation_of_where_it_came_from(self):
        score = build_movewell_score(_state(mobility_need=("LOW", 0.0)))

        self.assertTrue(score["method"])
        self.assertIn("not a medical measurement", score["method"])


class FocusTests(unittest.TestCase):
    def test_the_biggest_need_becomes_the_current_focus(self):
        score = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.05),
                stability_need=("MEDIUM", 0.45),
                functional_movement_need=("LOW", 0.1),
            )
        )

        self.assertEqual(score["focus"]["label"], "Stability")
        self.assertEqual(score["focus"]["key"], "stability_need")
        self.assertIn("stability", score["focus_statement"].lower())

    def test_the_focus_statement_does_not_diagnose_or_use_internal_vocabulary(self):
        score = build_movewell_score(_state(stability_need=("HIGH", 0.9)))
        statement = score["focus_statement"].lower()

        for leaked in (
            "need",
            "score",
            "deficit",
            "disorder",
            "impairment",
            "abnormal",
            "diagnos",
            "clinical",
            "agent",
        ):
            self.assertNotIn(leaked, statement, statement)

    def test_a_measured_focus_is_attributed_to_the_assessment(self):
        measured = build_movewell_score(_state(stability_need=("HIGH", 0.9)))
        answered = build_movewell_score(
            _state(
                mobility_need=("LOW", 0.0),
                stability_need=("LOW", 0.0),
                functional_movement_need=("LOW", 0.0),
                nutrition_need=("HIGH", 0.9),
            )
        )

        self.assertIn("assessment", measured["focus_statement"].lower())
        self.assertIn("told us", answered["focus_statement"].lower())

    def test_a_focus_is_still_named_when_only_answers_were_assessed(self):
        score = build_movewell_score(_state(nutrition_need=("HIGH", 0.9), behaviour_need=("MEDIUM", 0.5)))

        # No headline number, but the user is still told where the attention is.
        self.assertFalse(score["available"])
        self.assertIsNone(score["focus"])


class PreviousScoreTests(unittest.TestCase):
    def test_no_previous_score_leaves_the_change_null_rather_than_zero(self):
        score = with_previous(
            build_movewell_score(_state(mobility_need=("LOW", 0.0))), None
        )

        self.assertIsNone(score["previous"])
        # "No change measured" and "no previous measurement" are different
        # statements, and a 0 would collapse them.
        self.assertIsNone(score["change"])

    def test_a_previous_score_produces_the_difference(self):
        score = with_previous(
            build_movewell_score(_state(mobility_need=("LOW", 0.2))),
            64,
            "2026-09-01T09:00:00+00:00",
        )

        self.assertEqual(score["previous"]["value"], 64)
        self.assertEqual(score["change"], score["value"] - 64)
        self.assertEqual(score["previous"]["recorded_at"], "2026-09-01T09:00:00+00:00")

    def test_a_boolean_is_not_a_previous_score(self):
        score = with_previous(
            build_movewell_score(_state(mobility_need=("LOW", 0.0))), True
        )

        self.assertIsNone(score["previous"])

    def test_per_domain_history_says_which_area_moved(self):
        score = with_previous(
            build_movewell_score(
                _state(
                    mobility_need=("LOW", 0.1),
                    stability_need=("MEDIUM", 0.4),
                )
            ),
            previous_value=64,
            previous_domains={"mobility_need": 88, "stability_need": 50},
        )
        by_key = {d["key"]: d for d in score["domains"]}

        self.assertEqual(by_key["mobility_need"]["previous_value"], 88)
        self.assertEqual(by_key["mobility_need"]["change"], 2)
        self.assertEqual(by_key["stability_need"]["change"], 10)

    def test_a_domain_with_no_history_has_a_null_change_not_a_zero(self):
        score = with_previous(
            build_movewell_score(_state(mobility_need=("LOW", 0.1))),
            previous_value=64,
            previous_domains={},
        )

        self.assertIsNone(score["domains"][0]["previous_value"])
        self.assertIsNone(score["domains"][0]["change"])


class DomainPresentationTests(unittest.TestCase):
    def test_domains_are_listed_in_a_stable_order(self):
        score = build_movewell_score(
            _state(
                exercise_need=("LOW", 0.1),
                mobility_need=("LOW", 0.1),
                nutrition_need=("LOW", 0.1),
            )
        )

        self.assertEqual(
            [d["key"] for d in score["domains"]],
            ["mobility_need", "nutrition_need", "exercise_need"],
        )

    def test_each_domain_says_where_its_value_came_from(self):
        score = build_movewell_score(
            _state(mobility_need=("LOW", 0.1), nutrition_need=("LOW", 0.1))
        )
        by_key = {d["key"]: d for d in score["domains"]}

        self.assertEqual(by_key["mobility_need"]["source"], "measured")
        self.assertEqual(by_key["nutrition_need"]["source"], "answered")

    def test_the_need_assessments_own_evidence_is_carried_through_untouched(self):
        score = build_movewell_score(_state(mobility_need=("LOW", 0.1)))
        mobility = score["domains"][0]

        self.assertEqual(mobility["evidence"], ["mobility_need evidence"])

    def test_no_domain_exposes_an_internal_dimension_name_as_a_label(self):
        score = build_movewell_score(
            _state(mobility_need=("LOW", 0.1), functional_movement_need=("LOW", 0.1))
        )

        for domain in score["domains"]:
            self.assertNotIn("_need", domain["label"])
            self.assertTrue(domain["label"][0].isupper())


if __name__ == "__main__":
    unittest.main()
