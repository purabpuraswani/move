"""The Orchestrator's dynamic, explainable specialist-selection rules.

Explicit and structural, not a hidden threshold, and — since the plan
-generation fix — explicit about the difference between "measured, no
meaningful deficit" and "could not be measured at all".

Physio is required when current movement evidence is at MEDIUM/HIGH, or
when the user explicitly reports movement-related pain/injury history.
Missing or skipped assessment evidence alone does not activate Physio.

NOT_ASSESSED never becomes LOW, and it never becomes MEDIUM/HIGH. Every
decision below names exactly which dimension(s), at which level(s),
produced it — and, separately, which could not be evaluated and why —
so the Orchestrator's output stays explainable by inspection.
"""

from activity_agent.reasoning import STEPS_LOW_THRESHOLD
from need_assessment.rules import SITTING_HOURS_HIGH_THRESHOLD
from behaviour_agent.adherence import NOT_ADHERED, compute_behaviour_adherence
from orchestration.selection_policy import PHYSICAL_NEED_DIMENSIONS, TRIGGERING_LEVELS, evidence_summary
from nutrition_agent.report_relevance import report_nutrition_evidence
from recovery_agent.reasoning import SLEEP_SHORT_THRESHOLD_HOURS
from progress_agent.comparison import NOT_ENOUGH_DATA, compare_physical_assessments

# Re-exported under their historical names so existing importers of this
# module (and its tests) keep working unchanged.
PHYSIO_TRIGGER_DIMENSIONS = PHYSICAL_NEED_DIMENSIONS

# The three selection_mode values a physio decision can carry. `None` means
# Physio was not selected at all.
SELECTION_MODE_NEED_BASED = "need_based"
SELECTION_MODE_CONSERVATIVE_STARTER = "conservative_starter"


def _unassessed_clause(unassessed) -> str:
    """"; N dimension(s) could not be evaluated: a, b" — or "" when every
    dimension was evaluated. Appended to a reason so a reader is never told
    "nothing is at MEDIUM or HIGH" without also being told that some of it
    was never measured."""

    if not unassessed:
        return ""

    return (
        "; "
        + ", ".join(sorted(unassessed))
        + " could not be evaluated from the available evidence"
    )


def _movement_history_evidence(user_state):
    section = (user_state or {}).get("medical_context") or {}
    values = ((section.get("data") or {}).get("self_reported") or {}).get("values") or {}
    relevant = []
    for key in ("previous_injury", "joint_pain", "back_neck_pain"):
        value = values.get(key)
        if isinstance(value, str) and value.strip().lower() in {
            "yes", "sometimes", "ongoing", "current", "frequent"
        }:
            relevant.append(f"Self-reported {key.replace('_', ' ')}: {value.strip()}")
    return relevant


def decide_physio_required(
    need_profile, *, user_state=None, exercise_plan_exists=False
) -> dict:
    """Return the physio selection decision.

    ::

        {
          "physio_required": bool,
          "reason": str,
          "evaluated_dimensions": {dimension: level},   # assessed only
          "unassessed_dimensions": (dimension, ...),
          "selection_mode": "need_based" | "conservative_starter" | None,
        }

    `need_profile` may be None (current_needs unavailable) — handled as a
    distinct, explained case, never silently treated as "not required".

    `exercise_plan_exists` tells this function whether the user already has
    an exercise plan. It only ever affects the conservative starter branch
    (an existing plan means the dead-end this branch exists to prevent has
    already been prevented, so unchanged evidence must not mint a second
    plan version). It can never suppress an evidence-based selection.
    """

    history_evidence = _movement_history_evidence(user_state)

    if need_profile is None:
        if history_evidence:
            return {
                "physio_required": True,
                "reason": "self-reported movement-related history warrants physiotherapy review; current movement assessment is unavailable",
                "evaluated_dimensions": {},
                "unassessed_dimensions": PHYSICAL_NEED_DIMENSIONS,
                "selection_mode": SELECTION_MODE_NEED_BASED,
                "history_evidence": history_evidence,
            }
        return {
            "physio_required": False,
            "reason": (
                "current_needs is unavailable, so no physical need dimension "
                "could be evaluated; Physio is not invoked without evidence "
                "that it is needed"
            ),
            "evaluated_dimensions": {},
            "unassessed_dimensions": PHYSICAL_NEED_DIMENSIONS,
            "selection_mode": None,
        }

    summary = evidence_summary(need_profile)
    evaluated = summary["levels"]
    triggering = summary["triggering"]
    unassessed = summary["unassessed"]

    if triggering or history_evidence:
        named = ", ".join(f"{dim}={level}" for dim, level in sorted(triggering.items()))
        reasons = []
        if named:
            reasons.append(f"physical need dimension(s) at MEDIUM or HIGH: {named}")
        if history_evidence:
            reasons.append("self-reported movement-related history is relevant")

        return {
            "physio_required": True,
            "reason": "; ".join(reasons) + _unassessed_clause(unassessed),
            "evaluated_dimensions": evaluated,
            "unassessed_dimensions": unassessed,
            "selection_mode": SELECTION_MODE_NEED_BASED,
            "history_evidence": history_evidence,
        }

    return {
        "physio_required": False,
        "reason": (
            "no physical need dimension (mobility_need, stability_need, "
            "functional_movement_need) is at MEDIUM or HIGH"
            + _unassessed_clause(unassessed)
        ),
        "evaluated_dimensions": evaluated,
        "unassessed_dimensions": unassessed,
        "selection_mode": None,
    }


