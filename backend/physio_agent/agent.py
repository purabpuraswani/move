"""The Physio Agent's actual execution lifecycle.

    Physio Agent Run
          |
    Create agent_run_id (from the Orchestrator's TraceContext)
          |
    Build the structured input (input_contract.py, from User State)
          |
    Determine required capabilities (from current_needs — dynamic, not fixed)
          |
    Call Exercise MCP tools (via the injected ExerciseToolClient — never
        exercise_library/exercise_assessment directly)
          |
    Apply the deterministic safety gate (check_exercise_constraints +
        difficulty ceiling — see _apply_safety_gate)
          |
    Build a structured Exercise Plan (plan_schema.py) with a rationale per
        exercise
          |
    Return a Phase 0 Agent Result (orchestration.agent_result)

Every step above is a real function call doing real work on real (if
minimized) data — nothing here is a hard-coded exercise list standing in
for the process. run_physio_agent() takes an ExerciseToolClient as a
required argument specifically so it can never quietly default to
by-passing MCP: a caller must decide, explicitly, which client
implementation (mcp_client.McpExerciseToolClient in production;
tool_client.InProcessExerciseToolClient only in this project's own tests)
this run uses.
"""

from orchestration.agent_result import build_agent_result
from orchestration.ids import TraceContext, start_agent_run
from orchestration.selection_policy import (
    conservative_starter_applies,
    evidence_summary,
    starter_dimensions,
)
from physio_agent.input_contract import (
    PHYSIO_RELEVANT_NEED_DIMENSIONS,
    build_physio_agent_input,
)
from physio_agent.adaptation import (
    DECISION_ADD,
    DECISION_MAINTAIN,
    DECISION_PROGRESS,
    DECISION_REGRESS,
    DECISION_REMOVE,
    DECISION_REPLACE,
    decide_for_exercise,
    summarise,
)
from physio_agent.plan_schema import build_exercise_plan, build_exercise_plan_entry
from physio_agent.tool_client import ExerciseToolClient

AGENT_ID = "physio"

# A system decision, not a clinical one — exactly the discipline
# need_assessment/rules.py and exerciseAssessment/config.js already apply:
# with no fitness-history or medical-clearance data available anywhere in
# the User State, "advanced" exercises are excluded from an initial plan
# by default. This is the Phase 3 safety gate's difficulty ceiling (see
# section 12 of the Phase 3 brief); it is not a claim that "beginner" and
# "intermediate" are safe for any specific person, only that nothing in
# this system has evidence to justify recommending "advanced" instead.
DEFAULT_MAX_DIFFICULTY = "intermediate"
_DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}

# One physical need dimension -> one exercise_library target_capability.
# functional_movement_need maps to two capabilities because
# exercise_library/schema.py's TARGET_CAPABILITIES splits "functional
# movement" exercises across both "functional_movement" and "strength"
# (see backend/exercise_library/data.py — e.g. chair-sit-to-stand is
# tagged with both). Mapping to only one would silently under-search.
NEED_DIMENSION_TO_CAPABILITIES = {
    "mobility_need": ("mobility",),
    "stability_need": ("stability",),
    "functional_movement_need": ("functional_movement", "strength"),
}

# Only a dimension actually assessed at MEDIUM or HIGH contributes a
# capability to search for — NOT_ASSESSED and LOW contribute nothing. This
# mirrors the Orchestrator's own physio_required rule (backend/orchestrator/
# decision.py) applied at the level of "which capability", not just
# "whether to run at all".
TRIGGERING_LEVELS = ("MEDIUM", "HIGH")

MAX_EXERCISES_PER_PLAN = 6

# How many exercises one capability may contribute. Without a per-capability
# limit the first capability searched fills the whole plan, which is how a
# "personalised programme" ends up being one body area repeated.
MAX_EXERCISES_PER_CAPABILITY = 3

# A conservative starter plan is smaller and easier by construction: it is
# offered because capabilities could NOT be measured, so it stays at the
# bottom of the difficulty range and does not fill a full programme.
STARTER_MAX_EXERCISES = 4
STARTER_MAX_DIFFICULTY = "beginner"

