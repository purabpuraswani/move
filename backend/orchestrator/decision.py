"""The Orchestrator's dynamic, explainable specialist-selection rules.

Explicit and structural, not a hidden threshold, and — since the plan
-generation fix — explicit about the difference between "measured, no
meaningful deficit" and "could not be measured at all".

Physio is required only when at least one of the three physical Need
dimensions (mobility_need, stability_need, functional_movement_need) is
assessed at MEDIUM or HIGH. Missing or skipped movement evidence does not
activate Physio and does not produce a compensatory plan.

NOT_ASSESSED never becomes LOW, and it never becomes MEDIUM/HIGH. Every
decision below names exactly which dimension(s), at which level(s),
produced it — and, separately, which could not be evaluated and why —
so the Orchestrator's output stays explainable by inspection.
"""

from activity_agent.reasoning import STEPS_LOW_THRESHOLD
from orchestration.selection_policy import PHYSICAL_NEED_DIMENSIONS, TRIGGERING_LEVELS, evidence_summary
from nutrition_agent.report_relevance import report_nutrition_evidence
from recovery_agent.reasoning import SLEEP_SHORT_THRESHOLD_HOURS

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


def decide_physio_required(need_profile, *, exercise_plan_exists=False) -> dict:
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

    if need_profile is None:
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

    if triggering:
        named = ", ".join(f"{dim}={level}" for dim, level in sorted(triggering.items()))

        return {
            "physio_required": True,
            "reason": (
                f"physical need dimension(s) at MEDIUM or HIGH: {named}"
                + _unassessed_clause(unassessed)
            ),
            "evaluated_dimensions": evaluated,
            "unassessed_dimensions": unassessed,
            "selection_mode": SELECTION_MODE_NEED_BASED,
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


def decide_behaviour_required(need_profile) -> dict:
    """Return {"behaviour_required": bool, "reason": str, ...}."""

    return _single_dimension_decision(
        need_profile, "behaviour_need", "behaviour_required"
    )


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

    if not isinstance(progress_trigger, dict) or not progress_trigger.get("reason"):
        return {
            "progress_required": False,
            "reason": "progress_trigger was given but has no 'reason'",
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
    exercise_need_level = ((need_profile or {}).get("exercise_need") or {}).get("level")

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

    if sitting_hours is not None and sitting_hours >= 8:
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

    if exercise_need_level in ("MEDIUM", "HIGH"):
        return {
            "exercise_activity_required": True,
            "reason": f"Overall exercise need was assessed at {exercise_need_level}.",
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

    evidence = []
    if sleep_hours is not None:
        evidence.append(f"Sleep duration: {sleep_hours} hours/night")
    if sleep_quality:
        evidence.append(f"Sleep quality: {sleep_quality}")

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

    return {
        "recovery_required": False,
            "reason": (
                f"Reported sleep ({sleep_hours} hours) and rest answers did not "
                "cross this project's markers for treating recovery as a constraint."
            ),
        "evidence": evidence,
        "evaluated": True,
    }