# ---------------------------------------------------------------------------
# Behaviour and Nutrition selection — Phase 4. Same discipline as
# decide_physio_required above: explicit, structural, explainable by
# inspection, and reusing need_assessment.schema's own NEED_LEVELS
# ordering rather than a second one.
#
# Neither gets a conservative starter pathway, deliberately — see the long
# note in orchestration/selection_policy.py. Both dimensions are
# NOT_ASSESSED exactly when the user has not answered the onboarding
# questions that feed them, and the honest answer to an unanswered
# question is to ask it. What both DO get here is an accurate reason
# string: the previous one said "not at MEDIUM or HIGH" for an unanswered
# questionnaire, which reads as "we checked and you are fine".
# ---------------------------------------------------------------------------


def _single_dimension_decision(need_profile, dimension, key) -> dict:
    if need_profile is None:
        return {
            key: False,
            "reason": (
                f"current_needs is unavailable, so {dimension} could not be "
                "evaluated; this specialist is not invoked without evidence "
                "that it is needed"
            ),
            "evaluated_dimensions": {},
            "unassessed_dimensions": (dimension,),
        }

    level = (need_profile.get(dimension) or {}).get("level")

    if level in TRIGGERING_LEVELS:
        return {
            key: True,
            "reason": f"{dimension} is at {level}",
            "evaluated_dimensions": {dimension: level},
            "unassessed_dimensions": (),
        }

    if level is None or level == "NOT_ASSESSED":
        return {
            key: False,
            "reason": (
                f"{dimension} could not be evaluated from the available "
                "evidence, so no need has been established either way"
            ),
            "evaluated_dimensions": {},
            "unassessed_dimensions": (dimension,),
        }

    return {
        key: False,
        "reason": f"{dimension} was assessed at {level}, below MEDIUM",
        "evaluated_dimensions": {dimension: level},
        "unassessed_dimensions": (),
    }


def decide_behaviour_required(need_profile, behaviour_actions=None, user_state=None) -> dict:
    """Select for questionnaire evidence or a measured adherence barrier.

    Recorded actions count only for the current behaviour plan and only when
    the shared adherence calculation has enough records. No log entries
    remains unknown, never zero adherence.
    """
    decision = _single_dimension_decision(
        need_profile, "behaviour_need", "behaviour_required"
    )
    plans_section = (user_state or {}).get("behaviour") or {}
    plans = (plans_section.get("data") or {}).get("plans") or []
    current_plan_id = plans[-1].get("plan_id") if plans else None
    current_actions = [
        action for action in (behaviour_actions or [])
        if current_plan_id and action.get("plan_id") == current_plan_id
    ]
    adherence = compute_behaviour_adherence(current_actions) if current_plan_id else None
    decision["adherence_evidence"] = None
    if adherence and (
        adherence["status"] == NOT_ADHERED
        or (
            adherence["difficulty_rate"] is not None
            and adherence["difficulty_rate"] >= 0.5
        )
    ):
        decision["behaviour_required"] = True
        decision["adherence_evidence"] = adherence
        decision["reason"] = (
            "recorded actions for the current behaviour plan show an adherence "
            "or difficulty barrier"
        )
    return decision


