"""Turning a run_workflow() result (or a persisted User State) into the
clean, user-facing JSON shape the API actually returns.

Nothing in this module ever emits an internal orchestration identifier
(workflow_id, request_id, agent_run_id, tool_call_id, mcp_session_id), a raw
agent `findings` block, or a Mongo `_id` — only a plain-language summary of
what a caller-facing person needs: which plans exist, what is in them by
name, a plain-language safety status, and — since the plan-generation fix
— an explicit plan state saying which of three distinct situations the
caller is actually in. Both public functions here are pure — no
pymongo/bson import, no I/O beyond the (also pure, static-data)
exercise/nutrition/behaviour library lookups — so they are directly
unit-testable without a database connection.
"""

from datetime import datetime, timezone
from urllib.parse import quote

from behaviour_agent.adherence import (
    compute_behaviour_adherence,
)
from behaviour_library.catalog import (
    BehaviourTopicNotFoundError,
    get_behaviour_topic_details,
)
from exercise_library.catalog import ExerciseNotFoundError, get_exercise_details
from nutrition_library.catalog import (
    NutritionTopicNotFoundError,
    get_nutrition_topic_details,
)
from activity_agent.evidence import build_activity_view
from activity_agent.reasoning import assess_activity
from nutrition_agent.evidence import build_nutrition_evidence_view
from orchestration.evidence import STATUS_INSUFFICIENT_EVIDENCE
from orchestration.specialists import (
    ACTION_COMPLETE_HABIT,
    ACTION_LOG_NUTRITION,
    ACTION_START_EXERCISE,
    ACTION_VIEW_GUIDANCE,
    BEHAVIOUR_ADHERENCE,
    EXERCISE_MOVEMENT,
    NUTRITION_LIFESTYLE,
    RECOVERY_CARE,
    SAFETY_PRACTITIONER,
    SECTION_ACTIVITY_VOLUME,
    SECTION_EXERCISE_PROGRAMME,
    SECTION_HABIT_GOALS,
    SECTION_NUTRITION_GOALS,
    SECTION_RECOVERY_GUIDANCE,
    SECTION_SAFETY_GUIDANCE,
    SPECIALIST_ORDER,
    SPECIALISTS,
    definition,
    route_for,
)
from orchestrator.decision import (
    decide_behaviour_required,
    decide_exercise_activity_required,
    decide_nutrition_required,
    decide_physio_required,
    decide_recovery_required,
)
from physio_agent.agent import _movement_evidence
from recovery_agent.evidence import build_recovery_view
from recovery_agent.reasoning import assess_recovery
from safety.gate import _missing_safety_information
from safety.rules import reported_health_concerns
from safety.schema import STATUS_TO_LEVEL
from workflow.score import build_movewell_score, with_previous

# safety/schema.py's SAFETY_STATUSES, translated into a plain-language
# sentence a non-technical user can act on. These are the only five values
# evaluate_safety() ever produces (safety/gate.py) — this mapping never
# invents a new safety semantic of its own, it only rephrases the real one.
SAFETY_STATUS_MESSAGES = {
    "ALLOW": "Reviewed and approved.",
    "MODIFY": "Some recommendations need review before you follow them.",
    "PAUSE": "Some recommendations were paused for safety reasons.",
    "REFER": "Please consult a healthcare professional before proceeding.",
    "NOT_ASSESSED": "Not yet assessed.",
}

DEFAULT_SAFETY_MESSAGE = "Not yet assessed."


# ---------------------------------------------------------------------------
# The plan state model
# ---------------------------------------------------------------------------
#
# Three states, deliberately distinct, because collapsing them is what made
# a completed assessment indistinguishable from an untouched account:
#
#   NEVER_RUN                  The user has not yet completed the work a
#                              plan could be built from — no persisted
#                              workflow at all, or no assessment session
#                              that produced a single usable measurement.
#                              This is the ONLY state in which it is true
#                              to say "complete your assessment first".
#
#   PLAN_AVAILABLE             A workflow ran and at least one of the three
#                              plan sections holds a plan.
#
#   NO_PLAN_SAFE_OR_SUPPORTED  A workflow ran against real evidence and
#                              produced no plan. Always accompanied by what
#                              was missing (in Need Assessment's own words),
#                              why no plan followed, and what to do next.
#
# Every one of these is derived from the User State alone, so the same
# function serves a fresh run and a reload of a persisted state.
# ---------------------------------------------------------------------------

PLAN_STATES = ("NEVER_RUN", "PLAN_AVAILABLE", "NO_PLAN_SAFE_OR_SUPPORTED")

# Plain-language names for the need dimensions. Display only; the dimension
# keys themselves never reach the user.
_DIMENSION_LABELS = {
    "mobility_need": "Upper-body mobility",
    "stability_need": "Standing balance",
    "functional_movement_need": "Sit-to-stand strength",
    "behaviour_need": "Daily activity habits",
    "nutrition_need": "Eating patterns",
}

# Which step each dimension's evidence comes from, so "what you can do
# next" names a real screen rather than giving a vague instruction.
_PHYSICAL_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
)

_QUESTIONNAIRE_DIMENSIONS = ("behaviour_need", "nutrition_need")

NEXT_ACTION_ASSESSMENT = {
    "label": "Redo the movement assessment",
    "route": "/assessment",
}

NEXT_ACTION_ONBOARDING = {
    "label": "Answer the lifestyle questions",
    "route": "/onboarding",
}

NEXT_ACTION_NONE = {
    "label": "Check again after your next assessment",
    "route": "/assessment",
}

NEVER_RUN_REASON = (
    "No movement assessment has produced a usable measurement yet, so "
    "there is nothing to build a plan from."
)


def safety_status_message(safety_status) -> str:
    """Plain-language translation of a Safety Result's `status`.

    `safety_status` is `None` (no Safety Gate ran this cycle — e.g. no
    specialist agent was required) or one of safety/schema.py's
    SAFETY_STATUSES. Anything else (defensive: malformed/unrecognised)
    falls back to the same "not yet assessed" message rather than guessing
    or raising, since this function's only job is display text.
    """

    if safety_status is None:
        return DEFAULT_SAFETY_MESSAGE

    return SAFETY_STATUS_MESSAGES.get(safety_status, DEFAULT_SAFETY_MESSAGE)


def _exercise_name(exercise_id: str) -> str:
    try:
        return get_exercise_details(exercise_id)["name"]
    except ExerciseNotFoundError:
        # The plan recorded an id from a library snapshot that no longer
        # has it. Fall back to the id itself rather than hiding the entry
        # or raising — it is not a Mongo _id, so surfacing it is not an
        # internal-id leak.
        return exercise_id


def _nutrition_topic_name(topic_id: str) -> str:
    try:
        return get_nutrition_topic_details(topic_id)["name"]
    except NutritionTopicNotFoundError:
        return topic_id


def _behaviour_topic_name(topic_id: str) -> str:
    try:
        return get_behaviour_topic_details(topic_id)["name"]
    except BehaviourTopicNotFoundError:
        return topic_id


def _latest_plan_record(section: dict) -> dict:
    """The newest plan-version record from a User State plan section
    (`exercise_history` / `nutrition_plan` / `behaviour`), or None if the
    section is unavailable or has never had a plan created."""

    if not isinstance(section, dict) or not section.get("available"):
        return None

    plans = (section.get("data") or {}).get("plans") or []

    return plans[-1] if plans else None


def _exercise_plan_summary(user_state: dict) -> dict:
    record = _latest_plan_record(user_state.get("exercise_history") or {})

    if record is None:
        return {
            "available": False,
            "message": "No exercise plan has been created yet.",
        }

    exercise_ids = record.get("exercise_ids") or []

    return {
        "available": True,
        "goal": record.get("goal"),
        "exercise_count": len(exercise_ids),
        "exercises": [_exercise_name(exercise_id) for exercise_id in exercise_ids],
        # The same exercises paired with their library id, so the plan screen
        # can link each one to the page that performs it. Without this the UI
        # has only display names and cannot address an exercise at all.
        #
        # An exercise_id is a stable, public identifier from the static
        # exercise library (backend/exercise_library/data.py) -- not a Mongo
        # _id and not an internal orchestration id, so exposing it does not
        # breach this module's no-internal-identifiers rule. _exercise_name()
        # already falls back to the id for display when the library no longer
        # has the entry, for the same reason.
        "exercise_items": [
            {"id": exercise_id, "name": _exercise_name(exercise_id)}
            for exercise_id in exercise_ids
        ],
        "created_at": record.get("created_at"),
        # Which version of this user's exercise plan this is. Surfaced so a
        # caller (and this project's own tests) can see that plan history
        # survives a rebuild rather than restarting at 1 on every run.
        "plan_version": record.get("plan_version"),
        "adaptation_reason": record.get("adaptation_reason"),
    }


def _nutrition_plan_summary(user_state: dict) -> dict:
    record = _latest_plan_record(user_state.get("nutrition_plan") or {})

    if record is None:
        return {
            "available": False,
            "message": "No nutrition plan has been created yet.",
        }

    topic_ids = record.get("topic_ids") or []

    return {
        "available": True,
        "goal": record.get("goal"),
        "goal_count": len(topic_ids),
        "goals": [_nutrition_topic_name(topic_id) for topic_id in topic_ids],
        "created_at": record.get("created_at"),
        "plan_version": record.get("plan_version"),
        "adaptation_reason": record.get("adaptation_reason"),
    }


def _behaviour_plan_summary(user_state: dict) -> dict:
    record = _latest_plan_record(user_state.get("behaviour") or {})

    if record is None:
        return {
            "available": False,
            "message": "No behaviour/habit goals have been set yet.",
        }

    topic_ids = record.get("topic_ids") or []

    return {
        "available": True,
        "goal": record.get("goal"),
        "goal_count": len(topic_ids),
        "goals": [_behaviour_topic_name(topic_id) for topic_id in topic_ids],
        "created_at": record.get("created_at"),
        "plan_version": record.get("plan_version"),
        "adaptation_reason": record.get("adaptation_reason"),
    }


def _need_profile(user_state: dict):
    section = user_state.get("current_needs") or {}

    return section.get("data") if section.get("available") else None


def _assessment_produced_a_measurement(user_state: dict) -> bool:
    """True when a physical assessment session produced at least one usable
    measurement.

    `user_state/schema.py::_build_physical_assessment` marks the section
    unavailable both when no session exists and when a session exists in
    which no test completed, so `available` is exactly the question "is
    there a usable measurement to reason from" — which is the line between
    NEVER_RUN and NO_PLAN_SAFE_OR_SUPPORTED.
    """

    return bool((user_state.get("physical_assessment") or {}).get("available"))


def _unassessed_dimension_keys(user_state: dict) -> tuple:
    profile = _need_profile(user_state)

    if not profile:
        return ()

    return tuple(
        dimension
        for dimension in _PHYSICAL_DIMENSIONS + _QUESTIONNAIRE_DIMENSIONS
        if isinstance(profile.get(dimension), dict)
        and profile[dimension].get("level") == "NOT_ASSESSED"
    )


def _unassessed_dimensions(user_state: dict) -> list:
    """The dimensions Need Assessment could not evaluate, each with the
    reason Need Assessment itself gave — never a reason this module wrote.

    Returns `[{"capability": <plain name>, "reason": <str|None>}, ...]`.
    """

    profile = _need_profile(user_state)

    if not profile:
        return []

    missing = []

    for dimension in _unassessed_dimension_keys(user_state):
        evidence = (profile.get(dimension) or {}).get("evidence") or []

        missing.append(
            {
                "capability": _DIMENSION_LABELS.get(dimension, dimension),
                "reason": evidence[0] if evidence else None,
            }
        )

    return missing


def plan_state(user_state: dict, *, plans_available: bool) -> dict:
    """Which of the three plan states this User State is in, and — when
    there is no plan — what is missing, why, and what to do next.

    `plans_available` is passed in rather than recomputed so this function
    and the three plan summaries can never disagree about whether a plan
    exists.
    """

    if plans_available:
        return {
            "state": "PLAN_AVAILABLE",
            "reason": "Your plan is ready.",
            "missing": [],
            "next_action": None,
        }

    if not _assessment_produced_a_measurement(user_state):
        return {
            "state": "NEVER_RUN",
            "reason": NEVER_RUN_REASON,
            "missing": [],
            "next_action": NEXT_ACTION_ASSESSMENT,
        }

    missing = _unassessed_dimensions(user_state)
    missing_keys = set(_unassessed_dimension_keys(user_state))

    if missing_keys & set(_PHYSICAL_DIMENSIONS):
        next_action = NEXT_ACTION_ASSESSMENT
    elif missing_keys & set(_QUESTIONNAIRE_DIMENSIONS):
        next_action = NEXT_ACTION_ONBOARDING
    else:
        next_action = NEXT_ACTION_NONE

    if missing:
        reason = (
            "Your assessment was completed, but some of it could not be "
            "measured, and what was measured did not show a need this "
            "system would build a plan around. Nothing here is a finding "
            "about your health — it is a gap in what could be recorded."
        )
    else:
        reason = (
            "Your assessment was completed and everything it measures came "
            "back without a need this system would build a plan around. "
            "That is a result, not a failure."
        )

    return {
        "state": "NO_PLAN_SAFE_OR_SUPPORTED",
        "reason": reason,
        "missing": missing,
        "next_action": next_action,
    }


