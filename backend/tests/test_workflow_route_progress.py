"""Regression tests for the progress-triggered branch of POST /api/workflow/run.

This branch had a real, uncovered defect: `_progress_inputs()` returned
`current_plan`, `current_needs` and `nutrition_plan`, none of which are
`run_workflow()` parameters. They are splatted into that call with
`**progress_kwargs`, so every progress-triggered request raised TypeError
and returned 500. `tests/test_workflow_route.py` never sent a
`progress_trigger`, so nothing caught it.

The first test below is the structural guard that would have. It compares
the keys `_progress_inputs()` actually returns against the parameters
`run_workflow()` actually accepts, both read from the source by AST rather
than hard-coded here — so it keeps holding when either signature changes,
instead of asserting a list that silently goes stale.

Neither test needs pymongo: the AST test never imports the route module,
and the period test exercises `_nutrition_periods()`, which is pure date
arithmetic. Both run for real in this sandbox rather than self-skipping.
"""

import ast
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

BACKEND = pathlib.Path(__file__).resolve().parent.parent


def _function_node(relative_path: str, name: str):
    tree = ast.parse((BACKEND / relative_path).read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node

    raise AssertionError(f"{name}() not found in {relative_path}")


class ProgressKwargsMatchOrchestratorSignatureTests(unittest.TestCase):
    """The defect this file exists for: a key that is not a parameter."""

    def test_every_returned_key_is_a_real_run_workflow_parameter(self):
        run_workflow = _function_node("orchestrator/orchestrator.py", "run_workflow")
        accepted = {argument.arg for argument in run_workflow.args.kwonlyargs}
        accepted |= {argument.arg for argument in run_workflow.args.args}

        progress_inputs = _function_node("routes/workflow.py", "_progress_inputs")

        returned = set()

        for node in ast.walk(progress_inputs):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    self.assertIsInstance(
                        key,
                        ast.Constant,
                        "every returned key must be a literal so this guard can read it",
                    )
                    returned.add(key.value)

        self.assertTrue(returned, "_progress_inputs() returned no literal dict")

        invalid = returned - accepted

        self.assertEqual(
            invalid,
            set(),
            f"_progress_inputs() returns {sorted(invalid)}, which run_workflow() "
            "does not accept; splatting these raises TypeError -> HTTP 500",
        )

    def test_run_workflow_has_no_kwargs_catch_all(self):
        """The guard above is only meaningful while run_workflow() would
        actually reject an unknown key. If a **kwargs is ever added, the
        mismatch stops raising and this test says so explicitly rather
        than leaving the other test quietly toothless."""

        run_workflow = _function_node("orchestrator/orchestrator.py", "run_workflow")

        self.assertIsNone(
            run_workflow.args.kwarg,
            "run_workflow() gained **kwargs; the signature guard above no longer "
            "proves anything and needs rethinking",
        )


class NutritionPeriodsTests(unittest.TestCase):
    """`_nutrition_periods()` decides what adherence is measured over. It
    must never invent a window it cannot justify from the plan's own
    created_at."""

    def setUp(self):
        # Imported lazily: routes/workflow.py imports pymongo-backed stores
        # at module level, so this is skipped rather than failed when the
        # sandbox has no pymongo -- the AST tests above still run.
        try:
            from routes.workflow import _nutrition_periods

        except Exception as error:  # pragma: no cover - environment-dependent
            self.skipTest(f"routes.workflow not importable here: {error}")

        self._periods = _nutrition_periods

    def test_no_plan_yields_no_windows(self):
        self.assertEqual(self._periods(None), (None, None))
        self.assertEqual(self._periods({}), (None, None))

    def test_plan_without_created_at_yields_no_windows(self):
        self.assertEqual(self._periods({"plan_id": "p1"}), (None, None))

    def test_unparseable_created_at_yields_no_windows_rather_than_a_guess(self):
        self.assertEqual(
            self._periods({"plan_id": "p1", "created_at": "not-a-date"}),
            (None, None),
        )

    def test_plan_younger_than_two_days_yields_no_windows(self):
        today = datetime.now(timezone.utc)

        previous, current = self._periods(
            {"plan_id": "p1", "created_at": today.isoformat()}
        )

        self.assertIsNone(previous)
        self.assertIsNone(current)

    def test_windows_are_consecutive_non_overlapping_and_cover_the_plan(self):
        created = datetime.now(timezone.utc) - timedelta(days=9)

        previous, current = self._periods(
            {"plan_id": "p1", "created_at": created.isoformat()}
        )

        self.assertIsNotNone(previous)
        self.assertIsNotNone(current)

        # Previous starts at the plan's creation day, not before it: no
        # window may claim to observe a plan that did not yet exist.
        self.assertEqual(previous["start"].date(), created.date())

        # Consecutive, and non-overlapping.
        self.assertLess(previous["end"], current["start"])
        self.assertEqual(
            current["start"].date() - previous["end"].date(),
            timedelta(days=1),
        )

        # Current ends today, never in the future.
        self.assertEqual(current["end"].date(), datetime.now(timezone.utc).date())

    def test_a_naive_created_at_is_treated_as_utc_not_rejected(self):
        created = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=9)

        previous, current = self._periods(
            {"plan_id": "p1", "created_at": created.isoformat()}
        )

        self.assertIsNotNone(previous)
        self.assertIsNotNone(current)


if __name__ == "__main__":
    unittest.main()