def _confirmed_reports_of(user_state) -> list:
    """The confirmed reports on a User State, or an empty list."""

    section = (user_state or {}).get("medical_context") or {}

    if not section.get("available"):
        return []

    confirmed = (section.get("data") or {}).get("confirmed_reports") or {}

    return confirmed.get("reports") or []


def decide_nutrition_required(need_profile, user_state=None) -> dict:
    """Return {"nutrition_required": bool, "reason": str, ...}.

    Two independent kinds of evidence can make this specialist relevant,
    and either is enough:

    1. The dietary questionnaire (nutrition_need), as before.
    2. A medical report the user has CONFIRMED that records a
       nutrition-relevant measurement -- see
       nutrition_agent/report_relevance.py, which tests relevance only
       and never reads a value as a finding.

    `user_state` is optional so that callers which only have a need
    profile keep working unchanged; without it, only the questionnaire
    route can activate nutrition, exactly as before.
    """

    decision = _single_dimension_decision(
        need_profile, "nutrition_need", "nutrition_required"
    )

    report_evidence = report_nutrition_evidence(_confirmed_reports_of(user_state))

    decision["report_evidence"] = report_evidence["evidence"]
    decision["activated_by"] = []

    if decision["nutrition_required"]:
        decision["activated_by"].append("dietary_questionnaire")

    if not report_evidence["relevant"]:
        return decision

    decision["activated_by"].append("confirmed_medical_report")

    # A confirmed report makes the domain relevant even when the dietary
    # questions were never answered -- that is the whole point of the
    # second route. The reason records both, so the plan can say which
    # evidence brought the specialist in.
    if decision["nutrition_required"]:
        decision["reason"] = (
            f"{decision['reason']}; a confirmed medical report also records "
            "nutrition-relevant measurements"
        )
    else:
        decision["nutrition_required"] = True
        decision["reason"] = (
            "a confirmed medical report records nutrition-relevant "
            "measurements, so dietary and lifestyle support is relevant "
            f"(previously: {decision['reason']})"
        )

    return decision


# ---------------------------------------------------------------------------
# Progress selection — Phase 5. Deliberately driven by an explicit,
# named trigger the caller passes in (progress_trigger), never inferred
# from a schedule this application does not have (see
# progress_agent/reassessment.py's own docstring on why no recurring
# schedule is invented). The two real trigger reasons the Phase 5 brief
# names are "exercise_activity_recorded" (a result was just submitted —
# see routes/exercise_results.py) and "reassessment_completed" (a new
# physical assessment was just saved) — a caller names one of those (or
# any other short reason string) when it knows one actually happened.
# ---------------------------------------------------------------------------


def decide_progress_required(progress_trigger) -> dict:
    """Return {"progress_required": bool, "reason": str, "trigger": ...}.

    `progress_trigger` is None (nothing happened this call that would
    warrant a progress review) or a dict such as
    {"reason": "exercise_activity_recorded"}. Whether there is *enough*
    data to actually compare is the Progress Agent's own, more nuanced
    NOT_ENOUGH_DATA finding (progress_agent/comparison.py) — this function
    only decides whether reviewing progress was asked for at all.
    """

    if progress_trigger is None:
        return {
            "progress_required": False,
            "reason": "no progress trigger was given for this workflow run",
            "trigger": None,
        }

    if not isinstance(progress_trigger, dict) or not isinstance(
        progress_trigger.get("reason"), str
    ) or not progress_trigger["reason"].strip():
        return {
            "progress_required": False,
            "reason": "progress_trigger was given but has no 'reason'",
            "trigger": progress_trigger,
        }

    normalized_reason = progress_trigger["reason"].strip().lower().replace(" ", "_")
    valid_reasons = {
        "exercise_activity_recorded",
        "food_log_activity_recorded",
        "reassessment_completed",
        # Explicit manual review remains supported; no recurring schedule
        # is inferred by the system.
        "periodic_check",
    }
    if normalized_reason not in valid_reasons:
        return {
            "progress_required": False,
            "reason": f"unsupported progress event: {progress_trigger['reason']}",
            "trigger": progress_trigger,
        }

    return {
        "progress_required": True,
        "reason": f"progress trigger: {progress_trigger['reason']}",
        "trigger": progress_trigger,
    }


