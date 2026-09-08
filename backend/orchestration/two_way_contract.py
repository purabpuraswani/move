"""Structured Two-Way Communication Contract for MoveWell-AI Agents.

Implements the two-way request/response protocol between the Orchestrator
and specialist agents (Physio, Nutrition, Behaviour, Progress).

Agents are not simple one-shot functions. They can return:
- COMPLETE: full recommendation ready for safety evaluation
- NEEDS_CLARIFICATION: questions for user (e.g., pain location, missing meal, adherence barriers)
- NEEDS_REASSESSMENT: fresh camera assessment recommended
- SAFETY_CONCERN: red flag identified, requiring pause or referral
- INSUFFICIENT_DATA: not enough evidence yet to form recommendation
"""

from typing import Optional, Any
from enum import Enum


class SpecialistStatus(str, Enum):
    COMPLETE = "COMPLETE"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NEEDS_REASSESSMENT = "NEEDS_REASSESSMENT"
    SAFETY_CONCERN = "SAFETY_CONCERN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def build_specialist_request(
    *,
    workflow_id: str,
    request_id: str,
    agent_run_id: str,
    agent_id: str,
    task: str,
    user_state_context: Optional[dict] = None,
    relevant_needs: Optional[dict] = None,
    previous_plan: Optional[dict] = None,
    progress_context: Optional[dict] = None,
    confirmed_medical_context: Optional[dict] = None,
    available_information: Optional[dict] = None,
    clarification_answers: Optional[dict] = None,
) -> dict:
    """Build a structured SpecialistRequest."""
    return {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "agent_id": agent_id,
        "task": task,
        "user_state_context": user_state_context or {},
        "relevant_needs": relevant_needs or {},
        "previous_plan": previous_plan,
        "progress_context": progress_context,
        "confirmed_medical_context": confirmed_medical_context,
        "available_information": available_information or {},
        "clarification_answers": clarification_answers or {},
    }


def build_specialist_response(
    *,
    request_id: str,
    agent_id: str,
    status: str,
    reasoning_summary: str,
    recommendations: Optional[list] = None,
    questions: Optional[list] = None,
    constraints: Optional[list] = None,
    requested_actions: Optional[list] = None,
    confidence: str = "HIGH",
    follow_up_required: bool = False,
    metadata: Optional[dict] = None,
) -> dict:
    """Build a structured SpecialistResponse."""
    return {
        "request_id": request_id,
        "agent_id": agent_id,
        "status": status,
        "reasoning_summary": reasoning_summary,
        "recommendations": recommendations or [],
        "questions": questions or [],
        "constraints": constraints or [],
        "requested_actions": requested_actions or [],
        "confidence": confidence,
        "follow_up_required": follow_up_required,
        "metadata": metadata or {},
    }


# ---------------------------------------------------------------------------
# Two-Way Specialist Clarification Handlers (Physio, Nutrition, Behaviour)
# ---------------------------------------------------------------------------

def handle_physio_feedback_clarification(
    user_feedback: dict,
    user_state: dict,
    *,
    clarification_answer: Optional[str] = None,
) -> dict:
    """Two-way interaction for Physio.

    If user reports discomfort (e.g. knee pain during sit-to-stand):
    - Without clarification: asks whether pain was during movement or afterward.
    - With clarification ('during'): recommends exercise regression, seat height increase, or volume reduction.
    """
    feedback_text = (user_feedback.get("notes") or "").lower()
    is_pain = user_feedback.get("rating") == "pain" or "hurt" in feedback_text or "pain" in feedback_text

    if is_pain and not clarification_answer:
        return build_specialist_response(
            request_id="req_clarif_physio",
            agent_id="physio",
            status=SpecialistStatus.NEEDS_CLARIFICATION.value,
            reasoning_summary="User noted discomfort with an exercise; clarifying timing to advise regression vs rest.",
            questions=["Was the discomfort felt during the movement or only afterward?"],
            follow_up_required=True,
        )

    # If clarification provided or general fatigue
    regression_action = "Reduce movement depth or volume; push off firmly with both hands on support."
    if clarification_answer and "during" in clarification_answer.lower():
        regression_action = "Regress movement: elevate seat height or perform supported alternative; avoid painful range."

    return build_specialist_response(
        request_id="req_clarif_physio",
        agent_id="physio",
        status=SpecialistStatus.COMPLETE.value,
        reasoning_summary="Discomfort clarified; conservative regression and volume adjustment applied.",
        recommendations=[{"action": "regress_exercise", "guidance": regression_action}],
        constraints=["Do not force range of motion into sharp pain."],
        follow_up_required=False,
    )


def handle_nutrition_log_clarification(
    food_log_entries: list,
    *,
    clarification_answer: Optional[str] = None,
) -> dict:
    """Two-way interaction for Nutrition.

    Detects if key meals are missing (e.g., breakfast or dinner unlogged).
    Asks clarification without fabricating what the user ate.
    """
    logged_meals = {
        (entry.get("meal_type") or "").lower()
        for entry in (food_log_entries or [])
    }

    if "dinner" not in logged_meals and not clarification_answer:
        return build_specialist_response(
            request_id="req_clarif_nutrition",
            agent_id="nutrition",
            status=SpecialistStatus.NEEDS_CLARIFICATION.value,
            reasoning_summary="Full-day nutritional intake is incomplete because dinner is unlogged.",
            questions=["What did you have for dinner, or was dinner skipped?"],
            follow_up_required=True,
        )

    return build_specialist_response(
        request_id="req_clarif_nutrition",
        agent_id="nutrition",
        status=SpecialistStatus.COMPLETE.value,
        reasoning_summary="Daily dietary pattern evaluated with available food records.",
        recommendations=[
            {"topic_id": "build_a_hydration_habit", "rationale": "Support general hydration and balanced nutrition."}
        ],
        follow_up_required=False,
    )


def handle_behaviour_adherence_clarification(
    completed_sessions: int,
    planned_sessions: int,
    *,
    clarification_answer: Optional[str] = None,
) -> dict:
    """Two-way interaction for Behaviour.

    When adherence is low (<50%), inquires about scheduling or fatigue barriers.
    Adapts habit to shorter flexible sessions.
    """
    if planned_sessions > 0 and (completed_sessions / planned_sessions) < 0.5:
        if not clarification_answer:
            return build_specialist_response(
                request_id="req_clarif_behaviour",
                agent_id="behaviour",
                status=SpecialistStatus.NEEDS_CLARIFICATION.value,
                reasoning_summary="Adherence below target; investigating practical barriers without judgment.",
                questions=["What was the biggest hurdle to completing planned sessions this week?"],
                follow_up_required=True,
            )

        # Barrier answered (e.g. busy, no time)
        return build_specialist_response(
            request_id="req_clarif_behaviour",
            agent_id="behaviour",
            status=SpecialistStatus.COMPLETE.value,
            reasoning_summary="Identified routine and time constraint barrier; adapting to shorter flexible habit.",
            recommendations=[
                {
                    "topic_id": "take_regular_movement_breaks",
                    "action": "reduce_duration",
                    "guidance": "Shorten routine to 5-minute movement micro-breaks during the day.",
                }
            ],
            follow_up_required=False,
        )

    return build_specialist_response(
        request_id="req_clarif_behaviour",
        agent_id="behaviour",
        status=SpecialistStatus.COMPLETE.value,
        reasoning_summary="Adherence is consistent.",
        recommendations=[{"topic_id": "anchor_activity_to_an_existing_routine"}],
        follow_up_required=False,
    )
