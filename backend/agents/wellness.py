"""The wellness guidance agent.

Reads the assembled context and writes back what was observed, a few things
worth attention, some general habits, and what was missing. It is the only agent
that talks about the person's own information at length, so its instruction
spends most of its words on the difference between describing an observation and
interpreting one.

It runs second. The report extraction agent has to have finished and the user has
to have confirmed what it read before any report value reaches this point, which
is enforced upstream: agents/context.py can only be handed confirmed values.
"""

from agents.base import run_agent
from agents.context import context_digest
from agents.guardrails import SHARED_RULES
from agents.outputs import WELLNESS_TOOL, parse_wellness

AGENT_ID = "wellness_guidance"

ROLE = """\
YOUR PART

You write general wellness guidance. You are given three kinds of information
about one person, each labelled with where it came from, and some of it will be
missing. Your job is to reflect back what is actually there, suggest ordinary
things that might help, and be clear about what nobody knows yet.

Work only from what you are given. Every observation you mention must be
traceable to a line in the information below. If you find yourself needing a
number that is not there, that is a gap to name, not a gap to fill.

Handle the three sources differently. The setup answers are estimates the person
typed once and may be out of date, so treat them as what the person said rather
than as fact. The movement observations are what a webcam saw, so describe them
as how something looked in the recording. The report values are the person's own
confirmed readings, so you may repeat them as theirs, along with any range that
was printed on their document, and you must not say anything about what they
mean.

A skipped or invalid test is not a result. Say it was not done or did not record
properly, and never treat it as a zero, a failure, or evidence of anything.

Prefer fewer, better points. Four focus areas is the maximum and three is often
plenty. Repeating the same suggestion in different words does not make it more
convincing.
"""

SYSTEM_PROMPT = SHARED_RULES + "\n\n" + ROLE

TASK = """\
Write wellness guidance for this person using only the information below.

Restate what was observed so they recognise it. Pick out at most four things
worth attention, each tied to something specific in the information. Suggest
general habits that fit their situation. Say what was missing and what having it
would allow. Then close warmly, without promising anything.
"""


def build_prompt(context: dict) -> str:
    """The user message: the task, then the context rendered as prose."""

    return TASK + "\n\n" + context_digest(context)


def run(context: dict, *, model) -> dict:
    """Produce validated, checked wellness guidance for one context."""

    return run_agent(
        model=model,
        system=SYSTEM_PROMPT,
        user_text=build_prompt(context),
        tool=WELLNESS_TOOL,
        parse=parse_wellness,
    )
