"""Running the agents in order, and reporting honestly on each one.

The sequence is fixed: the report reader first, then wellness guidance, then care
navigation, each stage only ever reading what the stage before it produced. The
first of those does not run here — it runs when a report is uploaded, and its
output has to be confirmed by the user before it can enter a context at all,
which is what makes the ordering a property of the data rather than a habit of
this function.

Failures are isolated per agent, and named rather than smoothed over. Three
things can go wrong for different reasons and a person deserves to be told which:
nothing was configured, the provider had a problem, or the response broke a rule
and was withheld. A single "guidance unavailable" for all three would hide a
withheld response, which is the one case where something did happen and the user
has a right to know.

One exception to the isolation. A provider failure in the wellness agent means
the next call will fail the same way, so navigation is skipped rather than
retried into the same wall. A withheld response is different: that was the
model's wording, not the provider, and the next agent may well be fine.
"""

from datetime import datetime, timezone

from agents import navigation, wellness
from agents.context import context_summary
from agents.guardrails import DISCLAIMER, SAFETY_NOTE, GuardrailViolation
from agents.llm import AgentFailed, AgentUnavailable, model_status, select_model
from agents.outputs import AgentOutputError
from agents.plan import guidance_plan
from agents.registry import describe_agents
from reports.extraction import extraction_status

STATE_OK = "ok"
STATE_WITHHELD = "withheld_by_safety_rules"
STATE_FAILED = "failed"
STATE_NOT_RUN = "not_run"

WITHHELD_MESSAGE = (
    "This part was written but did not pass the safety rules this application "
    "applies to everything an AI writes here, so it was not shown. Nothing was "
    "edited to make it acceptable."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_one(agent_module, context, **kwargs) -> dict:
    """Run one agent, turning each kind of trouble into a described state."""

    try:
        result = agent_module.run(context, **kwargs)

        return {
            "state": STATE_OK,
            "output": result["output"],
            "attempts": result["attempts"],
            "retriedAfterRuleBreak": result["retriedAfterRuleBreak"],
            "message": None,
            "brokenRules": [],
        }

    except GuardrailViolation as violation:
        return {
            "state": STATE_WITHHELD,
            "output": None,
            "attempts": None,
            "retriedAfterRuleBreak": True,
            "message": WITHHELD_MESSAGE,
            # Descriptions of what was wrong, never the offending text. Echoing
            # a withheld sentence back to explain why it was withheld would
            # defeat withholding it.
            "brokenRules": violation.rules,
        }

    except AgentOutputError as error:
        return {
            "state": STATE_FAILED,
            "output": None,
            "attempts": None,
            "retriedAfterRuleBreak": False,
            "message": str(error),
            "brokenRules": [],
        }


def guidance_status(context: dict) -> dict:
    """What can be produced for this context, without producing it."""

    model = model_status()
    extraction = extraction_status()

    plan = guidance_plan(
        context,
        model_available=model["available"],
        model_reason=model.get("reason"),
        extraction_available=extraction["available"],
    )

    return {
        "agents": describe_agents(),
        "plan": plan,
        "context": context_summary(context),
        "aiAvailable": model["available"],
        "aiUnavailableReason": model.get("reason"),
        "reportReadingAvailable": extraction["available"],
        "disclaimer": DISCLAIMER,
        "safetyNote": SAFETY_NOTE,
    }


def run_guidance(context: dict, *, model=None) -> dict:
    """Produce guidance for one assembled context.

    Raises AgentUnavailable when no provider is configured, because that is a
    server configuration fact rather than a result. Everything else is reported
    inside the returned structure, per agent.
    """

    model = model or select_model()

    if not model.available:
        raise AgentUnavailable(getattr(model, "reason", "not configured"))

    plan = guidance_plan(
        context,
        model_available=True,
        extraction_available=extraction_status()["available"],
    )

    base = {
        "generatedAt": _now_iso(),
        "plan": plan,
        "context": context_summary(context),
        "provider": model.name,
        "model": model.model,
        "disclaimer": DISCLAIMER,
        "safetyNote": SAFETY_NOTE,
    }

    if not plan["canRun"]:
        return {
            **base,
            "ran": False,
            "agents": {
                wellness.AGENT_ID: _skipped(plan["blockers"][0]),
                navigation.AGENT_ID: _skipped(plan["blockers"][0]),
            },
        }

    provider_error = None

    try:
        first = _run_one(wellness, context, model=model)

    except AgentFailed as error:
        first = _failed(str(error))
        provider_error = str(error)

    if provider_error:
        second = _skipped(
            "Not attempted, because the previous step did not get a usable "
            "response from the AI provider."
        )

    else:
        try:
            second = _run_one(
                navigation, context, model=model,
                wellness_output=first.get("output"),
            )

        except AgentFailed as error:
            second = _failed(str(error))

    return {
        **base,
        "ran": first["state"] == STATE_OK or second["state"] == STATE_OK,
        "agents": {
            wellness.AGENT_ID: first,
            navigation.AGENT_ID: second,
        },
    }


def _skipped(message: str) -> dict:
    return {
        "state": STATE_NOT_RUN,
        "output": None,
        "attempts": None,
        "retriedAfterRuleBreak": False,
        "message": message,
        "brokenRules": [],
    }


def _failed(message: str) -> dict:
    return {
        "state": STATE_FAILED,
        "output": None,
        "attempts": None,
        "retriedAfterRuleBreak": False,
        "message": message,
        "brokenRules": [],
    }
