"""evaluate_safety(): the one entry point the Orchestrator calls.

Evaluates every candidate recommendation from every specialist agent that
ran (Physio/Behaviour/Nutrition) BEFORE the Orchestrator returns a final
result — never after, and never skippable: run_workflow() (orchestrator/
orchestrator.py) always calls this once per workflow that produced at
least an attempt to run a specialist agent, whether or not any candidate
recommendations survived.

Rules are tried in a fixed order (safety/rules.py), and the first match
wins — REFER (most severe) before PAUSE before MODIFY before ALLOW, with
NOT_ASSESSED checked first since it means there is nothing to rank at all.
This ordering is what "safety decisions override normal recommendations"
means concretely: a REFER-worthy condition is never silently downgraded to
a MODIFY just because a later rule would also have matched.
"""

from safety.rules import (
    rule_advanced_exercise_with_confirmed_medical_context_paused,
    rule_confirmed_medical_context_modifies_with_disclaimer,
    rule_default_allow,
    rule_no_candidates_not_assessed,
    rule_safety_status_high_refers,
)
from safety.schema import build_safety_result


class SafetyEvaluationError(ValueError):
    """Raised when evaluate_safety() is given malformed input."""


def _validate_candidate_recommendations(candidate_recommendations) -> None:
    if not isinstance(candidate_recommendations, list):
        raise SafetyEvaluationError("candidate_recommendations must be a list")

    for rec in candidate_recommendations:
        if not isinstance(rec, dict):
            raise SafetyEvaluationError("each candidate recommendation must be an object")

        if not isinstance(rec.get("id"), str) or not rec["id"]:
            raise SafetyEvaluationError("each candidate recommendation must have a non-empty 'id'")

        if not isinstance(rec.get("agent"), str) or not rec["agent"]:
            raise SafetyEvaluationError("each candidate recommendation must have a non-empty 'agent'")

        if not isinstance(rec.get("type"), str) or not rec["type"]:
            raise SafetyEvaluationError("each candidate recommendation must have a non-empty 'type'")


def evaluate_safety(
    *,
    need_profile: dict = None,
    confirmed_medical_context: dict = None,
    candidate_recommendations: list = None,
) -> dict:
    """Evaluate candidate specialist recommendations. Returns a validated
    Safety Result (safety/schema.py). Raises SafetyEvaluationError for
    malformed input — never silently treats malformed input as ALLOW.
    """

    candidate_recommendations = candidate_recommendations or []

    _validate_candidate_recommendations(candidate_recommendations)

    if need_profile is not None and not isinstance(need_profile, dict):
        raise SafetyEvaluationError("need_profile must be null or an object")

    if confirmed_medical_context is not None and not isinstance(confirmed_medical_context, dict):
        raise SafetyEvaluationError("confirmed_medical_context must be null or an object")

    decision = (
        rule_no_candidates_not_assessed(candidate_recommendations)
        or rule_safety_status_high_refers(need_profile, candidate_recommendations)
        or rule_advanced_exercise_with_confirmed_medical_context_paused(
            confirmed_medical_context, candidate_recommendations
        )
        or rule_confirmed_medical_context_modifies_with_disclaimer(
            confirmed_medical_context, candidate_recommendations
        )
        or rule_default_allow(candidate_recommendations)
    )

    return build_safety_result(**decision)
