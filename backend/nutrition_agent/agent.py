"""The Nutrition Agent's actual execution lifecycle.

    Nutrition Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the structured input (input_contract.py, from User State)
          |
    Determine which self-reported signals triggered a nutrition need
        (dynamic, not fixed — reads current_needs.nutrition_need +
        relevant_nutrition_signals)
          |
    Call Nutrition MCP tools (via the injected NutritionToolClient — never
        nutrition_library directly)
          |
    Build a structured Nutrition Plan (plan_schema.py) with a rationale
        per goal
          |
    Return a Phase 0 Agent Result (orchestration.agent_result)

Mirrors physio_agent/agent.py's discipline exactly. run_nutrition_agent()
takes a NutritionToolClient as a required argument specifically so it can
never quietly bypass MCP.
"""

from need_assessment.rules import (
    FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD,
    MEAL_PATTERN_TRIGGER_VALUES,
    PROCESSED_FOOD_TRIGGER_VALUES,
    WATER_GLASSES_LOW_THRESHOLD,
)
from orchestration.agent_result import build_agent_result
from orchestration.ids import TraceContext, start_agent_run
from nutrition_agent.adaptation import (
    DECISION_ADD,
    DECISION_MAINTAIN,
    DECISION_MODIFY,
    DECISION_REMOVE,
    decide_for_goal,
    summarise,
)
from nutrition_agent.evidence import build_nutrition_evidence_view
from nutrition_agent.report_relevance import report_nutrition_evidence
from nutrition_agent.input_contract import build_nutrition_agent_input
from nutrition_agent.plan_schema import build_nutrition_goal_entry, build_nutrition_plan
from nutrition_agent.tool_client import NutritionToolClient

AGENT_ID = "nutrition"

TRIGGERING_LEVELS = ("MEDIUM", "HIGH")

MAX_GOALS_PER_PLAN = 4


class NutritionAgentError(Exception):
    """Raised for a Nutrition Agent run that could not produce a result at
    all (as opposed to a run that completed with an empty plan)."""


def _triggered_signals(nutrition_signals: dict) -> list:
    """Return which of the four self-reported signals actually crossed this
    project's own system-decision thresholds (need_assessment.rules), so
    the plan this agent builds only targets signals that are actually a
    concern for this user — never every signal regardless of its value.
    """

    if not nutrition_signals:
        return []

    triggered = []

    meal_pattern = nutrition_signals.get("meal_pattern")
    if isinstance(meal_pattern, str) and meal_pattern in MEAL_PATTERN_TRIGGER_VALUES:
        triggered.append("meal_pattern")

    fruit_veg = nutrition_signals.get("fruit_vegetable_servings")
    if isinstance(fruit_veg, (int, float)) and fruit_veg < FRUIT_VEGETABLE_SERVINGS_LOW_THRESHOLD:
        triggered.append("fruit_vegetable_servings")

    water = nutrition_signals.get("water_glasses_per_day")
    if isinstance(water, (int, float)) and water < WATER_GLASSES_LOW_THRESHOLD:
        triggered.append("water_glasses_per_day")

    processed_food = nutrition_signals.get("processed_food_frequency")
    if isinstance(processed_food, str) and processed_food in PROCESSED_FOOD_TRIGGER_VALUES:
        triggered.append("processed_food_frequency")

    return triggered


# The four self-reported signals, said the way the user said them rather
# than the way the code stores them. Display only -- the signal keys
# themselves never reach the user.
SIGNAL_WORDING = {
    "meal_pattern": "your meal pattern",
    "fruit_vegetable_servings": "how much fruit and veg you eat",
    "water_glasses_per_day": "how much water you drink",
    "processed_food_frequency": "how often you eat processed food",
}


def _rationale_for(topic: dict, signal: str, nutrition_signals: dict) -> str:
    value = nutrition_signals.get(signal)
    described = SIGNAL_WORDING.get(signal, signal.replace("_", " "))

    return (
        f"You told us about {described} ({value}), which is what brought this "
        f"into your plan. '{topic['name']}' is general guidance on it -- not "
        "a judgement about your health."
    )