# ---------------------------------------------------------------------------
# Exercise & Physical Activity selection
# Evaluates general daily activity, walking volume, and sedentary habits
# distinct from clinical/physiotherapy movement deficits.
# ---------------------------------------------------------------------------


def decide_exercise_activity_required(user_state: dict, need_profile: dict = None) -> dict:
    """Return {"exercise_activity_required": bool, "reason": str, "evidence": list, "evaluated": bool}."""
    q_data = ((user_state or {}).get("questionnaire") or {}).get("data") or {}
    steps = q_data.get("daily_steps")
    sitting_hours = q_data.get("daily_sitting_hours")
    exercise_days = q_data.get("exercise_days")
    evidence = []
    if steps is not None:
        evidence.append(f"Daily steps: {steps}")
    if sitting_hours is not None:
        evidence.append(f"Daily sitting: {sitting_hours} hours")
    if exercise_days is not None:
        evidence.append(f"Exercise frequency: {exercise_days} days/week")

    # Activity evidence is the only thing that selects this specialist.
    # exercise_need is a composite of the camera movement checks, which
    # is physiotherapy's evidence: a HIGH movement need says nothing
    # about how far this person walks, and selecting an activity
    # specialist off it produced advice with no evidence behind it.
    # With no activity answers at all, the honest outcome is that this
    # domain was never evaluated -- not that activity is adequate.
    if not evidence:
        return {
            "exercise_activity_required": False,
            "reason": (
                "No daily activity evidence (steps, sitting time or exercise "
                "frequency) has been collected, so physical activity needs "
                "have not been evaluated."
            ),
            "evidence": [],
            "evaluated": False,
        }

    # Thresholds are imported from the specialist that owns the domain,
    # so the rule that selects an agent and the agent's own finding can
    # never disagree about what counts as low.
    if steps is not None and steps < STEPS_LOW_THRESHOLD:
        return {
            "exercise_activity_required": True,
            "reason": (
                f"Daily step count ({steps}) is below the active baseline "
                f"threshold ({STEPS_LOW_THRESHOLD:,} steps/day)."
            ),
            "evidence": evidence,
            "evaluated": True,
        }

    if sitting_hours is not None and sitting_hours >= SITTING_HOURS_HIGH_THRESHOLD:
        return {
            "exercise_activity_required": True,
            "reason": f"Daily sitting time ({sitting_hours} hours) indicates prolonged sedentary routine requiring active movement pacing.",
            "evidence": evidence,
            "evaluated": True,
        }

    if exercise_days is not None and exercise_days <= 1:
        return {
            "exercise_activity_required": True,
            "reason": f"Exercise frequency ({exercise_days} days/week) indicates low structured physical activity.",
            "evidence": evidence,
            "evaluated": True,
        }

    return {
        "exercise_activity_required": False,
        "reason": "Daily physical activity and movement volume meet current baseline recommendations.",
        "evidence": evidence,
        "evaluated": True,
    }


# ---------------------------------------------------------------------------
# Recovery & Care selection
# Evaluates rest, sleep duration, sleep quality, and post-activity recovery.
# ---------------------------------------------------------------------------