# ---------------------------------------------------------------------------
# The specialist view
# ---------------------------------------------------------------------------
#
# What the three specialist sections of the product show, assembled here
# from persisted agent output rather than written in React. The rule for
# this whole section: every sentence a user reads either comes from the
# agent/library data verbatim, or is a fixed phrasing of a value that data
# carries (a need level, a decision type). Nothing is inferred, and a
# section with no evidence behind it says so rather than filling itself in.
#
# It still emits no internal identifier: exercise ids are library ids (see
# _exercise_plan_summary), and no workflow/agent/tool/session id appears.
# ---------------------------------------------------------------------------

# A need level, said in words a non-clinical reader can act on. These are
# rephrasings of need_assessment/schema.py's four levels, not new semantics.
_LEVEL_WORDING = {
    "HIGH": "Needs work",
    "MEDIUM": "Could improve",
    "LOW": "Looks fine",
    "NOT_ASSESSED": "Not measured",
}

# What each measurable metric means in ordinary language. The keys are the
# exercise library's own `measurable_metrics` values. Deliberately contains
# no computer-vision vocabulary: a user is told what is being watched, not
# how the watching works.
_METRIC_WORDING = {
    "repetitions": "how many you complete",
    "durationSeconds": "how long you hold it",
    "rangeOfMotion": "how far you move",
    "symmetry": "whether your left and right sides match",
    "movementQuality": "how steady and controlled the movement is",
    "completion": "whether you finish the set",
}

# The decision types, said plainly. Same six values as
# physio_agent/plan_schema.py's DECISION_TYPES.
_DECISION_WORDING = {
    "ADD": "Added",
    "REMOVE": "Removed",
    "REPLACE": "Swapped",
    "MAINTAIN": "Unchanged",
    "PROGRESS": "Moved up",
    "REGRESS": "Made easier",
}

_SELECTION_MODE_WORDING = {
    "need_based": (
        "These were chosen for the movement needs your assessment actually "
        "measured."
    ),
    "conservative_starter": (
        "Your assessment could not measure everything, so these are gentle "
        "starting points for the parts that could not be measured. They are "
        "not based on a finding that anything is wrong."
    ),
}

# What an exercise is FOR, said as a capability rather than as the test the
# finding came from. `_DIMENSION_LABELS` names the assessment finding
# ("Upper-body mobility", measured by the shoulder test); this names the
# thing the exercise trains, which is not the same sentence.
_TARGET_WORDING = {
    "mobility_need": "Moving freely",
    "stability_need": "Balance and steadiness",
    "functional_movement_need": "Everyday movements",
}

_CAPABILITY_WORDING = {
    "mobility": "Moving freely",
    "stability": "Balance and steadiness",
    "strength": "Strength",
    "functional_movement": "Everyday movements",
}

NEXT_REVIEW_MOVEMENT = (
    "When you record exercises, what you actually managed is reviewed "
    "against your assessment, and this programme is adjusted from it — "
    "exercises can move up, be made easier, be swapped, or stay as they "
    "are. Nothing changes without something recorded to change it."
)


def _findings_from_needs(user_state: dict, dimensions) -> list:
    """What the assessment established for a set of dimensions: the level in
    plain words, plus Need Assessment's own evidence sentences."""

    profile = _need_profile(user_state)

    if not profile:
        return []

    findings = []

    for dimension in dimensions:
        entry = profile.get(dimension)

        if not isinstance(entry, dict):
            continue

        findings.append(
            {
                "capability": _DIMENSION_LABELS.get(dimension, dimension),
                "finding": _LEVEL_WORDING.get(entry.get("level"), "Not measured"),
                "measured": entry.get("level") != "NOT_ASSESSED",
                "evidence": list(entry.get("evidence") or []),
            }
        )

    return findings


def _watching_for(exercise_id: str, measurement_method) -> list:
    """What this system can actually observe about one exercise, in ordinary
    language — read from the library, never claimed."""

    if measurement_method == "manual_completion":
        return ["whether you mark it as done"]

    try:
        details = get_exercise_details(exercise_id)
    except ExerciseNotFoundError:
        return []

    return [
        _METRIC_WORDING[metric]
        for metric in details.get("measurable_metrics") or []
        if metric in _METRIC_WORDING
    ]


def _programme_entries(record: dict) -> list:
    """The exercises as the Movement screen shows them: the full
    prescription and the agent's own reason for each one."""

    entries = record.get("exercises") or []

    if not entries:
        # A plan recorded before the prescription was persisted. The ids are
        # still real, so the programme is shown; the per-exercise reasoning
        # simply is not there to show, and is left out rather than invented.
        return [
            {
                "id": exercise_id,
                "name": _exercise_name(exercise_id),
                "why": None,
                "target": None,
                "difficulty": None,
                "sets": None,
                "repetitions": None,
                "duration_seconds": None,
                "progression": None,
                "regression": None,
                "safety": [],
                "change": None,
                "watching": [],
            }
            for exercise_id in record.get("exercise_ids") or []
        ]

    programme = []

    for entry in entries:
        exercise_id = entry.get("exercise_id")

        programme.append(
            {
                "id": exercise_id,
                "name": _exercise_name(exercise_id),
                "why": entry.get("rationale"),
                "target": _TARGET_WORDING.get(entry.get("target_need")),
                "difficulty": entry.get("difficulty"),
                "sets": entry.get("sets"),
                "repetitions": entry.get("repetitions"),
                "duration_seconds": entry.get("duration_seconds"),
                "progression": entry.get("progression"),
                "regression": entry.get("regression"),
                "safety": list(entry.get("safety_notes") or []),
                "change": _DECISION_WORDING.get(entry.get("decision_type")),
                "watching": _watching_for(exercise_id, entry.get("measurement_method")),
            }
        )

    return programme


def _changes_of(record: dict) -> list:
    """What changed in this plan version and why — the agent's own decisions,
    excluding the ones that changed nothing."""

    changes = []

    for decision in record.get("decisions") or []:
        decision_type = decision.get("decision_type")

        if decision_type in (None, "MAINTAIN", "ADD"):
            continue

        changes.append(
            {
                "exercise": _exercise_name(decision.get("exercise_id")),
                "change": _DECISION_WORDING.get(decision_type, decision_type),
                "reason": decision.get("reason"),
            }
        )

    return changes


def movement_specialist(user_state: dict) -> dict:
    """The Movement specialist section, or None when there is no programme.

    Every field is read from the persisted plan-version record the Physio
    Agent produced (orchestrator/state_update.py) or from the Need Profile.
    """

    record = _latest_plan_record(user_state.get("exercise_history") or {})

    if record is None:
        return None

    watching = []

    for entry in _programme_entries(record):
        for item in entry["watching"]:
            if item not in watching:
                watching.append(item)

    return {
        "title": "Movement",
        "what_i_found": _findings_from_needs(user_state, _PHYSICAL_DIMENSIONS),
        "working_on": [
            _CAPABILITY_WORDING.get(capability, capability)
            for capability in record.get("capabilities_targeted") or []
        ],
        "why_this_programme": _SELECTION_MODE_WORDING.get(
            record.get("selection_mode")
        ),
        "goal": record.get("goal"),
        "programme": _programme_entries(record),
        "watching": watching,
        # What has actually been recorded so far, counted from the
        # decisions' own evidence. Empty means nothing has been recorded
        # yet, which the screen states rather than filling in.
        "learning": _unique(
            (
                f"{_exercise_name(decision.get('exercise_id'))}: "
                f"{decision['evidence']['results_recorded']} recorded "
                f"{'session' if decision['evidence']['results_recorded'] == 1 else 'sessions'}."
            )
            for decision in record.get("decisions") or []
            if isinstance(decision.get("evidence"), dict)
            and decision["evidence"].get("results_recorded")
        ),
        # Movement's ask is the same for every exercise: perform it with
        # the camera so there is something to review. An exercise MoveNet
        # cannot observe says so instead of implying it will be measured.
        "need_from_you": _unique(
            (
                "Mark this as done after you do it: "
                f"{entry['name']} is not measured by camera."
                if not entry["watching"]
                or entry["watching"] == ["whether you mark it as done"]
                else f"Record {entry['name']} with the camera so it can be "
                "reviewed."
            )
            for entry in _programme_entries(record)
        ),
        "changes": _changes_of(record),
        "plan_version": record.get("plan_version"),
        "next_review": NEXT_REVIEW_MOVEMENT,
    }


# What an adherence status means to a reader. The three values come from
# the agents' own ADHERENCE_STATUSES; this is a rephrasing, not a second
# vocabulary. There is deliberately no wording for "assumed" -- no such
# status exists.
_ADHERENCE_WORDING = {
    "KNOWN": "Being followed, from what you have recorded",
    "NOT_LOGGED": "Nothing recorded for this yet",
    "UNKNOWN": "Not enough recorded to say yet",
}


def _unique(values) -> list:
    """De-duplicated, order-preserving. Several goals commonly ask for the
    same thing, and the user should be asked once."""

    seen = []

    for value in values:
        if value and value not in seen:
            seen.append(value)

    return seen


def _topic_goal_items(record: dict, name_of) -> list:
    """The goals as the specialist screen shows them: what to do, why, and
    what is known about following it.

    Falls back to the bare topic ids for a plan recorded before the goals
    were persisted in full — the focus is still shown, the reasoning simply
    is not there to show and is not invented.
    """

    goals = record.get("goals") or []

    if not goals:
        return [
            {
                "topic_id": topic_id,
                "name": name_of(topic_id),
                "action": None,
                "why": None,
                "adherence": None,
            }
            for topic_id in record.get("topic_ids") or []
        ]

    return [
        {
            # The library's own public topic id, needed so the habits panel
            # can record an action against this specific goal. Like an
            # exercise id it is a static library identifier, not a Mongo _id
            # and not an orchestration id, so surfacing it breaks no rule
            # this module holds.
            "topic_id": entry.get("topic_id"),
            "name": name_of(entry.get("topic_id")),
            "action": entry.get("practical_goal"),
            "why": entry.get("rationale"),
            "adherence": _ADHERENCE_WORDING.get(entry.get("adherence_status")),
        }
        for entry in goals
    ]


def _topic_specialist(
    user_state: dict, *, section_name, dimension, title, name_of, next_review
) -> dict:
    """The Nutrition and Behaviour specialist sections.

    Both agents persist a goal and a list of topic ids rather than a
    per-item prescription, so these sections show what is really recorded:
    what the assessment established, why the specialist was involved, the
    current focus, and what would change it. Where there is no evidence yet
    — no food logged, no adherence recorded — that is stated as an absence
    rather than filled in.
    """

    record = _latest_plan_record(user_state.get(section_name) or {})

    if record is None:
        return None

    profile = _need_profile(user_state) or {}
    entry = profile.get(dimension) or {}
    goals = record.get("goals") or []
    goal_items = _topic_goal_items(record, name_of)

    return {
        "title": title,
        "what_i_found": _findings_from_needs(user_state, (dimension,)),
        "why_involved": (
            f"{_DIMENSION_LABELS.get(dimension, dimension)} was assessed at "
            f"{_LEVEL_WORDING.get(entry.get('level'), 'not measured').lower()}, "
            "which is what brought this specialist in."
            if entry.get("level") in ("MEDIUM", "HIGH")
            else None
        ),
        "goal": record.get("goal"),
        # Names only, kept for any caller still reading the old shape.
        "focus": [item["name"] for item in goal_items],
        # The same goals with the action, the reason and what is known
        # about following each one.
        "focus_items": goal_items,
        # What the user can actually do today: the goals' own practical
        # wording, straight from the library.
        "today": _unique(item["action"] for item in goal_items),
        # What the specialist is missing, in its own words. This is how a
        # user finds out that "not enough evidence" is about logging rather
        # than about them.
        "need_from_you": _unique(
            need for goal in goals for need in (goal.get("evidence_needed") or [])
        ),
        # What it has actually learned so far. Empty means nothing has been
        # recorded, which the UI states rather than filling in.
        "learning": _unique(
            used for goal in goals for used in (goal.get("evidence_used") or [])
        ),
        "changes": (
            [{"exercise": None, "change": "Updated", "reason": record["adaptation_reason"]}]
            if record.get("adaptation_reason")
            else []
        ),
        "plan_version": record.get("plan_version"),
        "next_review": next_review,
    }


NEXT_REVIEW_NUTRITION = (
    "What you log is compared across the life of this plan. If there is "
    "not enough logged to compare, that is reported as not enough data — "
    "it is never guessed at."
)

NEXT_REVIEW_BEHAVIOUR = (
    "How consistently you keep these up is what decides whether they stay, "
    "change, or are replaced."
)


