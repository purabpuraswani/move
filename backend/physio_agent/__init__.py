"""The Physio Agent — the first genuinely functional specialist agent.

Responsible for movement/exercise intervention only: reading physical
Need Profile dimensions and physical assessment data, retrieving candidate
exercises through the Exercise MCP capability (never the exercise library
directly), applying a deterministic, explainable safety gate, and returning
a structured Agent Result (backend/orchestration/agent_result.py) carrying
an exercise plan with a plain-language rationale per exercise.

What the Physio Agent is NOT:
  - not a diagnosis engine — it never names a condition, only observed
    needs and exercise categories ("supports balance training", never
    "treats your balance disorder");
  - not a replacement for a physiotherapist;
  - not given raw webcam frames or raw MoveNet keypoints — its input
    (input_contract.py) carries only already-derived, already-validated
    structured data;
  - not free to touch arbitrary User State fields — the Orchestrator
    (backend/orchestrator/) is the only thing that writes the Agent
    Result's effects back into the User State, through one dedicated
    function, the same discipline Phase 1's apply_need_profile() set;
  - not a hard-coded exercise list — see agent.py's module docstring for
    why, and tool_client.py for how it actually calls the Exercise MCP
    capability instead of importing exercise_library directly.

Package layout:
    input_contract.py  the minimized, structured input the agent reads
    plan_schema.py      the structured, validated exercise-plan shape
    tool_client.py       the ExerciseToolClient interface the agent talks
                          to, plus an explicitly-labelled in-process test
                          double used only by this project's own tests
    mcp_client.py         the REAL MCP client implementation of that
                          interface — what production code must use
    agent.py              the agent's actual execution lifecycle
"""
