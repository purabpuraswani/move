import unittest

from orchestration.ids import (
    ID_PREFIXES,
    TraceContext,
    new_agent_run_id,
    new_mcp_session_id,
    new_request_id,
    new_tool_call_id,
    new_workflow_id,
    start_agent_run,
    start_tool_call,
    start_workflow,
)


class IdGenerationTests(unittest.TestCase):
    def test_each_id_has_its_own_prefix_and_is_unique(self):
        generators = {
            "workflow_id": new_workflow_id,
            "request_id": new_request_id,
            "agent_run_id": new_agent_run_id,
            "tool_call_id": new_tool_call_id,
        }

        for key, generate in generators.items():
            first, second = generate(), generate()

            self.assertNotEqual(first, second)
            self.assertTrue(first.startswith(ID_PREFIXES[key] + "_"))

    def test_mcp_session_id_is_always_none_in_phase_0(self):
        # There is no MCP transport yet. This function must never fabricate a
        # session id — see the module docstring.
        self.assertIsNone(new_mcp_session_id())
        self.assertIsNone(new_mcp_session_id())


class TraceContextLifecycleTests(unittest.TestCase):
    def test_start_workflow_issues_a_fresh_workflow_and_request_id(self):
        context = start_workflow()

        self.assertTrue(context.workflow_id)
        self.assertTrue(context.request_id)
        self.assertIsNone(context.agent_run_id)
        self.assertIsNone(context.tool_call_id)
        self.assertIsNone(context.mcp_session_id)

    def test_start_workflow_can_continue_an_existing_workflow_id(self):
        first_request = start_workflow()
        second_request = start_workflow(workflow_id=first_request.workflow_id)

        self.assertEqual(first_request.workflow_id, second_request.workflow_id)
        self.assertNotEqual(first_request.request_id, second_request.request_id)

    def test_start_agent_run_keeps_workflow_and_request_but_issues_a_run_id(self):
        request = start_workflow()
        run = start_agent_run(request)

        self.assertEqual(run.workflow_id, request.workflow_id)
        self.assertEqual(run.request_id, request.request_id)
        self.assertIsNotNone(run.agent_run_id)
        self.assertIsNone(run.tool_call_id)

    def test_two_agent_runs_from_the_same_request_get_different_run_ids(self):
        request = start_workflow()

        first_run = start_agent_run(request)
        second_run = start_agent_run(request)

        self.assertNotEqual(first_run.agent_run_id, second_run.agent_run_id)

    def test_start_tool_call_requires_an_agent_run_first(self):
        request = start_workflow()

        with self.assertRaises(ValueError):
            start_tool_call(request)

    def test_start_tool_call_defaults_mcp_session_id_to_none(self):
        run = start_agent_run(start_workflow())
        call = start_tool_call(run)

        self.assertIsNotNone(call.tool_call_id)
        self.assertIsNone(call.mcp_session_id)

    def test_start_tool_call_carries_a_real_mcp_session_id_when_given_one(self):
        run = start_agent_run(start_workflow())
        call = start_tool_call(run, mcp_session_id="mcp_sess_example")

        self.assertEqual(call.mcp_session_id, "mcp_sess_example")

    def test_trace_context_is_immutable(self):
        context = start_workflow()

        with self.assertRaises(Exception):
            context.workflow_id = "tampered"

    def test_as_dict_carries_all_five_identifiers(self):
        call = start_tool_call(start_agent_run(start_workflow()))

        as_dict = call.as_dict()

        self.assertEqual(
            set(as_dict),
            {
                "workflow_id",
                "request_id",
                "agent_run_id",
                "tool_call_id",
                "mcp_session_id",
            },
        )


if __name__ == "__main__":
    unittest.main()