def decide_recovery_required(user_state: dict) -> dict:
    """Return {"recovery_required": bool, "reason": str, "evidence": list, "evaluated": bool}."""
    q_data = ((user_state or {}).get("questionnaire") or {}).get("data") or {}
    sleep_hours = q_data.get("sleep_hours")
    if sleep_hours is None:
        sleep_hours = q_data.get("sleep_duration_hours")
    sleep_quality = q_data.get("sleep_quality")
    stress_level = q_data.get("stress_level")
    recovery_difficulties = q_data.get("recovery_difficulties")

    evidence = []
    if sleep_hours is not None:
        evidence.append(f"Sleep duration: {sleep_hours} hours/night")
    if sleep_quality:
        evidence.append(f"Sleep quality: {sleep_quality}")
    if stress_level in ("low", "moderate", "high"):
        evidence.append(f"Self-reported stress level: {stress_level}")
    if isinstance(recovery_difficulties, list):
        evidence.append(
            "Recovery difficulties: " + (", ".join(recovery_difficulties) if recovery_difficulties else "none reported")
        )

    if not evidence:
        return {
            "recovery_required": False,
            "reason": (
                "No sleep or rest answers have been collected, so recovery "
                "has not been evaluated."
            ),
            "evidence": [],
            "evaluated": False,
        }

    if sleep_hours is not None and sleep_hours < SLEEP_SHORT_THRESHOLD_HOURS:
        return {
            "recovery_required": True,
            "reason": (
                f"Sleep duration ({sleep_hours} hours/night) is below this "
                f"project's {SLEEP_SHORT_THRESHOLD_HOURS:g}-hour marker for treating "
                "rest as a constraint on how quickly activity increases."
            ),
            "evidence": evidence,
            "evaluated": True,
        }

    if sleep_quality and str(sleep_quality).lower() in ("poor", "fair", "restless"):
        return {
            "recovery_required": True,
            "reason": f"Self-reported sleep quality is '{sleep_quality}', indicating opportunity for restorative rest routines.",
            "evidence": evidence,
            "evaluated": True,
        }

    if stress_level in ("moderate", "high") or (isinstance(recovery_difficulties, list) and bool(recovery_difficulties)):
        return {
            "recovery_required": True,
            "reason": "The user reported recovery context that warrants a personalized review.",
            "evidence": evidence,
            "evaluated": True,
        }

    return {
        "recovery_required": False,
            "reason": (
                f"Reported sleep ({sleep_hours} hours) and rest answers did not "
                "cross this project's markers for treating recovery as a constraint."
                if sleep_hours is not None or sleep_quality
                else "Reported stress and recovery information did not indicate a progression constraint this cycle."
            ),
        "evidence": evidence,
        "evaluated": True,
    }


# ---------------------------------------------------------------------------
# Unified selection record. Relevance (selected/not selected) is decided by
# the specialist rules above. Context readiness is a separate check: it can
# defer execution without pretending the specialist is irrelevant.
# ---------------------------------------------------------------------------

AGENT_IDENTIFIERS = {
    "physio": "physio",
    "exercise_activity": "exercise_activity",
    "nutrition": "nutrition",
    "recovery": "recovery",
    "behaviour": "behaviour",
    "progress": "progress",
}

SELECTED = "SELECTED"
SELECTED_CONTEXT_REQUIRED = "SELECTED \u2013 CONTEXT REQUIRED"
NOT_SELECTED = "NOT SELECTED"


def _dimension_evidence(need_profile, dimensions):
    evidence = []
    for dimension in dimensions:
        entry = (need_profile or {}).get(dimension) or {}
        if entry.get("level") in TRIGGERING_LEVELS:
            evidence.extend(entry.get("evidence") or [])
    return evidence


