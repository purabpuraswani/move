"""The Safety Gate's deterministic rules — each one named, and each one
reading only data this application actually has.

None of these rules perform unrestricted AI diagnosis. Each is a plain
structural check: is a Need Profile field at a given level, does a
confirmed medical report exist, does a candidate recommendation declare a
difficulty above a named ceiling. Exactly the same "system decision, not a
clinical one" discipline need_assessment/rules.py and physio_agent/agent.py
already apply — see this module's docstring in safety/__init__.py.

Rules are evaluated in order; the first rule that matches decides the
whole Safety Result for this call. This keeps the decision explainable by
inspection (exactly which rule fired, never a black-box aggregate score).
"""

# Same ceiling physio_agent.agent.DEFAULT_MAX_DIFFICULTY already uses —
# reused, not reinvented, so the Physio Agent's own per-exercise gate and
# this cross-agent gate never quietly disagree about what "too advanced"
# means.
MAX_DIFFICULTY_WITH_CONFIRMED_MEDICAL_CONTEXT = "beginner"
_DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def rule_no_candidates_not_assessed(candidate_recommendations: list):
    """NOT_ASSESSED: nothing was produced to evaluate.

    An empty candidate list is not the same as "everything is safe" — it
    means the gate has nothing to check, and says so rather than
    defaulting to ALLOW.
    """

    if candidate_recommendations:
        return None

    return {
        "status": "NOT_ASSESSED",
        "reason": (
            "No candidate recommendations were produced by any specialist "
            "agent, so there is nothing for the Safety Gate to evaluate."
        ),
        "flags": [],
        "actions": [],
        "requires_referral": False,
        "modified_recommendation_ids": [],
        "blocked_recommendation_ids": [],
    }


def rule_safety_status_high_refers(need_profile: dict, candidate_recommendations: list):
    """REFER: the Need Profile's own safety_status is HIGH.

    need_assessment.rules.assess_safety_status() is always NOT_ASSESSED in
    this application today (no validated escalation rule set exists there
    yet — see that module's docstring) — this rule cannot currently be
    triggered by a live run, and this project does not invent a case to
    trigger it. It exists as a real, supported code path: if a future,
    reviewed escalation rule set is added to need_assessment/rules.py and
    ever produces safety_status=HIGH, this Safety Gate honours it
    immediately, without the Orchestrator needing a second change.
    """

    if not need_profile:
        return None

    safety_status = need_profile.get("safety_status") or {}

    if safety_status.get("level") != "HIGH":
        return None

    evidence = safety_status.get("evidence") or []

    return {
        "status": "REFER",
        "reason": (
            "The Need Profile's safety_status is HIGH: "
            + ("; ".join(evidence) if evidence else "no evidence text was recorded")
        ),
        "flags": ["safety_status_high"],
        "actions": ["refer_to_professional", "block_all_recommendations"],
        "requires_referral": True,
        "modified_recommendation_ids": [],
        "blocked_recommendation_ids": [rec["id"] for rec in candidate_recommendations],
    }


def rule_advanced_exercise_with_confirmed_medical_context_paused(
    confirmed_medical_context, candidate_recommendations: list
):
    """PAUSE: a confirmed medical report exists on file, and a candidate
    exercise recommendation is above this gate's reduced ceiling for that
    case (MAX_DIFFICULTY_WITH_CONFIRMED_MEDICAL_CONTEXT).

    This is deliberately narrower than physio_agent.agent's own
    per-exercise safety gate (which already caps everyone at
    "intermediate"): this rule only pauses — does not block outright —
    because a confirmed medical report existing does not by itself mean
    the recommended exercise is contraindicated; it means this system does
    not have the clinical information to confirm it either way, and PAUSE
    (pending explicit review) is preferable to a false ALLOW.
    """

    if not confirmed_medical_context:
        return None

    paused_ids = [
        rec["id"]
        for rec in candidate_recommendations
        if rec.get("type") == "exercise"
        and _DIFFICULTY_ORDER.get(rec.get("difficulty"), 0)
        > _DIFFICULTY_ORDER[MAX_DIFFICULTY_WITH_CONFIRMED_MEDICAL_CONTEXT]
    ]

    if not paused_ids:
        return None

    return {
        "status": "PAUSE",
        "reason": (
            "This user has a confirmed medical report on file, and "
            f"{len(paused_ids)} candidate exercise recommendation(s) are "
            f"above the '{MAX_DIFFICULTY_WITH_CONFIRMED_MEDICAL_CONTEXT}' "
            "difficulty this gate uses whenever confirmed medical context "
            "exists. Paused pending explicit review, not blocked outright."
        ),
        "flags": ["confirmed_medical_context_present", "difficulty_above_reduced_ceiling"],
        "actions": [f"pause_recommendation:{rec_id}" for rec_id in paused_ids],
        "requires_referral": False,
        "modified_recommendation_ids": [],
        "blocked_recommendation_ids": paused_ids,
    }


def rule_confirmed_medical_context_modifies_with_disclaimer(confirmed_medical_context, candidate_recommendations: list):
    """MODIFY: a confirmed medical report exists, but nothing above was
    paused or referred — every remaining candidate recommendation is
    allowed through, but annotated with a disclaimer, since this system
    has not confirmed whether the report bears on that recommendation.
    """

    if not confirmed_medical_context or not candidate_recommendations:
        return None

    ids = [rec["id"] for rec in candidate_recommendations]

    return {
        "status": "MODIFY",
        "reason": (
            "This user has a confirmed medical report on file. All "
            "candidate recommendations are allowed through with an added "
            "disclaimer to discuss them against that report with a "
            "healthcare professional."
        ),
        "flags": ["confirmed_medical_context_present"],
        "actions": ["add_medical_disclaimer"],
        "requires_referral": False,
        "modified_recommendation_ids": ids,
        "blocked_recommendation_ids": [],
    }


def rule_default_allow(candidate_recommendations: list):
    """ALLOW: nothing above matched — no medical context, no HIGH safety
    status, no difficulty concern. The default, but only ever reached
    after every other named rule has explicitly declined to match.
    """

    return {
        "status": "ALLOW",
        "reason": (
            "No safety rule was triggered: no confirmed medical context on "
            "file, the Need Profile's safety_status is not HIGH, and no "
            "candidate exercise recommendation exceeds this gate's "
            "difficulty ceiling."
        ),
        "flags": [],
        "actions": [],
        "requires_referral": False,
        "modified_recommendation_ids": [],
        "blocked_recommendation_ids": [],
    }
