"""The Behaviour Agent's structured input contract, and how it is built.

Mirrors physio_agent/input_contract.py and nutrition_agent/input_contract.py
exactly. `relevant_behaviour_signals` is a narrow, already-real subset of
the questionnaire section — exactly the fields
need_assessment.rules.assess_behaviour_need() already reads
(daily_sitting_hours, daily_screen_hours, exercise_days, exercise_minutes,
work_type) — never adherence or feedback history, because this application
tracks none yet (see behaviour_library/mcp_servers/behaviour_server.py's
docstring on why no get_adherence/get_user_feedback tool exists).

adherence_feedback is always None in Phase 4: no adherence-tracking or
feedback-collection UI exists yet. Structured but empty, so a later phase
does not need to change this contract's shape.
"""

REQUIRED_FIELDS = (
    "workflow_id",
    "request_id",
    "agent_run_id",
    "current_needs",
    "relevant_behaviour_signals",
    "confirmed_medical_context",
    "adherence_feedback",
)

_BEHAVIOUR_QUESTIONNAIRE_FIELDS = (
    "daily_sitting_hours",
    "daily_screen_hours",
    "exercise_days",
    "exercise_minutes",
    "work_type",
)


class BehaviourAgentInputValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Behaviour Agent input."""


def _fail(message: str):
    raise BehaviourAgentInputValidationError(message)


def build_behaviour_agent_input(
    user_state: dict, *, workflow_id: str, request_id: str, agent_run_id: str
) -> dict:
    """Build the minimized Behaviour Agent input from a validated User State."""

    current_needs_section = user_state.get("current_needs") or {}
    questionnaire_section = user_state.get("questionnaire") or {}
    medical_context_section = user_state.get("medical_context") or {}

    confirmed_medical_context = None

    if medical_context_section.get("available"):
        confirmed = (medical_context_section.get("data") or {}).get(
            "confirmed_reports"
        ) or {}
        reports = confirmed.get("reports") or []

        if reports:
            confirmed_medical_context = {
                "source": "user_confirmed_medical_report",
                "reports": reports,
            }

    relevant_behaviour_signals = None

    if questionnaire_section.get("available"):
        data = questionnaire_section["data"]
        values = {key: data.get(key) for key in _BEHAVIOUR_QUESTIONNAIRE_FIELDS}

        if any(value is not None for value in values.values()):
            relevant_behaviour_signals = values

    payload = {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "current_needs": (
            current_needs_section.get("data")
            if current_needs_section.get("available")
            else None
        ),
        "relevant_behaviour_signals": relevant_behaviour_signals,
        "confirmed_medical_context": confirmed_medical_context,
        # No adherence-tracking UI exists yet. See module docstring.
        "adherence_feedback": None,
    }

    validate_behaviour_agent_input(payload)

    return payload


def validate_behaviour_agent_input(payload) -> None:
    """Raise BehaviourAgentInputValidationError if `payload` is malformed."""

    if not isinstance(payload, dict):
        _fail("a Behaviour Agent input must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in payload]

    if missing:
        _fail(f"missing field(s): {', '.join(missing)}")

    unexpected = set(payload) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"unexpected field(s): {', '.join(sorted(unexpected))}")

    for key in ("workflow_id", "request_id", "agent_run_id"):
        if not isinstance(payload[key], str) or not payload[key]:
            _fail(f"{key} must be a non-empty string")

    if payload["current_needs"] is not None and not isinstance(
        payload["current_needs"], dict
    ):
        _fail("current_needs must be null or an object")

    if payload["relevant_behaviour_signals"] is not None and not isinstance(
        payload["relevant_behaviour_signals"], dict
    ):
        _fail("relevant_behaviour_signals must be null or an object")

    forbidden_substrings = (
        "keypoint", "landmark", "skeleton", "rawframe", "video", "image",
        "base64", "dataurl",
    )
    serialised = str(payload).lower()

    for term in forbidden_substrings:
        if term in serialised:
            _fail(
                f"Behaviour Agent input appears to contain {term!r} — "
                "refusing to build an input that might carry raw media data"
            )
