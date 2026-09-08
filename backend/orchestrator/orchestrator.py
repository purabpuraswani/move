"""run_workflow(): the actual end-to-end multi-agent execution (Phase 4).

    User State
        |
    Need Assessment (only if current_needs is not already populated —
        reused from Phase 1, never recomputed if already present)
        |
    Orchestrator decision (decision.py) -> which of Physio/Behaviour/
        Nutrition are required? (each decided independently and
        explicitly — never "always run all three", never a hidden
        threshold)
        |
    Selected agents run independently (no agent reads another agent's
        output, no artificial agent-to-agent conversation — structured
        data only, aggregated afterwards by this module)
        |
    Each Agent Result is validated (orchestration.agent_result)
        |
    Candidate recommendations from every *completed* agent are collected
        into one normalised list and sent through the Safety Gate
        (safety.gate.evaluate_safety) — this happens even if only one
        agent ran, and even if the gate ends up NOT_ASSESSED
        |
    Safety decisions are applied: a PAUSE/REFER outcome removes the
        affected recommendation(s) from what is actually persisted to the
        User State and from `final_recommendations` — a blocked/paused
        candidate never appears unchanged in the approved set
        |
    User State updates (state_update.py) for whichever agents still have
        at least one approved recommendation after the safety gate
        |
    Orchestrator Result

Phase 3's single-agent behaviour is preserved exactly for a Physio-only
run: `tool_client` keeps its old meaning (the Exercise/Physio tool
client), `selected_agents == ["physio"]`/`state_updates == ["exercise_history"]`
when only Physio is required, and a Physio run with no tool_client
supplied is still the same distinct, non-crashing error it was in Phase 3.
Behaviour and Nutrition are additive, not replacements.
"""

from behaviour_agent.agent import run_behaviour_agent
from behaviour_agent.tool_client import BehaviourToolClient
from nutrition_agent.agent import run_nutrition_agent
from nutrition_agent.tool_client import NutritionToolClient
from orchestration.agent_result import validate_agent_result
from orchestration.ids import TraceContext, start_workflow
from orchestrator.decision import (
    decide_behaviour_required,
    decide_nutrition_required,
    decide_physio_required,
    decide_progress_required,
)
from orchestrator.state_update import (
    apply_behaviour_plan,
    apply_nutrition_plan,
    apply_physio_plan,
    refresh_plan_evidence,
)
from physio_agent.agent import run_physio_agent
from physio_agent.tool_client import ExerciseToolClient
from progress_agent.agent import run_progress_agent
from progress_agent.tool_client import ProgressToolClient
from safety.gate import SafetyEvaluationError, evaluate_safety
from user_state.schema import UserStateValidationError, validate_user_state

# Phase 5: which specialist agent an adaptation_recommendation dispatches
# to, if any. PROGRESS/REGRESS both mean "physio should review the
# exercise plan again" (progression and regression are both an exercise
# selection question, per the brief's "Physio remains responsible for
# exercise selection" rule); MODIFY means an adherence problem, which is
# Behaviour's territory, not Physio's or Nutrition's. MAINTAIN/CONTINUE/
# REASSESS never dispatch a specialist re-run on their own — REASSESS
# means a new physical assessment is needed first, not a plan change.
# Nutrition-adaptation dispatch is deliberately absent: no nutrition
# adherence data source exists yet to justify one (see docs/architecture.md).
_ADAPTATION_DISPATCH = {
    "PROGRESS": "physio",
    "REGRESS": "physio",
    "MODIFY": "behaviour",
}

# Phase 6: nutrition-specific adaptation dispatch, evaluated independently
# of _ADAPTATION_DISPATCH above (a physical recommendation and a nutrition
# recommendation can both fire in the same cycle — they are separate axes,
# see progress_agent/nutrition_progress.py's module docstring). Only
# MODIFY dispatches: CONTINUE/MAINTAIN never dispatch a re-run on their
# own (same rule as physical MAINTAIN/CONTINUE), and REASSESS means more
# food-log data is needed first, not a plan change.
_NUTRITION_ADAPTATION_DISPATCH = {
    "MODIFY": "nutrition",
}

