"""Running one agent: call, validate, check, retry once, or refuse.

Every agent goes through this function, so the order of operations is the same
each time and cannot be forgotten in a new one. Validate the structure before
checking the content, because a check applied to unvalidated input is checking
whatever the model happened to send. Check before returning, because the point
of a check that runs afterwards is that nothing gets past it.

One retry, and only one. A blunt rule catches innocent phrasing sometimes, and a
second attempt with the broken rules named nearly always resolves it. A third
attempt would mean the model is not going to comply, and quietly trying until
something passes is a way of selecting for a response that slipped through
rather than one that was right.
"""

from agents.guardrails import (
    GuardrailViolation,
    check_payload,
    correction_instruction,
)
from agents.outputs import AgentOutputError

MAX_ATTEMPTS = 2

EMPTY_RESPONSE_INSTRUCTION = (
    "Your previous response could not be used because the required parts were "
    "missing or empty. Answer again and fill in every required field with real "
    "content drawn from the information you were given. If a section has nothing "
    "to put in it, say what is missing rather than leaving it blank."
)


def run_agent(*, model, system: str, user_text: str, tool: dict, parse) -> dict:
    """Produce one validated, checked agent response.

    Returns the parsed response together with how it was reached, so a caller
    can record that a retry was needed. Raises AgentUnavailable or AgentFailed
    from the model, AgentOutputError if nothing usable came back twice, or
    GuardrailViolation if a rule was broken twice.
    """

    correction = None
    broken = []
    attempts = 0

    while attempts < MAX_ATTEMPTS:
        attempts += 1

        raw = model.call(system, user_text, tool, extra_user_text=correction)

        try:
            parsed = parse(raw)

        except AgentOutputError:
            if attempts >= MAX_ATTEMPTS:
                raise

            correction = EMPTY_RESPONSE_INSTRUCTION

            continue

        broken = check_payload(parsed)

        if not broken:
            return {
                "output": parsed,
                "attempts": attempts,
                "retriedAfterRuleBreak": attempts > 1,
            }

        correction = correction_instruction(broken)

    raise GuardrailViolation(broken)
