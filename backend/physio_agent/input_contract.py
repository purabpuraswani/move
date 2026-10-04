"""The Physio Agent's structured input contract, and how it is built.

Data minimization is the point of this module: the Orchestrator hands the
Physio Agent this contract, never the raw User State. Every field here is
either identifier metadata (for tracing) or a value the agent actually
needs to select and constrain exercises — nothing else from the User State
crosses this boundary, and nothing here can ever carry a webcam frame, a
MoveNet keypoint, or a pose sequence: physical_assessment's `data` is
already Phase 0's privacy-filtered structured shape (status/measurements/
quality/invalidReasons/attempts), never raw signal.

confirmed_medical_context is exactly that — confirmed only. It is read
from `user_state["medical_context"]["data"]["confirmed_reports"]`, never
from `self_reported` (onboarding checklist answers are self-reported, not
confirmed) and never from any unconfirmed report extraction (there is no
path to one here at all: user_state/schema.py only ever receives
confirmed_values_for_user()'s output in the first place).

exercise_preferences is always None in Phase 3: no preference-collection
UI exists in this application yet. This field exists so a later phase that
adds one does not need to change this contract's shape — the same
"structure now, populate later" discipline Phase 0's User State sections
already use.
"""

from need_assessment.schema import NEED_DIMENSIONS

REQUIRED_FIELDS = (
    "workflow_id",
    "request_id",
    "agent_run_id",
    "physical_assessment",
    "movement_evidence",
    "current_needs",
    "relevant_user_profile",
    "relevant_lifestyle_constraints",
    "confirmed_medical_context",
    "exercise_preferences",
)

# Only the three physical Need dimensions are the Physio Agent's business —
# nutrition_need, behaviour_need, and safety_status are read by the
# Orchestrator (for selection and the safety gate, respectively) but are
# not this agent's own concern to reason about.
PHYSIO_RELEVANT_NEED_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
)

assert set(PHYSIO_RELEVANT_NEED_DIMENSIONS).issubset(set(NEED_DIMENSIONS))


class PhysioAgentInputValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Physio Agent input."""


def _fail(message: str):
    raise PhysioAgentInputValidationError(message)


def build_physio_agent_input(
    user_state: dict, *, workflow_id: str, request_id: str, agent_run_id: str
) -> dict:
    """Build the minimized Physio Agent input from a validated User State.

    Does not itself call validate_user_state() — the caller (the
    Orchestrator) already has, and re-validating here would just be a
    second copy of the same check. This function only ever *reads* the
    state; it never mutates it and never writes anything back.
    """

    current_needs_section = user_state.get("current_needs") or {}
    physical_assessment_section = user_state.get("physical_assessment") or {}
    basic_profile_section = user_state.get("basic_profile") or {}
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
        "physical_assessment": (
            physical_assessment_section.get("data")
            if physical_assessment_section.get("available")
            else None
        ),
        "movement_evidence": build_movement_evidence(
            physical_assessment_section.get("data")
            if physical_assessment_section.get("available")
            else None
        ),
        "current_needs": (
            current_needs_section.get("data")
            if current_needs_section.get("available")
            else None
        ),
        # Deliberately a narrow subset: only the fields that could plausibly
        # bear on exercise selection (nothing here drives Phase 3's actual
        # selection logic yet — see agent.py — but the shape is here rather
        # than invented later).
        "relevant_user_profile": (
            {"age": basic_profile_section["data"].get("age")}
            if basic_profile_section.get("available")
            else None
        ),
        "relevant_lifestyle_constraints": (
            {
                "daily_sitting_hours": questionnaire_section["data"].get(
                    "daily_sitting_hours"
                ),
                # Added for physio_agent/shaping.py: how often the user
                # already exercises decides how much programme is
                # realistic to give them. Still a narrow view -- this
                # agent gets the two activity answers that bear on plan
                # size, not the whole questionnaire.
                "exercise_days": questionnaire_section["data"].get("exercise_days"),
                "work_type": questionnaire_section["data"].get("work_type"),
            }
            if questionnaire_section.get("available")
            else None
        ),
        "confirmed_medical_context": confirmed_medical_context,
        # No preference-collection UI exists yet. See module docstring.
        "exercise_preferences": None,
    }

    validate_physio_agent_input(payload)

    return payload


def build_movement_evidence(physical_assessment) -> dict:
    """Expose the stored baseline measurements in domain-shaped form.

    This is a projection, not a second source of truth: missing, skipped, or
    invalid tests retain their status and produce no invented measurements.
    """

    tests = (physical_assessment or {}).get("tests") or {}

    shoulder = tests.get("shoulder") or {}
    shoulder_measurements = shoulder.get("measurements") or {}
    left_shoulder = (shoulder_measurements.get("left") or {}).get("finalElevationDeg")
    right_shoulder = (shoulder_measurements.get("right") or {}).get("finalElevationDeg")

    ftsst = tests.get("ftsst") or {}
    ftsst_measurements = ftsst.get("measurements") or {}
    ftsst_setup = ftsst.get("setup") or {}

    balance = tests.get("balance") or {}
    balance_measurements = balance.get("measurements") or {}

    return {
        "shoulder": {
            "status": shoulder.get("status", "not_started"),
            "left_elevation_deg": left_shoulder,
            "right_elevation_deg": right_shoulder,
            "side_difference_deg": shoulder_measurements.get("observableDifferenceDeg"),
            "repetitions": {
                "left": (shoulder_measurements.get("left") or {}).get("repetitionCount"),
                "right": (shoulder_measurements.get("right") or {}).get("repetitionCount"),
            },
        },
        "sit_to_stand": {
            "status": ftsst.get("status", "not_started"),
            "time_seconds": ftsst_measurements.get("completionTimeSeconds"),
            "stands_detected": ftsst_measurements.get("repetitionsDetected"),
            "required_stands": ftsst_measurements.get("requiredRepetitions"),
            "chair_height_cm": ftsst_setup.get("chairSeatHeightCm"),
            "measured_side": ftsst_setup.get("measuredSide"),
        },
        "balance": {
            "status": balance.get("status", "not_started"),
            "left_hold_seconds": (balance_measurements.get("left") or {}).get("holdDurationSeconds"),
            "right_hold_seconds": (balance_measurements.get("right") or {}).get("holdDurationSeconds"),
            "side_difference_seconds": (
                balance_measurements.get("observableDifferenceMs") / 1000
                if isinstance(balance_measurements.get("observableDifferenceMs"), (int, float))
                else None
            ),
            "left_end_reason": (balance_measurements.get("left") or {}).get("endReason"),
            "right_end_reason": (balance_measurements.get("right") or {}).get("endReason"),
        },
    }


def validate_physio_agent_input(payload) -> None:
    """Raise PhysioAgentInputValidationError if `payload` is malformed."""

    if not isinstance(payload, dict):
        _fail("a Physio Agent input must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in payload]

    if missing:
        _fail(f"missing field(s): {', '.join(missing)}")

    unexpected = set(payload) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"unexpected field(s): {', '.join(sorted(unexpected))}")

    for key in ("workflow_id", "request_id", "agent_run_id"):
        if not isinstance(payload[key], str) or not payload[key]:
            _fail(f"{key} must be a non-empty string")

    if not isinstance(payload["movement_evidence"], dict):
        _fail("movement_evidence must be an object")

    if payload["current_needs"] is not None and not isinstance(
        payload["current_needs"], dict
    ):
        _fail("current_needs must be null or an object")

    # A second line of defence, mirroring assessments/schema.py's and
    # exercise_assessment/schema.py's own discipline: nothing shaped like
    # raw pose/frame data may cross this boundary, however it got here.
    forbidden_substrings = ("keypoint", "landmark", "skeleton", "rawframe", "video", "image", "base64", "dataurl")
    serialised = str(payload).lower()
    # "image_plane" is legitimate protocol definition metadata (e.g. camera_image_plane_projection,
    # downward_vertical_image_plane) describing projection geometry, not raw image data.
    sanitized = serialised.replace("image_plane", "").replace("camera_image", "")

    for term in forbidden_substrings:
        if term in sanitized:
            _fail(
                f"Physio Agent input appears to contain {term!r} — refusing "
                "to build an input that might carry pose/frame data"
            )
