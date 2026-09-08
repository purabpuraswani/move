"""Progress Agent -> MCP Client -> Progress MCP Server -> Tool -> Result,
over the REAL MCP transport (Phase 5).

Skips itself, honestly, when the `mcp` package is not installed — exactly
like tests/test_physio_agent_mcp_integration.py (Phase 3) and the
equivalent Phase 4 files. This sandbox has no PyPI network access, so this
test is not expected to execute here; it documents and verifies the real
client<->server path for whichever environment does have `mcp` installed.
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
class RealProgressMcpTransportIntegrationTests(unittest.TestCase):
    """Only defined so unittest reports 'skipped', never 'passed', when
    `mcp` is absent — see module docstring."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server_url = f"http://127.0.0.1:{cls.port}/mcp"
        backend_dir = Path(__file__).resolve().parent.parent
        cls.server_process = subprocess.Popen(
            [sys.executable, "-m", "mcp_servers.progress_server", "--port", str(cls.port)],
            cwd=str(backend_dir),
        )
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        cls.server_process.terminate()
        cls.server_process.wait(timeout=5)

    def _client(self):
        from progress_agent.mcp_client import McpProgressToolClient

        return McpProgressToolClient(
            server_url=self.server_url, workflow_id="wf_mcp_it", request_id="req_mcp_it"
        )

    def test_compare_assessments_over_the_real_transport(self):
        client = self._client()
        result = client.compare_assessments(
            baseline_assessment=None, previous_assessment=None, current_assessment=None,
        )
        self.assertIn("comparison", result)
        self.assertIsNotNone(result["metadata"]["mcp_session_id"])

    def test_check_reassessment_required_over_the_real_transport(self):
        client = self._client()
        result = client.check_reassessment_required(current_assessment_completed_at=None)
        self.assertTrue(result["required"])

    def test_the_orchestrator_runs_a_progress_review_over_the_real_transport(self):
        from orchestrator.orchestrator import run_workflow
        from user_state.schema import build_user_state

        state = build_user_state()
        state["current_needs"] = {
            "available": True,
            "reason": None,
            "data": {
                "assessmentVersion": "0.1.0",
                "mobility_need": {"level": "LOW", "score": 0.1, "evidence": ["x"], "confidence": "HIGH"},
                "stability_need": {"level": "LOW", "score": 0.1, "evidence": ["x"], "confidence": "HIGH"},
                "functional_movement_need": {"level": "LOW", "score": 0.1, "evidence": ["x"], "confidence": "HIGH"},
                "behaviour_need": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
                "nutrition_need": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
                "exercise_need": {"level": "NOT_ASSESSED", "score": None, "evidence": ["x"], "confidence": "NONE"},
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

        result = run_workflow(
            state,
            progress_tool_client=self._client(),
            progress_trigger={"reason": "periodic check"},
        )

        progress_result = next(r for r in result["agent_results"] if r["agent"] == "progress")
        self.assertEqual(progress_result["status"], "completed")
        self.assertIsNotNone(progress_result["metadata"]["mcp_session_id"])


if __name__ == "__main__":
    unittest.main()
