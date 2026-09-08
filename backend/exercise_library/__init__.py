"""The Exercise Library: structured intervention exercises, separate from the
three baseline assessment tests.

The baseline tests (backend/assessments/, src/assessment/) exist to measure
where a user starts. This package exists to hold what a user might be asked
to *do* about it — a library a future Physio Agent will select from, not a
fourth assessment test and not itself a decision-maker. Nothing in this
package decides which exercise a user should do; that is Phase 3 (Physio
Agent) work. This package only makes the options available in a structured,
queryable, reviewable form.

Ten exercises were implemented in Phase 2, chosen and drafted from two public,
freely citable sources — the National Institute on Aging's Go4Life program
(go4life.nia.nih.gov) and the CDC's STEADI initiative (the 4-Stage Balance
Test) — both aimed at exactly this population (older or deconditioned adults,
fall-prevention and everyday functional movement). Each exercise records its
`reference` field so the source is never lost, and every safety constraint or
progression note is written as this project's own plain-language adaptation,
not a verbatim clinical protocol. A second batch of ten general
wellness/mobility/strength exercises was added afterward to reach twenty,
using the exact same schema and validation, drawn from general
exercise-science knowledge rather than a newly named source, filling
difficulty/category gaps the first ten left (see data.py's
GENERAL_REFERENCE). None of this is a substitute for a
physiotherapist's review before real use — see docs/architecture.md's
Exercise Library section for how that review is expected to happen.

    schema.py    the Exercise data shape and validate_exercise()
    data.py      the twenty exercises, as data
    catalog.py   search_exercises(), get_exercise_details(),
                 check_exercise_constraints() — pure functions over data.py,
                 with no database, no model call, and no agent behind them.
                 These are exactly the functions backend/mcp_servers/exercise_server.py
                 wraps as MCP tools; they are written and tested independently
                 of MCP so the domain logic is verifiable without the MCP SDK
                 installed.
"""