# The library entries that ARE one of the three baseline assessment
# movements. These measure the user; they are not the intervention. Chair
# Sit-to-Stand is the FTSST test and Standing Shoulder Raise is the
# hand/shoulder raise test, so prescribing them back is "we measured your
# sit-to-stand, here is sit-to-stand" — the assessment masquerading as a
# programme.
#
# supported-single-leg-stand is deliberately NOT here: the balance TEST is
# an unsupported one-leg stand, and the supported version is a genuinely
# different, easier movement — a legitimate intervention and regression.
#
# They are de-prioritised rather than banned: if a capability has no other
# candidate the user is better served by a suitable exercise they have
# already done once than by an empty section (see _rank_candidates).
BASELINE_ASSESSMENT_MOVEMENTS = (
    "chair-sit-to-stand",
    "standing-shoulder-raise",
)

# What this system can actually observe, read off the library record rather
# than assumed. An exercise MoveNet cannot measure is still prescribable —
# it is simply recorded by the user saying they did it.
MEASUREMENT_MOVENET = "movenet_derived_metrics"
MEASUREMENT_MANUAL = "manual_completion"

SELECTION_MODE_NEED_BASED = "need_based"
SELECTION_MODE_CONSERVATIVE_STARTER = "conservative_starter"


class PhysioAgentError(Exception):
    """Raised for a Physio Agent run that could not produce a result at all
    (as opposed to a run that completed with an empty plan, which is a
    valid, structured outcome — see run_physio_agent())."""


def _required_capabilities(current_needs: dict) -> dict:
    """Map each triggering physical need dimension to the capabilities to
    search for, and the evidence for why. Returns
    {capability: [{"dimension": ..., "level": ..., "evidence": [...]}]}.
    """

    triggers = {}

    for dimension in PHYSIO_RELEVANT_NEED_DIMENSIONS:
        entry = current_needs.get(dimension) if current_needs else None

        if not entry or entry.get("level") not in TRIGGERING_LEVELS:
            continue

        for capability in NEED_DIMENSION_TO_CAPABILITIES[dimension]:
            triggers.setdefault(capability, []).append(
                {
                    "dimension": dimension,
                    "level": entry["level"],
                    "evidence": entry.get("evidence", []),
                }
            )

    return triggers


def _starter_capabilities(current_needs: dict) -> dict:
    """The capabilities a conservative starter plan covers: those belonging
    to the need dimensions that could NOT be assessed.

    Shaped exactly like `_required_capabilities` so the rest of the run is
    identical whichever mode produced the capability set — but the trigger
    entries record level NOT_ASSESSED, and carry Need Assessment's own
    explanation of why it could not be evaluated. Nothing here upgrades a
    level or invents a deficit: the entries say, in the data itself, that
    this capability is unknown.
    """

    triggers = {}

    for dimension in starter_dimensions(current_needs):
        entry = current_needs.get(dimension) if current_needs else None

        for capability in NEED_DIMENSION_TO_CAPABILITIES[dimension]:
            triggers.setdefault(capability, []).append(
                {
                    "dimension": dimension,
                    "level": "NOT_ASSESSED",
                    "evidence": (entry or {}).get("evidence", []),
                }
            )

    return triggers


def _within_difficulty_ceiling(exercise: dict, max_difficulty=None) -> bool:
    ceiling = max_difficulty or DEFAULT_MAX_DIFFICULTY

    return _DIFFICULTY_ORDER.get(exercise["difficulty"], 99) <= _DIFFICULTY_ORDER[
        ceiling
    ]


def _measurement_method(exercise: dict) -> str:
    """How this system can actually observe this exercise — read from the
    library's own movenet_support, never assumed."""

    support = exercise.get("movenet_support") or {}

    return MEASUREMENT_MOVENET if support.get("implemented") else MEASUREMENT_MANUAL


DIMENSION_PRIMARY_BODY_AREAS = {
    "mobility_need": {"shoulders", "arms"},
    "functional_movement_need": {"legs", "hips"},
    "stability_need": {"legs", "hips", "core", "ankles"},
}