# One agent id -> the plan-list key inside that agent's findings.plan, the
# field name inside each plan entry that is this candidate's id, and (for
# Physio only) the field carrying a declared difficulty the Safety Gate's
# difficulty-ceiling rule can read. Kept in one place so
# _candidate_recommendations()/_filter_plan() never have to special-case
# each agent by name more than once.
_AGENT_PLAN_SHAPE = {
    "physio": {"list_key": "exercises", "id_key": "exercise_id", "difficulty_key": "difficulty"},
    "behaviour": {"list_key": "habit_goals", "id_key": "topic_id", "difficulty_key": None},
    "nutrition": {"list_key": "nutrition_goals", "id_key": "topic_id", "difficulty_key": None},
}


def _build_result(
    *, workflow_id, request_id, orchestrator_decision, selected_agents,
    agent_results, safety_result, final_recommendations, coordination_notes,
    state_updates, updated_user_state, errors,
):
    return {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "orchestrator_decision": orchestrator_decision,
        "selected_agents": selected_agents,
        "agent_results": agent_results,
        "safety_result": safety_result,
        "final_recommendations": final_recommendations,
        "coordination_notes": coordination_notes,
        "state_updates": state_updates,
        "updated_user_state": updated_user_state,
        "errors": errors,
    }


def _confirmed_medical_context(user_state: dict):
    section = user_state.get("medical_context") or {}

    if not section.get("available"):
        return None

    confirmed = (section.get("data") or {}).get("confirmed_reports") or {}
    reports = confirmed.get("reports") or []

    if not reports:
        return None

    return {"source": "user_confirmed_medical_report", "reports": reports}


def _candidate_recommendations(agent_results: dict) -> list:
    """Normalise every completed agent's plan entries into one flat list
    the Safety Gate can evaluate: [{"id", "agent", "type", "difficulty"}].
    An agent that did not run, or ran but produced no plan, contributes
    nothing — never a guessed candidate.
    """

    candidates = []

    for agent_id, result in agent_results.items():
        if result is None or result.get("status") != "completed":
            continue

        if agent_id not in _AGENT_PLAN_SHAPE:
            # Non-plan-producing agents (Progress) never contribute a
            # candidate recommendation of their own — they only ever
            # recommend that a specialist agent re-run, which then
            # contributes its own candidates through this same loop.
            continue

        shape = _AGENT_PLAN_SHAPE[agent_id]
        plan = (result.get("findings") or {}).get("plan") or {}
        entries = plan.get(shape["list_key"]) or []

        for entry in entries:
            candidates.append(
                {
                    "id": entry[shape["id_key"]],
                    "agent": agent_id,
                    "type": "exercise" if agent_id == "physio" else f"{agent_id}_goal",
                    "difficulty": (
                        entry.get(shape["difficulty_key"])
                        if shape["difficulty_key"]
                        else None
                    ),
                }
            )

    return candidates


def _filtered_plan(agent_id: str, plan: dict, removed_ids: set) -> dict:
    """Return a copy of `plan` with any entry whose id is in `removed_ids`
    taken out. Used to make sure a PAUSE/REFER-blocked recommendation is
    never the thing actually written to the User State, even though the
    original Agent Result (kept in `agent_results` for audit) still shows
    what the agent originally proposed.
    """

    shape = _AGENT_PLAN_SHAPE[agent_id]
    entries = plan.get(shape["list_key"]) or []

    kept = [entry for entry in entries if entry[shape["id_key"]] not in removed_ids]

    return {**plan, shape["list_key"]: kept}


def _coordination_notes(agent_results: dict, need_profile) -> list:
    """Identify the one concrete cross-agent conflict this project's rules
    call out by name: Physio recommending more exercise while Behaviour's
    own need level says baseline adherence is poor. Deterministic — reads
    only the levels/plans already computed, invents nothing.
    """

    notes = []

    physio_result = agent_results.get("physio")
    behaviour_result = agent_results.get("behaviour")

    physio_has_plan = bool(
        physio_result
        and physio_result.get("status") == "completed"
        and (physio_result.get("findings") or {}).get("plan", {}).get("exercises")
    )
    behaviour_level = (
        (need_profile or {}).get("behaviour_need") or {}
    ).get("level")

    if physio_has_plan and behaviour_level == "HIGH":
        notes.append(
            "Physio produced an exercise plan while behaviour_need is HIGH "
            "(baseline adherence/activity signals are poor). Combined "
            "guidance: introduce the Behaviour Agent's small movement-break "
            "habit goal(s) alongside the exercise plan, rather than the "
            "exercise plan alone, since a low-adherence baseline is "
            "evidence a larger change is less likely to stick on its own."
        )

    return notes


