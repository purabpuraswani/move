import unittest

from orchestrator.decision import decide_physio_required


def _entry(level):
    return {"level": level, "score": None, "evidence": [], "confidence": "NONE"}


def _profile(mobility, stability, functional_movement):
    return {
        "mobility_need": _entry(mobility),
        "stability_need": _entry(stability),
        "functional_movement_need": _entry(functional_movement),
    }


class PhysioRequiredHighTests(unittest.TestCase):
    def test_high_mobility_and_stability_selects_physio(self):
        decision = decide_physio_required(_profile("HIGH", "HIGH", "MEDIUM"))
        self.assertTrue(decision["physio_required"])
        self.assertIn("mobility_need=HIGH", decision["reason"])
        self.assertIn("stability_need=HIGH", decision["reason"])

    def test_a_single_medium_dimension_is_enough(self):
        decision = decide_physio_required(_profile("LOW", "MEDIUM", "LOW"))
        self.assertTrue(decision["physio_required"])


class PhysioNotRequiredTests(unittest.TestCase):
    def test_all_low_does_not_select_physio(self):
        decision = decide_physio_required(_profile("LOW", "LOW", "LOW"))
        self.assertFalse(decision["physio_required"])
        self.assertIn("no physical need dimension", decision["reason"])

    def test_all_not_assessed_does_not_select_physio(self):
        decision = decide_physio_required(_profile("NOT_ASSESSED", "NOT_ASSESSED", "NOT_ASSESSED"))
        self.assertFalse(decision["physio_required"])


class MissingNeedProfileTests(unittest.TestCase):
    def test_none_need_profile_does_not_select_physio_and_says_why(self):
        decision = decide_physio_required(None)
        self.assertFalse(decision["physio_required"])
        self.assertIn("unavailable", decision["reason"])
        self.assertEqual(decision["evaluated_dimensions"], {})


class ExplainabilityTests(unittest.TestCase):
    def test_evaluated_dimensions_always_reports_all_three_when_present(self):
        decision = decide_physio_required(_profile("HIGH", "LOW", "NOT_ASSESSED"))
        self.assertEqual(
            decision["evaluated_dimensions"],
            {"mobility_need": "HIGH", "stability_need": "LOW", "functional_movement_need": "NOT_ASSESSED"},
        )


if __name__ == "__main__":
    unittest.main()