def _adaptation_rationale(topic: dict, decision: dict) -> str:
    """The reason shown for an adapted goal: the decision's own recorded
    reason, plus what the replacement topic is when one was chosen."""

    if decision["decision_type"] == DECISION_MODIFY:
        return f"{decision['reason']} '{topic['name']}' is the new focus."

    return decision["reason"]


def _previous_goals(previous_plan: dict) -> list:
    """The previous plan's goals as `(topic_id, target_signal)` pairs.

    Reads the richer `decisions` list a plan record carries since the
    Nutrition Agent started making structured decisions, and falls back to
    the bare `topic_ids` for a record written before that. An older record
    has no stored signal, and None is the honest value for that.
    """

    decisions = previous_plan.get("decisions")

    if isinstance(decisions, list) and decisions:
        return [
            (entry.get("topic_id"), entry.get("target_signal"))
            for entry in decisions
            if isinstance(entry, dict)
            and entry.get("topic_id")
            and entry.get("decision_type") != DECISION_REMOVE
        ]

    return [(topic_id, None) for topic_id in (previous_plan.get("topic_ids") or [])]


def _mcp_session_id_of(*tool_results) -> str | None:
    for tool_result in tool_results:
        if not isinstance(tool_result, dict):
            continue
        metadata = tool_result.get("metadata")
        if isinstance(metadata, dict) and metadata.get("mcp_session_id"):
            return metadata["mcp_session_id"]
    return None


