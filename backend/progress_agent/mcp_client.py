"""The real MCP client: Progress Agent -> MCP Client -> Progress MCP Server.

Mirrors physio_agent/mcp_client.py and its Phase 4 siblings exactly,
including the same sandbox disclosure: this module could not be executed
in this development sandbox (no PyPI network access to install `mcp`).
Written against the SDK's documented, stable public client API, not
executed here.
"""

import json
import asyncio

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to use McpProgressToolClient. Install it with "
        "`pip install mcp` inside backend's virtual environment. Nothing "
        "else in MoveWell AI depends on this package. For testing the "
        "Progress Agent's own decision logic without a live MCP server, "
        "see tool_client.py's InProcessProgressToolClient (test-only)."
    ) from exc

from progress_agent.tool_client import ProgressToolClient


def _attach_session_id(payload, session_id):
    """Stamp the real transport session id into a tool result's metadata.

    The server cannot report this value. An MCP session id belongs to the
    client's own handshake with the Streamable HTTP transport, and the SDK
    hands it to the client as the third value yielded by
    `streamablehttp_client(...)`. That value was being unpacked and thrown
    away, which is why every tool result came back with
    `metadata.mcp_session_id: None` even though the server logs showed real
    sessions being created, negotiated and terminated.

    It is READ from the transport, never generated: if the transport
    reports no session id the field stays None rather than being filled
    with a workflow id, a request id, or a fresh uuid. A non-null value
    already set by the server is never overwritten.
    """

    if not session_id or not isinstance(payload, dict):
        return payload

    metadata = payload.get("metadata")

    if isinstance(metadata, dict):
        if metadata.get("mcp_session_id") is None:
            metadata["mcp_session_id"] = session_id
    elif metadata is None:
        payload["metadata"] = {"mcp_session_id": session_id}

    return payload

class McpToolCallError(RuntimeError):
    """Raised when a real MCP tool call could not be completed at all."""


class McpProgressToolClient(ProgressToolClient):
    """The real Progress MCP client. See module docstring for session model."""

    def __init__(self, *, server_url: str, workflow_id: str, request_id: str):
        self.server_url = server_url
        self.workflow_id = workflow_id
        self.request_id = request_id

    def compare_assessments(self, *, baseline_assessment=None, previous_assessment=None, current_assessment=None) -> dict:
        return self._call_tool(
            "compare_assessments_tool",
            {
                "baseline_assessment": baseline_assessment,
                "previous_assessment": previous_assessment,
                "current_assessment": current_assessment,
            },
        )

    def calculate_adherence(self, *, plan_record, exercise_results=None) -> dict:
        return self._call_tool(
            "calculate_adherence_tool",
            {"plan_record": plan_record, "exercise_results": exercise_results or []},
        )

    def check_reassessment_required(self, *, current_assessment_completed_at=None) -> dict:
        return self._call_tool(
            "check_reassessment_required_tool",
            {"current_assessment_completed_at": current_assessment_completed_at},
        )

    def calculate_nutrition_adherence(
        self, *, nutrition_plan, food_log_entries=None, period_start=None, period_end=None
    ) -> dict:
        return self._call_tool(
            "calculate_nutrition_adherence_tool",
            {
                "nutrition_plan": nutrition_plan,
                "food_log_entries": food_log_entries or [],
                "period_start": period_start,
                "period_end": period_end,
            },
        )

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        arguments = {
            **arguments,
            "workflow_id": self.workflow_id,
            "request_id": self.request_id,
        }

        try:
            return asyncio.run(self._call_tool_async(tool_name, arguments))

        except Exception as error:  # noqa: BLE001
            raise McpToolCallError(
                f"MCP tool call {tool_name!r} failed: {error}"
            ) from error

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> dict:
        async with streamablehttp_client(self.server_url) as (
            read_stream,
            write_stream,
            get_session_id,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(tool_name, arguments=arguments)

                if result.structuredContent is not None:
                    return _attach_session_id(
                        result.structuredContent, get_session_id()
                    )

                # Not every SDK version populates structuredContent. mcp
                # 1.29 returns a dict-returning tool's result as a JSON text
                # block instead, so the payload is present and correct but
                # in the other place. Parsing it here reads the real
                # response rather than reconstructing one.
                #
                # This used to fall straight through to the error below,
                # which made a perfectly good result look like a protocol
                # failure -- invisibly, since these tests could not run
                # without the `mcp` package installed.
                for block in result.content or []:
                    text = getattr(block, "text", None)

                    if not text:
                        continue

                    try:
                        parsed = json.loads(text)

                    except (TypeError, ValueError):
                        continue

                    if isinstance(parsed, dict):
                        return _attach_session_id(parsed, get_session_id())

                # Genuinely unreadable: no structured content and no content
                # block carrying a JSON object. Reported, never guessed at.
                return {
                    "error": (
                        "MCP tool call returned no structuredContent and no "
                        "content block carrying a JSON object"
                    ),
                    "raw_content": [str(block) for block in result.content],
                }
