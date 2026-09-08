"""The real MCP client: Nutrition Agent -> MCP Client -> Nutrition MCP Server.

Mirrors physio_agent/mcp_client.py exactly, including its disclosure: this
module could not be executed in this development sandbox (no PyPI network
access to install `mcp`, confirmed unchanged from Phase 2/3). It is written
against the SDK's documented, stable public client API from training
knowledge, not executed here.
"""

import json
import asyncio

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to use McpNutritionToolClient. Install it with "
        "`pip install mcp` inside backend's virtual environment. Nothing "
        "else in MoveWell AI depends on this package. For testing the "
        "Nutrition Agent's own decision logic without a live MCP server, "
        "see tool_client.py's InProcessNutritionToolClient (test-only)."
    ) from exc

from nutrition_agent.tool_client import NutritionToolClient


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
    """Raised when a real MCP tool call could not be completed at all
    (transport/connection failure, not a tool-level {"error": ...} result)."""


class McpNutritionToolClient(NutritionToolClient):
    """The real Nutrition MCP client. See module docstring for session model."""

    def __init__(self, *, server_url: str, workflow_id: str, request_id: str):
        self.server_url = server_url
        self.workflow_id = workflow_id
        self.request_id = request_id

    def search_nutrition_guidance(self, **kwargs) -> dict:
        return self._call_tool("search_nutrition_guidance_tool", kwargs)

    def get_nutrition_topic_details(self, topic_id: str) -> dict:
        return self._call_tool(
            "get_nutrition_topic_details_tool", {"topic_id": topic_id}
        )

    def search_food(self, query: str) -> dict:
        return self._call_tool("search_food_tool", {"query": query})

    def get_food_details(self, food_id: str) -> dict:
        return self._call_tool("get_food_details_tool", {"food_id": food_id})

    def record_food_log(self, entry: dict, *, user_id: str, plan_id: str = None) -> dict:
        return self._call_tool(
            "record_food_log_tool",
            {"entry": entry, "user_id": user_id, "plan_id": plan_id},
        )

    def calculate_food_adherence(
        self, plan_record: dict, food_log_entries: list, *, period_start=None, period_end=None
    ) -> dict:
        return self._call_tool(
            "calculate_food_adherence_tool",
            {
                "plan_record": plan_record,
                "food_log_entries": food_log_entries,
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

        except Exception as error:  # noqa: BLE001 — re-raised as our own type
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