def _rank_candidates(exercises: list, target_dimension: str = None) -> list:
    """Intervention exercises first, baseline assessment movements last.

    A stable sort on one key, so within each group the library's own order
    is preserved and the selection stays reproducible.
    When target_dimension is provided, non-assessment exercises that directly
    target that dimension's primary body areas are ranked ahead of other
    interventions, ensuring relevant exercises (e.g. upper-body reach for
    mobility need, seated marching/knee extensions for functional movement need)
    are prioritized before falling back to other areas.
    """

    primary_areas = DIMENSION_PRIMARY_BODY_AREAS.get(target_dimension) or set()

    def sort_key(exercise):
        is_baseline = exercise["exercise_id"] in BASELINE_ASSESSMENT_MOVEMENTS
        areas = set(exercise.get("target_body_area") or [])
        matches_area = bool(areas & primary_areas) if primary_areas else True
        if is_baseline:
            return 2
        if matches_area:
            return 0
        return 1

    return sorted(exercises, key=sort_key)


def _rationale_for(
    exercise: dict, capability: str, triggers_by_capability: dict, mode: str
) -> str:
    triggers = triggers_by_capability.get(capability, [])
    dimension_labels = {
        "mobility_need": "upper-body mobility",
        "stability_need": "standing balance",
        "functional_movement_need": "sit-to-stand strength",
    }

    if mode == SELECTION_MODE_CONSERVATIVE_STARTER:
        unmeasured = ", ".join(
            dimension_labels[t["dimension"]] for t in triggers
        ) or "this capability"

        return (
            f"Your assessment could not measure {unmeasured}, so this is "
            f"offered as a gentle starting point rather than as a finding "
            f"about your movement. {exercise['name']} supports "
            f"{capability.replace('_', ' ')} training at the "
            f"{exercise['difficulty']} level."
        )

    reasons = "; ".join(
f"{dimension_labels[t['dimension']]} is {t['level']}" for t in triggers
    )

    return (
        f"Selected because {reasons or 'the current needs assessment flags this capability'}, "
        f"and {exercise['name']} supports {capability.replace('_', ' ')} training "
        f"at the {exercise['difficulty']} level."
    )


def _apply_safety_gate(
    exercise: dict, tool_client: ExerciseToolClient
) -> tuple:
    """The Phase 3 safety gate. Returns (allowed: bool, safety_notes: list,
    rejection_reason: str|None).

    Deliberately limited to what is actually knowable here: the exercise's
    own declared difficulty (checked against DEFAULT_MAX_DIFFICULTY) and
    its own declared safety_constraints/common_mistakes, surfaced verbatim
    via the real check_exercise_constraints MCP capability — never a
    personalised medical judgment this system has no evidence to make. If
    a genuinely comprehensive safety system existed, it would sit exactly
    here; documented in docs/architecture.md as a known limitation, not
    silently assumed to be more than it is.
    """

    if not _within_difficulty_ceiling(exercise):
        return False, [], (
            f"{exercise['name']} is difficulty '{exercise['difficulty']}', "
            f"above this system's default ceiling of '{DEFAULT_MAX_DIFFICULTY}' "
            "(no fitness-history or clearance data exists to justify recommending it)"
        )

    constraints = tool_client.check_exercise_constraints(exercise["exercise_id"])

    if "error" in constraints:
        return False, [], f"could not verify safety constraints: {constraints['error']}"

    safety_notes = list(constraints.get("safetyConstraints", []))

    return True, safety_notes, None


def _mcp_session_id_of(tool_result) -> str:
    """The real MCP session id a tool result was produced under, or None.

    The value originates in the Streamable HTTP transport's own handshake
    and is carried into every tool result's metadata by the MCP client
    (see physio_agent/mcp_client.py's _attach_session_id). Reading it back
    out here is how an Agent Result reports the session its tool calls
    actually ran on.

    It is never synthesised. workflow_id, request_id, agent_run_id and
    tool_call_id are four different identifiers with four different
    meanings, and none of them is a substitute -- if no tool call carried a
    session id, this returns None and the Agent Result says so honestly.
    """

    if not isinstance(tool_result, dict):
        return None

    metadata = tool_result.get("metadata")

    if not isinstance(metadata, dict):
        return None

    return metadata.get("mcp_session_id")

def _capabilities_of(exercise: dict) -> tuple:
    return tuple(exercise.get("target_capability") or ())


def _previous_decisions(previous_plan: dict) -> list:
    """The previous plan's exercises, as `(exercise_id, target_need)` pairs.

    Reads the richer `decisions` list a plan record carries since the
    Physio Agent started making structured decisions, and falls back to the
    bare `exercise_ids` for a plan recorded before that — an older plan is
    still adaptable, it simply has no recorded target_need to carry
    forward, and None is the honest value for that rather than a guess.
    """

    decisions = previous_plan.get("decisions")

    if isinstance(decisions, list) and decisions:
        return [
            (entry.get("exercise_id"), entry.get("target_need"))
            for entry in decisions
            if isinstance(entry, dict)
            and entry.get("exercise_id")
            and entry.get("decision_type") != DECISION_REMOVE
        ]

    return [
        (exercise_id, None) for exercise_id in (previous_plan.get("exercise_ids") or [])
    ]