def run_nutrition_agent(
    user_state: dict,
    tool_client: NutritionToolClient,
    *,
    parent_trace: TraceContext,
    previous_plan: dict = None,
    food_log_entries: list = None,
    period_start=None,
    period_end=None,
) -> dict:
    """Run one Nutrition Agent execution. Returns a validated Agent Result.

    `previous_plan` (a plan-version record from
    orchestrator/state_update.py) puts the agent in ADAPTATION mode: rather
    than rebuilding a plan from the questionnaire alone, it reviews the plan
    the user already has against what they actually logged, and decides
    MAINTAIN / MODIFY / REMOVE per focus, with ADDs covering any newly
    triggered signal.

    The adherence itself is not computed here. `food_log_entries` and the
    period bounds are passed to the Nutrition MCP server's
    `calculate_food_adherence` tool, and this agent reads that tool's
    four-state answer. Nothing logged means NOT_LOGGED and a request to
    log -- never a claim that the user did not follow the plan.
    """

    trace = start_agent_run(parent_trace)

    payload = build_nutrition_agent_input(
        user_state,
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
    )

    current_needs = payload["current_needs"]
    nutrition_signals = payload["relevant_nutrition_signals"]

    nutrition_need = (
        (current_needs or {}).get("nutrition_need") if current_needs else None
    )

    # A confirmed medical report can make this domain relevant on its own,
    # with the dietary questions never answered (see
    # orchestrator/decision.py's second activation route). What it cannot
    # do is tell us WHICH dietary change to prescribe: that still comes
    # from the questionnaire. So this path contributes what the evidence
    # actually supports -- the report context, a prompt to complete the
    # questions, and a referral of the figures to a clinician -- and never
    # a meal plan derived from a lab value.
    report_context = report_nutrition_evidence(
        (payload.get("confirmed_medical_context") or {}).get("reports")
    )

    if (
        nutrition_need is None or nutrition_need.get("level") not in TRIGGERING_LEVELS
    ) and report_context["relevant"]:
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            priority="medium",
            findings={
                "mode": "report_context_only",
                "reason": (
                    "A confirmed medical report records nutrition-relevant "
                    "measurements, but the dietary questions have not been "
                    "answered, so no specific dietary change can be targeted "
                    "yet."
                ),
                "report_evidence": report_context["evidence"],
                "missing_information": [
                    "Meal pattern, fruit/vegetable servings, water intake and "
                    "processed-food frequency have not been answered."
                ],
            },
            recommendations=[
                {
                    "id": "discuss_report_values_with_clinician",
                    "title": "Discuss these results with your clinician",
                    "action": (
                        "Take your confirmed report to your doctor or a "
                        "registered dietitian and ask what, if anything, it "
                        "means for your diet."
                    ),
                    # Quotes the report and stops. MoveWell does not read a
                    # value as high, low, or indicative of a condition.
                    "why": (
                        "Your confirmed report contains measurements that are "
                        "usually relevant to diet. MoveWell records what the "
                        "report says but does not interpret the figures."
                    ),
                },
                {
                    "id": "complete_nutrition_questions",
                    "title": "Answer the nutrition questions",
                    "action": (
                        "Complete the four dietary questions in your profile: "
                        "meal pattern, fruit and vegetable servings, water "
                        "intake, and how often you eat processed food."
                    ),
                    "why": (
                        "Without them there is no evidence of what your diet "
                        "actually looks like, so no specific dietary support "
                        "can be tailored to you."
                    ),
                },
            ],
            requires_reassessment=False,
        )

    if nutrition_need is None or nutrition_need.get("level") not in TRIGGERING_LEVELS:
        # Reachable in a direct unit test of the agent; the Orchestrator's
        # own selection rule normally prevents this agent from running at
        # all in this case.
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={
                "reason": (
                    "nutrition_need is not at MEDIUM or HIGH "
                    f"(level={nutrition_need.get('level') if nutrition_need else None!r})"
                )
            },
            recommendations=[],
        )

    triggered_signals = _triggered_signals(nutrition_signals)

    if not triggered_signals:
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={
                "reason": (
                    "nutrition_need is at MEDIUM/HIGH but no individual "
                    "self-reported signal could be identified as the cause "
                    "(e.g. it was derived from unrecognised string values)"
                )
            },
            recommendations=[],
        )

    goal_entries = []
    decisions = []
    tool_call_failed = None
    mcp_session_id = None
    adherence = None
    covered_signals = set()

    if previous_plan is not None:
        # One real tool call for the plan as a whole: adherence is a
        # property of following the plan over a period, not of one goal.
        try:
            adherence_result = tool_client.calculate_food_adherence(
                previous_plan,
                food_log_entries or [],
                period_start=period_start,
                period_end=period_end,
            )

        except Exception as error:  # noqa: BLE001
            adherence_result = {"error": str(error)}

        mcp_session_id = mcp_session_id or _mcp_session_id_of(adherence_result)

        # A failed adherence call is not a failed run: it means this cycle
        # has no adherence evidence, which the decision rules already know
        # how to handle honestly (UNKNOWN, and a request for more logging).
        adherence = (
            adherence_result.get("adherence")
            if isinstance(adherence_result, dict)
            else None
        )

        for topic_id, target_signal in _previous_goals(previous_plan):
            still_triggered = (
                target_signal in triggered_signals if target_signal else True
            )

            decision = decide_for_goal(
                topic_id=topic_id,
                target_signal=target_signal,
                adherence=adherence,
                still_triggered=still_triggered,
            )

            if decision["decision_type"] == DECISION_REMOVE:
                decisions.append(decision)
                continue

            topic = None
            signal_for_lookup = target_signal or (
                triggered_signals[0] if triggered_signals else None
            )

            if decision["decision_type"] == DECISION_MODIFY and signal_for_lookup:
                try:
                    search_result = tool_client.search_nutrition_guidance(
                        target_signal=signal_for_lookup
                    )
                except Exception as error:  # noqa: BLE001
                    tool_call_failed = str(error)
                    break

                mcp_session_id = mcp_session_id or _mcp_session_id_of(search_result)

                if "error" not in search_result:
                    alternatives = [
                        candidate
                        for candidate in search_result["topics"]
                        if candidate["topic_id"] != topic_id
                    ]
                    topic = alternatives[0] if alternatives else None

                if topic is None:
                    # Nothing else covers this signal, so the honest
                    # outcome is to keep what they have. The decision is
                    # rewritten to what actually happened.
                    decision["decision_type"] = DECISION_MAINTAIN
                    decision["reason"] = (
                        "This has been hard to keep up with, but there is no "
                        "other guidance for it, so it stays for now."
                    )

            if topic is None:
                try:
                    details = tool_client.get_nutrition_topic_details(topic_id)
                except Exception as error:  # noqa: BLE001
                    tool_call_failed = str(error)
                    break

                mcp_session_id = mcp_session_id or _mcp_session_id_of(details)

                if "error" in details:
                    # The topic has gone from the library. Drop it rather
                    # than carry an entry that cannot be described.
                    continue

                topic = details["topic"]

            decisions.append(decision)

            if target_signal:
                covered_signals.add(target_signal)

            goal_entries.append(
                build_nutrition_goal_entry(
                    topic_id=topic["topic_id"],
                    practical_goal=topic["practical_goal_examples"][0],
                    rationale=_adaptation_rationale(topic, decision),
                    safety_notes=list(topic["safety_notes"]),
                    target_signal=target_signal,
                    decision_type=decision["decision_type"],
                    evidence_used=decision["evidence_used"] or None,
                    evidence_needed=decision["evidence_needed"] or None,
                    adherence_status=decision["adherence_status"],
                )
            )

    for signal in triggered_signals:
        if signal in covered_signals:
            continue

        if len(goal_entries) >= MAX_GOALS_PER_PLAN:
            break

        try:
            search_result = tool_client.search_nutrition_guidance(target_signal=signal)

        except Exception as error:  # noqa: BLE001
            tool_call_failed = str(error)
            break

        mcp_session_id = mcp_session_id or _mcp_session_id_of(search_result)

        if "error" in search_result:
            tool_call_failed = search_result["error"]
            break

        topics = search_result["topics"]

        if not topics:
            continue

        topic = topics[0]

        goal_entries.append(
            build_nutrition_goal_entry(
                topic_id=topic["topic_id"],
                practical_goal=topic["practical_goal_examples"][0],
                rationale=_rationale_for(topic, signal, nutrition_signals),
                safety_notes=list(topic["safety_notes"]),
                target_signal=signal,
                decision_type=DECISION_ADD,
                # A brand new focus has no adherence history by definition.
                # UNKNOWN says that; it does not say the user has been
                # failing to log.
                adherence_status="UNKNOWN",
                evidence_needed=[
                    "Log what you eat so this can be reviewed against what "
                    "you are actually doing."
                ],
            )
        )

        decisions.append(
            {
                "topic_id": topic["topic_id"],
                "decision_type": DECISION_ADD,
                "reason": _rationale_for(topic, signal, nutrition_signals),
                "adherence_status": "UNKNOWN",
                "evidence_used": [],
                "evidence_needed": [],
                "target_signal": signal,
            }
        )

    if tool_call_failed is not None:
        return build_agent_result(
            agent=AGENT_ID,
            status="failed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            mcp_session_id=mcp_session_id,
            findings={"reason": f"Nutrition MCP search failed: {tool_call_failed}"},
            safety_flags=["mcp_unavailable_or_tool_error"],
            requires_reassessment=True,
        )

    plan = build_nutrition_plan(
        goal=(
            "Your nutrition focus, reviewed against what you logged."
            if previous_plan is not None
            else "Support the nutrition-related signals flagged by the "
            "current needs assessment."
        ),
        nutrition_goals=goal_entries,
    )

    evidence_view = build_nutrition_evidence_view(
        user_state, food_log_entries=food_log_entries
    )

    findings = {
        "nutrition_need_level": nutrition_need["level"],
        # What this domain could and could not establish, from the same
        # function the specialist card reads. With nothing answered this
        # is INSUFFICIENT_EVIDENCE plus the specific questions that are
        # missing -- never generic dietary advice.
        "evidence_status": evidence_view["status"],
        "missing_information": evidence_view["missing_information"],
        "evidence_used": evidence_view["evidence_used"],
        "confidence": evidence_view["confidence"],
        "triggered_signals": triggered_signals,
        # Every decision this cycle, including the REMOVEs that by
        # definition have no goal entry, and what each one was decided from.
        "decisions": decisions,
        "adherence": adherence,
        "adaptation_summary": (
            summarise(decisions) if previous_plan is not None else None
        ),
        "adapted_from_plan_id": (
            previous_plan.get("plan_id") if previous_plan is not None else None
        ),
        "plan": plan,
    }

    requires_reassessment = not goal_entries

    return build_agent_result(
        agent=AGENT_ID,
        status="completed",
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        mcp_session_id=mcp_session_id,
        priority="high" if nutrition_need["level"] == "HIGH" else "medium",
        findings=findings,
        recommendations=[
            {"topic_id": entry["topic_id"], "reason": entry["rationale"]}
            for entry in goal_entries
        ],
        requires_reassessment=requires_reassessment,
        safety_flags=[],
    )
