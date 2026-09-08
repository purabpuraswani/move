"""Physio Agent -> MCP Client -> Exercise MCP Server -> Tool -> Result
-> Physio Agent -> Orchestrator, over the REAL MCP transport.

Skips itself, honestly, when the `mcp` package is not installed — exactly
like backend/tests/test_mcp_exercise_server.py (Phase 2). This sandbox has
no PyPI network access (confirmed in Phase 2, re-confirmed unchanged in
Phase 3), so these tests are not expected to execute here; they document
and verify the real client<->server path for whichever environment does
have `mcp` installed (this project's real .venv).

What runs here when `mcp` IS available: starts a real
`exercise_server.py` FastMCP server as a subprocess on an ephemeral port,
points `McpExerciseToolClient` at it, and runs the Orchestrator's full
workflow against it — a real Streamable HTTP connection, a real
`initialize` handshake, and real tool calls, not an in-process function
call. This is deliberately a heavier, slower test than the rest of the
suite; it exists specifically to prove the transport boundary, which
InProcessExerciseToolClient-based tests elsewhere in this suite do not
and cannot prove.
"""

import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None

SKIP_REASON = (
    "the 'mcp' package is not installed in this environment (no PyPI "
    "network access in this sandbox); install it in the project's real "
    ".venv to run this real client-server-tool integration test instead "
    "of skipping it"
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(MCP_AVAILABLE, SKIP_REASON)
class RealMcpTransportIntegrationTests(unittest.TestCase):
    """Only defined so unittest reports 'skipped', never 'passed', when
    `mcp` is absent — see module docstring."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server_url = f"http://127.0.0.1:{cls.port}/mcp"
        backend_dir = Path(__file__).resolve().parent.parent
        cls.server_process = subprocess.Popen(
            [sys.executable, "-m", "mcp_servers.exercise_server", "--port", str(cls.port)],
            cwd=str(backend_dir),
        )
        # A real server needs a moment to bind before a client can connect;
        # this is a plain startup wait, not a protocol-level fake.
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        cls.server_process.terminate()
        cls.server_process.wait(timeout=5)

    def _client(self):
        from physio_agent.mcp_client import McpExerciseToolClient

        return McpExerciseToolClient(
            server_url=self.server_url, workflow_id="wf_mcp_it", request_id="req_mcp_it"
        )

    def test_search_exercises_over_the_real_transport(self):
        client = self._client()
        result = client.search_exercises(target_capability="stability")
        self.assertIn("exercises", result)
        self.assertIsNotNone(result["metadata"]["mcp_session_id"])

    def test_the_orchestrator_runs_the_full_workflow_over_the_real_transport(self):
        from orchestrator.orchestrator import run_workflow
        from user_state.schema import build_user_state

        state = build_user_state()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {"level": "HIGH", "score": 0.9, "evidence": ["x"], "confidence": "HIGH"},
                "stability_need": {"level": "LOW", "score": 0.1, "evidence": ["x"], "confidence": "HIGH"},
                "functional_movement_need": {"level": "LOW", "score": 0.1, "evidence": ["x"], "confidence": "HIGH"},
                "behaviour_need": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
                "nutrition_need": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
                "exercise_need": {"level": "HIGH", "score": 0.9, "evidence": ["x"], "confidence": "HIGH"},
                "safety_status": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
                "overallSummary": {
                    "headline": "x", "dimensionsAtHigh": [], "dimensionsAtMedium": [],
                    "dimensionsAtLow": [], "dimensionsNotAssessed": [], "assessedCount": 0,
                    "notAssessedCount": 0,
                },
                "metadata": {
                    "assessmentVersion": "0.1.0", "generatedAt": "2026-01-01T00:00:00Z",
                    "workflowId": "wf_x", "requestId": "req_x",
                },
            },
        }

        result = run_workflow(state, tool_client=self._client())

        self.assertEqual(result["selected_agents"], ["physio"])
        self.assertEqual(result["agent_results"][0]["status"], "completed")
        self.assertIsNotNone(result["agent_results"][0]["metadata"]["mcp_session_id"])


if __name__ == "__main__":
    unittest.main()
