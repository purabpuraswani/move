"""The Behaviour/Habit Agent's actual execution lifecycle.

    Behaviour Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the structured input (input_contract.py, from User State)
          |
    Determine which questionnaire signals triggered a behaviour need
        (reuses need_assessment.rules's own thresholds — no second,
        divergent set of numbers)
          |
    Call Behaviour MCP tools (via the injected BehaviourToolClient — never
        behaviour_library directly)
          |
    Build a structured Habit Plan (plan_schema.py) with a rationale per
        goal
          |
    Return a Phase 0 Agent Result (orchestration.agent_result)

Mirrors physio_agent/agent.py and nutrition_agent/agent.py exactly.
"""

from need_assessment.rules import (
    EXERCISE_DAYS_LOW_THRESHOLD,
    SCREEN_HOURS_HIGH_THRESHOLD,
    SITTING_HOURS_HIGH_THRESHOLD,
    WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD,
)
from orchestration.agent_result import build_agent_result
from orchestration.ids import TraceContext, start_agent_run
from behaviour_agent.adaptation import (
    ACTIVITY_SIGNALS,
    DECISION_ADD,
    DECISION_MAINTAIN,
    DECISION_MODIFY,
    DECISION_REMOVE,
    EVIDENCE_NEEDED_RECORD_IT,
    EVIDENCE_NEEDED_SESSIONS,
    completed_session_count,
    decide_for_goal,
    summarise,
)
from behaviour_agent.barriers import behaviour_interventions, identify_barriers
from behaviour_agent.adherence import summarise_for_progress
from behaviour_agent.input_contract import build_behaviour_agent_input
from behaviour_agent.plan_schema import build_habit_goal_entry, build_habit_plan
from behaviour_agent.tool_client import BehaviourToolClient

AGENT_ID = "behaviour"

TRIGGERING_LEVELS = ("MEDIUM", "HIGH")

MAX_GOALS_PER_PLAN = 4


class BehaviourAgentError(Exception):
    """Raised for a Behaviour Agent run that could not produce a result at
    all (as opposed to a run that completed with an empty plan)."""


def _triggered_signals(signals: dict) -> list:
    """Return which questionnaire-derived signals crossed the same
    thresholds need_assessment.rules.assess_behaviour_need() already
    applies — reused, not reinvented, so this agent's plan and the Need
    Profile's evidence always agree on what "triggered" means.
    """

    if not signals:
        return []

    triggered = []

    sitting = signals.get("daily_sitting_hours")
    if isinstance(sitting, (int, float)) and sitting >= SITTING_HOURS_HIGH_THRESHOLD:
        triggered.append("daily_sitting_hours")

    screen = signals.get("daily_screen_hours")
    if isinstance(screen, (int, float)) and screen >= SCREEN_HOURS_HIGH_THRESHOLD:
        triggered.append("daily_screen_hours")

    exercise_days = signals.get("exercise_days")
    if isinstance(exercise_days, (int, float)) and exercise_days < EXERCISE_DAYS_LOW_THRESHOLD:
        triggered.append("exercise_days")

    exercise_minutes = signals.get("exercise_minutes")
    if (
        isinstance(exercise_days, (int, float))
        and isinstance(exercise_minutes, (int, float))
        and exercise_days * exercise_minutes < WEEKLY_EXERCISE_MINUTES_LOW_THRESHOLD
    ):
        triggered.append("weekly_exercise_minutes")

    return triggered


# The questionnaire signals, said the way the user answered them rather
# than the way the code stores them. Display only.
SIGNAL_WORDING = {
    "daily_sitting_hours": "hours a day sitting",
    "daily_screen_hours": "hours a day on screens",
    "exercise_days": "days a week you exercise",
    "weekly_exercise_minutes": "minutes of exercise a week",
}


def signal_value(signal: str, signals: dict):
    """The value behind one signal, computed the same way
    `_triggered_signals` computes it -- so what is recorded on a decision
    and what triggered it can never disagree."""

    if signal == "weekly_exercise_minutes":
        days = signals.get("exercise_days")
        minutes = signals.get("exercise_minutes")

        if isinstance(days, (int, float)) and isinstance(minutes, (int, float)):
            return days * minutes

        return None

    return (signals or {}).get(signal)


def _rationale_for(topic: dict, signal: str, signals: dict) -> str:
    value = signal_value(signal, signals)
    described = SIGNAL_WORDING.get(signal, signal.replace("_", " "))

    return (
        f"You told us about {described} ({value}), which is what brought this "
        f"into your plan. '{topic['name']}' is general guidance on it -- not "
        "a judgement about your health."
    )


def _adaptation_rationale(topic: dict, decision: dict) -> str:
    if decision["decision_type"] == DECISION_MODIFY:
        return f"{decision['reason']} '{topic['name']}' is the new approach."

    return decision["reason"]


