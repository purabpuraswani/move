"""Tests for the Exercise MCP Server.

These tests exercise the server ONLY when the real `mcp` package (the
official Model Context Protocol Python SDK) is importable in this
environment. It is not installable in this sandbox (no PyPI network
access — confirmed separately), so these tests SKIP themselves with an
explicit, honest reason rather than faking a pass. This is deliberate:
faking MCP protocol behavior in a test is exactly the kind of fake
behavior this project's build rules forbid.

The domain logic these tools wrap (exercise_library.catalog,
exercise_assessment.schema) is already fully tested without `mcp` in
test_exercise_catalog.py and test_exercise_assessment_schema.py. What this
file additionally covers, when `mcp` IS available, is specific to the MCP
layer itself: that the server exposes the right tools, that tool calls
return well-formed structured results, that unknown/invalid input is
handled without crashing the server, and that each result carries
observability metadata (workflow_id/request_id/tool_call_id) propagated
from backend.orchestration.ids rather than invented ad hoc.
"""

import importlib.util
import unittest

MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None

SKIP_REASON = (
    "the 'mcp' package is not installed in this environment (no PyPI "
    "network access in this sandbox); install it in the project's real "
    ".venv to run these tests for real rather than skipping them"
)


@unittest.skipUnless(MCP_AVAILABLE, SKIP_REASON)
class ExerciseMcpServerToolsTests(unittest.TestCase):
    """Only defined so unittest can report it as 'skipped', never 'passed',
    when `mcp` is absent — see module docstring."""

    def setUp(self):
        from mcp_servers import exercise_server

        self.server = exercise_server

    def test_the_server_exposes_the_five_expected_tools(self):
        tool_names = {
            "search_exercises_tool",
            "get_exercise_details_tool",
            "get_demo_animation_tool",
            "check_exercise_constraints_tool",
            "record_exercise_result_tool",
        }
        registered = {tool.name for tool in self.server.server._tool_manager.list_tools()}
        self.assertTrue(tool_names.issubset(registered))

    def test_search_exercises_tool_returns_structured_results_with_metadata(self):
        result = self.server.search_exercises_tool(target_capability="stability")
        self.assertIn("exercises", result)
        self.assertIn("count", result)
        self.assertIn("metadata", result)
        self.assertEqual(result["count"], len(result["exercises"]))
        self.assertIn("tool_call_id", result["metadata"])
        self.assertIn("workflow_id", result["metadata"])
        self.assertIn("mcp_session_id", result["metadata"])

    def test_get_exercise_details_tool_valid_id(self):
        result = self.server.get_exercise_details_tool("wall-sit")
        self.assertIn("exercise", result)
        self.assertEqual(result["exercise"]["exercise_id"], "wall-sit")

    def test_get_exercise_details_tool_unknown_id_returns_error_not_crash(self):
        result = self.server.get_exercise_details_tool("not-a-real-exercise")
        self.assertIn("error", result)
        self.assertIn("metadata", result)

    def test_get_demo_animation_tool_returns_demonstration_reference(self):
        result = self.server.get_demo_animation_tool("wall-sit")
        self.assertEqual(result["demonstrationId"], "exercise-wall-sit")
        self.assertEqual(result["renderedBy"], "src/movementDemos (client-side)")

    def test_check_exercise_constraints_tool_valid_id(self):
        result = self.server.check_exercise_constraints_tool("chair-sit-to-stand")
        self.assertIn("safetyConstraints", result)
        self.assertIn("metadata", result)

    def test_record_exercise_result_tool_accepts_a_valid_result(self):
        result = self.server.record_exercise_result_tool(
            exercise_id="wall-sit",
            status="completed",
            measurements={"durationSeconds": 20, "completion": 1},
        )
        self.assertTrue(result["accepted"])
        self.assertIn("result", result)

    def test_record_exercise_result_tool_rejects_an_invalid_result(self):
        result = self.server.record_exercise_result_tool(
            exercise_id="wall-sit", status="bogus-status", measurements={}
        )
        self.assertIn("error", result)
        self.assertNotIn("accepted", result)

    def test_workflow_and_request_ids_are_propagated_when_supplied(self):
        result = self.server.search_exercises_tool(
            workflow_id="wf-test-123", request_id="req-test-456"
        )
        self.assertEqual(result["metadata"]["workflow_id"], "wf-test-123")
        self.assertEqual(result["metadata"]["request_id"], "req-test-456")

    def test_a_fresh_call_without_ids_generates_new_ones_not_shared_state(self):
        first = self.server.search_exercises_tool()
        second = self.server.search_exercises_tool()
        self.assertNotEqual(first["metadata"]["workflow_id"], second["metadata"]["workflow_id"])

    def test_mcp_session_id_is_never_faked_absent_a_real_transport_session(self):
        result = self.server.search_exercises_tool()
        # backend.orchestration.ids.new_mcp_session_id() only ever returns a
        # real id once bound to an actual MCP transport session; called
        # directly (not through a live streamable-http connection) it must
        # stay None rather than invent one.
        self.assertIsNone(result["metadata"]["mcp_session_id"])


class ExerciseMcpServerUnavailableTests(unittest.TestCase):
    """Runs unconditionally (with or without `mcp`) — documents the honest
    failure mode this sandbox actually exhibits today."""

    @unittest.skipIf(MCP_AVAILABLE, "mcp is installed in this environment; import-guard path not exercised")
    def test_importing_the_server_without_mcp_raises_a_helpful_import_error(self):
        import importlib
        import sys

        sys.path.insert(0, ".")
        for name in list(sys.modules):
            if name == "mcp_servers.exercise_server":
                del sys.modules[name]

        with self.assertRaises(ImportError) as ctx:
            importlib.import_module("mcp_servers.exercise_server")

        self.assertIn("pip install mcp", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
