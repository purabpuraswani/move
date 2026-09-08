"""The Progress Agent: deterministic comparison over real historical data.

Mirrors the structural discipline of backend/physio_agent/,
backend/nutrition_agent/, and backend/behaviour_agent/, but this agent
produces no plan of its own — it produces a structured comparison
(baseline vs current, previous vs current) plus an adaptation
recommendation for the Orchestrator, which is the only thing allowed to
act on it (see orchestrator/orchestrator.py). The Progress Agent never
selects an exercise, a nutrition goal, or a habit goal itself — that
remains Physio/Nutrition/Behaviour's job.

    comparison.py     the deterministic, direction-aware metric comparator
    adherence.py       the deterministic adherence/completion-rate calculator
    schema.py          PROGRESS_DIRECTIONS, ADAPTATION_RECOMMENDATIONS, and
                        a findings validator
    input_contract.py  the minimized structured input this agent receives
    tool_client.py      the interface + test-only in-process double
    mcp_client.py        the real MCP client
    agent.py              the execution lifecycle (AGENT_ID = "progress")

Non-diagnostic: this agent never claims a clinical outcome, an injury, or
a disease. "DECLINED" means a measured value moved the wrong way against
this project's own thresholds — nothing more.
"""