def specialists(user_state: dict) -> list:
    """The specialists that are actually involved for this user, in the
    order the product presents them. A specialist with no plan is absent
    from the list rather than present and empty — the Orchestrator did not
    involve it, and pretending otherwise would misrepresent the decision.
    """

    sections = [
        movement_specialist(user_state),
        _topic_specialist(
            user_state,
            section_name="nutrition_plan",
            dimension="nutrition_need",
            title="Nutrition",
            name_of=_nutrition_topic_name,
            next_review=NEXT_REVIEW_NUTRITION,
        ),
        _topic_specialist(
            user_state,
            section_name="behaviour",
            dimension="behaviour_need",
            title="Daily habits",
            name_of=_behaviour_topic_name,
            next_review=NEXT_REVIEW_BEHAVIOUR,
        ),
    ]

    return [section for section in sections if section is not None]


_ASSESSMENT_TEST_IDS = ("shoulder", "ftsst", "balance")


def _physical_assessment_summary(user_state: dict) -> dict:
    section = user_state.get("physical_assessment") or {}
    tests = (section.get("data") or {}).get("tests") or {}

    completed_tests = [
        t for t in _ASSESSMENT_TEST_IDS
        if (tests.get(t) or {}).get("status") == "completed"
    ]
    invalid_tests = [
        t for t in _ASSESSMENT_TEST_IDS
        if (tests.get(t) or {}).get("status") == "invalid"
    ]
    remaining_tests = [
        t for t in _ASSESSMENT_TEST_IDS
        if t not in completed_tests
    ]

    if len(completed_tests) == len(_ASSESSMENT_TEST_IDS):
        summary_status = "COMPLETE"
    elif len(completed_tests) > 0:
        summary_status = "PARTIAL"
    elif len(invalid_tests) > 0:
        summary_status = "INSUFFICIENT_DATA"
    else:
        summary_status = "NONE_COMPLETED"

    return {
        "status": summary_status,
        "tests_completed": len(completed_tests),
        "tests_total": len(_ASSESSMENT_TEST_IDS),
        "completed_tests": completed_tests,
        "remaining_tests": remaining_tests,
        "tests": {
            t: (tests.get(t) or {}).get("status", "not_started")
            for t in _ASSESSMENT_TEST_IDS
        },
    }


def serialise_workflow_state(
    user_state: dict,
    safety_status=None,
    safety_result=None,
    tracking: dict = None,
    previous_score: dict = None,
) -> dict:
    """Build the user-facing workflow response from persisted user state.

    `tracking` is this user's already-fetched records (exercise results,
    behaviour actions, food log entries). It is passed in rather than
    fetched here because this module reads no database; omitting it means
    every domain reports its tracking as not recorded, which is exactly what
    an unavailable record means.

    `unified_plan` is the authoritative plan the plan screen renders. The
    three `*_plan` summaries and `specialists_team` are kept because other
    screens and this project's tests read them, and both are derived from
    the same `user_state` — one source of truth, three views of it, none of
    which can disagree about what the user's plan contains.
    """

    exercise_plan = _exercise_plan_summary(user_state)
    nutrition_plan = _nutrition_plan_summary(user_state)
    behaviour_plan = _behaviour_plan_summary(user_state)

    plans_available = any(
        summary["available"]
        for summary in (exercise_plan, nutrition_plan, behaviour_plan)
    )
    current_plan_state = plan_state(user_state, plans_available=plans_available)

    return {
        "generated_at": user_state.get("generatedAt"),
        # The one number the product is organised around: a restatement of the
        # need values above, refused when nothing was measured
        # (workflow/score.py).
        "movewell_score": with_previous(
            build_movewell_score(user_state),
            (previous_score or {}).get("value"),
            (previous_score or {}).get("recorded_at"),
            (previous_score or {}).get("domains"),
        ),
        "exercise_plan": exercise_plan,
        "nutrition_plan": nutrition_plan,
        "behaviour_plan": behaviour_plan,
        "safety_status": safety_status_message(safety_status),
        "plan_state": current_plan_state,
        "plan_status": current_plan_state["state"],
        "specialists": specialists(user_state),
        "specialists_team": build_specialists_team(
            user_state, safety_status=safety_status, safety_result=safety_result
        ),
        "unified_plan": build_unified_plan(
            user_state,
            safety_status=safety_status,
            safety_result=safety_result,
            tracking=tracking,
        ),
        "assessment_summary": _physical_assessment_summary(user_state),
    }


def _status_from(active: bool, evaluated: bool) -> str:
    """The three selection states a specialist card can be in.

    `NOT_ASSESSED` is deliberately its own state and never folded into
    "nothing needed": the first means this project has no evidence to judge
    the domain with, the second means it looked and found no need. They are
    different sentences because they are different facts.
    """

    if active:
        return "ACTIVE"

    return "EVALUATED_NOT_REQUIRED" if evaluated else "NOT_ASSESSED"


_STATUS_LABELS = {
    "ACTIVE": "Selected for your plan",
    "EVALUATED_NOT_REQUIRED": "Reviewed — nothing needed right now",
    "NOT_ASSESSED": "Not yet assessed",
}


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, _STATUS_LABELS["NOT_ASSESSED"])


def _card_base(specialist_id: str) -> dict:
    """The fields every specialist card shares, read from the one place the
    five specialists are defined (orchestration/specialists.py)."""

    spec = definition(specialist_id)

    return {
        "id": spec["id"],
        "alias": spec["slug"],
        "name": spec["name"],
        "title": spec["title"],
        "subtitle": spec["subtitle"],
        "icon": spec["icon"],
        "focus": spec["focus"],
        "route": route_for(specialist_id),
    }


_MOVEMENT_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
)


def _prescription_text(entry: dict) -> str:
    """The dosage of one prescribed exercise, said the way the plan screen
    shows it ("2 × 8", "2 × 20s hold"). Built only from the numbers the plan
    record actually carries."""

    sets = entry.get("sets")
    repetitions = entry.get("repetitions")
    duration = entry.get("duration_seconds")

    if sets and repetitions:
        return f"{sets} × {repetitions}"

    if sets and duration:
        return f"{sets} × {duration}s hold"

    if repetitions:
        return f"{repetitions} repetitions"

    if duration:
        return f"{duration}s hold"

    return None


def _movement_evidence_lines(assessed_movements, not_assessed_movements) -> list:
    """What the camera actually measured, movement by movement, with an
    unmeasured check listed as unmeasured rather than as a finding."""

    lines = [f"{entry['label']}: measured" for entry in assessed_movements]
    lines += [
        f"{entry['label']}: not measured ({entry['status']})"
        for entry in not_assessed_movements
    ]

    return lines


def _exercise_movement_card(user_state: dict, need_profile: dict) -> dict:
    """The one movement specialist, over both kinds of movement evidence.

    Two domain modules feed it and neither is discarded: the activity
    decision and domain reasoning (self-reported daily volume) and the
    physiotherapy decision and exercise selection (camera-measured movement
    needs). Merging them here — rather than in the client — is what makes
    "Exercise & Movement" one coach rather than two cards a user has to
    reconcile.
    """

    activity_decision = decide_exercise_activity_required(user_state, need_profile)
    activity_active = bool(activity_decision.get("exercise_activity_required"))
    activity_evaluated = bool(activity_decision.get("evaluated"))
    activity_domain = assess_activity(build_activity_view(user_state))

    movement_decision = decide_physio_required(need_profile, exercise_plan_exists=True)
    movement_active = bool(movement_decision.get("physio_required"))
    movement_evaluated = any(
        isinstance(need_profile.get(dimension), dict)
        and need_profile[dimension].get("level") != "NOT_ASSESSED"
        for dimension in _MOVEMENT_DIMENSIONS
    )

    plan_record = _latest_plan_record(user_state.get("exercise_history") or {})
    programme = _programme_entries(plan_record) if plan_record else []

    active = activity_active or movement_active
    evaluated = activity_evaluated or movement_evaluated
    status = _status_from(active, evaluated)

    # The reason is whichever of the two movement decisions fired. When
    # neither fired, both explanations are reported, so "nothing was needed"
    # and "nothing could be measured" never collapse into one sentence.
    reason = " ".join(
        text
        for text, fired in (
            (movement_decision.get("reason"), movement_active),
            (activity_decision.get("reason"), activity_active),
        )
        if fired and text
    )

    if not active:
        reason = " ".join(
            text
            for text, fired in (
                (movement_decision.get("reason"), not movement_active),
                (activity_decision.get("reason"), not activity_active),
            )
            if fired and text
        )

    assessed_movements, not_assessed_movements = _movement_evidence(
        (user_state.get("physical_assessment") or {}).get("data")
    )

    evidence = _movement_evidence_lines(assessed_movements, not_assessed_movements)

    for line in activity_domain["evidence_used"]:
        if line not in evidence:
            evidence.append(line)

    if not evidence:
        evidence = [
            (need_profile.get("overallSummary") or {}).get("headline")
            or "No baseline movement check has produced a usable measurement yet."
        ]

    recommendations = [
        {
            "id": item["id"],
            "title": item["title"],
            "action": item["action"],
            "why": item["why"],
        }
        for item in activity_domain["activity_recommendations"]
    ] + [
        {
            "id": entry["id"],
            "title": entry["name"],
            "action": _prescription_text(entry)
            or f"Perform {entry['name']} as shown in the demonstration.",
            "why": entry.get("why"),
        }
        for entry in programme
    ]

    missing = list(activity_domain["missing_information"])

    for dimension in movement_decision.get("unassessed_dimensions") or ():
        line = (
            f"{_DIMENSION_LABELS.get(dimension, dimension)} could not be "
            "measured"
        )
        if line not in missing:
            missing.append(line)

    return {
        **_card_base(EXERCISE_MOVEMENT),
        "evaluated": evaluated,
        "active": active,
        "plan_included": bool(programme),
        "status": status,
        "status_label": _status_label(status),
        "reason": reason,
        "evidence": evidence,
        "assessed_movements": assessed_movements,
        "not_assessed_movements": not_assessed_movements,
        "findings": activity_domain["activity_findings"],
        "progression": activity_domain["progression"],
        "constraints": activity_domain["constraints"],
        "missing_information": missing,
        "confidence": activity_domain["confidence"],
        "recommendations": recommendations,
        "exercises": programme,
        "movement_decision": movement_decision,
        "activity_decision": activity_decision,
    }


def _nutrition_lifestyle_card(user_state: dict, need_profile: dict) -> dict:
    decision = decide_nutrition_required(need_profile, user_state)
    active = bool(decision.get("nutrition_required"))

    level = (need_profile.get("nutrition_need") or {}).get("level")
    evaluated = active or (level is not None and level != "NOT_ASSESSED")

    plan_record = _latest_plan_record(user_state.get("nutrition_plan") or {})
    evidence_view = build_nutrition_evidence_view(user_state)
    goals = _topic_goal_items(plan_record, _nutrition_topic_name) if plan_record else []

    status = _status_from(active, evaluated)

    evidence = list((need_profile.get("nutrition_need") or {}).get("evidence") or [])

    for line in evidence_view["evidence_used"]:
        if line not in evidence:
            evidence.append(line)

    return {
        **_card_base(NUTRITION_LIFESTYLE),
        "evaluated": evaluated,
        "active": active,
        "plan_included": bool(goals),
        "status": status,
        "status_label": _status_label(status),
        "reason": decision.get("reason"),
        "activated_by": decision.get("activated_by") or [],
        "report_evidence": decision.get("report_evidence") or [],
        "evidence": evidence,
        "evidence_status": evidence_view["status"],
        "missing_information": evidence_view["missing_information"],
        "confidence": evidence_view["confidence"],
        "recommendations": [
            {
                "id": item["topic_id"],
                "title": item["name"],
                "action": item["action"],
                "why": item["why"],
            }
            for item in goals
        ],
        "goals": goals,
    }


def _behaviour_adherence_card(user_state: dict, need_profile: dict) -> dict:
    decision = decide_behaviour_required(need_profile)
    active = bool(decision.get("behaviour_required"))

    level = (need_profile.get("behaviour_need") or {}).get("level")
    evaluated = level is not None and level != "NOT_ASSESSED"

    plan_record = _latest_plan_record(user_state.get("behaviour") or {})
    goals = _topic_goal_items(plan_record, _behaviour_topic_name) if plan_record else []

    status = _status_from(active, evaluated)

    return {
        **_card_base(BEHAVIOUR_ADHERENCE),
        "evaluated": evaluated,
        "active": active,
        "plan_included": bool(goals),
        "status": status,
        "status_label": _status_label(status),
        "reason": decision.get("reason"),
        "evidence": list((need_profile.get("behaviour_need") or {}).get("evidence") or []),
        "recommendations": [
            {
                "id": item["topic_id"],
                "title": item["name"],
                "action": item["action"],
                "why": item["why"],
            }
            for item in goals
        ],
        "goals": goals,
    }


