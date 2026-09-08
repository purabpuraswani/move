"""The Nutrition Agent's structured input contract, and how it is built.

Mirrors physio_agent/input_contract.py's data-minimization discipline
exactly. The Orchestrator hands the Nutrition Agent this contract, never
the raw User State. `relevant_nutrition_signals` is exactly
user_state["nutrition"]["data"] (the four Phase 4 self-reported fields) —
never any raw food-tracking data, because this application collects none.

confirmed_medical_context is read the same way physio_agent's is: only
from `medical_context.data.confirmed_reports`, never self-reported, never
unconfirmed report extraction.

food_preferences is always None in Phase 4: no preference-collection UI
exists yet for food preferences specifically (this application's
onboarding does not ask). This field exists, structured but empty, so a
later phase that adds one does not need to change this contract's shape —
the same discipline exercise_preferences uses in physio_agent's contract.
This agent must never invent a value for it.
"""

REQUIRED_FIELDS = (
    "workflow_id",
    "request_id",
    "agent_run_id",
    "current_needs",
    "relevant_nutrition_signals",
    "relevant_lifestyle_constraints",
    "confirmed_medical_context",
    "food_preferences",
)

NUTRITION_RELEVANT_NEED_DIMENSIONS = ("nutrition_need",)


class NutritionAgentInputValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Nutrition Agent input."""


def _fail(message: str):
    raise NutritionAgentInputValidationError(message)


def build_nutrition_agent_input(
    user_state: dict, *, workflow_id: str, request_id: str, agent_run_id: str
) -> dict:
    """Build the minimized Nutrition Agent input from a validated User State.

    Does not itself call validate_user_state() — the caller (the
    Orchestrator) already has. Only ever reads the state; never mutates it.
    """

    current_needs_section = user_state.get("current_needs") or {}
    nutrition_section = user_state.get("nutrition") or {}
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

    payload = {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "current_needs": (
            current_needs_section.get("data")
            if current_needs_section.get("available")
            else None
        ),
        "relevant_nutrition_signals": (
            nutrition_section.get("data")
            if nutrition_section.get("available")
            else None
        ),
        # Deliberately a narrow subset, same discipline as
        # physio_agent.input_contract.build_physio_agent_input's
        # relevant_lifestyle_constraints.
        "relevant_lifestyle_constraints": (
            {"work_type": questionnaire_section["data"].get("work_type")}
            if questionnaire_section.get("available")
            else None
        ),
        "confirmed_medical_context": confirmed_medical_context,
        # No food-preference-collection UI exists yet. See module docstring.
        "food_preferences": None,
    }

    validate_nutrition_agent_input(payload)

    return payload


def validate_nutrition_agent_input(payload) -> None:
    """Raise NutritionAgentInputValidationError if `payload` is malformed."""

    if not isinstance(payload, dict):
        _fail("a Nutrition Agent input must be an object")

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

    if payload["relevant_nutrition_signals"] is not None and not isinstance(
        payload["relevant_nutrition_signals"], dict
    ):
        _fail("relevant_nutrition_signals must be null or an object")

    # Same second line of defence as physio_agent.input_contract: nothing
    # shaped like raw pose/frame/food-image data may cross this boundary.
    forbidden_substrings = (
        "keypoint", "landmark", "skeleton", "rawframe", "video", "image",
        "base64", "dataurl",
    )
    serialised = str(payload).lower()

    for term in forbidden_substrings:
        if term in serialised:
            _fail(
                f"Nutrition Agent input appears to contain {term!r} — "
                "refusing to build an input that might carry raw media data"
            )
