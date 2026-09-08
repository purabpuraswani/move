"""Need Assessment: turning a User State into a structured Need Profile.

    User State  ->  Need Assessment  ->  Need Profile  ->  User State.current_needs

This package reads a User State (backend/user_state/schema.py) and produces a
Need Profile: a level (LOW / MEDIUM / HIGH / NOT_ASSESSED) per dimension, with
a score, evidence, and confidence attached to each — never a bare label with
no explanation behind it.

What this package is not: it is not a diagnosis. "stability_need = HIGH" is a
statement about where an intervention may help, not a claim that the user has
a balance disorder — see rules.py's module docstring for how each dimension is
phrased to keep that distinction. It is not a specialist agent, and it does
not decide which agents should run; it produces the input a future
Orchestrator will use to make that decision (Phase 3), and it is not that
Orchestrator itself. It does not implement MCP, and it does not touch MoveNet
or any assessment-scoring code — it only reads the already-computed
measurements a completed assessment session carries in the User State.

    schema.py       the Need Profile shape: dimensions, levels, and the
                     level/score/evidence/confidence envelope every dimension
                     entry has, plus validation.
    rules.py         the actual derivation: one function per dimension, each
                     a pure function of the relevant User State section(s),
                     with its thresholds named and documented as system
                     decisions, not clinical cutoffs.
    assessment.py    assemble_need_profile() (User State -> Need Profile) and
                     apply_need_profile() (Need Profile -> an updated User
                     State with current_needs populated).

Determinism: every function in this package is pure and threshold-based —
same User State in, same Need Profile out, every time. Nothing here calls a
model, reads a clock for anything but the `generatedAt` timestamp, or uses
randomness.
"""