def _recovery_care_card(user_state: dict, need_profile: dict) -> dict:
    decision = decide_recovery_required(user_state)
    active = bool(decision.get("recovery_required"))
    evaluated = bool(decision.get("evaluated"))

    domain = assess_recovery(build_recovery_view(user_state))

    status = _status_from(active, evaluated)

    evidence = domain["evidence_used"] or [
        "No sleep or rest answers recorded yet."
    ]

    return {
        **_card_base(RECOVERY_CARE),
        "evaluated": evaluated,
        "active": active,
        "plan_included": False,
        "status": status,
        "status_label": _status_label(status),
        "reason": decision.get("reason"),
        "evidence": evidence,
        "findings": domain["recovery_findings"],
        "recovery_status": domain["recovery_status"],
        "constraint": domain["constraint"],
        "missing_information": (
            domain["missing_information"]
            if domain["status"] == STATUS_INSUFFICIENT_EVIDENCE
            else []
        ),
        "confidence": domain["confidence"],
        "recommendations": [
            {
                "id": item["id"],
                "title": item["title"],
                "action": item["action"],
                "why": item["why"],
            }
            for item in domain["recovery_recommendations"]
        ],
    }


# Safety's own action codes, said in words a user can act on. Same
# discipline as SAFETY_STATUS_MESSAGES: a rephrasing of a value the Safety
# Gate itself produced, never a new safety claim written here.
_SAFETY_ACTION_WORDING = {
    "refer_to_professional": (
        "Talk to a qualified healthcare professional before continuing."
    ),
    "block_all_recommendations": (
        "Recommendations from this run were withheld pending that conversation."
    ),
    "add_medical_disclaimer": (
        "Discuss these recommendations against your confirmed report with a "
        "healthcare professional."
    ),
    "add_professional_discussion_note": (
        "Mention these recommendations when you next speak to a healthcare "
        "professional."
    ),
}


def _safety_action_wording(code: str) -> str:
    if code in _SAFETY_ACTION_WORDING:
        return _SAFETY_ACTION_WORDING[code]

    if code.startswith("pause_recommendation:"):
        paused = code.split(":", 1)[1]

        return (
            f"Paused for review before you follow it: {_exercise_name(paused)}."
        )

    # An action code this module does not know about is reported as itself
    # rather than hidden or guessed at.
    return code.replace("_", " ")


def _safety_practitioner_card(
    user_state: dict, need_profile: dict, *, safety_status=None, safety_result=None
) -> dict:
    raw_status = safety_status or (safety_result or {}).get("status")
    code = raw_status or "NOT_ASSESSED"
    evaluated = raw_status is not None

    safety_code_labels = {
        "ALLOW": "Reviewed — approved",
        "MODIFY": "Reviewed — modified",
        "PAUSE": "Reviewed — paused",
        "REFER": "Reviewed — referral recommended",
        "NOT_ASSESSED": "Not yet assessed",
    }

    self_reported_health = (
        ((user_state.get("medical_context") or {}).get("data") or {}).get(
            "self_reported"
        )
        if (user_state.get("medical_context") or {}).get("available")
        else None
    )
    reported_concerns = reported_health_concerns(self_reported_health)

    # confirmed_reports is a container that exists even when empty, so its
    # presence is not evidence of a report. Only a non-empty reports list
    # is — the same test the Orchestrator applies before handing anything to
    # the Safety Gate.
    container = (
        ((user_state.get("medical_context") or {}).get("data") or {}).get(
            "confirmed_reports"
        )
        if (user_state.get("medical_context") or {}).get("available")
        else None
    )
    confirmed_reports = (
        container
        if isinstance(container, dict) and container.get("reports")
        else None
    )

    actions = list((safety_result or {}).get("actions") or [])

    evidence = [
        "Reported at onboarding: "
        + (
            ", ".join(concern.replace("_", " ") for concern in reported_concerns)
            if reported_concerns
            else "no health conditions reported"
        ),
        "Confirmed medical report on file: "
        + ("yes" if confirmed_reports else "no"),
        "Every candidate exercise's declared difficulty is checked against "
        "this review's ceiling before a plan is stored.",
    ]

    missing = _missing_safety_information(
        need_profile, confirmed_reports, self_reported_health
    )

    card = {
        **_card_base(SAFETY_PRACTITIONER),
        "evaluated": evaluated,
        # A safety review that happened is always part of the picture, even
        # when its verdict is ALLOW: the user is entitled to know a review
        # took place. `constrains_plan` distinguishes a verdict that changed
        # something from one that did not.
        "active": evaluated and code != "NOT_ASSESSED",
        "plan_included": False,
        "constrains_plan": code in ("MODIFY", "PAUSE", "REFER"),
        "status": code,
        "status_label": safety_code_labels.get(code, safety_code_labels["NOT_ASSESSED"]),
        "level": STATUS_TO_LEVEL.get(code),
        "reason": (safety_result or {}).get("reason")
        or safety_status_message(raw_status),
        "evidence": evidence,
        "flags": list((safety_result or {}).get("flags") or []),
        "safety_actions": [
            {"code": action, "text": _safety_action_wording(action)}
            for action in actions
        ],
        "requires_referral": bool((safety_result or {}).get("requires_referral")),
        "missing_safety_information": missing,
        "blocked_recommendation_ids": list(
            (safety_result or {}).get("blocked_recommendation_ids") or []
        ),
        "modified_recommendation_ids": list(
            (safety_result or {}).get("modified_recommendation_ids") or []
        ),
        "recommendations": [],
    }

    return card


def build_specialists_team(user_state: dict = None, safety_status=None, safety_result=None) -> list:
    """The five specialists, in presentation order — always all five.

    A specialist the Orchestrator did not select is still present, because
    "this specialist reviewed your evidence and nothing was needed" is
    information, whereas an absent card is not. Every field is derived from
    this user's own state: the selection comes from orchestrator/decision.py
    and each card's evidence from the same pure function that specialist's
    own agent runs. No per-user sentence is written in this module.
    """

    user_state = user_state or {}
    need_profile = _need_profile(user_state) or {}

    cards = {
        EXERCISE_MOVEMENT: _exercise_movement_card(user_state, need_profile),
        NUTRITION_LIFESTYLE: _nutrition_lifestyle_card(user_state, need_profile),
        BEHAVIOUR_ADHERENCE: _behaviour_adherence_card(user_state, need_profile),
        RECOVERY_CARE: _recovery_care_card(user_state, need_profile),
        SAFETY_PRACTITIONER: _safety_practitioner_card(
            user_state,
            need_profile,
            safety_status=safety_status,
            safety_result=safety_result,
        ),
    }

    return [cards[specialist_id] for specialist_id in SPECIALIST_ORDER]


# ---------------------------------------------------------------------------
# The unified plan
# ---------------------------------------------------------------------------
#
# ONE plan, assembled server-side, and the only thing the plan screen
# renders. The five specialists are the internal specialisation; what a
# person reads is a single list of actions that already had the
# cross-specialist constraints and the Safety Gate applied to them.
#
# Every item carries the identifiers an action needs as *domain* ids — an
# exercise id from the 20-exercise intervention library, a nutrition or
# behaviour topic id from its own library — plus the plan id of the record
# it came from. Never a workflow id, never an agent-run id, never a Mongo
# _id: those identify a run of this pipeline, not a thing a user does.
#
# `actions` here means "the things in your plan", not "the buttons". The
# button is item["action"], and it is decided here too, so the client never
# decides what a plan item does. That is what makes the client unable to
# reconstruct a plan: it has nothing left to reconstruct.

TRACKING_NOT_RECORDED = "NOT_RECORDED"
TRACKING_RECORDED = "RECORDED"
TRACKING_COMPLETED = "COMPLETED"

# Which measurement a plan item's own progress is compared on, in the order
# this project prefers them. All three are "higher is better" for every
# exercise in the library, so a direction here is a factual comparison of
# two recorded numbers, not a judgement about the user.
_PROGRESS_METRICS = (
    ("repetitions", "Repetitions"),
    ("durationSeconds", "Hold time"),
    ("completion", "Share of the target completed"),
)

_PROGRESS_DIRECTION_WORDING = {
    "IMPROVING": "Up on your last session",
    "HOLDING": "The same as your last session",
    "DECLINING": "Down on your last session",
    "NOT_ENOUGH_DATA": "Not enough sessions recorded to compare yet",
    "NOT_RECORDED": "Nothing recorded for this yet",
}


def _tracking_not_recorded(label: str, *, counts_toward_section: bool = False, unit: str = None) -> dict:
    return {
        "status": TRACKING_NOT_RECORDED,
        "label": label,
        "summary": None,
        "recorded": 0,
        "counts_toward_section": counts_toward_section,
        "unit": unit,
        "rows": [],
    }


def _iso_text(value):
    if value is None:
        return None

    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _sort_key(result: dict):
    return str(
        result.get("recorded_at")
        or result.get("completedAt")
        or result.get("completed_at")
        or ""
    )


def _public_result(result: dict) -> dict:
    return {
        "status": result.get("status"),
        # Documents written before this field existed were all camera
        # sessions, so that is what they are reported as.
        "source": result.get("source") or "camera",
        "recorded_at": _iso_text(
            result.get("recorded_at") or result.get("completedAt")
        ),
        "measurements": result.get("measurements") or {},
    }


def _measurement_summary(result: dict, entry: dict) -> str:
    """What one recorded session actually showed, in the plan item's own
    terms ("8 repetitions of 10, 92% of the target completed"). Built only
    from the numbers the result carries and the target the plan set; a
    missing number is left out rather than filled in."""

    measurements = result.get("measurements") or {}
    pieces = []

    repetitions = measurements.get("repetitions")

    if repetitions is not None:
        target = entry.get("repetitions")
        pieces.append(
            f"{repetitions} repetitions"
            + (f" of {target}" if target else "")
        )

    seconds = measurements.get("durationSeconds")

    if seconds is not None:
        pieces.append(f"{round(seconds)}s held")

    completion = measurements.get("completion")

    if completion is not None:
        pieces.append(f"{round(completion * 100)}% of the target completed")

    return ", ".join(pieces) or None


def _results_for(results, *, plan_id, exercise_id=None, item_id=None) -> list:
    """The recorded sessions that belong to one plan item, newest first.

    A result recorded against a different plan is not counted here: it
    happened, but it is not evidence about this plan (the same ownership
    accounting progress_agent/adherence.py already applies).

    `item_id` is the more precise match when the result carries one — it
    names the exact plan item the user was working through — but a result
    recorded without it (an older record, or an exercise started outside
    the plan) still counts for the exercise it names, rather than being
    silently dropped.
    """

    matching = [
        result
        for result in (results or [])
        if isinstance(result, dict)
        and (exercise_id is None or result.get("exerciseId") == exercise_id)
        and (item_id is None or result.get("item_id") in (None, item_id))
        and (plan_id is None or result.get("plan_id") == plan_id)
    ]

    return sorted(matching, key=_sort_key, reverse=True)


def _result_metric(result: dict, metric: str):
    return (result.get("measurements") or {}).get(metric)


def _item_progress(results: list, entry: dict) -> dict:
    """This item's own recorded history, compared to itself. Never to a
    norm, never to another person, and never when there is only one
    session."""

    if not results:
        return {
            "direction": "NOT_RECORDED",
            "label": _PROGRESS_DIRECTION_WORDING["NOT_RECORDED"],
            "metric": None,
            "previous": None,
            "current": None,
        }

    current = results[0]
    previous = results[1] if len(results) > 1 else None

    base = {
        "metric": None,
        "previous": _public_result(previous) if previous else None,
        "current": _public_result(current),
        "recorded": len(results),
    }

    if previous is None:
        return {
            **base,
            "direction": "NOT_ENOUGH_DATA",
            "label": _PROGRESS_DIRECTION_WORDING["NOT_ENOUGH_DATA"],
        }

    for metric, label in _PROGRESS_METRICS:
        before = _result_metric(previous, metric)
        after = _result_metric(current, metric)

        if before is None or after is None:
            continue

        if after > before:
            direction = "IMPROVING"
        elif after < before:
            direction = "DECLINING"
        else:
            direction = "HOLDING"

        return {
            **base,
            "metric": label,
            "direction": direction,
            "label": (
                f"{_PROGRESS_DIRECTION_WORDING[direction]}: {label.lower()} "
                f"went from {before:g} to {after:g}"
            ),
            "from": before,
            "to": after,
        }

    return {
        **base,
        "direction": "NOT_ENOUGH_DATA",
        "label": _PROGRESS_DIRECTION_WORDING["NOT_ENOUGH_DATA"],
    }


def _item_tracking(results: list, entry: dict) -> dict:
    if not results:
        return _tracking_not_recorded(
            "Nothing recorded for this yet.",
            counts_toward_section=True,
            unit="session",
        )

    latest = results[0]
    completed = sum(1 for result in results if result.get("status") == "completed")
    source = latest.get("source") or "camera"

    return {
        "status": TRACKING_COMPLETED if completed else TRACKING_RECORDED,
        "label": (
            f"{len(results)} session"
            + ("s" if len(results) != 1 else "")
            + f" recorded, {completed} meeting the target"
        ),
        "summary": _measurement_summary(latest, entry),
        "recorded": len(results),
        "completed": completed,
        "counts_toward_section": True,
        "unit": "session",
        "latest": _public_result(latest),
        "how_it_was_recorded": (
            "confirmed by you" if source == "manual_confirmation" else "measured by camera"
        ),
        "rows": [],
    }


