"""Shared plumbing for the future orchestrator and specialist agents.

Phase 0 adds two things here, and nothing else:

    ids.py            the five observability identifiers every future agent
                       run and tool call will carry.
    agent_result.py    the one result shape every future specialist agent
                       (Physio, Nutrition, Behaviour, Progress, Safety) will
                       return to the Orchestrator.

Neither module talks to a database, a model provider, or MCP. That is
deliberate: this package is the contract other code will be written against,
so it has to be stable and trivially testable before anything depends on it.

Nothing in this package is a fake version of the orchestrator, an agent, or
an MCP session. There is no orchestrator implementation here yet — dynamic
agent selection from a need profile is Phase-3 work — and mcp_session_id
below is always None until a real MCP transport exists to issue one.
"""
