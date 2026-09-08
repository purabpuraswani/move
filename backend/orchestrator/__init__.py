"""The real Orchestrator — the first one that actually runs an agent.

Not the same module as the old `agents/orchestrator.py`, which runs the old
LLM-driven wellness_guidance/care_navigation pipeline (a distinct,
still-active capability — see docs/architecture.md's Phase 3 section for
why that one was not removed). This package is new, and reads only the
Phase 0/1/2 contracts:

    User State  ->  current_needs  ->  Orchestrator  ->  (Physio Agent?)  ->  Updated User State

Layout:
    decision.py     dynamic, explainable Physio-selection rule
    state_update.py the one sanctioned function that writes a Physio Agent
                     Result's effect back into exercise_history
    orchestrator.py run_workflow() — the actual end-to-end execution
"""
