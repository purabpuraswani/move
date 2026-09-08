"""The care navigation agent.

Suggests the kind of professional a person might choose to talk to, and what they
could usefully ask when they get there. The most delicate of the three agents,
because a suggestion to see someone carries an implied reason, and an implied
reason is a diagnosis the person never agreed to hear.

Two constraints do most of the work. The role is chosen from a fixed list of
general professionals rather than written by the model, so no specialty can be
named and no condition implied by the choice. And the suggestion is framed as
something the person may wish to raise, never as something they need to have
looked at, because whether anything needs looking at is not knowable from here.

It runs third, after the wellness agent, and is given that agent's focus areas so
that both halves of the response point at the same things. Working it out again
independently would produce two lists that disagree, and a person reading them
would have no way to tell which one to believe.
"""

from agents.base import run_agent
from agents.context import context_digest
from agents.guardrails import SHARED_RULES
from agents.outputs import NAVIGATION_TOOL, PROFESSIONAL_TYPES, parse_navigation

AGENT_ID = "care_navigation"

_ROLE_LIST = "\n".join(
    f"- {key}: {value['label']}" for key, value in PROFESSIONAL_TYPES.items()
)

ROLE = f"""\
YOUR PART

You help someone work out who they might talk to, and what to ask. You are not
making a referral, you are not triaging, and you are not deciding that anything
needs attention. You are laying out options a person can take or leave.

Choose the kind of professional from this list and nothing else:

{_ROLE_LIST}

Never name a medical specialty, not even as an example. Sending someone to a
particular specialist tells them what you think is wrong with them, which is a
diagnosis whatever words it is wrapped in.

Frame every suggestion as something the person may wish to raise if they want to.
"You may find it useful to mention how much you sit to a physiotherapist" is
right. "You should have your shoulder checked" is not, because it says something
needs checking and you cannot know that.

Write the questions in the person's own voice, as things they could ask. A
question is safe where an answer would not be: "is this something I should be
paying attention to?" belongs to their clinician, not to you.

If there is little information to work from, say so and suggest less. One good
suggestion beats five padded ones, and a suggestion invented to fill the list
implies a concern that nothing supports.
"""

SYSTEM_PROMPT = SHARED_RULES + "\n\n" + ROLE

TASK = """\
Suggest who this person might choose to talk to, and what they could ask.

Use the information below and the wellness guidance that has already been written
for them, so that the two agree with each other. Say what each kind of
professional could look at, in the wording of a suggestion. Give questions they
could take with them. Finish with what this tool could not tell them, so they
know what to ask about rather than assume.
"""


def _wellness_recap(wellness_output) -> str:
    """The other agent's conclusions, as short lines.

    Only the headings and the reasons behind them. Passing the whole response
    would invite this agent to reword it, and the person is going to read both.
    """

    if not isinstance(wellness_output, dict):
        return ""

    lines = []

    for area in wellness_output.get("focusAreas") or []:
        if not isinstance(area, dict):
            continue

        title = area.get("title")

        if not title:
            continue

        why = area.get("whyThisCameUp")

        lines.append(f"- {title}" + (f" (because {why})" if why else ""))

    for gap in wellness_output.get("missingInformation") or []:
        if isinstance(gap, str) and gap.strip():
            lines.append(f"- Noted as missing: {gap.strip()}")

    if not lines:
        return (
            "WELLNESS GUIDANCE ALREADY WRITTEN\nNothing was picked out, so work "
            "from the information below alone."
        )

    return "WELLNESS GUIDANCE ALREADY WRITTEN\nFocus areas it identified:\n" + \
        "\n".join(lines)


def build_prompt(context: dict, wellness_output=None) -> str:
    """The user message: the task, the other agent's output, then the context."""

    parts = [TASK, _wellness_recap(wellness_output), context_digest(context)]

    return "\n\n".join(part for part in parts if part)


def run(context: dict, *, model, wellness_output=None) -> dict:
    """Produce validated, checked care navigation for one context."""

    return run_agent(
        model=model,
        system=SYSTEM_PROMPT,
        user_text=build_prompt(context, wellness_output),
        tool=NAVIGATION_TOOL,
        parse=parse_navigation,
    )
