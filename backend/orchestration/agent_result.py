"""The one result shape every future specialist agent returns.

Physio, Nutrition, Behaviour, Progress and Safety will all be different
agents doing different work, but the Orchestrator needs to read their
outputs without knowing which agent produced which — that is what makes
"the Orchestrator combines specialist outputs" implementable instead of a
pile of per-agent special cases. This module is that common shape, and the
validation that keeps every agent honest about it.

Building this now, with no agents behind it yet, is deliberate: the contract
is reviewable on its own, and no agent's first draft accidentally becomes the
de facto shape everyone else has to reverse-engineer.

Nothing here is a fake agent. build_agent_result() is a constructor a real
agent will call with its real findings; it produces nothing on its own.
"""

from typing import Optional

AGENT_STATUSES = ("completed", "skipped", "failed", "not_run")

PRIORITIES = ("low", "medium", "high", "critical")

# Kept in one place so a caller cannot invent a fifth agent id that the
# Orchestrator would silently accept. Extend this tuple when a specialist
# agent is actually implemented — not before, per the Phase 0 boundary.
KNOWN_AGENT_IDS = (
    "physio",
    "nutrition",
    "behaviour",
    "progress",
    "safety",
)

REQUIRED_METADATA_KEYS = ("workflow_id", "request_id", "agent_run_id")
OPTIONAL_METADATA_KEYS = ("tool_call_id", "mcp_session_id")


class AgentResultValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Agent Result."""


def _fail(message: str):
    raise AgentResultValidationError(message)


def build_agent_result(
    *,
    agent: str,
    status: str,
    workflow_id: str,
    request_id: str,
    agent_run_id: str,
    priority: Optional[str] = None,
    findings: Optional[dict] = None,
    recommendations: Optional[list] = None,
    requires_reassessment: bool = False,
    safety_flags: Optional[list] = None,
    tool_call_id: Optional[str] = None,
    mcp_session_id: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
) -> dict:
    """Build a validated Agent Result. Raises AgentResultValidationError.

    `findings` and `recommendations` are intentionally untyped beyond
    "object" / "list of objects" here — what a Physio finding looks like and
    what a Nutrition finding looks like are different, and that difference is
    each agent's to define. What this contract fixes is that findings and
    recommendations are always present under the same two names, in the same
    two shapes (an object, a list), so the Orchestrator can always look for
    them there regardless of which agent it is reading.
    """

    metadata = {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "tool_call_id": tool_call_id,
        "mcp_session_id": mcp_session_id,
    }

    if extra_metadata:
        overlapping = set(extra_metadata) & set(metadata)

        if overlapping:
            _fail(
                "extra_metadata cannot override the reserved keys: "
                f"{', '.join(sorted(overlapping))}"
            )

        metadata.update(extra_metadata)

    result = {
        "agent": agent,
        "status": status,
        "priority": priority,
        "findings": findings if findings is not None else {},
        "recommendations": recommendations if recommendations is not None else [],
        "requiresReassessment": bool(requires_reassessment),
        "safetyFlags": safety_flags if safety_flags is not None else [],
        "metadata": metadata,
    }

    validate_agent_result(result)

    return result


def validate_agent_result(result) -> None:
    """Raise AgentResultValidationError if `result` is not a valid Agent Result.

    Checks structure and the closed vocabularies (status, priority), not the
    domain content of findings/recommendations — that is each agent's own
    schema to define and validate before calling build_agent_result().
    """

    if not isinstance(result, dict):
        _fail("an Agent Result must be an object")

    expected_keys = {
        "agent",
        "status",
        "priority",
        "findings",
        "recommendations",
        "requiresReassessment",
        "safetyFlags",
        "metadata",
    }

    missing = expected_keys - set(result)

    if missing:
        _fail(f"missing field(s): {', '.join(sorted(missing))}")

    unexpected = set(result) - expected_keys

    if unexpected:
        _fail(f"unexpected field(s): {', '.join(sorted(unexpected))}")

    if not isinstance(result["agent"], str) or not result["agent"]:
        _fail("agent must be a non-empty string")

    if result["agent"] not in KNOWN_AGENT_IDS:
        _fail(
            f"agent {result['agent']!r} is not one of the known agent ids "
            f"({', '.join(KNOWN_AGENT_IDS)}). Add it to KNOWN_AGENT_IDS in "
            "orchestration/agent_result.py once that agent is actually "
            "implemented."
        )

    if result["status"] not in AGENT_STATUSES:
        _fail(f"status must be one of {', '.join(AGENT_STATUSES)}")

    if result["priority"] is not None and result["priority"] not in PRIORITIES:
        _fail(f"priority must be null or one of {', '.join(PRIORITIES)}")

    if not isinstance(result["findings"], dict):
        _fail("findings must be an object")

    if not isinstance(result["recommendations"], list):
        _fail("recommendations must be a list")

    if not isinstance(result["requiresReassessment"], bool):
        _fail("requiresReassessment must be a boolean")

    if not isinstance(result["safetyFlags"], list):
        _fail("safetyFlags must be a list")

    _validate_metadata(result["metadata"])


def _validate_metadata(metadata) -> None:
    if not isinstance(metadata, dict):
        _fail("metadata must be an object")

    for key in REQUIRED_METADATA_KEYS:
        value = metadata.get(key)

        if not isinstance(value, str) or not value:
            _fail(f"metadata.{key} is required and must be a non-empty string")

    for key in OPTIONAL_METADATA_KEYS:
        value = metadata.get(key)

        if value is not None and (not isinstance(value, str) or not value):
            _fail(f"metadata.{key} must be null or a non-empty string")

    known = set(REQUIRED_METADATA_KEYS) | set(OPTIONAL_METADATA_KEYS)
    unexpected = set(metadata) - known

    if unexpected:
        _fail(f"metadata has unexpected field(s): {', '.join(sorted(unexpected))}")
