"""The shared User State: one structured account of a user for future agents.

Phase 0 introduces this package as the foundation the rest of the agentic
architecture (need analysis, the orchestrator, and the specialist agents that
come after it) will read from. Nothing reads or writes through this package
yet outside its own tests — building it before anything depends on it is the
point, so its shape can be reviewed before code accumulates around it.

The design carries over a rule that already existed in agents/context.py:
gaps are stated, not filled. A section with nothing behind it says so, with a
reason, rather than being omitted or defaulted to a value that looks like
data. That is what makes a partially-onboarded user representable at all, and
it is why every section below is independently optional.

This package deliberately does not import anything from agents/. The old
agents package is scheduled for removal once the specialist agents replace it
(see backend/agents/__init__.py and the Phase 0 report), and the User State is
meant to outlive that removal. It reads the same underlying stores
(assessments/store.py, reports/store.py, the profile document) but does not
share code with the wellness/navigation pipeline.

    schema.py   section shapes, build_user_state(), validate_user_state()
"""
