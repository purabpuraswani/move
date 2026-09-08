"""Bridging Phase 0's observability IDs into an MCP tool call.

Deliberately tiny, and deliberately not a new ID scheme: everything here is
`orchestration.ids.TraceContext` (backend/orchestration/ids.py), read and
carried, never reissued with different semantics. This module's only job is
to shape those five ids into the small metadata block every Exercise MCP
tool result attaches to its structured output, so a caller (eventually the
Physio Agent, tracing a tool call back through workflow -> request ->
agent run -> MCP session -> tool call) has something to read regardless of
which tool it called.
"""

from orchestration.ids import TraceContext, start_tool_call


def tool_call_metadata(parent: TraceContext, *, mcp_session_id: str = None) -> dict:
    """Derive a tool-call TraceContext from `parent` and return it as a dict.

    `mcp_session_id` is accepted, not generated — see orchestration/ids.py
    and this package's own docstring on why a fake one is never minted here.
    A caller with no real MCP session yet (Phase 2 has no MCP client) simply
    omits it, and the field stays null, honestly.
    """

    trace = start_tool_call(parent, mcp_session_id=mcp_session_id)

    return trace.as_dict()