def _previous_goals(previous_plan: dict) -> list:
    """The previous plan's goals as `(topic_id, target_signal, value)`.

    The recorded value is what makes MODIFY reachable: without something to
    compare a re-answer against, there is no evidence that the current
    approach is not working, and the honest decision is to leave it alone.
    """

    current_goal_text = {
        entry.get("topic_id"): entry.get("practical_goal")
        for entry in (previous_plan.get("goals") or [])
        if isinstance(entry, dict)
    }

    decisions = previous_plan.get("decisions")

    if isinstance(decisions, list) and decisions:
        return [
            (
                entry.get("topic_id"),
                entry.get("target_signal"),
                entry.get("signal_value"),
                current_goal_text.get(entry.get("topic_id")),
            )
            for entry in decisions
            if isinstance(entry, dict)
            and entry.get("topic_id")
            and entry.get("decision_type") != DECISION_REMOVE
        ]

    return [
        (topic_id, None, None, current_goal_text.get(topic_id))
        for topic_id in (previous_plan.get("topic_ids") or [])
    ]


def _next_practical_goal(topic: dict, current_goal):
    """A different concrete action for the same habit, or None.

    Every behaviour library topic carries more than one
    `practical_goal_examples` entry, and swapping between them is a real
    change to what the user is asked to do -- which matters here because
    the library has exactly ONE topic per questionnaire signal, so there is
    never another topic to swap to. Without this, MODIFY could be decided
    and then never carried out.
    """

    examples = topic.get("practical_goal_examples") or []
    alternatives = [example for example in examples if example != current_goal]

    return alternatives[0] if alternatives else None


def _mcp_session_id_of(*tool_results) -> str | None:
    for tool_result in tool_results:
        if not isinstance(tool_result, dict):
            continue
        metadata = tool_result.get("metadata")
        if isinstance(metadata, dict) and metadata.get("mcp_session_id"):
            return metadata["mcp_session_id"]
    return None


