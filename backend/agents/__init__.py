"""The agents, and the boundary they work inside.

Three agents run in a fixed order, each reading only what the one before it
produced.

    1. report_extraction  — reports/extraction.py, run when a report is
                            uploaded. Transcribes; nothing more. Its output is
                            candidate data that the user must check and confirm.
    2. wellness_guidance  — agents/wellness.py. Restates what was observed and
                            suggests general habits.
    3. care_navigation    — agents/navigation.py. Suggests a kind of
                            professional and questions to ask, from the wellness
                            agent's conclusions.

The modules, and why each one is separate:

    context.py      what an agent may know, assembled and rendered. Standard
                    library only, so the boundary is testable.
    sources.py      the only code that fetches data for an agent.
    guardrails.py   the rules given to the model, and the check applied to what
                    comes back.
    outputs.py      the shapes a response may have, and the reading of it.
    base.py         call, validate, check, retry once, or refuse.
    llm.py          the model transport, with the socket injectable.
    plan.py         what can run, what is blocking it, and what would help.
    orchestrator.py the sequence, with each agent's trouble reported as its own.
    registry.py     what each agent is and is not allowed to do, in one place.
    store.py        the last run, kept so opening a page costs nothing.

The rule that holds all of it together: only report values the user has confirmed
can reach an agent, and that is not a check any of these modules performs. It
follows from reports/store.py refusing to serialise anything else.
"""
