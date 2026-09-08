"""The five observability identifiers, and nothing that fakes what they trace.

    workflow_id     one whole user workflow, start to finish
                    (e.g. one guidance run, one exercise session)
    request_id      one HTTP request into the backend
    agent_run_id    one execution of one agent inside that request
    tool_call_id    one invocation of one tool by that agent
    mcp_session_id  the real MCP protocol session an agent's MCP client is
                    using, when it is using one. Nullable, and it must stay
                    null until an actual MCP transport exists to open one.
                    Nothing here issues a value for it — see the module
                    docstring on why.

These identifiers are application-level tracing, not MCP protocol state.
mcp_session_id is a *reference* to a session id that some future MCP client
module will obtain from a real handshake; this module never invents one.
Conflating the two would be exactly the "fake handshake" the target
architecture rules out.

Each id is a short, prefixed, sortable-enough token — not a bare UUID —
so a log line or a dashboard row is identifiable by eye before you match it
against anything else: "run_3f2a..." next to "tool_9b10..." already tells you
which is which.
"""

from dataclasses import dataclass, replace
from typing import Optional
from uuid import uuid4


def _token(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_workflow_id() -> str:
    return _token("wf")


def new_request_id() -> str:
    return _token("req")


def new_agent_run_id() -> str:
    return _token("run")


def new_tool_call_id() -> str:
    return _token("tool")


def new_mcp_session_id() -> Optional[str]:
    """Always None in Phase 0.

    There is no MCP transport yet, so there is nothing to open a session
    with. This function exists so that call sites are already written
    against the eventual signature (something that returns a session id or
    None) rather than needing to be rewritten when MCP arrives — at which
    point this becomes a real handshake, not a random token generator.
    """

    return None


ID_PREFIXES = {
    "workflow_id": "wf",
    "request_id": "req",
    "agent_run_id": "run",
    "tool_call_id": "tool",
}


@dataclass(frozen=True)
class TraceContext:
    """The identifiers one piece of work carries through the system.

    Immutable on purpose: a TraceContext is derived into a narrower one for a
    nested unit of work (a request inside a workflow, an agent run inside a
    request, a tool call inside an agent run) rather than mutated in place,
    so a log statement holding a reference to one can never see it change
    under it.
    """

    workflow_id: str
    request_id: str
    agent_run_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    mcp_session_id: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "tool_call_id": self.tool_call_id,
            "mcp_session_id": self.mcp_session_id,
        }


def start_workflow(*, workflow_id: Optional[str] = None) -> TraceContext:
    """Begin tracing a new workflow, e.g. one guidance run or exercise session.

    A caller that already has a workflow_id (continuing a workflow that spans
    more than one request) passes it in; a caller starting a new one leaves it
    out.
    """

    return TraceContext(
        workflow_id=workflow_id or new_workflow_id(),
        request_id=new_request_id(),
    )


def start_agent_run(parent: TraceContext) -> TraceContext:
    """Derive the trace context for one agent execution inside `parent`.

    Keeps workflow_id and request_id, issues a fresh agent_run_id, and clears
    tool_call_id and mcp_session_id — a new agent run has made no tool calls
    and opened no MCP session yet.
    """

    return replace(
        parent,
        agent_run_id=new_agent_run_id(),
        tool_call_id=None,
        mcp_session_id=None,
    )


def start_tool_call(
    parent: TraceContext, *, mcp_session_id: Optional[str] = None
) -> TraceContext:
    """Derive the trace context for one tool call inside an agent run.

    `mcp_session_id` is accepted, not generated: whatever MCP client module
    eventually makes this call passes in the session id its own handshake
    established (or None, for a stateless call, or when the tool is not an
    MCP tool at all).
    """

    if parent.agent_run_id is None:
        raise ValueError(
            "a tool call must be derived from a TraceContext that already has "
            "an agent_run_id — start_agent_run() first"
        )

    return replace(
        parent,
        tool_call_id=new_tool_call_id(),
        mcp_session_id=mcp_session_id,
    )