def run_workflow(
    user_state: dict,
    *,
    tool_client: ExerciseToolClient = None,
    behaviour_tool_client: BehaviourToolClient = None,
    nutrition_tool_client: NutritionToolClient = None,
    progress_tool_client: ProgressToolClient = None,
    progress_trigger: dict = None,
    baseline_assessment: dict = None,
    previous_assessment: dict = None,
    current_assessment: dict = None,
    exercise_results: list = None,
    nutrition_food_log_previous_period: list = None,
    nutrition_food_log_current_period: list = None,
    # Recorded behaviour actions -- the evidence a habit plan is reviewed
    # against. Supplied by the caller (routes/workflow.py reads them from
    # behaviour_log/store.py) rather than fetched here, for the same reason
    # every other piece of evidence is: this module touches no database.
    behaviour_actions: list = None,
    nutrition_period_previous: dict = None,
    nutrition_period_current: dict = None,
    workflow_id: str = None,
    request_id: str = None,
) -> dict:
    """Run the Phase 4/5 multi-agent workflow against one User State.

    `tool_client` (Exercise/Physio), `behaviour_tool_client`, and
    `nutrition_tool_client` are each supplied by the caller only when that
    agent might actually run — a production caller passes the matching
    `Mcp*ToolClient`; this project's own tests pass the matching
    `InProcess*ToolClient`. An agent that is required but has no matching
    client produces a named error and no Agent Result for that agent,
    exactly like Phase 3's Physio-only behaviour — it never silently skips
    or crashes the whole workflow, and it never prevents an *independent*
    agent (one that does have its client) from still running.

    Phase 5 closed-loop parameters (all optional, all `None` by default so
    every Phase 3/4 call site is completely unaffected):

    `progress_trigger` — a caller-supplied `{"reason": "..."}` dict saying
    *why* the Progress Agent should run this cycle (e.g. "exercise
    activity recorded" or "reassessment completed"). `run_workflow` never
    invents this on its own and never runs Progress on a fixed schedule —
    per the brief, there is no scheduling mechanism in this application
    yet, so a caller (a route handler reacting to a real event) decides
    when a progress review is warranted and passes the trigger in.
    `baseline_assessment` / `previous_assessment` / `current_assessment` —
    raw assessment documents (the same shape `assessments/store.py`
    already returns), passed straight through to the Progress Agent.
    `run_workflow` never fetches these itself and never mutates or
    reorders them — the caller is responsible for keeping baseline fixed
    across reassessments.
    `exercise_results` — the caller's already-fetched list of persisted
    exercise-result documents (`exercise_assessment/store.py`'s shape),
    used only for Progress's exercise-performance-history comparison.

    `nutrition_food_log_previous_period` / `nutrition_food_log_current_period`
    (Phase 6) — the caller's already-fetched lists of persisted food_log
    documents (`food_log/store.py`'s shape) for two comparison periods,
    each paired with `nutrition_period_previous` / `nutrition_period_current`
    (`{"start": ..., "end": ...}`). `run_workflow` builds the
    `nutrition_plan` record itself from the User State's own
    `nutrition_plan` section (the same way it already builds the exercise
    `current_plan` record below) — the caller never passes a nutrition
    plan record directly. All four are optional and `None` by default;
    omitting them means Progress's nutrition_progress finding is simply
    `None` for this cycle, exactly like omitting the physical assessment
    arguments.

    When `progress_trigger` is given, this becomes a second execution
    phase (Phase B) *after* the existing Phase 4 need-based agent
    selection (Phase A): the Progress Agent runs, and if its
    `adaptation_recommendation` maps to a specialist
    (`_ADAPTATION_DISPATCH`), that specialist agent is run too — but only
    if it was not already run in Phase A this cycle, to avoid a redundant
    double plan-version for the same workflow run. Every agent result from
    both phases (Phase A's need-based selections and Phase B's
    progress-triggered dispatch) is then merged into ONE candidate
    collection and evaluated by exactly ONE Safety Gate pass — Safety
    Gate is never run twice and never bypassed for adaptation-triggered
    plans.
    """

    try:
        validate_user_state(user_state)
    except UserStateValidationError as error:
        trace = start_workflow(workflow_id=workflow_id)
        empty_decision = {"physio_required": False, "reason": "invalid", "evaluated_dimensions": {}}
        return _build_result(
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            orchestrator_decision={
                "physio_required": False,
                "behaviour_required": False,
                "nutrition_required": False,
                "reason": "User State is missing or malformed; nothing could be evaluated",
                "physio": empty_decision,
                "behaviour": {"behaviour_required": False, "reason": "invalid", "evaluated_dimensions": {}},
                "nutrition": {"nutrition_required": False, "reason": "invalid", "evaluated_dimensions": {}},
            },
            selected_agents=[],
            agent_results=[],
            safety_result=None,
            final_recommendations=[],
            coordination_notes=[],
            state_updates=[],
            updated_user_state=None,
            errors=[f"invalid User State: {error}"],
        )

    if request_id is None:
        trace = start_workflow(workflow_id=workflow_id)
        workflow_id, request_id = trace.workflow_id, trace.request_id

    parent_trace = TraceContext(workflow_id=workflow_id, request_id=request_id)

    current_needs_section = user_state.get("current_needs") or {}
    need_profile = (
        current_needs_section.get("data")
        if current_needs_section.get("available")
        else None
    )

    # Whether this user already has an exercise plan. Read from the User
    # State the caller handed in (which, since the assembly merge fix,
    # carries plans forward across runs). It only ever affects the
    # conservative starter pathway in decide_physio_required — an
    # evidence-based selection is never suppressed by it.
    exercise_history_section = user_state.get("exercise_history") or {}
    existing_exercise_plans = (
        (exercise_history_section.get("data") or {}).get("plans") or []
        if exercise_history_section.get("available")
        else []
    )
    current_exercise_plan = (
        existing_exercise_plans[-1] if existing_exercise_plans else None
    )
    exercise_plan_exists = bool(existing_exercise_plans)

    def _current_plan_of(section_name):
        """The newest plan-version record in one plan section, or None.

        The specialist agents need the plan the user already has in order
        to adapt it rather than rebuild it. Read once here so Phase A and
        Phase B can never disagree about which record is current.
        """

        section = user_state.get(section_name) or {}
        plans = (
            (section.get("data") or {}).get("plans") or []
            if section.get("available")
            else []
        )

        return plans[-1] if plans else None

    current_nutrition_plan = _current_plan_of("nutrition_plan")
    current_behaviour_plan = _current_plan_of("behaviour")

    physio_decision = decide_physio_required(
        need_profile, exercise_plan_exists=exercise_plan_exists
    )
    behaviour_decision = decide_behaviour_required(need_profile)
    nutrition_decision = decide_nutrition_required(need_profile)
    progress_decision = decide_progress_required(progress_trigger)

    orchestrator_decision = {
        "physio_required": physio_decision["physio_required"],
        "behaviour_required": behaviour_decision["behaviour_required"],
        "nutrition_required": nutrition_decision["nutrition_required"],
        "progress_required": progress_decision["progress_required"],
        "physio": physio_decision,
        "behaviour": behaviour_decision,
        "nutrition": nutrition_decision,
        "progress": progress_decision,
    }

    selected_agents = [
        agent_id
        for agent_id, required in (
            ("physio", physio_decision["physio_required"]),
            ("behaviour", behaviour_decision["behaviour_required"]),
            ("nutrition", nutrition_decision["nutrition_required"]),
        )
        if required
    ]

    if not selected_agents and not progress_decision["progress_required"]:
        return _build_result(
            workflow_id=workflow_id,
            request_id=request_id,
            orchestrator_decision=orchestrator_decision,
            selected_agents=[],
            agent_results=[],
            safety_result=None,
            final_recommendations=[],
            coordination_notes=[],
            state_updates=[],
            updated_user_state=user_state,
            errors=[],
        )

    errors = []
    agent_results = {}  # agent_id -> Agent Result dict, only for agents that actually ran

    # Each selected agent runs independently: none of them reads another
    # agent's output, and a missing client or a runtime failure for one
    # agent never prevents another selected agent (with its own client)
    # from running.
    if "physio" in selected_agents:
        if tool_client is None:
            errors.append("Physio is required but no ExerciseToolClient was provided to run_workflow()")
        else:
            try:
                # A user who already has a plan is not given a second first
                # draft. Whatever selected Physio this cycle — a standing
                # need or a Progress recommendation — the run is an
                # adaptation of the plan they have, judged against what
                # they actually recorded. Without this, a persisting need
                # rebuilt an identical ADD-only plan on every run and the
                # adaptation path below could never be reached, because
                # Phase A had already run the agent.
                result = run_physio_agent(
                    user_state,
                    tool_client,
                    parent_trace=parent_trace,
                    previous_plan=current_exercise_plan,
                    exercise_results=exercise_results,
                )
                validate_agent_result(result)
                agent_results["physio"] = result
            except Exception as error:  # noqa: BLE001
                errors.append(f"Physio Agent run failed: {error}")

    if "behaviour" in selected_agents:
        if behaviour_tool_client is None:
            errors.append("Behaviour is required but no BehaviourToolClient was provided to run_workflow()")
        else:
            try:
                # A user who already has habit goals is not given a fresh
                # set: the run reviews the goals they have against their
                # latest answers and their recorded sessions.
                result = run_behaviour_agent(
                    user_state,
                    behaviour_tool_client,
                    parent_trace=parent_trace,
                    previous_plan=current_behaviour_plan,
                    exercise_results=exercise_results,
                    behaviour_actions=behaviour_actions,
                )
                validate_agent_result(result)
                agent_results["behaviour"] = result
            except Exception as error:  # noqa: BLE001
                errors.append(f"Behaviour Agent run failed: {error}")

    if "nutrition" in selected_agents:
        if nutrition_tool_client is None:
            errors.append("Nutrition is required but no NutritionToolClient was provided to run_workflow()")
        else:
            try:
                # Likewise for nutrition: with a plan already in place the
                # run reviews it against what the user actually logged,
                # through the Nutrition MCP server's own adherence tool.
                result = run_nutrition_agent(
                    user_state,
                    nutrition_tool_client,
                    parent_trace=parent_trace,
                    previous_plan=current_nutrition_plan,
                    food_log_entries=nutrition_food_log_current_period,
                    period_start=(nutrition_period_current or {}).get("start"),
                    period_end=(nutrition_period_current or {}).get("end"),
                )
                validate_agent_result(result)
                agent_results["nutrition"] = result
            except Exception as error:  # noqa: BLE001
                errors.append(f"Nutrition Agent run failed: {error}")

    # ------------------------------------------------------------------
    # Phase B (Phase 5): progress-triggered review + adaptation dispatch.
    # Runs strictly after Phase A above, and only when the caller supplied
    # a `progress_trigger` — never on an invented schedule. `adaptation_info`
    # records, per specialist agent id, the structured reason a Phase-B
    # dispatch happened, so the eventual plan-version record below can
    # carry a real `adaptation_reason` / `triggered_by` instead of a vague
    # "plan updated".
    # ------------------------------------------------------------------
    adaptation_info = {}

    if progress_decision["progress_required"]:
        if progress_tool_client is None:
            errors.append(
                "Progress review is required but no ProgressToolClient was "
                "provided to run_workflow()"
            )
        else:
            existing_history_section = user_state.get("exercise_history") or {}
            existing_plans = (
                (existing_history_section.get("data") or {}).get("plans", [])
                if existing_history_section.get("available")
                else []
            )
            current_plan_record = existing_plans[-1] if existing_plans else None

            existing_nutrition_section = user_state.get("nutrition_plan") or {}
            existing_nutrition_plans = (
                (existing_nutrition_section.get("data") or {}).get("plans", [])
                if existing_nutrition_section.get("available")
                else []
            )
            nutrition_plan_record = existing_nutrition_plans[-1] if existing_nutrition_plans else None

            try:
                progress_result = run_progress_agent(
                    baseline_assessment=baseline_assessment,
                    previous_assessment=previous_assessment,
                    current_assessment=current_assessment,
                    exercise_history=(
                        existing_history_section.get("data")
                        if existing_history_section.get("available")
                        else None
                    ),
                    exercise_results=exercise_results,
                    current_plan=current_plan_record,
                    current_needs=need_profile,
                    nutrition_plan=nutrition_plan_record,
                    nutrition_food_log_previous_period=nutrition_food_log_previous_period,
                    nutrition_food_log_current_period=nutrition_food_log_current_period,
                    behaviour_actions=behaviour_actions,
                    nutrition_period_previous=nutrition_period_previous,
                    nutrition_period_current=nutrition_period_current,
                    tool_client=progress_tool_client,
                    parent_trace=parent_trace,
                )
                validate_agent_result(progress_result)
                agent_results["progress"] = progress_result
                if "progress" not in selected_agents:
                    selected_agents.append("progress")
            except Exception as error:  # noqa: BLE001
                errors.append(f"Progress Agent run failed: {error}")
                progress_result = None

            if progress_result is not None and progress_result.get("status") == "completed":
                findings = progress_result.get("findings") or {}
                recommendation = findings.get("adaptation_recommendation")
                dispatch_agent = _ADAPTATION_DISPATCH.get(recommendation)

                if dispatch_agent:
                    reassessment = findings.get("reassessment") or {}
                    direction = findings.get("overall_direction")
                    reason = (
                        f"Progress Agent recommended {recommendation} "
                        f"(overall_direction={direction}, "
                        f"reassessment_required={reassessment.get('required')})"
                    )

                    # If the dispatch-target agent already ran in Phase A
                    # this same cycle (its own need level independently
                    # warranted a run), it is NOT re-run a second time —
                    # that would be a redundant duplicate plan version.
                    # But the resulting plan version IS still attributed
                    # to the Progress recommendation below: when a
                    # progress_trigger was supplied and Progress's own
                    # comparison independently arrives at the same
                    # specialist, that plan version genuinely was a
                    # progress-driven adaptation this cycle, not a bare
                    # "plan updated" with no traceable reason (rule: every
                    # adaptation needs a structured reason, never vague).
                    already_ran = dispatch_agent in agent_results

                    # Physio is the one specialist whose Phase-A run can be
                    # superseded rather than skipped. Phase A runs before
                    # the Progress Agent, so a Phase-A adaptation was made
                    # without the reassessment/adherence finding that has
                    # just arrived. Re-running it with that finding and
                    # REPLACING the earlier result keeps one physio result,
                    # one plan version and one entry in selected_agents —
                    # it is the same run, decided on complete evidence,
                    # not a second one.
                    if (
                        dispatch_agent == "physio"
                        and already_ran
                        and tool_client is not None
                        and current_exercise_plan is not None
                    ):
                        try:
                            agent_results["physio"] = run_physio_agent(
                                user_state,
                                tool_client,
                                parent_trace=parent_trace,
                                previous_plan=current_exercise_plan,
                                exercise_results=exercise_results,
                                progress_recommendation=recommendation,
                            )
                            validate_agent_result(agent_results["physio"])
                        except Exception as error:  # noqa: BLE001
                            errors.append(
                                "Progress-informed Physio adaptation failed: "
                                f"{error}"
                            )

                    if dispatch_agent == "physio" and not already_ran:
                        if tool_client is None:
                            errors.append(
                                "Progress recommended a Physio adaptation but no "
                                "ExerciseToolClient was provided to run_workflow()"
                            )
                        else:
                            try:
                                # ADAPTATION, not a second first draft.
                                # The agent is given the plan the user
                                # already has and the results they actually
                                # recorded against it, so it can decide
                                # MAINTAIN / PROGRESS / REGRESS / REPLACE /
                                # REMOVE per exercise instead of rebuilding
                                # from the need profile alone. Without these
                                # two arguments a progress-triggered run
                                # produced another ADD-only plan and five of
                                # the six decision types were unreachable.
                                result = run_physio_agent(
                                    user_state,
                                    tool_client,
                                    parent_trace=parent_trace,
                                    previous_plan=current_exercise_plan,
                                    exercise_results=exercise_results,
                                    progress_recommendation=recommendation,
                                )
                                validate_agent_result(result)
                                agent_results["physio"] = result
                                if "physio" not in selected_agents:
                                    selected_agents.append("physio")
                            except Exception as error:  # noqa: BLE001
                                errors.append(
                                    f"Progress-triggered Physio adaptation failed: {error}"
                                )

                    elif dispatch_agent == "behaviour" and not already_ran:
                        if behaviour_tool_client is None:
                            errors.append(
                                "Progress recommended a Behaviour adaptation but no "
                                "BehaviourToolClient was provided to run_workflow()"
                            )
                        else:
                            try:
                                result = run_behaviour_agent(
                                    user_state,
                                    behaviour_tool_client,
                                    parent_trace=parent_trace,
                                    previous_plan=current_behaviour_plan,
                                    exercise_results=exercise_results,
                                    behaviour_actions=behaviour_actions,
                                )
                                validate_agent_result(result)
                                agent_results["behaviour"] = result
                                if "behaviour" not in selected_agents:
                                    selected_agents.append("behaviour")
                            except Exception as error:  # noqa: BLE001
                                errors.append(
                                    f"Progress-triggered Behaviour adaptation failed: {error}"
                                )

                    # Attribute the adaptation reason whenever the
                    # dispatch-target agent ends up with a completed,
                    # plan-bearing result this cycle — whether it was
                    # (re)run just now in Phase B, or it already ran in
                    # Phase A and Progress's own recommendation
                    # independently agrees with that same specialist. A
                    # dispatch target with no plan (its own need-gate
                    # said no, or its run failed) gets no attribution —
                    # there is no plan version to attach a reason to.
                    dispatch_result = agent_results.get(dispatch_agent)
                    dispatch_shape = _AGENT_PLAN_SHAPE.get(dispatch_agent) or {}
                    dispatch_plan = (
                        (dispatch_result.get("findings") or {}).get("plan")
                        if dispatch_result and dispatch_result.get("status") == "completed"
                        else None
                    )

                    if dispatch_plan and dispatch_plan.get(dispatch_shape.get("list_key")):
                        adaptation_info[dispatch_agent] = {
                            "reason": reason,
                            "triggered_by": "progress_agent",
                        }

                # Nutrition adaptation dispatch (Phase 6) — evaluated
                # independently of the physical dispatch above, since a
                # single Progress run can recommend a physical adaptation
                # AND a nutrition adaptation in the same cycle (they are
                # separate axes; see progress_agent/nutrition_progress.py).
                # Only present at all when the caller supplied nutrition
                # context to run_workflow() (Progress's own
                # findings.nutrition_progress is None otherwise).
                nutrition_progress = findings.get("nutrition_progress")

                if nutrition_progress is not None:
                    nutrition_recommendation = nutrition_progress.get("adaptation_recommendation")
                    nutrition_dispatch_agent = _NUTRITION_ADAPTATION_DISPATCH.get(nutrition_recommendation)

                    if nutrition_dispatch_agent:
                        nutrition_reason = (
                            f"Progress Agent recommended {nutrition_recommendation} for "
                            f"nutrition (nutrition_progress_status={nutrition_progress.get('status')}, "
                            f"current_adherence_status={nutrition_progress.get('current_adherence_status')})"
                        )

                        # Same no-double-run rule as the physical dispatch
                        # above: never re-run a specialist that already ran
                        # in Phase A this cycle.
                        nutrition_already_ran = nutrition_dispatch_agent in agent_results

                        if nutrition_dispatch_agent == "nutrition" and not nutrition_already_ran:
                            if nutrition_tool_client is None:
                                errors.append(
                                    "Progress recommended a Nutrition adaptation but no "
                                    "NutritionToolClient was provided to run_workflow()"
                                )
                            else:
                                try:
                                    result = run_nutrition_agent(
                                        user_state,
                                        nutrition_tool_client,
                                        parent_trace=parent_trace,
                                        previous_plan=current_nutrition_plan,
                                        food_log_entries=(
                                            nutrition_food_log_current_period
                                        ),
                                        period_start=(
                                            nutrition_period_current or {}
                                        ).get("start"),
                                        period_end=(
                                            nutrition_period_current or {}
                                        ).get("end"),
                                    )
                                    validate_agent_result(result)
                                    agent_results["nutrition"] = result
                                    if "nutrition" not in selected_agents:
                                        selected_agents.append("nutrition")
                                except Exception as error:  # noqa: BLE001
                                    errors.append(
                                        f"Progress-triggered Nutrition adaptation failed: {error}"
                                    )

                        # Same attribution rule as the physical dispatch:
                        # attribute whenever the dispatch target ends up
                        # with a completed, plan-bearing result this cycle,
                        # whether freshly run just now or already run in
                        # Phase A and independently agreeing.
                        nutrition_dispatch_result = agent_results.get(nutrition_dispatch_agent)
                        nutrition_dispatch_shape = _AGENT_PLAN_SHAPE.get(nutrition_dispatch_agent) or {}
                        nutrition_dispatch_plan = (
                            (nutrition_dispatch_result.get("findings") or {}).get("plan")
                            if nutrition_dispatch_result and nutrition_dispatch_result.get("status") == "completed"
                            else None
                        )

                        if nutrition_dispatch_plan and nutrition_dispatch_plan.get(
                            nutrition_dispatch_shape.get("list_key")
                        ):
                            adaptation_info[nutrition_dispatch_agent] = {
                                "reason": nutrition_reason,
                                "triggered_by": "progress_agent",
                            }

    # The Safety Gate runs whenever at least one selected agent actually
    # produced an Agent Result — even if that result has an empty plan —
    # so a NOT_ASSESSED/ALLOW outcome is itself a real, recorded decision,
    # never silently skipped. It is never bypassed once agents have run.
    safety_result = None
    final_recommendations = []
    removed_ids_by_agent = {}

    if agent_results:
        candidates = _candidate_recommendations(agent_results)

        try:
            safety_result = evaluate_safety(
                need_profile=need_profile,
                confirmed_medical_context=_confirmed_medical_context(user_state),
                candidate_recommendations=candidates,
            )
        except SafetyEvaluationError as error:
            errors.append(f"Safety Gate could not evaluate candidates: {error}")

        if safety_result is not None:
            blocked = set(safety_result["blocked_recommendation_ids"])

            if safety_result["status"] == "REFER":
                # REFER blocks everything, named or not — a referral means
                # nothing from this run reaches the user unreviewed.
                blocked |= {c["id"] for c in candidates}

            for candidate in candidates:
                if candidate["id"] in blocked:
                    removed_ids_by_agent.setdefault(candidate["agent"], set()).add(candidate["id"])
                    continue

                entry = dict(candidate)

                if safety_result["status"] == "MODIFY" and candidate["id"] in set(
                    safety_result["modified_recommendation_ids"]
                ):
                    entry["safety_note_added"] = True

                final_recommendations.append(entry)

    coordination_notes = _coordination_notes(agent_results, need_profile)

    # State updates: only for an agent that (a) actually ran, (b)
    # completed with a plan, and (c) still has at least one approved
    # recommendation after the Safety Gate. A plan reduced to nothing by
    # the Safety Gate is treated exactly like "no plan was produced" —
    # nothing is written, and it is never silently written unchanged.
    state_updates = []
    updated_user_state = user_state

    _APPLY_FUNCS = {
        "physio": ("exercise_history", apply_physio_plan),
        "behaviour": ("behaviour", apply_behaviour_plan),
        "nutrition": ("nutrition_plan", apply_nutrition_plan),
    }

    for agent_id in ("physio", "behaviour", "nutrition"):
        result = agent_results.get(agent_id)

        if result is None or result["status"] != "completed":
            continue

        findings = result.get("findings") or {}
        plan = findings.get("plan")

        if not plan:
            continue

        # An adaptation that decided to change nothing is not a new plan.
        # Writing one would inflate the version history every time the user
        # opened the page, and would attach a version to a decision that
        # was explicitly "leave this alone".
        if findings.get("adapted_from_plan_id") and not findings.get(
            "adaptation_summary"
        ):
            # No new version -- but the review still produced evidence, and
            # discarding it would leave the specialist screen unable to say
            # what it has learned. The current record is refreshed in place;
            # its identity, version and history are untouched.
            section_name = _APPLY_FUNCS[agent_id][0]
            updated_user_state = refresh_plan_evidence(
                updated_user_state, section_name=section_name, agent_result=result
            )
            continue

        removed = removed_ids_by_agent.get(agent_id, set())
        plan_to_apply = _filtered_plan(agent_id, plan, removed) if removed else plan

        shape = _AGENT_PLAN_SHAPE[agent_id]

        if not plan_to_apply.get(shape["list_key"]):
            if removed:
                errors.append(
                    f"{agent_id} plan was entirely removed by the Safety Gate "
                    "(status="
                    f"{safety_result['status'] if safety_result else 'unknown'}"
                    "); nothing was written to the User State for it"
                )
            continue

        section_name, apply_func = _APPLY_FUNCS[agent_id]
        filtered_result = (
            {**result, "findings": {**result["findings"], "plan": plan_to_apply}}
            if removed
            else result
        )

        adaptation = adaptation_info.get(agent_id) or {}

        try:
            updated_user_state = apply_func(
                updated_user_state,
                filtered_result,
                adaptation_reason=adaptation.get("reason"),
                triggered_by=adaptation.get("triggered_by"),
            )
            state_updates.append(section_name)
        except (ValueError, UserStateValidationError) as error:
            errors.append(f"could not apply {agent_id} plan to User State: {error}")

    return _build_result(
        workflow_id=workflow_id,
        request_id=request_id,
        orchestrator_decision=orchestrator_decision,
        selected_agents=selected_agents,
        agent_results=[agent_results[a] for a in selected_agents if a in agent_results],
        safety_result=safety_result,
        final_recommendations=final_recommendations,
        coordination_notes=coordination_notes,
        state_updates=state_updates,
        updated_user_state=updated_user_state,
        errors=errors,
    )
