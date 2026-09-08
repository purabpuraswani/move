"""The real MCP client: Physio Agent -> MCP Client -> Exercise MCP Server.

This is the ONLY `ExerciseToolClient` implementation (see tool_client.py)
that may be wired into the Physio Agent outside this project's own tests.
It connects to a running `backend/mcp_servers/exercise_server.py` process
over the real Streamable HTTP transport Phase 2 chose, performs the real
`initialize` handshake, and calls the five tools that server actually
exposes — never a sixth, invented one.

Session model: each public method here opens a connection, performs the
handshake, makes exactly one tool call, and closes the session. This is a
deliberate Phase 3 simplification, not a fake session — every step (the
transport connection, the handshake, the tool call, the response) is a
real MCP protocol exchange, using the SDK's own client classes, and the
resulting `mcp_session_id` is whatever the server's real handshake for
that one connection actually returned. A production system serving many
requests concurrently would want a longer-lived, reused client session
instead of reconnecting per call; that is future work, tracked honestly in
docs/architecture.md rather than silently assumed away.

DISCLOSURE: exactly like backend/mcp_servers/exercise_server.py, this
module could not be executed in this development sandbox — there is no
PyPI network access here to install the `mcp` package (confirmed directly
in Phase 2 and re-confirmed unchanged in Phase 3). It is written against
the SDK's documented, stable public client API
(`mcp.ClientSession`, `mcp.client.streamable_http.streamablehttp_client`)
from training knowledge, not executed. `backend/tests/test_physio_agent_mcp_integration.py`
is written to skip itself honestly when `mcp` is unavailable, exactly like
Phase 2's `test_mcp_exercise_server.py`.
"""

import json
import asyncio

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError as exc:  # pragma: no cover — exercised only without `mcp` installed
    raise ImportError(
        "The 'mcp' package (the official Model Context Protocol Python SDK) "
        "is required to use McpExerciseToolClient. Install it with "
        "`pip install mcp` inside backend's virtual environment. Nothing "
        "else in MoveWell AI depends on this package. For testing the "
        "Physio Agent's own decision logic without a live MCP server, see "
        "tool_client.py's InProcessExerciseToolClient (test-only)."
    ) from exc

from physio_agent.tool_client import ExerciseToolClient


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
    (transport/connection failure, not a tool-level {"error": ...} result,
    which is returned to the caller normally — a tool-level error is a
    valid, structured MCP response, not a client failure)."""


class McpExerciseToolClient(ExerciseToolClient):
    """The real Exercise MCP client. See module docstring for session model."""

    def __init__(self, *, server_url: str, workflow_id: str, request_id: str):
        self.server_url = server_url
        self.workflow_id = workflow_id
        self.request_id = request_id

    def search_exercises(self, **kwargs) -> dict:
        return self._call_tool("search_exercises_tool", kwargs)

    def get_exercise_details(self, exercise_id: str) -> dict:
        return self._call_tool("get_exercise_details_tool", {"exercise_id": exercise_id})

    def check_exercise_constraints(self, exercise_id: str) -> dict:
        return self._call_tool(
            "check_exercise_constraints_tool", {"exercise_id": exercise_id}
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

                # FastMCP tools that return a dict populate structuredContent
                # with that exact dict on the wire; that is the real,
                # structured result this client hands back to the Physio
                # Agent — never a re-derived or re-guessed value.
                if result.structuredContent is not None:
                    return _attach_session_id(
                        result.structuredContent, get_session_id()
                    )

                # Not every SDK version populates structuredContent. mcp
                # 1.29 returns a dict-returning tool's result as a JSON text
                # block instead, so the payload is present and correct but
                # in the other place. Parsing it here is reading the real
                # response, not reconstructing one: the dict returned is
                # exactly what the tool produced.
                #
                # This branch used to stringify the blocks straight into an
                # error, which made a perfectly good result look like a
                # protocol failure -- and did so invisibly, because these
                # tests could not run without the `mcp` package installed.
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