def _exercise_action(exercise_id: str, plan_id, item_id: str) -> dict:
    """The button for one exercise item. It opens the existing exercise
    page, carrying the item's own domain ids so the result can be recorded
    against the exact plan item that asked for it."""

    route = f"/exercise/{quote(str(exercise_id), safe='')}"

    query = []

    if plan_id:
        query.append(f"planId={quote(str(plan_id), safe='')}")

    if item_id:
        query.append(f"itemId={quote(str(item_id), safe='')}")

    if query:
        route = f"{route}?{'&'.join(query)}"

    return {
        "kind": ACTION_START_EXERCISE,
        "label": "Start exercise",
        "route": route,
        "panel": None,
        "recorded_by": "exercise_results",
    }


def _guidance_action(specialist_id: str, label: str = "View guidance") -> dict:
    return {
        "kind": ACTION_VIEW_GUIDANCE,
        "label": label,
        "route": route_for(specialist_id),
        "panel": None,
        "recorded_by": None,
    }


def _withheld_action(safety_status: str) -> dict:
    label = {
        "PAUSE": "Paused — see safety guidance",
        "REFER": "Withheld — see safety guidance",
    }.get(safety_status, "Not available — see safety guidance")

    return {
        "kind": "withheld",
        "label": label,
        "route": route_for(SAFETY_PRACTITIONER),
        "panel": None,
        "recorded_by": None,
    }


def _safety_applied(item: dict, safety_result) -> dict:
    """Apply this run's Safety Result to one plan item.

    The Orchestrator has already removed blocked recommendations from what
    was persisted, so this is not a second filter over the same data — it
    is what carries the safety decision onto the plan a user is reading
    later, including for a plan stored before this run's verdict existed.
    A REFER withholds everything, which is what makes a referral affect the
    plan rather than appear beside it.
    """

    if not safety_result:
        return item

    # The Safety specialist's own guidance is never withheld by its own
    # verdict: a REFER is precisely the case where the user has to be able
    # to read who to talk to.
    if item.get("specialist") == SAFETY_PRACTITIONER:
        return item

    status = safety_result.get("status")
    item_id = item.get("item_id")
    reason = safety_result.get("reason")

    blocked = set(safety_result.get("blocked_recommendation_ids") or [])
    modified = set(safety_result.get("modified_recommendation_ids") or [])

    if status == "REFER" or (item_id and item_id in blocked):
        item["withheld"] = True
        item["metadata"]["safety"] = {
            "withheld": True,
            "status": status,
            "reason": reason,
        }
        item["action"] = _withheld_action(status)
        return item

    if item_id and item_id in modified:
        item["metadata"]["safety"] = {
            "withheld": False,
            "status": status,
            "note": reason,
        }

    return item


def _exercise_programme_items(user_state: dict, results: list) -> list:
    record = _latest_plan_record(user_state.get("exercise_history") or {})

    if record is None:
        return []

    plan_id = record.get("plan_id")
    items = []

    for entry in _programme_entries(record):
        # The exercise id IS this item's domain id: it is the identifier the
        # exercise library, the exercise page and the results API all use,
        # and inventing a second one would be a second source of truth.
        item_id = entry.get("id")
        item_results = _results_for(
            results, plan_id=plan_id, exercise_id=item_id, item_id=item_id
        )

        items.append(
            {
                "specialist": EXERCISE_MOVEMENT,
                "section": SECTION_EXERCISE_PROGRAMME,
                "plan_id": plan_id,
                "item_id": item_id,
                "kind": "exercise",
                "title": entry.get("name"),
                "detail": _prescription_text(entry),
                "why": entry.get("why"),
                "target": entry.get("target"),
                "metadata": {
                    "exercise_id": item_id,
                    "difficulty": entry.get("difficulty"),
                    "sets": entry.get("sets"),
                    "repetitions": entry.get("repetitions"),
                    "duration_seconds": entry.get("duration_seconds"),
                    "progression": entry.get("progression"),
                    "regression": entry.get("regression"),
                    "safety_notes": list(entry.get("safety") or []),
                    "change": entry.get("change"),
                    "watching_for": list(entry.get("watching") or []),
                },
                "action": _exercise_action(item_id, plan_id, item_id),
                "tracking": _item_tracking(item_results, entry),
                "progress": _item_progress(item_results, entry),
            }
        )

    return items


def _activity_volume_items(user_state: dict, results: list) -> list:
    """Daily-volume guidance. It is a target the user works towards outside
    the app, so its action is to see how it is tracked rather than a button
    that pretends to record a walk — MoveWell has no step log."""

    domain = assess_activity(build_activity_view(user_state))

    if domain["status"] == STATUS_INSUFFICIENT_EVIDENCE:
        return []

    items = []

    for recommendation in domain["activity_recommendations"]:
        items.append(
            {
                "specialist": EXERCISE_MOVEMENT,
                "section": SECTION_ACTIVITY_VOLUME,
                "plan_id": None,
                "item_id": recommendation["id"],
                "kind": "activity_goal",
                "title": recommendation["title"],
                "detail": recommendation["action"],
                "why": recommendation["why"],
                "target": (recommendation.get("target") or {}).get("to"),
                "metadata": {
                    "target": recommendation.get("target"),
                    "constraints": domain["constraints"],
                    "measured_by": "self-reported answers",
                },
                "action": _guidance_action(
                    EXERCISE_MOVEMENT, "See how this is tracked"
                ),
                "tracking": _activity_tracking(domain),
                "progress": _activity_progress(recommendation, domain),
            }
        )

    return items


def _activity_tracking(domain: dict) -> dict:
    lines = list(domain["evidence_used"])

    if not lines:
        return _tracking_not_recorded(
            "No daily activity answers have been recorded yet."
        )

    return {
        "status": TRACKING_RECORDED,
        "label": "From the answers you gave",
        "summary": "; ".join(lines),
        "recorded": len(lines),
        # These are answers the user gave at onboarding, not records of
        # activity performed, so they must NOT be added to the section's
        # session count — that would turn five answers into five sessions.
        "counts_toward_section": False,
        "unit": "answer",
        "rows": [
            {"label": finding["signal"], "value": finding["finding"]}
            for finding in domain["activity_findings"]
        ],
    }


def _activity_progress(recommendation: dict, domain: dict) -> dict:
    """The volume target this one recommendation proposes, from the domain's
    own progression entry for that metric. A recommendation with no
    progression entry says so rather than borrowing another metric's
    numbers."""

    metric = (recommendation.get("target") or {}).get("metric")
    entry = next(
        (
            row
            for row in domain["progression"]
            if row.get("metric") == metric
        ),
        None,
    )

    if entry is None:
        return {
            "direction": "NOT_RECORDED",
            "label": (
                "This target is held at its current level; there is no "
                "increase to compare yet."
            ),
            "metric": metric,
            "previous": None,
            "current": None,
            "rows": [],
        }

    return {
        "direction": "PLANNED",
        "label": (
            f"{str(entry['metric']).replace('_', ' ')} target moves from "
            f"{entry['current']:g} to {entry['next_target']:g}, reviewed after "
            f"{entry['review_after']}."
        ),
        "metric": entry["metric"],
        "previous": entry["current"],
        "current": entry["next_target"],
        "rate": entry["rate"],
        "review_after": entry["review_after"],
        "rows": [entry],
    }


def _nutrition_items(user_state: dict, food_log_entries: list) -> list:
    record = _latest_plan_record(user_state.get("nutrition_plan") or {})

    if record is None:
        return []

    plan_id = record.get("plan_id")
    entries = [
        entry
        for entry in (food_log_entries or [])
        if isinstance(entry, dict)
        and (plan_id is None or entry.get("plan_id") == plan_id)
    ]
    days = {_iso_text(entry.get("recorded_at")) or "" for entry in entries}
    days.discard("")

    if not entries:
        tracking = _tracking_not_recorded(
            "Nothing logged against this plan yet. What you log is what this "
            "plan is reviewed against — nothing is assumed.",
            counts_toward_section=True,
            unit="food log entry",
        )
    else:
        tracking = {
            "status": TRACKING_RECORDED,
            "label": (
                f"{len(entries)} food log entr"
                + ("ies" if len(entries) != 1 else "y")
                + f" on {len(days)} day" + ("s" if len(days) != 1 else "")
            ),
            "summary": None,
            "recorded": len(entries),
            "completed": 0,
            "counts_toward_section": True,
            "unit": "food log entry",
            "rows": [],
        }

    items = []

    for goal in _topic_goal_items(record, _nutrition_topic_name):
        items.append(
            {
                "specialist": NUTRITION_LIFESTYLE,
                "section": SECTION_NUTRITION_GOALS,
                "plan_id": plan_id,
                "item_id": goal["topic_id"],
                "kind": "nutrition_goal",
                "title": goal["name"],
                "detail": goal["action"],
                "why": goal["why"],
                "target": None,
                "metadata": {
                    "topic_id": goal["topic_id"],
                    "adherence": goal["adherence"],
                },
                # Logging a meal is an action with a real, persisted record
                # behind it (food_log), so this is a panel the client
                # already has rather than a route to a page that only talks.
                "action": {
                    "kind": ACTION_LOG_NUTRITION,
                    "label": "Log a meal",
                    "route": None,
                    "panel": "food_log",
                    "recorded_by": "food_log",
                },
                "tracking": tracking,
                "progress": {
                    "direction": "RECORDED" if entries else "NOT_RECORDED",
                    "label": (
                        f"{len(entries)} entr"
                        + ("ies" if len(entries) != 1 else "y")
                        + " logged against this plan so far."
                        if entries
                        else "Nothing logged against this plan yet."
                    ),
                    "metric": None,
                    "previous": None,
                    "current": None,
                    "rows": [],
                },
            }
        )

    return items


def _behaviour_items(user_state: dict, behaviour_actions: list) -> list:
    record = _latest_plan_record(user_state.get("behaviour") or {})

    if record is None:
        return []

    plan_id = record.get("plan_id")
    actions = [
        action
        for action in (behaviour_actions or [])
        if isinstance(action, dict)
        and (plan_id is None or action.get("plan_id") == plan_id)
    ]
    today = _iso_text(_now_utc())[:10]

    items = []

    for goal in _topic_goal_items(record, _behaviour_topic_name):
        topic_id = goal["topic_id"]
        adherence = compute_behaviour_adherence(actions, topic_id=topic_id)
        todays = [
            action
            for action in actions
            if action.get("topic_id") == topic_id
            and str(_iso_text(action.get("recorded_at")) or "").startswith(today)
        ]
        latest_today = sorted(todays, key=_sort_key, reverse=True)
        recorded_today = (
            latest_today[0].get("status") if latest_today else None
        )

        if adherence["status"] == "NOT_LOGGED":
            tracking_row = _tracking_not_recorded(
                "Nothing recorded for this habit yet.",
                counts_toward_section=True,
                unit="habit record",
            )
        else:
            tracking_row = {
                "status": TRACKING_RECORDED,
                "label": (
                    f"{adherence['completed_actions']} completed of "
                    f"{adherence['recorded_actions']} recorded"
                ),
                "summary": (
                    "; ".join(adherence["notes"])
                    if adherence.get("notes")
                    else None
                ),
                "recorded": adherence["recorded_actions"],
                "completed": adherence["completed_actions"],
                "completion_rate": adherence["completion_rate"],
                "recorded_today": recorded_today,
                "counts_toward_section": True,
                "unit": "habit record",
                "rows": [],
            }

        items.append(
            {
                "specialist": BEHAVIOUR_ADHERENCE,
                "section": SECTION_HABIT_GOALS,
                "plan_id": plan_id,
                "item_id": topic_id,
                "kind": "habit_goal",
                "title": goal["name"],
                "detail": goal["action"],
                "why": goal["why"],
                "target": None,
                "metadata": {
                    "topic_id": topic_id,
                    "adherence": goal["adherence"],
                    "adherence_status": adherence["status"],
                },
                "action": {
                    "kind": ACTION_COMPLETE_HABIT,
                    "label": "Complete habit",
                    "route": None,
                    "panel": "behaviour_actions",
                    "recorded_by": "behaviour_log",
                },
                "tracking": tracking_row,
                "progress": {
                    "direction": adherence["status"],
                    "label": (
                        "; ".join(adherence["notes"])
                        if adherence.get("notes")
                        else _PROGRESS_DIRECTION_WORDING["NOT_RECORDED"]
                    ),
                    "metric": "completion_rate",
                    "previous": None,
                    "current": adherence["completion_rate"],
                    "rows": [],
                },
            }
        )

    return items


