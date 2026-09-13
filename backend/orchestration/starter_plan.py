"""Personalized Maintenance / Starter Plan generation for healthy/low-need users.

Ensures that any user who has completed assessments and scored LOW (or has
low needs with no triggering deficits) receives an active, personalized,
MoveNet-supported starter plan rather than an empty plan or 'no intervention required'.
"""

from datetime import datetime, timezone
import uuid

from exercise_library.catalog import get_exercise_details
from safety.gate import evaluate_safety
from user_state.schema import validate_user_state


STARTER_EXERCISE_IDS = (
    # Functional movement & strength: gentle seated marching
    "seated-marching",
    # Mobility: shoulder & upper body reach
    "standing-overhead-reach",
    # Stability: single-leg balance & postural stability
    "supported-single-leg-stand",
)

STARTER_HABIT_TOPIC_ID = "take_regular_movement_breaks"
STARTER_NUTRITION_TOPIC_ID = "build_a_hydration_habit"


def build_maintenance_starter_plan(
    user_state: dict,
    *,
    workflow_id: str,
    request_id: str,
    tool_client=None,
) -> tuple[dict, dict]:
    """Create a personalized maintenance starter plan for a healthy/low-need user.

    Returns (updated_user_state, safety_result).
    Passes all candidate recommendations through the real Safety Gate.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    plan_id = f"plan_starter_{uuid.uuid4().hex[:12]}"
    agent_run_id = f"run_{uuid.uuid4().hex[:12]}"

    exercise_entries = []
    candidate_recommendations = []

    for exercise_id in STARTER_EXERCISE_IDS:
        details = get_exercise_details(exercise_id)
        capability = (details.get("target_capability") or ["functional_movement"])[0]

        sets = details.get("sets") or 2
        repetitions = details.get("repetitions") or (10 if details.get("duration_seconds") is None else None)
        duration_seconds = details.get("duration_seconds") if details.get("repetitions") is None else None
        measurement_method = "hold_duration" if duration_seconds is not None and repetitions is None else "rep_count"
        prescription = (
            f"{sets} sets of {duration_seconds}s hold"
            if measurement_method == "hold_duration"
            else f"{sets} sets of {repetitions} reps"
        )
        rationale = (
            f"Personalized beginner option for {capability.replace('_', ' ')} "
            "and daily movement maintenance; it does not indicate an impairment."
        )

        entry = {
            "exercise_id": exercise_id,
            "sets": sets,
            "repetitions": repetitions,
            "duration_seconds": duration_seconds,
            "difficulty": "beginner",
            "progression": details.get("progression") or "Gradually increase repetitions or reduce hand support.",
            "regression": details.get("regression") or "Perform seated or with firm two-handed support.",
            "rationale": rationale,
            "safety_notes": details.get("safety_constraints") or ["Move with control; stop if you feel pain or dizziness."],
            "target_need": capability,
            "selection_reason": rationale,
            "prescription": prescription,
            "measurement_method": measurement_method,
            "progression_rule": details.get("progression") or "Gradually increase repetitions or reduce hand support.",
            "regression_rule": details.get("regression") or "Perform seated or with firm two-handed support.",
            "safety_constraints": details.get("safety_constraints") or ["Move with control; stop if you feel pain or dizziness."],
            "adaptation_action": "MAINTAIN",
        }
        exercise_entries.append(entry)
        candidate_recommendations.append({
            "id": exercise_id,
            "agent": "physio",
            "type": "exercise",
            "difficulty": "beginner",
            "declared_constraints": details.get("safety_constraints") or [],
        })

    # Habit recommendation
    candidate_recommendations.append({
        "id": STARTER_HABIT_TOPIC_ID,
        "agent": "behaviour",
        "type": "habit",
    })

    # Nutrition recommendation
    candidate_recommendations.append({
        "id": STARTER_NUTRITION_TOPIC_ID,
        "agent": "nutrition",
        "type": "nutrition_guidance",
    })

    need_profile = (user_state.get("current_needs") or {}).get("data")
    medical_ctx = (user_state.get("medical_context") or {}).get("data")

    # Pass all candidates through Safety Gate
    safety_result = evaluate_safety(
        need_profile=need_profile,
        confirmed_medical_context=medical_ctx,
        candidate_recommendations=candidate_recommendations,
    )

    # Safety Gate filtering: blocked or paused recommendations must be removed
    blocked_ids = set(safety_result.get("blocked_recommendation_ids") or [])
    if safety_result.get("status") == "REFER":
        filtered_exercises = []
    else:
        filtered_exercises = [
            entry for entry in exercise_entries
            if entry["exercise_id"] not in blocked_ids
        ]

    updated = dict(user_state)

    # Update exercise_history only if safe exercises remain
    if filtered_exercises:
        existing_plans = list(((updated.get("exercise_history") or {}).get("data") or {}).get("plans") or [])
        exercise_record = {
            "plan_id": plan_id,
            "plan_version": len(existing_plans) + 1,
            "created_at": now_iso,
            "goal": "Personalized starter and maintenance plan for functional movement, mobility, and stability.",
            "exercise_ids": [e["exercise_id"] for e in filtered_exercises],
            "exercises": filtered_exercises,
            "source": "orchestrator_maintenance",
            "agent_run_id": agent_run_id,
            "recorded_at": now_iso,
            "adaptation_reason": None,
            "triggered_by": "need_assessment_maintenance",
        }
        updated["exercise_history"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": existing_plans + [exercise_record],
            },
        }

    # Update behaviour section if no active behaviour plan exists and not blocked/referred
    existing_habits = list(((updated.get("behaviour") or {}).get("data") or {}).get("plans") or [])
    if not existing_habits and safety_result.get("status") != "REFER" and STARTER_HABIT_TOPIC_ID not in blocked_ids:
        habit_record = {
            "plan_id": f"habit_{plan_id}",
            "plan_version": 1,
            "created_at": now_iso,
            "goal": "Build daily movement break consistency.",
            "topic_ids": [STARTER_HABIT_TOPIC_ID],
            "source": "orchestrator_maintenance",
            "agent_run_id": agent_run_id,
            "recorded_at": now_iso,
            "adaptation_reason": None,
            "triggered_by": "need_assessment_maintenance",
        }
        updated["behaviour"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [habit_record],
            },
        }

    # Update nutrition_plan section if no active nutrition plan exists and not blocked/referred
    existing_nutrition = list(((updated.get("nutrition_plan") or {}).get("data") or {}).get("plans") or [])
    if not existing_nutrition and safety_result.get("status") != "REFER" and STARTER_NUTRITION_TOPIC_ID not in blocked_ids:
        nutrition_record = {
            "plan_id": f"nutrition_{plan_id}",
            "plan_version": 1,
            "created_at": now_iso,
            "goal": "Hydration and balanced whole foods maintenance.",
            "topic_ids": [STARTER_NUTRITION_TOPIC_ID],
            "source": "orchestrator_maintenance",
            "agent_run_id": agent_run_id,
            "recorded_at": now_iso,
            "adaptation_reason": None,
            "triggered_by": "need_assessment_maintenance",
        }
        updated["nutrition_plan"] = {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [nutrition_record],
            },
        }

    # Update safety section
    updated["safety"] = {
        "available": True,
        "reason": None,
        "data": {
            "schemaVersion": "0.1.0",
            "latestResult": safety_result,
        },
    }

    validate_user_state(updated)
    return updated, safety_result