def _library_record(exercise_id, candidates_by_capability, tool_client):
    """The library record for one exercise: from what this run already
    searched where possible, otherwise by a real tool call.

    An exercise that is in the plan but no longer in the library returns
    None, and the caller keeps it rather than silently dropping it.
    """

    for exercises in candidates_by_capability.values():
        for exercise in exercises:
            if exercise["exercise_id"] == exercise_id:
                return exercise

    try:
        result = tool_client.get_exercise_details(exercise_id)

    except Exception:  # noqa: BLE001
        return None

    if not isinstance(result, dict) or "error" in result:
        return None

    return result.get("exercise")


def _adapt_existing_plan(
    *,
    previous_plan,
    exercise_results,
    triggers_by_capability,
    candidates_by_capability,
    tool_client,
    max_exercises,
    progress_recommendation=None,
):
    """Decide what happens to each exercise the user already has.

    Returns `(plan_entries, decisions, taken_per_capability, chosen_ids)`.
    `decisions` includes REMOVEs, which by definition have no plan entry —
    the plan says what to do now, the decision list says what was decided,
    and the two are not the same thing.
    """

    targeted_capabilities = set(triggers_by_capability)

    plan_entries = []
    decisions = []
    taken_per_capability = {}
    chosen_ids = set()

    for exercise_id, target_need in _previous_decisions(previous_plan):
        exercise = _library_record(
            exercise_id, candidates_by_capability, tool_client
        )

        capabilities = set(_capabilities_of(exercise)) if exercise else set()
        capability = next(
            (name for name in sorted(capabilities & targeted_capabilities)), None
        )

        decision = decide_for_exercise(
            exercise_id=exercise_id,
            target_need=target_need,
            has_progression=bool(exercise and exercise.get("progression")),
            has_regression=bool(exercise and exercise.get("regression")),
            exercise_results=exercise_results,
            # An exercise whose record has gone from the library cannot be
            # shown to be off-target, so it is not removed for that reason.
            still_targeted=bool(capability) or exercise is None,
            programme_direction=progress_recommendation,
        )

        decisions.append(decision)

        if decision["decision_type"] == DECISION_REMOVE or exercise is None:
            continue

        if decision["decision_type"] == DECISION_REPLACE:
            replacement = _pick_replacement(
                capability, candidates_by_capability, chosen_ids, exercise_id
            )

            if replacement is None:
                # Nothing else in the library covers this capability, so
                # the honest outcome is to keep what they have rather than
                # leave the capability uncovered. The decision is rewritten
                # to what actually happened.
                decision["decision_type"] = DECISION_MAINTAIN
                decision["reason"] = (
                    "You have been finding this difficult, but there is no "
                    "other exercise in the library for this capability, so "
                    "it stays for now."
                )

            else:
                decision["replaced_by"] = replacement["exercise_id"]
                exercise = replacement

        allowed, safety_notes, rejection_reason = _apply_safety_gate(
            exercise, tool_client
        )

        if not allowed:
            # A safety rejection overrides every other decision, and is
            # recorded as the removal it actually is.
            decision["decision_type"] = DECISION_REMOVE
            decision["reason"] = (
                "This has been taken out of your programme for safety: "
                f"{rejection_reason}"
            )
            continue

        if len(plan_entries) >= max_exercises:
            break

        plan_entries.append(
            build_exercise_plan_entry(
                exercise_id=exercise["exercise_id"],
                sets=exercise["sets"],
                repetitions=exercise["repetitions"],
                duration_seconds=exercise["duration_seconds"],
                difficulty=exercise["difficulty"],
                progression=exercise["progression"],
                regression=exercise["regression"],
                rationale=_adaptation_rationale(exercise, decision),
                safety_notes=safety_notes,
                target_need=target_need or None,
                decision_type=decision["decision_type"],
                measurement_method=_measurement_method(exercise),
            )
        )

        chosen_ids.add(exercise["exercise_id"])

        if capability:
            taken_per_capability[capability] = (
                taken_per_capability.get(capability, 0) + 1
            )

    return plan_entries, decisions, taken_per_capability, chosen_ids