def _recovery_items(user_state: dict) -> list:
    """Recovery guidance is advice about rest, not a task MoveWell can
    observe the completion of — there is no recovery-action record in this
    application. So each item's action is to open the guidance, and its
    tracking says plainly that nothing is recorded, rather than offering a
    button whose press would go nowhere."""

    domain = assess_recovery(build_recovery_view(user_state))

    if domain["status"] == STATUS_INSUFFICIENT_EVIDENCE:
        return []

    items = []

    for recommendation in domain["recovery_recommendations"]:
        items.append(
            {
                "specialist": RECOVERY_CARE,
                "section": SECTION_RECOVERY_GUIDANCE,
                "plan_id": None,
                "item_id": recommendation["id"],
                "kind": "recovery_action",
                "title": recommendation["title"],
                "detail": recommendation["action"],
                "why": recommendation["why"],
                "target": None,
                "metadata": {
                    "constraint": domain["constraint"],
                    "recovery_status": domain["recovery_status"],
                },
                "action": _guidance_action(RECOVERY_CARE),
                "tracking": _tracking_not_recorded(
                    "MoveWell does not record recovery actions, so nothing "
                    "here is assumed or scored."
                ),
                "progress": {
                    "direction": "NOT_RECORDED",
                    "label": (
                        "Recovery guidance is reviewed from your own answers; "
                        "there is no completion record to compare."
                    ),
                    "metric": None,
                    "previous": None,
                    "current": None,
                    "rows": [],
                },
            }
        )

    return items


def _safety_items(safety_result) -> list:
    """The Safety specialist's own contribution: what it decided and what
    that means for the plan. Its action is to open the guidance, because
    the decision itself is the deliverable — there is nothing for the user
    to tick off."""

    if not safety_result:
        return []

    status = safety_result.get("status")
    reason = safety_result.get("reason")
    actions = list(safety_result.get("actions") or [])

    items = []

    if not actions:
        items.append(
            {
                "specialist": SAFETY_PRACTITIONER,
                "section": SECTION_SAFETY_GUIDANCE,
                "plan_id": None,
                "item_id": None,
                "kind": "safety_decision",
                "title": safety_status_message(status),
                # Deliberately no `detail`: the gate's reason is written about
                # the user in the third person ("this user reported ..."), and it
                # is already on the plan's own safety block. Repeating it here
                # put system prose on the user's own card.
                "detail": None,
                "why": None,
                "target": None,
                "metadata": {
                    "status": status,
                    "level": STATUS_TO_LEVEL.get(status),
                    "requires_referral": bool(
                        safety_result.get("requires_referral")
                    ),
                },
                "action": _guidance_action(SAFETY_PRACTITIONER),
                "tracking": _tracking_not_recorded(
                    "MoveWell records the outcome of each safety review; it "
                    "does not score you."
                ),
                "progress": {
                    "direction": status,
                    "label": safety_status_message(status),
                    "metric": None,
                    "previous": None,
                    "current": None,
                    "rows": [],
                },
            }
        )

        return items

    for action in actions:
        items.append(
            {
                "specialist": SAFETY_PRACTITIONER,
                "section": SECTION_SAFETY_GUIDANCE,
                "plan_id": None,
                # A safety action code is not a domain item id: nothing else
                # in the system addresses a plan item by it. It is recorded
                # in metadata instead of being presented as an id it is not.
                "item_id": None,
                "kind": "safety_guidance",
                "title": _safety_action_wording(action),
                "detail": reason,
                "why": None,
                "target": None,
                "metadata": {
                    "action_code": action,
                    "status": status,
                    "level": STATUS_TO_LEVEL.get(status),
                    "requires_referral": bool(
                        safety_result.get("requires_referral")
                    ),
                },
                "action": _guidance_action(
                    SAFETY_PRACTITIONER,
                    "See who to talk to"
                    if safety_result.get("requires_referral")
                    else "View guidance",
                ),
                "tracking": _tracking_not_recorded(
                    "MoveWell records the outcome of each safety review; it "
                    "does not score you."
                ),
                "progress": {
                    "direction": status,
                    "label": safety_status_message(status),
                    "metric": None,
                    "previous": None,
                    "current": None,
                    "rows": [],
                },
            }
        )

    return items


def _now_utc():
    return datetime.now(timezone.utc)


def _section_focus(
    user_state: dict, need_profile: dict, specialist_id: str, card: dict
) -> str:
    """CURRENT FOCUS, said from what was actually measured.

    Each clause is a need dimension's own level, rephrased by
    `_LEVEL_WORDING`, or a capability the plan record says it is targeting.
    An unmeasured dimension is left out here and reported under `missing`
    instead — it is not a finding and must not read as one.
    """

    profile = need_profile or {}
    parts = []

    if specialist_id == EXERCISE_MOVEMENT:
        for dimension in _MOVEMENT_DIMENSIONS:
            entry = profile.get(dimension)

            if isinstance(entry, dict) and entry.get("level") != "NOT_ASSESSED":
                parts.append(
                    f"{_DIMENSION_LABELS.get(dimension, dimension)}: "
                    f"{_LEVEL_WORDING.get(entry.get('level'), 'not measured')}"
                )

        record = _latest_plan_record(user_state.get("exercise_history") or {})

        for capability in (record or {}).get("capabilities_targeted") or []:
            wording = _CAPABILITY_WORDING.get(capability, capability)

            if wording not in parts:
                parts.append(wording)

    elif specialist_id == NUTRITION_LIFESTYLE:
        entry = profile.get("nutrition_need") or {}

        if entry.get("level") != "NOT_ASSESSED":
            parts.append(
                "Eating patterns: "
                f"{_LEVEL_WORDING.get(entry.get('level'), 'not measured')}"
            )

    elif specialist_id == BEHAVIOUR_ADHERENCE:
        entry = profile.get("behaviour_need") or {}

        if entry.get("level") != "NOT_ASSESSED":
            parts.append(
                "Daily activity habits: "
                f"{_LEVEL_WORDING.get(entry.get('level'), 'not measured')}"
            )

    elif specialist_id == RECOVERY_CARE:
        domain = assess_recovery(build_recovery_view(user_state))

        if domain["recovery_status"] == "CONSTRAINED":
            parts.append("Rest and workload pacing: being paced down")
        elif domain["recovery_status"] == "SUPPORTIVE":
            parts.append("Rest and workload pacing: supporting the current pace")

        # Only this domain's own sleep findings — never the whole evidence
        # list, which carries programme counts that are not a recovery
        # focus.
        for finding in domain["recovery_findings"]:
            parts.append(finding["finding"])

    elif specialist_id == SAFETY_PRACTITIONER:
        parts.append(
            "Review outcome: "
            + safety_status_message(card.get("status"))
        )

    return "; ".join(part for part in parts if part) or None


def _section_decision(user_state: dict, specialist_id: str, card: dict) -> str:
    """SPECIALIST DECISION: what the specialist actually decided, in its own
    recorded words — a plan goal, the changes it made, a constraint it
    placed, or the safety verdict. None when there is nothing recorded."""

    if specialist_id == EXERCISE_MOVEMENT:
        record = _latest_plan_record(user_state.get("exercise_history") or {})

        if record is None:
            return None

        parts = [record.get("goal")] if record.get("goal") else []

        for change in _changes_of(record):
            parts.append(
                f"{change['exercise']}: {change['change'].lower()}"
                + (f" — {change['reason']}" if change.get("reason") else "")
            )

        if not parts:
            parts.append(
                f"{len(record.get('exercise_ids') or [])} exercise(s) selected "
                "from your movement evidence."
            )

        return " ".join(parts)

    if specialist_id in (NUTRITION_LIFESTYLE, BEHAVIOUR_ADHERENCE):
        section_name = (
            "nutrition_plan"
            if specialist_id == NUTRITION_LIFESTYLE
            else "behaviour"
        )
        record = _latest_plan_record(user_state.get(section_name) or {})

        if record is None:
            return card.get("reason")

        parts = [record.get("goal")] if record.get("goal") else []
        parts.append(
            f"{len(record.get('topic_ids') or [])} focus area(s) selected."
        )

        if record.get("adaptation_reason"):
            parts.append(f"Changed: {record['adaptation_reason']}")

        return " ".join(parts)

    if specialist_id == RECOVERY_CARE:
        domain = assess_recovery(build_recovery_view(user_state))

        if domain["status"] == STATUS_INSUFFICIENT_EVIDENCE:
            return None

        if domain["constraint"]["limit_progression"]:
            return domain["constraint"]["reason"]

        return (
            "No rest or workload constraint was placed on your plan this "
            "cycle; the reported rest supports the current pace."
        )

    if specialist_id == SAFETY_PRACTITIONER:
        return card.get("reason")

    return None


def _section_next_step(user_state: dict, specialist_id: str, card: dict) -> str:
    status = card.get("status")
    has_items = bool(card.get("plan_included"))

    if specialist_id == EXERCISE_MOVEMENT:
        if status == "ACTIVE":
            return NEXT_REVIEW_MOVEMENT if has_items else (
                "Prepare your plan from your latest measurements to turn this "
                "into exercises."
            )

        if status == "EVALUATED_NOT_REQUIRED":
            return (
                "Nothing further is needed from you for movement right now. "
                "The next assessment re-checks it."
            )

        return (
            f"{NEXT_ACTION_ASSESSMENT['label']} so this can be evaluated "
            "rather than assumed."
        )

    if specialist_id == NUTRITION_LIFESTYLE:
        if status == "ACTIVE":
            return NEXT_REVIEW_NUTRITION

        if status == "EVALUATED_NOT_REQUIRED":
            return (
                "Nothing further is needed from you for nutrition right now. "
                "Your answers are re-read on your next plan review."
            )

        return (
            f"{NEXT_ACTION_ONBOARDING['label']} so this can be evaluated "
            "rather than assumed."
        )

    if specialist_id == BEHAVIOUR_ADHERENCE:
        if status == "ACTIVE":
            return NEXT_REVIEW_BEHAVIOUR

        if status == "EVALUATED_NOT_REQUIRED":
            return (
                "Nothing further is needed from you for habits right now. Your "
                "answers are re-read on your next plan review."
            )

        return (
            f"{NEXT_ACTION_ONBOARDING['label']} so this can be evaluated "
            "rather than assumed."
        )

    if specialist_id == RECOVERY_CARE:
        if status == "ACTIVE":
            return (
                "Recovery is re-read from your answers and your recorded "
                "sessions on your next plan review."
            )

        if status == "EVALUATED_NOT_REQUIRED":
            return (
                "Your reported rest did not cross this project's markers for "
                "treating recovery as a constraint."
            )

        return (
            f"{NEXT_ACTION_ONBOARDING['label']} so this can be evaluated "
            "rather than assumed."
        )

    if specialist_id == SAFETY_PRACTITIONER:
        code = card.get("status")

        if code == "REFER":
            return (
                "MoveWell recommends talking to a qualified healthcare "
                "professional before you continue with these recommendations."
            )

        if code in ("MODIFY", "PAUSE"):
            return (
                "Follow the guidance above and raise these recommendations "
                "with a qualified healthcare professional."
            )

        if code == "ALLOW":
            return "Reviewed and approved — nothing further is needed from you."

        missing = card.get("missing_safety_information") or []

        return (
            "Not yet assessed. " + "; ".join(missing) + "."
            if missing
            else "Not yet assessed."
        )

    return None


# ---------------------------------------------------------------------------
# The plan as a person reads it
# ---------------------------------------------------------------------------
#
# The three helpers below exist because the plan screen was answering
# engineering questions -- what was this based on, what is not known, what did
# each specialist record -- instead of the two a user has: *what should I do*
# and *what is MoveWell doing about it*. None of them invents anything; each one
# condenses a value the plan already carries.
#
# The condensing is deliberately here rather than in the client, for the same
# reason the plan itself is: a screen that writes its own summary of a
# specialist's decision will eventually describe a decision that was never made.

# Which measurement dimension a focus area is about, in the words a person uses
# rather than the Need Profile's key names.
_FOCUS_AREA_WORDING = {
    "mobility_need": "Upper-body mobility",
    "stability_need": "Balance",
    "functional_movement_need": "Everyday movement",
}

# A stated nutrition goal, said as a focus area. Only used when the user
# actually selected one during the check-in.
_NUTRITION_GOAL_FOCUS = {
    "balanced_eating": "Balanced eating",
    "hydration": "Hydration",
    "healthy_lifestyle": "Healthy lifestyle",
    "weight_management": "Weight management",
}

# The compact status a team card shows. Deliberately four words, so five cards
# can be read at a glance: this is the "who is on my team" question, not the
# "what did they conclude" one.
TEAM_STATUS_LABELS = {
    "ACTIVE": "Active",
    "NOT_ASSESSED": "Not assessed",
    "NOT_NEEDED": "Not needed",
    "REVIEWED": "Reviewed",
    "MODIFIED": "Reviewed — precautions",
    "PAUSED": "Paused for safety",
    "REFERRAL": "Referral recommended",
}


def _team_status(card: dict) -> str:
    """The compact status for one specialist card."""

    status = card.get("status")

    if card.get("id") == SAFETY_PRACTITIONER:
        return {
            "ALLOW": "REVIEWED",
            "MODIFY": "MODIFIED",
            "PAUSE": "PAUSED",
            "REFER": "REFERRAL",
        }.get(status, "NOT_ASSESSED")

    if status == "ACTIVE":
        return "ACTIVE"

    if status == "EVALUATED_NOT_REQUIRED":
        return "NOT_NEEDED"

    return "NOT_ASSESSED"


