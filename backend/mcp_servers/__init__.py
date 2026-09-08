"""Capability-oriented MCP servers — Phase 2 implements exactly one.

    Assessment MCP    Exercise MCP    User/Health MCP
    Nutrition MCP     Behaviour MCP   Progress MCP    Safety/Referral MCP

Only Exercise MCP (exercise_server.py) has real tools in Phase 2. The other
six are named here only as the shape this package is meant to grow into —
none of them exist yet, and nothing in this package pretends otherwise.

SDK, protocol, and transport — decided, not guessed
--------------------------------------------------

SDK: the official Model Context Protocol Python SDK, package name `mcp` on
PyPI (https://github.com/modelcontextprotocol/python-sdk), used through its
high-level `mcp.server.fastmcp.FastMCP` server class and `@tool()` decorator.
This is a real, separate dependency — see backend/requirements.txt — not
something this project vendors or reimplements.

Protocol version: not hardcoded here. MCP's initialize handshake negotiates
the protocol version between client and server, and the installed `mcp`
package is what actually implements that negotiation; pinning a version
number in this codebase would be describing behaviour we do not own and
cannot enforce. What we do control, and do pin, is the SDK version
(backend/requirements.txt), because that determines which protocol
version(s) the server on this end is capable of negotiating.

Transport: Streamable HTTP, run as its own standalone ASGI process
(`python -m mcp_servers.exercise_server`), not merged into the existing
FastAPI app on backend/main.py. Two reasons, both practical rather than
aesthetic. First, Streamable HTTP is the SDK's stateful transport — it
issues a real `Mcp-Session-Id` on initialize and expects it back on every
subsequent request — which is what lets this project's own `mcp_session_id`
observability field (backend/orchestration/ids.py) hold something genuine
instead of staying null forever; the alternative, stdio, has no
protocol-level session identifier at all, only a process's lifetime,
which would make that field meaningless for this transport. Second, running
it standalone means this module's exact ASGI-mounting call (which varies
across `mcp` SDK versions — some expose `.streamable_http_app()`, others
mount differently) never has to match backend/main.py's FastAPI app
construction; `FastMCP.run(transport="streamable-http")` is the SDK's own
stable, documented entrypoint for exactly this, so it is what this module
uses to start.

Session model: stateful, per the Streamable HTTP transport's own design —

    connect (HTTP POST to the server's endpoint)
        -> initialize / capability negotiation
        -> server returns a session id (Mcp-Session-Id header)
        -> every further request from that client carries the same header
        -> multiple tool calls reuse the one negotiated session
        -> the client closes the session (or it expires) when done

This project does not run a session handshake before every tool call — that
would be inventing behaviour the transport does not have. It also does not
mint its own fake session ids: `orchestration.ids.new_mcp_session_id()`
still always returns None (see backend/orchestration/ids.py's own docstring)
because nothing in Phase 2 is an MCP *client* yet — that is Phase 3, when
the Physio Agent's MCP client performs the real handshake and receives a
real session id from whichever server it is talking to. What Phase 2
guarantees is that when that client exists, the session id it gets back is
a genuine one, not a placeholder this project invented in advance to fill a
field.

A note on verification, stated plainly rather than glossed over: this
sandbox's network policy blocks package installation from PyPI, including a
plain `pip install mcp` (confirmed — see the Phase 2 report), so the code in
exercise_server.py has not been executed against the real `mcp` package in
this session. It is written against that package's documented, stable
high-level API (`FastMCP`, `@tool()`, `.run(transport=...)`), and the domain
logic it wraps (exercise_library, exercise_assessment) is fully executable
and fully tested without `mcp` installed at all — see
backend/tests/test_mcp_exercise_server.py, which skips itself (rather than
faking a pass) when the package is not present, and runs for real the
moment it is.
"""