def _pick_replacement(capability, candidates_by_capability, chosen_ids, replaced_id):
    """A different library exercise for the same capability, or None."""

    if not capability:
        return None

    for exercise in _rank_candidates(candidates_by_capability.get(capability) or []):
        if exercise["exercise_id"] in chosen_ids:
            continue

        if exercise["exercise_id"] == replaced_id:
            continue

        if exercise["exercise_id"] in BASELINE_ASSESSMENT_MOVEMENTS:
            continue

        return exercise

    return None


def _adaptation_rationale(exercise: dict, decision: dict) -> str:
    """The user-facing reason for an adapted entry: the decision's own
    reason, plus the library's own instruction for how the change is made.

    Nothing is written here that is not either the decision's recorded
    reason or the library's own progression/regression text.
    """

    reason = decision["reason"]

    if decision["decision_type"] == DECISION_PROGRESS and exercise.get("progression"):
        return f"{reason} How: {exercise['progression']}"

    if decision["decision_type"] == DECISION_REGRESS and exercise.get("regression"):
        return f"{reason} How: {exercise['regression']}"

    if decision["decision_type"] == DECISION_REPLACE:
        return (
            f"{reason} {exercise['name']} works the same capability at the "
            f"{exercise['difficulty']} level."
        )

    return reason


