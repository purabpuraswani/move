"""The Safety Gate: a deterministic check over specialist-agent outputs.

This is NOT another specialist agent producing recommendations of its own
— it sits across the pipeline, downstream of Physio/Behaviour/Nutrition,
deciding whether their candidate recommendations may reach the user at
all. It never performs unrestricted AI diagnosis; every decision here
comes from a named, deterministic rule reading data this application
actually has: an exercise's own declared `difficulty` (from
exercise_library), a confirmed medical report on file
(user_state["medical_context"]["data"]["confirmed_reports"] — never
self-reported and never unconfirmed report extraction), and the Need
Profile's own `safety_status` field.

    schema.py   the Safety Result contract (ALLOW/MODIFY/PAUSE/REFER/
                NOT_ASSESSED) and its validator
    rules.py    the actual deterministic rules, each named and documented
    gate.py     evaluate_safety() — the one entry point the Orchestrator calls

Consistent with need_assessment/rules.py's assess_safety_status(), which
is always NOT_ASSESSED in this application (no validated escalation rule
set exists that would justify a REFER outcome from that layer): this
module does not invent clinical red flags either. Where there is
insufficient validated information to make a safety judgment, the honest
answer is NOT_ASSESSED — never a false ALLOW.
"""