def run_behaviour_agent(
    user_state: dict,
    tool_client: BehaviourToolClient,
    *,
    parent_trace: TraceContext,
    previous_plan: dict = None,
    exercise_results: list = None,
    behaviour_actions: list = None,
) -> dict:
    """Run one Behaviour Agent execution. Returns a validated Agent Result.

    `previous_plan` puts the agent in ADAPTATION mode: it reviews the habit
    goals the user already has against the evidence this application
    actually holds -- their latest questionnaire answers, and recorded
    exercise sessions for the two signals that genuinely are about activity.

    `behaviour_actions` is this user's recorded actions from the behaviour
    log -- the most specific evidence there is, because each record is
    about one habit goal. Recorded exercise sessions remain a secondary
    signal, used only for the two questionnaire signals that genuinely are
    about activity. See behaviour_agent/adaptation.py for the precedence
    and behaviour_agent/adherence.py for how a rate is computed (and when
    it is refused).

    No recorded action is never read as failure: with nothing recorded the
    status is NOT_LOGGED and the plan is left alone.
    """

    trace = start_agent_run(parent_trace)

    payload = build_behaviour_agent_input(
        user_state,
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
    )

    current_needs = payload["current_needs"]
    signals = payload["relevant_behaviour_signals"]

    behaviour_need = (
        (current_needs or {}).get("behaviour_need") if current_needs else None
    )

    if behaviour_need is None or behaviour_need.get("level") not in TRIGGERING_LEVELS:
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={
                "reason": (
                    "behaviour_need is not at MEDIUM or HIGH "
                    f"(level={behaviour_need.get('level') if behaviour_need else None!r})"
                )
            },
            recommendations=[],
        )

    triggered_signals = _triggered_signals(signals)

    if not triggered_signals:
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={
                "reason": (
                    "behaviour_need is at MEDIUM/HIGH but no individual "
                    "questionnaire signal could be identified as the cause"
                )
            },
            recommendations=[],
        )

    goal_entries = []
    # topic_id -> the library record behind it, for barriers.py. Kept
    # as the goals are selected rather than re-fetched afterwards: a
    # second lookup could disagree with what was actually chosen.
    selected_topic_records = {}
    decisions = []
    tool_call_failed = None
    mcp_session_id = None
    covered_signals = set()
    completed_sessions = completed_session_count(exercise_results)

    if previous_plan is not None:
        for (
            topic_id,
            target_signal,
            previous_value,
            current_goal,
        ) in _previous_goals(previous_plan):
            still_triggered = (
                target_signal in triggered_signals if target_signal else True
            )

            decision = decide_for_goal(
                topic_id=topic_id,
                target_signal=target_signal,
                previous_value=previous_value,
                current_value=signal_value(target_signal, signals)
                if target_signal
                else None,
                still_triggered=still_triggered,
                completed_sessions=completed_sessions,
                actions=behaviour_actions,
            )

            if decision["decision_type"] == DECISION_REMOVE:
                decisions.append(decision)
                continue

            topic = None

            if decision["decision_type"] == DECISION_MODIFY and target_signal:
                try:
                    search_result = tool_client.search_behaviour_guidance(
                        target_signal=target_signal
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
                    # No other topic covers this signal -- which is the
                    # normal case, since the library holds one topic per
                    # signal. The change is then made to the concrete
                    # action instead, below, once the topic is resolved.
                    pass

            if topic is None:
                try:
                    details = tool_client.get_behaviour_topic_details(topic_id)
                except Exception as error:  # noqa: BLE001
                    tool_call_failed = str(error)
                    break

                mcp_session_id = mcp_session_id or _mcp_session_id_of(details)

                if "error" in details:
                    continue

                topic = details["topic"]

            practical_goal = topic["practical_goal_examples"][0]

            if decision["decision_type"] == DECISION_MODIFY:
                replacement_goal = (
                    _next_practical_goal(topic, current_goal)
                    if topic["topic_id"] == topic_id
                    else practical_goal
                )

                if replacement_goal is None:
                    # Nothing else to ask for: neither another topic nor
                    # another action. Keeping what they have is the honest
                    # outcome, and the decision is rewritten to say so
                    # rather than claiming a change that did not happen.
                    decision["decision_type"] = DECISION_MAINTAIN
                    decision["reason"] = (
                        "This does not seem to be working, but there is no "
                        "other way to approach it in the library, so it "
                        "stays for now."
                    )
                else:
                    practical_goal = replacement_goal

            elif current_goal and topic["topic_id"] == topic_id:
                # Unchanged goals keep the exact action the user already
                # has, rather than silently reverting to the first example.
                practical_goal = current_goal

            decisions.append(decision)

            if target_signal:
                covered_signals.add(target_signal)

            selected_topic_records[topic["topic_id"]] = topic
            goal_entries.append(
                build_habit_goal_entry(
                    topic_id=topic["topic_id"],
                    practical_goal=practical_goal,
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
            search_result = tool_client.search_behaviour_guidance(target_signal=signal)

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

        selected_topic_records[topic["topic_id"]] = topic
        goal_entries.append(
            build_habit_goal_entry(
                topic_id=topic["topic_id"],
                practical_goal=topic["practical_goal_examples"][0],
                rationale=_rationale_for(topic, signal, signals),
                safety_notes=list(topic["safety_notes"]),
                target_signal=signal,
                decision_type=DECISION_ADD,
                # A brand new goal has no history by definition. UNKNOWN
                # says that; it never says the user has been failing.
                adherence_status="UNKNOWN",
                evidence_needed=[
                    EVIDENCE_NEEDED_SESSIONS
                    if signal in ACTIVITY_SIGNALS
                    else EVIDENCE_NEEDED_RECORD_IT
                ],
            )
        )

        decisions.append(
            {
                "topic_id": topic["topic_id"],
                "decision_type": DECISION_ADD,
                "reason": _rationale_for(topic, signal, signals),
                "adherence_status": "UNKNOWN",
                "evidence_used": [],
                "evidence_needed": [],
                "target_signal": signal,
                "signal_value": signal_value(signal, signals),
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
            findings={"reason": f"Behaviour MCP search failed: {tool_call_failed}"},
            safety_flags=["mcp_unavailable_or_tool_error"],
            requires_reassessment=True,
        )

    plan = build_habit_plan(
        goal="Support the sedentary-behaviour signals flagged by the current needs assessment.",
        habit_goals=goal_entries,
    )

    behaviour_adherence = summarise_for_progress(behaviour_actions)
    # Library barriers are read only for the topics this plan actually
    # selected, so a barrier never appears for a goal the user does not have.
    selected_topics = [
        selected_topic_records[entry["topic_id"]]
        for entry in goal_entries
        if entry["topic_id"] in selected_topic_records
    ]
    barriers = identify_barriers(behaviour_adherence, selected_topics)

    findings = {
        "behaviour_need_level": behaviour_need["level"],
        "triggered_signals": triggered_signals,
        "decisions": decisions,
        "completed_exercise_sessions": completed_sessions,
        # What the recorded actions add up to across every goal. Computed
        # by behaviour_agent/adherence.py, which returns NOT_LOGGED or
        # INSUFFICIENT_DATA rather than a rate when there is not enough.
        "behaviour_adherence": behaviour_adherence,
        # This specialist's own lever: what is getting in the way, and the
        # change to the plan's shape that addresses it. Never an exercise
        # and never a dose -- those belong to Physio and to Exercise &
        # Physical Activity, and repeating them here would be this agent
        # doing another agent's job.
        "barriers": barriers,
        "behaviour_interventions": behaviour_interventions(
            behaviour_adherence, barriers, len(goal_entries)
        ),
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
        priority="high" if behaviour_need["level"] == "HIGH" else "medium",
        findings=findings,
        recommendations=[
            {"topic_id": entry["topic_id"], "reason": entry["rationale"]}
            for entry in goal_entries
        ],
        requires_reassessment=requires_reassessment,
        safety_flags=[],
    )