def run_physio_agent(
    user_state: dict,
    tool_client: ExerciseToolClient,
    *,
    parent_trace: TraceContext,
    previous_plan: dict = None,
    exercise_results: list = None,
    progress_recommendation: str = None,
) -> dict:
    """Run one Physio Agent execution. Returns a validated Agent Result.

    `parent_trace` must already have a workflow_id/request_id (from the
    Orchestrator); this function derives its own agent_run_id from it via
    start_agent_run() — the same observability infrastructure every other
    part of this system uses, not a parallel one.

    `previous_plan` (a plan-version record from
    orchestrator/state_update.py) and `exercise_results` (this user's
    recorded performance) put the agent in ADAPTATION mode: instead of
    building a first plan, it decides what happens to each exercise the
    user already has — MAINTAIN, PROGRESS, REGRESS, REPLACE or REMOVE —
    from what they actually recorded, and ADDs cover for any capability
    left uncovered. Omit both and it builds a first plan exactly as before.

    `progress_recommendation` is the Progress Agent's own physical-axis
    recommendation for this cycle, which is derived from the reassessment
    comparison and adherence rather than from any single exercise. It only
    ever decides an exercise whose own results are not enough to decide it.

    Adaptation never runs on absence: an exercise with no recorded results
    and no programme-level finding is MAINTAINed and says so, and a session
    the camera could not measure is never read as the user struggling (see
    physio_agent/adaptation.py).
    """

    trace = start_agent_run(parent_trace)

    payload = build_physio_agent_input(
        user_state,
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
    )

    current_needs = payload["current_needs"]

    if current_needs is None:
        return build_agent_result(
            agent=AGENT_ID,
            status="failed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={"reason": "current_needs is unavailable; Physio Agent cannot run without it"},
            requires_reassessment=True,
        )

    # ------------------------------------------------------------------
    # Selection mode. Evidence-based selection first; the conservative
    # starter pathway only where the deterministic rule in
    # orchestration/selection_policy.py says it applies. The two are never
    # mixed: a plan is built either from measured needs or from measurement
    # gaps, and its entries say which.
    # ------------------------------------------------------------------
    triggers_by_capability = _required_capabilities(current_needs)
    selection_mode = SELECTION_MODE_NEED_BASED
    max_difficulty = DEFAULT_MAX_DIFFICULTY
    max_exercises = MAX_EXERCISES_PER_PLAN

    if not triggers_by_capability and conservative_starter_applies(current_needs):
        triggers_by_capability = _starter_capabilities(current_needs)
        selection_mode = SELECTION_MODE_CONSERVATIVE_STARTER
        max_difficulty = STARTER_MAX_DIFFICULTY
        max_exercises = STARTER_MAX_EXERCISES

    if not triggers_by_capability:
        # Reachable in a direct unit test of the agent; the Orchestrator's
        # own selection rule (backend/orchestrator/decision.py) is what
        # normally prevents this agent from running at all in this case.
        return build_agent_result(
            agent=AGENT_ID,
            status="completed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={"reason": "no physical need dimension is at MEDIUM or HIGH"},
            recommendations=[],
        )

    candidates_by_capability = {}
    tool_call_failed = None

    # The real MCP session the searches below run on. Captured from the
    # first tool result that reports one, and carried into this agent's
    # own result metadata at the end -- otherwise the session id stops at
    # the tool result and the Agent Result claims no MCP session happened.
    mcp_session_id = None

    for capability in triggers_by_capability:
        try:
            search_result = tool_client.search_exercises(
                target_capability=capability
            )

        except Exception as error:  # noqa: BLE001
            tool_call_failed = str(error)
            break

        mcp_session_id = mcp_session_id or _mcp_session_id_of(search_result)

        if "error" in search_result:
            tool_call_failed = search_result["error"]
            break

        candidates_by_capability[capability] = search_result["exercises"]

    if tool_call_failed is not None:
        return build_agent_result(
            agent=AGENT_ID,
            status="failed",
            workflow_id=trace.workflow_id,
            request_id=trace.request_id,
            agent_run_id=trace.agent_run_id,
            findings={"reason": f"Exercise MCP search failed: {tool_call_failed}"},
            safety_flags=["mcp_unavailable_or_tool_error"],
            requires_reassessment=True,
            mcp_session_id=mcp_session_id,
        )

    # ------------------------------------------------------------------
    # Selection. Capability by capability, so the programme covers what the
    # evidence points at rather than being filled by whichever search ran
    # first; intervention exercises ahead of baseline assessment movements
    # (_rank_candidates), and a per-capability cap so one capability cannot
    # take the whole plan. Every candidate still passes the same
    # deterministic safety gate, and nothing is added twice.
    # ------------------------------------------------------------------
    rejected = []
    adaptation_decisions = []
    taken_per_capability = {}

    if previous_plan is not None:
        # ADAPTATION. What the user already has, judged against what they
        # actually recorded, before anything new is considered.
        (
            plan_entries,
            adaptation_decisions,
            taken_per_capability,
            chosen_ids,
        ) = _adapt_existing_plan(
            previous_plan=previous_plan,
            exercise_results=exercise_results,
            triggers_by_capability=triggers_by_capability,
            candidates_by_capability=candidates_by_capability,
            tool_client=tool_client,
            max_exercises=max_exercises,
            progress_recommendation=progress_recommendation,
        )

    else:
        plan_entries = []
        chosen_ids = set()

    for capability, exercises in candidates_by_capability.items():
        taken_for_capability = taken_per_capability.get(capability, 0)
        target_dimension = (triggers_by_capability.get(capability) or [{}])[0].get(
            "dimension"
        )

        for exercise in _rank_candidates(exercises, target_dimension=target_dimension):
            if len(plan_entries) >= max_exercises:
                break

            if taken_for_capability >= MAX_EXERCISES_PER_CAPABILITY:
                break

            if exercise["exercise_id"] in chosen_ids:
                continue

            if (
                exercise["exercise_id"] in BASELINE_ASSESSMENT_MOVEMENTS
                and taken_for_capability > 0
            ):
                # A baseline assessment movement is a fallback, not a
                # programme entry: it is used only when this capability
                # would otherwise contribute nothing at all. Because
                # _rank_candidates puts them last, anything already taken
                # here is a real intervention exercise.
                continue

            if not _within_difficulty_ceiling(exercise, max_difficulty):
                # Not a safety rejection — this exercise was simply outside
                # the difficulty band this run is allowed to draw from, so
                # it is not reported as one.
                continue

            allowed, safety_notes, rejection_reason = _apply_safety_gate(
                exercise, tool_client
            )

            if not allowed:
                rejected.append(
                    {"exercise_id": exercise["exercise_id"], "reason": rejection_reason}
                )
                continue

            plan_entries.append(
                build_exercise_plan_entry(
                    exercise_id=exercise["exercise_id"],
                    sets=exercise["sets"],
                    repetitions=exercise["repetitions"],
                    duration_seconds=exercise["duration_seconds"],
                    difficulty=exercise["difficulty"],
                    progression=exercise["progression"],
                    regression=exercise["regression"],
                    rationale=_rationale_for(
                        exercise, capability, triggers_by_capability, selection_mode
                    ),
                    safety_notes=safety_notes,
                    target_need=target_dimension,
                    # Every entry in a newly built plan is an addition. The
                    # other decision types belong to adaptation, which runs
                    # against an existing plan — claiming PROGRESS here
                    # would be claiming a comparison that never happened.
                    decision_type="ADD",
                    measurement_method=_measurement_method(exercise),
                )
            )

            chosen_ids.add(exercise["exercise_id"])
            taken_for_capability += 1

            if previous_plan is not None:
                # Everything the capability loop contributes to an
                # adaptation cycle is, by definition, an addition: it is an
                # exercise the user did not have before.
                adaptation_decisions.append(
                    {
                        "exercise_id": exercise["exercise_id"],
                        "decision_type": DECISION_ADD,
                        "reason": (
                            "Added to cover a capability your programme was "
                            "not working on."
                        ),
                        "evidence": {"results_recorded": 0},
                        "target_need": target_dimension,
                    }
                )

    if previous_plan is not None:
        goal = (
            "Your movement programme, updated from what you actually "
            "recorded."
        )
    elif selection_mode == SELECTION_MODE_CONSERVATIVE_STARTER:
        goal = (
            "A gentle starting programme for the movement capabilities your "
            "assessment could not measure."
        )
    else:
        goal = (
            "Support the movement capabilities flagged by the current needs "
            "assessment."
        )

    plan = build_exercise_plan(goal=goal, exercises=plan_entries)

    need_levels = {
        dimension: current_needs[dimension]["level"]
        for dimension in PHYSIO_RELEVANT_NEED_DIMENSIONS
        if current_needs.get(dimension)
    }

    # `findings` is deliberately untyped beyond "object" (see
    # orchestration/agent_result.py's build_agent_result docstring) — this
    # is the Physio Agent's own findings shape: the need levels it acted
    # on, the plan it built, and any candidates the safety gate rejected
    # (so a caller can see *why* a plan is smaller than expected, not just
    # that it is). Nothing here is passed as `extra_metadata`: that
    # parameter can only ever add keys to the fixed observability metadata
    # object, which orchestration/agent_result.py's own validator refuses
    # if it doesn't recognise them — this is domain content, not metadata.
    summary = evidence_summary(current_needs)

    findings = {
        "need_levels": need_levels,
        # Which pathway built this plan, and what the evidence looked like
        # when it did. This is what lets a caller (and the Movement screen)
        # explain the programme without re-deriving the reasoning — and what
        # keeps "we measured this and found nothing" distinguishable from
        # "we could not measure this" all the way to the user.
        "selection_mode": selection_mode,
        "capabilities_targeted": sorted(triggers_by_capability),
        "unassessed_dimensions": list(summary["unassessed"]),
        # Every decision this cycle, including the REMOVEs that by
        # definition have no plan entry. This is what the plan-version
        # record persists and what the Movement screen explains from — the
        # UI never re-derives a reason of its own.
        "decisions": adaptation_decisions
        or [
            {
                "exercise_id": entry["exercise_id"],
                "decision_type": entry["decision_type"],
                "reason": entry["rationale"],
                "evidence": {"results_recorded": 0},
                "target_need": entry.get("target_need"),
            }
            for entry in plan_entries
        ],
        "adaptation_summary": (
            summarise(adaptation_decisions) if previous_plan is not None else None
        ),
        "adapted_from_plan_id": (
            previous_plan.get("plan_id") if previous_plan is not None else None
        ),
        "plan": plan,
        "rejected_candidates": rejected,
    }

    safety_flags = ["no_suitable_exercise_found"] if not plan_entries and rejected else []
    requires_reassessment = not plan_entries

    return build_agent_result(
        agent=AGENT_ID,
        status="completed",
        workflow_id=trace.workflow_id,
        request_id=trace.request_id,
        agent_run_id=trace.agent_run_id,
        priority="high" if "HIGH" in need_levels.values() else ("medium" if "MEDIUM" in need_levels.values() else None),
        findings=findings,
        recommendations=[
            {"exercise_id": entry["exercise_id"], "reason": entry["rationale"]}
            for entry in plan_entries
        ],
        requires_reassessment=requires_reassessment,
        safety_flags=safety_flags,
        mcp_session_id=mcp_session_id,
    )