def _stated_nutrition_goal(user_state: dict):
    """The goal the user chose during the nutrition check-in, or None.

    Read from the nutrition section rather than from the Need Profile, because
    the Need Profile only carries need *dimensions* — a preference is not a
    dimension and is never copied into one. Reading it from the wrong place is
    why the first version of the summary said "eating patterns" for someone who
    had explicitly said "hydration".
    """

    section = (user_state or {}).get("nutrition") or {}

    if not section.get("available"):
        return None

    goal = (section.get("data") or {}).get("nutrition_goal")

    return goal if isinstance(goal, str) and goal in _NUTRITION_GOAL_FOCUS else None


def _short_reason(
    specialist_id: str, card: dict, need_profile: dict, *, nutrition_goal: str = None
) -> str:
    """One short sentence saying why this specialist is or is not involved.

    Each branch reads a value the plan already carries and states it in the
    words a person would use. Where the value is absent, the sentence says the
    domain was not assessed — it never infers a finding from silence.
    """

    status = card.get("status")
    profile = need_profile or {}

    if specialist_id == EXERCISE_MOVEMENT:
        highlighted = [
            _FOCUS_AREA_WORDING[dimension]
            for dimension in _MOVEMENT_DIMENSIONS
            if isinstance(profile.get(dimension), dict)
            and profile[dimension].get("level") in ("MEDIUM", "HIGH")
        ]

        if status == "ACTIVE" and highlighted:
            return (
                "Your assessment highlighted "
                + _join_wording(highlighted)
                + "."
            )

        if status == "ACTIVE":
            return "Your daily activity answers brought movement into your plan."

        if status == "EVALUATED_NOT_REQUIRED":
            return "Your movement assessment did not show a need right now."

        return "Not assessed yet — this needs a movement assessment."

    if specialist_id == NUTRITION_LIFESTYLE:
        if status == "ACTIVE":
            if nutrition_goal:
                return (
                    "Your nutrition check-in answers brought this in, focused "
                    f"on {_NUTRITION_GOAL_FOCUS[nutrition_goal].lower()}."
                )

            return "Your nutrition check-in answers brought this into your plan."

        if status == "EVALUATED_NOT_REQUIRED":
            return "Your nutrition answers did not show a need right now."

        return "Not assessed yet — the nutrition check-in has not been completed."

    if specialist_id == BEHAVIOUR_ADHERENCE:
        if status == "ACTIVE":
            return "Your daily habits put consistency at the centre of this plan."

        if status == "EVALUATED_NOT_REQUIRED":
            return "Your reported habits did not show a need right now."

        return "Not assessed yet — the lifestyle questions are unanswered."

    if specialist_id == RECOVERY_CARE:
        constraint = card.get("constraint") or {}

        if status == "ACTIVE" and constraint.get("limit_progression"):
            return "Your reported rest is pacing how quickly activity increases."

        if status == "ACTIVE":
            return "Your reported rest supports the planned volume."

        if status == "EVALUATED_NOT_REQUIRED":
            return "Your reported rest did not need a change."

        return "Not assessed yet — the sleep questions are unanswered."

    if specialist_id == SAFETY_PRACTITIONER:
        return {
            "ALLOW": "Reviewed your plan and approved it.",
            "MODIFY": "Reviewed your plan and added precautions.",
            "PAUSE": "Paused part of your plan pending review.",
            "REFER": "Recommends talking to a healthcare professional first.",
        }.get(status, "Not yet reviewed.")

    return card.get("reason") or ""


def _join_wording(parts) -> str:
    """"a, b and c" — so a generated sentence reads like a sentence."""

    items = [part for part in parts if part]

    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    return ", ".join(items[:-1]) + " and " + items[-1]


def _empty_state(
    specialist_id: str, card: dict, section: dict, items: list
) -> dict:
    """What to tell a user when this part of the plan has nothing yet.

    Three questions, always answered together: what is missing, why it matters,
    and what to do about it. A state with nothing to do is not emitted at all —
    "nothing recorded yet" with no action beside it is the repetition this
    screen was rebuilt to remove, and the section's own `next_step` already says
    what happens. Nor is one emitted for a section that has recorded actions:
    it is not empty.
    """

    status = card.get("status")

    if specialist_id == SAFETY_PRACTITIONER:
        # The safety review is a supervisor, not an action the user can be
        # missing. "Nothing recorded" would be meaningless here.
        return None

    if status == "NOT_ASSESSED":
        return {
            "kind": "not_assessed",
            "message": {
                EXERCISE_MOVEMENT: (
                    "Complete your movement assessment and MoveWell can build "
                    "this part of your plan."
                ),
                NUTRITION_LIFESTYLE: (
                    "Complete your nutrition check-in so MoveWell can "
                    "personalize this part of your plan."
                ),
                BEHAVIOUR_ADHERENCE: (
                    "Answer the lifestyle questions so MoveWell can build a "
                    "habit plan that fits your week."
                ),
                RECOVERY_CARE: (
                    "Answer the sleep questions so MoveWell can tell whether "
                    "your recovery needs pacing."
                ),
            }.get(specialist_id, "Not assessed yet."),
            "action": {
                EXERCISE_MOVEMENT: {
                    "kind": "start_assessment",
                    "label": "Start assessment",
                    "route": "/assessment",
                },
                NUTRITION_LIFESTYLE: {
                    "kind": "nutrition_check_in",
                    "label": "Complete check-in",
                    "route": "/nutrition-check-in",
                },
                BEHAVIOUR_ADHERENCE: {
                    "kind": "answer_lifestyle_questions",
                    "label": "Answer the questions",
                    "route": "/onboarding",
                },
                RECOVERY_CARE: {
                    "kind": "answer_lifestyle_questions",
                    "label": "Answer the questions",
                    "route": "/onboarding",
                },
            }.get(specialist_id),
        }

    if not items:
        return None

    tracking_status = (section.get("tracking") or {}).get("status")

    if tracking_status != TRACKING_NOT_RECORDED:
        return None

    if specialist_id == EXERCISE_MOVEMENT:
        first = next(
            (item for item in items if item.get("action", {}).get("route")), None
        )

        return {
            "kind": "no_records",
            "message": (
                "Complete your first session to start tracking your progress."
            ),
            "action": (
                {
                    "kind": ACTION_START_EXERCISE,
                    "label": "Start exercise",
                    "route": first["action"]["route"],
                }
                if first
                else None
            ),
        }

    if specialist_id == BEHAVIOUR_ADHERENCE:
        return {
            "kind": "no_records",
            "message": (
                "Complete your first habit to start your adherence history."
            ),
            "action": {
                "kind": ACTION_COMPLETE_HABIT,
                "label": "Record a habit",
                "anchor": f"#specialist-{specialist_id}",
            },
        }

    if specialist_id == NUTRITION_LIFESTYLE:
        return {
            "kind": "no_records",
            "message": (
                "Log your first meal so this plan has something to review."
            ),
            "action": {
                "kind": ACTION_LOG_NUTRITION,
                "label": "Log a meal",
                "anchor": f"#specialist-{specialist_id}",
            },
        }

    return None


def build_plan_summary(
    need_profile: dict = None,
    cards: dict = None,
    plan_sections: dict = None,
    *,
    nutrition_goal: str = None,
) -> dict:
    """The short summary at the top of the plan, from this plan's own content.

    `focus_areas` names the domains the Orchestrator actually selected this
    cycle, using the measured need levels and any goal the user stated. A plan
    with no selected specialist says so instead of inventing a focus, and the
    `next` line is the one fixed sentence that describes what happens next in
    this product.
    """

    profile = need_profile or {}
    cards = cards or {}
    plan_sections = plan_sections or {}

    areas = []

    movement_items = plan_sections.get(EXERCISE_MOVEMENT) or []

    if cards.get(EXERCISE_MOVEMENT, {}).get("status") == "ACTIVE":
        for dimension in _MOVEMENT_DIMENSIONS:
            entry = profile.get(dimension)

            if isinstance(entry, dict) and entry.get("level") in ("MEDIUM", "HIGH"):
                wording = _FOCUS_AREA_WORDING[dimension]

                if wording not in areas:
                    areas.append(wording)

        if any(item.get("section") == SECTION_ACTIVITY_VOLUME for item in movement_items):
            areas.append("Daily movement")

    if cards.get(NUTRITION_LIFESTYLE, {}).get("status") == "ACTIVE":
        areas.append(
            _NUTRITION_GOAL_FOCUS[nutrition_goal] if nutrition_goal else "Eating patterns"
        )

    if cards.get(BEHAVIOUR_ADHERENCE, {}).get("status") == "ACTIVE":
        areas.append("Consistency")

    if cards.get(RECOVERY_CARE, {}).get("status") == "ACTIVE":
        areas.append("Recovery and rest")

    # Four is as many as a sentence can carry before it stops being a summary.
    areas = areas[:4]

    if areas:
        headline = (
            "Your plan is currently focused on "
            + _join_wording([area.lower() for area in areas])
            + "."
        )
    else:
        headline = (
            "Nothing in your plan needs a change right now. Your assessment "
            "and answers did not show a need MoveWell would build a plan "
            "around."
        )

    return {
        "headline": headline,
        "focus_areas": areas,
        "next": (
            "Complete your activities. MoveWell uses what you record and your "
            "next assessment to adapt the plan after this one."
        ),
    }


def build_collaboration(
    cards: dict,
    sections: dict,
    need_profile: dict = None,
    *,
    nutrition_goal: str = None,
) -> dict:
    """How the five specialists produced ONE plan.

    This is a summary of decisions, from the same values the sections show —
    never a transcript, never a chain of thought, and never a specialist
    presented as contributing when it did not. A specialist that was not
    selected appears with the honest sentence and, where the user can act on it,
    the action that would assess it.
    """

    profile = need_profile or {}
    steps = []

    steps.append(
        {
            "kind": "assessment",
            "title": "Your assessment and answers",
            "icon": "📋",
            "participated": True,
            "summary": _input_summary(cards, profile),
        }
    )

    for specialist_id in SPECIALIST_ORDER:
        card = cards.get(specialist_id) or {}
        section = sections.get(specialist_id) or {}
        participated = bool(card.get("active")) if specialist_id != SAFETY_PRACTITIONER else bool(card.get("evaluated"))

        steps.append(
            {
                "kind": "specialist",
                "specialist": specialist_id,
                "title": card.get("title"),
                "icon": card.get("icon"),
                "participated": participated,
                "summary": _short_reason(
                    specialist_id, card, profile, nutrition_goal=nutrition_goal
                ),
                "action": (section.get("empty_state") or {}).get("action"),
            }
        )

    steps.append(
        {
            "kind": "synthesis",
            "title": "MoveWell",
            "icon": "✨",
            "participated": True,
            "summary": (
                "These were combined into your one MoveWell plan, with the "
                "safety review applied before anything reached you."
            ),
        }
    )

    return {
        "title": "How your MoveWell team worked",
        "intro": (
            "MoveWell picked the specialists your own evidence called for. "
            "This is what each of them contributed."
        ),
        "steps": steps,
    }


def _input_summary(cards: dict, need_profile: dict) -> str:
    """What MoveWell looked at, named from what actually exists.

    Read from the cards' own activation sources and the measured need levels,
    so this cannot claim MoveWell used something it never received.
    """

    sources = []
    profile = need_profile or {}

    movement = cards.get(EXERCISE_MOVEMENT) or {}
    measured_movement = any(
        isinstance(profile.get(dimension), dict)
        and profile[dimension].get("level") not in (None, "NOT_ASSESSED")
        for dimension in _MOVEMENT_DIMENSIONS
    ) or bool((movement.get("assessed_movements") or []))

    if measured_movement:
        sources.append("your movement assessment")

    nutrition = cards.get(NUTRITION_LIFESTYLE) or {}

    if "dietary_questionnaire" in (nutrition.get("activated_by") or []):
        sources.append("your nutrition check-in")

    if "confirmed_medical_report" in (nutrition.get("activated_by") or []):
        sources.append("the medical report you confirmed")

    behaviour = cards.get(BEHAVIOUR_ADHERENCE) or {}
    recovery = cards.get(RECOVERY_CARE) or {}

    if (behaviour.get("evidence") or []) or (recovery.get("evidence") or []):
        sources.append("your lifestyle answers")

    if not sources:
        return "MoveWell has not received enough information yet to assess you."

    return "MoveWell looked at " + _join_wording(sources) + "."