def build_selection_explanations(user_state, need_profile, decisions, progress_context=None):
    """Return one explainable, execution-ready selection record per specialist.

    The `required` values in `decisions` represent domain relevance. Missing
    information only changes readiness and execution eligibility; it never
    turns an unassessed dimension into a need.
    """
    evidence = {
        "physio": _dimension_evidence(
            need_profile, ("mobility_need", "stability_need")
        ) + list(decisions["physio"].get("history_evidence") or []),
        "behaviour": _dimension_evidence(need_profile, ("behaviour_need",)),
        "nutrition": _dimension_evidence(need_profile, ("nutrition_need",)),
        "exercise_activity": list(
            decisions["exercise_activity"].get("evidence") or []
        ),
        "recovery": list(decisions["recovery"].get("evidence") or []),
        "progress": [],
    }
    if decisions["exercise_activity"].get("exercise_activity_required", False):
        evidence["exercise_activity"].extend(
            _dimension_evidence(need_profile, ("mobility_need", "stability_need"))
        )
    evidence["nutrition"].extend(
        decisions["nutrition"].get("report_evidence") or []
    )
    if decisions["nutrition"].get("activated_by"):
        evidence["nutrition"].extend(decisions["nutrition"]["activated_by"])
    adherence = decisions["behaviour"].get("adherence_evidence")
    if adherence:
        evidence["behaviour"].extend(adherence.get("notes") or [])
    trigger = decisions["progress"].get("trigger")
    if isinstance(trigger, dict) and trigger.get("reason"):
        evidence["progress"].append(f"Progress event: {trigger['reason']}")

    required = {
        "physio": decisions["physio"].get("physio_required", False),
        "exercise_activity": decisions["exercise_activity"].get(
            "exercise_activity_required", False
        ),
        "nutrition": decisions["nutrition"].get("nutrition_required", False),
        "recovery": decisions["recovery"].get("recovery_required", False),
        "behaviour": decisions["behaviour"].get("behaviour_required", False),
        "progress": decisions["progress"].get("progress_required", False),
    }
    reasons = {
        "physio": decisions["physio"].get("reason", ""),
        "exercise_activity": decisions["exercise_activity"].get("reason", ""),
        "nutrition": decisions["nutrition"].get("reason", ""),
        "recovery": decisions["recovery"].get("reason", ""),
        "behaviour": decisions["behaviour"].get("reason", ""),
        "progress": decisions["progress"].get("reason", ""),
    }

    missing = {agent_id: [] for agent_id in required}
    nutrition = (user_state.get("nutrition") or {})
    nutrition_data = nutrition.get("data") or {}
    has_nutrition_signals = nutrition.get("available") and any(
        value is not None for value in nutrition_data.values()
    )
    nutrition_activation = decisions["nutrition"].get("activated_by") or []
    if (
        required["nutrition"]
        and "confirmed_medical_report" in nutrition_activation
        and "dietary_questionnaire" not in nutrition_activation
        and not has_nutrition_signals
    ):
        # A confirmed report can establish relevance, but dietary preferences
        # and intake context are needed before a personalized nutrition plan.
        missing["nutrition"].append("self-reported nutrition profile")

    evaluated_physio = decisions["physio"].get("evaluated_dimensions") or {}
    has_measured_physical_need = any(
        level in TRIGGERING_LEVELS for level in evaluated_physio.values()
    )
    physio_history_only = bool(decisions["physio"].get("history_evidence")) and not has_measured_physical_need
    if required["physio"] and physio_history_only:
        missing["physio"].append(
            "details of the current pain or injury and its effect on movement"
        )

    progress_context = progress_context or {}
    if required["progress"]:
        comparisons = compare_physical_assessments(
            progress_context.get("baseline_assessment"),
            progress_context.get("previous_assessment"),
            progress_context.get("current_assessment"),
        )
        has_comparison = any(
            metric["baseline_vs_current"]["direction"] != NOT_ENOUGH_DATA
            or metric["previous_vs_current"]["direction"] != NOT_ENOUGH_DATA
            for metric in comparisons.values()
        )
        if not has_comparison:
            missing["progress"].append(
                "at least one comparable historical and current movement measurement"
            )

    result = {}
    for agent_id in required:
        is_relevant = bool(required[agent_id])
        missing_items = missing[agent_id]
        status = (
            SELECTED_CONTEXT_REQUIRED
            if is_relevant and missing_items
            else SELECTED if is_relevant else NOT_SELECTED
        )
        result[agent_id] = {
            "agent_identifier": AGENT_IDENTIFIERS[agent_id],
            "selection_status": status,
            "evidence_used": evidence[agent_id],
            "reason_for_selection": reasons[agent_id],
            "missing_required_information": missing_items,
            "context_readiness": (
                "NOT_APPLICABLE"
                if not is_relevant
                else "REQUIRED" if missing_items else "READY"
            ),
            "execution_eligibility": is_relevant and not missing_items,
        }
    return result


def evaluate_specialist_selection(
    user_state, need_profile, progress_trigger=None, *,
    exercise_plan_exists=False, behaviour_actions=None, progress_context=None,
):
    """Evaluate all specialists once and return both source decisions and
    normalized explanations used by the executor and workflow route."""
    decisions = {
        "physio": decide_physio_required(
            need_profile, user_state=user_state,
            exercise_plan_exists=exercise_plan_exists,
        ),
        "behaviour": decide_behaviour_required(
            need_profile, behaviour_actions=behaviour_actions, user_state=user_state
        ),
        "nutrition": decide_nutrition_required(need_profile, user_state),
        "progress": decide_progress_required(progress_trigger),
        "exercise_activity": decide_exercise_activity_required(
            user_state, need_profile
        ),
        "recovery": decide_recovery_required(user_state),
    }
    return decisions, build_selection_explanations(
        user_state, need_profile, decisions, progress_context=progress_context
    )