def build_unified_plan(
    user_state: dict,
    *,
    safety_status=None,
    safety_result=None,
    tracking: dict = None,
) -> dict:
    """The one MoveWell plan: five specialist sections and their items.

    `tracking` carries this user's already-fetched records — the same
    documents the stores return, not a copy of them:

        {"exercise_results": [...], "behaviour_actions": [...],
         "food_log_entries": [...]}

    Every key is optional; omitting one means that domain's tracking is
    reported as not recorded, which is what an absent record means. Nothing
    in this function reads a database, and nothing in it invents a
    measurement: what it cannot find, it says it cannot find.
    """

    tracking = tracking or {}
    user_state = user_state or {}
    need_profile = _need_profile(user_state) or {}
    nutrition_goal = _stated_nutrition_goal(user_state)

    team = build_specialists_team(
        user_state, safety_status=safety_status, safety_result=safety_result
    )
    cards = {card["id"]: card for card in team}

    exercise_results = list(tracking.get("exercise_results") or [])
    behaviour_actions = list(tracking.get("behaviour_actions") or [])
    food_log_entries = list(tracking.get("food_log_entries") or [])

    plan_sections = {
        EXERCISE_MOVEMENT: _exercise_programme_items(user_state, exercise_results)
        + _activity_volume_items(user_state, exercise_results),
        NUTRITION_LIFESTYLE: _nutrition_items(user_state, food_log_entries),
        BEHAVIOUR_ADHERENCE: _behaviour_items(user_state, behaviour_actions),
        RECOVERY_CARE: _recovery_items(user_state),
        SAFETY_PRACTITIONER: _safety_items(safety_result),
    }

    position = 0
    flat_items = []

    for specialist_id in SPECIALIST_ORDER:
        for item in plan_sections[specialist_id]:
            _safety_applied(item, safety_result)
            position += 1
            item["position"] = position
            flat_items.append(item)

    sections = []

    for specialist_id in SPECIALIST_ORDER:
        card = cards[specialist_id]
        items = plan_sections[specialist_id]
        selected = bool(card.get("active")) or bool(items)

        sections.append(
            {
                "specialist": specialist_id,
                "title": card["title"],
                "subtitle": card["subtitle"],
                "icon": card["icon"],
                "route": card["route"],
                "status": card["status"],
                "status_label": card["status_label"],
                # The compact pair the team card shows, and the one sentence it
                # shows under the name. Condensed server-side so five cards say
                # five different, true things.
                "team_status": _team_status(card),
                "team_status_label": TEAM_STATUS_LABELS.get(
                    _team_status(card), card["status_label"]
                ),
                "short_reason": _short_reason(
                    specialist_id, card, need_profile, nutrition_goal=nutrition_goal
                ),
                # Whether this specialist is part of the plan the user is
                # reading: the Orchestrator selected it this cycle, or it has
                # actions in the plan already. "Not selected" is not the same
                # as "not reviewed", which is what `status` says.
                "selected": selected,
                "why_active": card.get("reason") if card.get("active") else None,
                "why_inactive": None if card.get("active") else card.get("reason"),
                "current_focus": _section_focus(
                    user_state, need_profile, specialist_id, card
                ),
                "decision": _section_decision(user_state, specialist_id, card),
                "actions": items,
                "tracking": _section_tracking(specialist_id, items),
                "progress": _section_progress(specialist_id, user_state, items),
                "next_step": _section_next_step(user_state, specialist_id, card),
                "evidence": list(card.get("evidence") or []),
                "missing": list(
                    card.get("missing_information")
                    or card.get("missing_safety_information")
                    or []
                ),
                "is_safety_supervisor": specialist_id == SAFETY_PRACTITIONER,
            }
        )

    # Filled in after the sections exist, because the honest empty state depends
    # on that section's own tracking status.
    for section in sections:
        section["empty_state"] = _empty_state(
            section["specialist"],
            cards[section["specialist"]],
            section,
            section["actions"],
        )

    constraints = _plan_constraints(user_state, safety_result)

    plan_ids = {
        specialist_id: sorted(
            {
                item["plan_id"]
                for item in plan_sections[specialist_id]
                if item.get("plan_id")
            }
        )
        for specialist_id in SPECIALIST_ORDER
    }

    versions = [
        record.get("plan_version")
        for record in (
            _latest_plan_record(user_state.get("exercise_history") or {}),
            _latest_plan_record(user_state.get("nutrition_plan") or {}),
            _latest_plan_record(user_state.get("behaviour") or {}),
        )
        if isinstance(record, dict) and record.get("plan_version")
    ]

    plan_state_details = plan_state(
        user_state, plans_available=bool(flat_items)
    )

    return {
        "available": bool(flat_items),
        "plan_id": _current_plan_id(user_state),
        "plan_ids": plan_ids,
        "version": max(versions) if versions else None,
        "generated_at": user_state.get("generatedAt"),
        "state": plan_state_details,
        # What this plan is about, in one sentence, and what happens next.
        "summary": build_plan_summary(
            need_profile, cards, plan_sections, nutrition_goal=nutrition_goal
        ),
        "safety": _safety_block(safety_status, safety_result),
        "specialists": team,
        "sections": sections,
        # The same items, in plan order. `sections[].actions` holds these
        # very objects -- this is one list read two ways, not a second
        # derivation, so the two can never disagree.
        "items": flat_items,
        "constraints": constraints,
        # How the selected specialists produced this one plan, from their own
        # decisions.
        "collaboration": build_collaboration(
            cards,
            {section["specialist"]: section for section in sections},
            need_profile,
            nutrition_goal=nutrition_goal,
        ),
        "active_specialists": [
            specialist_id
            for specialist_id in SPECIALIST_ORDER
            if cards[specialist_id].get("active")
        ],
        "counts": {
            "selected_specialists": sum(1 for s in sections if s["selected"]),
            "actions": len(flat_items),
            "exercises": sum(1 for item in flat_items if item["kind"] == "exercise"),
        },
    }


def _section_tracking(specialist_id: str, items: list) -> dict:
    """What has actually been recorded for this section, counted from the
    items' own tracking rather than computed twice.

    Only items whose tracking comes from a real record store are counted —
    a daily-volume target built from onboarding answers is not a session,
    and adding it to the session count would inflate what the user has
    actually done.
    """

    if not items:
        return _tracking_not_recorded(
            "No actions are in this part of your plan yet."
        )

    counted = [item for item in items if item["tracking"].get("counts_toward_section")]
    recorded = sum(item["tracking"].get("recorded") or 0 for item in counted)
    completed = sum(item["tracking"].get("completed") or 0 for item in counted)
    statuses = {item["tracking"].get("status") for item in counted}

    if TRACKING_COMPLETED in statuses:
        status = TRACKING_COMPLETED
    elif TRACKING_RECORDED in statuses:
        status = TRACKING_RECORDED
    else:
        status = TRACKING_NOT_RECORDED

    units = {
        item["tracking"].get("unit") for item in counted if item["tracking"].get("unit")
    }
    unit = units.pop() if len(units) == 1 else "record"

    how = [
        item["tracking"].get("how_it_was_recorded")
        for item in items
        if item["tracking"].get("how_it_was_recorded")
    ]

    if status == TRACKING_NOT_RECORDED:
        label = "Nothing recorded for this part of the plan yet."
    elif status == TRACKING_COMPLETED:
        label = (
            f"{completed} of {recorded} recorded {unit}"
            + ("s" if recorded != 1 else "")
            + " met the target"
        )
    else:
        label = (
            f"{recorded} {unit}" + ("s" if recorded != 1 else "") + " recorded so far"
        )

    return {
        "status": status,
        "label": label,
        "summary": how[0] if how else None,
        "recorded": recorded,
        "completed": completed,
        "rows": [
            {
                "label": item["title"],
                "value": item["tracking"].get("summary")
                or item["tracking"].get("label"),
            }
            for item in items
        ],
    }


def _section_progress(specialist_id: str, user_state: dict, items: list) -> dict:
    """Where this part of the plan has got to, from the records and the plan
    version — never from a score this module made up."""

    section_name = {
        EXERCISE_MOVEMENT: "exercise_history",
        NUTRITION_LIFESTYLE: "nutrition_plan",
        BEHAVIOUR_ADHERENCE: "behaviour",
    }.get(specialist_id)

    record = (
        _latest_plan_record(user_state.get(section_name) or {})
        if section_name
        else None
    )

    directions = [item["progress"].get("direction") for item in items]
    improving = sum(1 for direction in directions if direction == "IMPROVING")
    declining = sum(1 for direction in directions if direction == "DECLINING")

    if not items:
        direction = "NOT_RECORDED"
    elif all(d == "NOT_RECORDED" for d in directions):
        direction = "NOT_RECORDED"
    elif improving and not declining:
        direction = "IMPROVING"
    elif declining and not improving:
        direction = "DECLINING"
    elif improving or declining:
        direction = "MIXED"
    elif any(d == "NOT_ENOUGH_DATA" for d in directions):
        direction = "NOT_ENOUGH_DATA"
    else:
        direction = "HOLDING"

    return {
        "direction": direction,
        "plan_version": (record or {}).get("plan_version"),
        "adaptation_reason": (record or {}).get("adaptation_reason"),
        "triggered_by": (record or {}).get("triggered_by"),
        "label": {
            "IMPROVING": "Your recorded sessions are moving up.",
            "DECLINING": "Your recorded sessions came down last time.",
            "MIXED": "Some of this moved up and some came down.",
            "HOLDING": "Your recorded sessions are holding steady.",
            "NOT_ENOUGH_DATA": "Not enough recorded sessions to compare yet.",
            "NOT_RECORDED": "Nothing recorded for this part of the plan yet.",
        }[direction],
        "rows": [
            {
                "label": item["title"],
                "value": item["progress"].get("label"),
            }
            for item in items
        ],
    }


def _plan_constraints(user_state: dict, safety_result) -> list:
    """Every constraint that changed this plan — the cross-specialist layer
    the Orchestrator and the Safety Gate actually produced this cycle, said
    in their own words."""

    constraints = []

    if safety_result and safety_result.get("status") in (
        "MODIFY",
        "PAUSE",
        "REFER",
    ):
        status = safety_result["status"]

        constraints.append(
            {
                "source": SAFETY_PRACTITIONER,
                "type": {
                    "MODIFY": "modify",
                    "PAUSE": "pause",
                    "REFER": "refer",
                }[status],
                "reason": safety_result.get("reason"),
                "actions": [
                    _safety_action_wording(action)
                    for action in safety_result.get("actions") or []
                ],
                "applies_to": (
                    "all_recommendations"
                    if status == "REFER"
                    else list(
                        safety_result.get("blocked_recommendation_ids") or []
                    )
                    + list(
                        safety_result.get("modified_recommendation_ids") or []
                    )
                ),
            }
        )

    recovery = assess_recovery(build_recovery_view(user_state))

    if recovery["constraint"]["limit_progression"]:
        constraints.append(
            {
                "source": RECOVERY_CARE,
                "type": "limit_progression",
                "reason": recovery["constraint"]["reason"],
                "actions": [],
                "applies_to": [EXERCISE_MOVEMENT],
            }
        )

    activity = assess_activity(build_activity_view(user_state))

    for entry in activity["constraints"]:
        constraints.append(
            {
                "source": EXERCISE_MOVEMENT,
                "type": entry["constraint"],
                "reason": entry["detail"],
                "actions": [],
                "applies_to": [EXERCISE_MOVEMENT],
            }
        )

    return constraints


def _current_plan_id(user_state: dict):
    """The plan id of the most recently created plan record across the three
    plan sections, or None when no plan exists. Read, not invented."""

    candidates = []

    for section_name in ("exercise_history", "nutrition_plan", "behaviour"):
        record = _latest_plan_record(user_state.get(section_name) or {})

        if isinstance(record, dict) and record.get("plan_id"):
            candidates.append(
                (
                    str(record.get("created_at") or ""),
                    record["plan_id"],
                )
            )

    if not candidates:
        return None

    return sorted(candidates)[-1][1]


def _safety_block(safety_status, safety_result) -> dict:
    code = safety_status or (safety_result or {}).get("status") or "NOT_ASSESSED"

    return {
        "status": code,
        "level": STATUS_TO_LEVEL.get(code),
        "message": safety_status_message(safety_status or code),
        "reason": (safety_result or {}).get("reason"),
        "flags": list((safety_result or {}).get("flags") or []),
        "requires_referral": bool((safety_result or {}).get("requires_referral")),
        "constrains_plan": code in ("MODIFY", "PAUSE", "REFER"),
    }

def never_run_response() -> dict:
    """The shape `GET /api/workflow/latest` returns for an account that has
    never had a workflow run persisted at all.

    Lives here, beside the state model, so "no document at all" and "a
    document with no plan in it" cannot end up describing themselves in
    two different vocabularies.
    """

    return {
        "available": False,
        "message": "No recommendations have been generated yet.",
        "plan_state": {
            "state": "NEVER_RUN",
            "reason": NEVER_RUN_REASON,
            "missing": [],
            "next_action": NEXT_ACTION_ASSESSMENT,
        },
        "specialists_team": build_specialists_team({}, safety_status=None),
        # An account with nothing measured has no score, and says so rather than
        # showing a zero: "we do not know yet" is not a bad result.
        "movewell_score": build_movewell_score({}),
        # The same five-specialist, no-actions plan the plan screen reads for
        # an account with nothing recorded yet: all five present and
        # NOT_ASSESSED, and not one invented item.
        "unified_plan": build_unified_plan({}),
        "assessment_summary": {
            "status": "NONE_COMPLETED",
            "tests_completed": 0,
            "tests_total": len(_ASSESSMENT_TEST_IDS),
            "completed_tests": [],
            "remaining_tests": list(_ASSESSMENT_TEST_IDS),
            "tests": {t: "not_started" for t in _ASSESSMENT_TEST_IDS},
        },
    }
