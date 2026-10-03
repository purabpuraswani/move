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
from orchestrator.decision import (
    decide_exercise_activity_required,
    decide_recovery_required,
)
from physio_agent.agent import _movement_evidence
from recovery_agent.evidence import build_recovery_view
from recovery_agent.reasoning import assess_recovery
from safety.gate import _missing_safety_information
from safety.rules import reported_health_concerns
from safety.schema import STATUS_TO_LEVEL

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
    user_state: dict, safety_status=None, safety_result=None
) -> dict:
    """Build the user-facing workflow response from persisted user state."""

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
        "assessment_summary": _physical_assessment_summary(user_state),
    }


def build_specialists_team(user_state: dict = None, safety_status=None, safety_result=None) -> list:
    user_state = user_state or {}
    need_profile = _need_profile(user_state) or {}
    exercise_plan = _exercise_plan_summary(user_state)
    nutrition_plan = _nutrition_plan_summary(user_state)
    behaviour_plan = _behaviour_plan_summary(user_state)

    # 1. Exercise & Physical Activity
    #
    # The card shows what the Exercise & Physical Activity specialist
    # actually reasoned, by calling the same pure function the agent runs
    # (activity_agent/reasoning.py). It used to hold two fixed paragraphs
    # that every user saw word for word, whatever their step count; a card
    # that cannot differ between users is not a specialist.
    exercise_dec = decide_exercise_activity_required(user_state, need_profile)
    is_exercise_active = exercise_dec.get("exercise_activity_required", False)
    exercise_evaluated = exercise_dec.get("evaluated", False)

    activity_domain = assess_activity(build_activity_view(user_state))
    exercise_recs = (
        [
            {
                "id": item["id"],
                "title": item["title"],
                "action": item["action"],
                "why": item["why"],
            }
            for item in activity_domain["activity_recommendations"]
        ]
        if is_exercise_active
        else []
    )
    exercise_evidence = activity_domain["evidence_used"] or [
        "No daily activity answers (steps, sitting time, exercise frequency) recorded yet."
    ]
    exercise_missing = (
        activity_domain["missing_information"]
        if activity_domain["status"] == STATUS_INSUFFICIENT_EVIDENCE
        else []
    )

    exercise_status = (
        "ACTIVE"
        if is_exercise_active
        else ("EVALUATED_NOT_REQUIRED" if exercise_evaluated else "NOT_ASSESSED")
    )
    exercise_label = (
        "Active recommendation included"
        if is_exercise_active
        else (
            "Reviewed — no specific intervention required"
            if exercise_evaluated
            else "Not yet evaluated"
        )
    )

    # 2. Physiotherapy & Movement
    is_physio_active = exercise_plan.get("available", False)
    has_physio_eval = bool(
        need_profile.get("mobility_need")
        or need_profile.get("stability_need")
        or need_profile.get("functional_movement_need")
    )
    physio_status = (
        "ACTIVE"
        if is_physio_active
        else ("EVALUATED_NOT_REQUIRED" if has_physio_eval else "NOT_ASSESSED")
    )
    physio_label = (
        "Active recommendation included"
        if is_physio_active
        else (
            "Reviewed — no specific intervention required"
            if has_physio_eval
            else "Not yet evaluated"
        )
    )
    physio_reason = (
        exercise_plan.get("goal")
        or "Tailored movement exercises matched to your baseline movement assessment."
        if is_physio_active
        else (
            "Movement assessment tests showed capability within baseline norms; no corrective exercises needed."
            if has_physio_eval
            else "Complete the baseline movement check (shoulder raise, sit-to-stand, balance) to evaluate."
        )
    )
    assessed_movements, not_assessed_movements = _movement_evidence(
        (user_state.get("physical_assessment") or {}).get("data")
    )

    # What the camera actually measured, named movement by movement. An
    # unmeasured check is listed as unmeasured and never as a finding
    # about the user's movement.
    physio_evidence = [
        f"{entry['label']}: measured" for entry in assessed_movements
    ] + [
        f"{entry['label']}: not measured ({entry['status']})"
        for entry in not_assessed_movements
    ] or [
        (need_profile.get("overallSummary") or {}).get("headline")
        or "No baseline movement check has produced a usable measurement yet."
    ]

    # The full prescription for the team card: the same entries the
    # Movement panel renders (name, focus, dosage, difficulty, safety),
    # so the card can show what was actually recommended instead of a
    # single summary line. Built from the stored plan record, not
    # re-derived, so card and panel cannot disagree.
    physio_plan_record = _latest_plan_record(user_state.get("exercise_history") or {})
    physio_programme = _programme_entries(physio_plan_record) if physio_plan_record else []

    physio_recs = (
        [
            {
                "id": item.get("id"),
                "title": item.get("name"),
                "action": f"Perform {item.get('name')} as part of your movement routine.",
                "why": "Targets functional mobility and stability identified in assessment.",
            }
            for item in exercise_plan.get("exercise_items", [])
        ]
        if is_physio_active
        else []
    )

    # 3. Nutrition & Lifestyle
    is_nutrition_active = nutrition_plan.get("available", False)
    has_nutrition_eval = bool(need_profile.get("nutrition_need"))
    nutrition_status = (
        "ACTIVE"
        if is_nutrition_active
        else ("EVALUATED_NOT_REQUIRED" if has_nutrition_eval else "NOT_ASSESSED")
    )
    nutrition_label = (
        "Active recommendation included"
        if is_nutrition_active
        else (
            "Reviewed — no specific intervention required"
            if has_nutrition_eval
            else "Not yet evaluated"
        )
    )
    nutrition_reason = (
        nutrition_plan.get("goal")
        or "Nutritional guidance tailored to your recorded eating patterns and hydration."
        if is_nutrition_active
        else (
            "Reported meal patterns and dietary variety are adequate; no active nutrition intervention required."
            if has_nutrition_eval
            else "Answer the lifestyle questionnaire to evaluate everyday nutrition habits."
        )
    )
    nutrition_evidence_view = build_nutrition_evidence_view(user_state)

    nutrition_recs = (
        [
            {
                "id": f"nutrition_{i}",
                "title": goal,
                "action": f"Focus on {goal.lower()} in your daily food routine.",
                "why": "Provides evidence-based dietary balance calibrated with your health profile.",
            }
            for i, goal in enumerate(nutrition_plan.get("goals", []))
        ]
        if is_nutrition_active
        else []
    )

    # 4. Recovery & Care
    #
    # Same change as Exercise above: the card reports the Recovery
    # specialist's own finding and the constraint it placed on
    # progression, instead of two fixed sentences about sleep that were
    # shown to every user regardless of what they reported.
    recovery_dec = decide_recovery_required(user_state)
    is_recovery_active = recovery_dec.get("recovery_required", False)
    recovery_evaluated = recovery_dec.get("evaluated", False)

    recovery_domain = assess_recovery(build_recovery_view(user_state))
    recovery_recs = (
        [
            {
                "id": item["id"],
                "title": item["title"],
                "action": item["action"],
                "why": item["why"],
            }
            for item in recovery_domain["recovery_recommendations"]
        ]
        if is_recovery_active
        else []
    )
    recovery_evidence = recovery_domain["evidence_used"] or [
        "No sleep or rest answers recorded yet."
    ]
    recovery_missing = (
        recovery_domain["missing_information"]
        if recovery_domain["status"] == STATUS_INSUFFICIENT_EVIDENCE
        else []
    )
    recovery_constraint = recovery_domain["constraint"]

    recovery_status = (
        "ACTIVE"
        if is_recovery_active
        else ("EVALUATED_NOT_REQUIRED" if recovery_evaluated else "NOT_ASSESSED")
    )
    recovery_label = (
        "Active recommendation included"
        if is_recovery_active
        else (
            "Reviewed — no specific intervention required"
            if recovery_evaluated
            else "Not yet evaluated"
        )
    )

    # 5. Behaviour & Adherence
    is_behaviour_active = behaviour_plan.get("available", False)
    has_behaviour_eval = bool(need_profile.get("behaviour_need"))
    behaviour_status = (
        "ACTIVE"
        if is_behaviour_active
        else ("EVALUATED_NOT_REQUIRED" if has_behaviour_eval else "NOT_ASSESSED")
    )
    behaviour_label = (
        "Active recommendation included"
        if is_behaviour_active
        else (
            "Reviewed — no specific intervention required"
            if has_behaviour_eval
            else "Not yet evaluated"
        )
    )
    behaviour_reason = (
        behaviour_plan.get("goal")
        or "Adaptive habit routines designed to fit into your existing daily schedule."
        if is_behaviour_active
        else (
            "Daily activity pacing and routine adherence meet standard guidelines; no habit intervention needed."
            if has_behaviour_eval
            else "Answer the lifestyle questionnaire to evaluate behavioural habits."
        )
    )
    behaviour_recs = (
        [
            {
                "id": f"behaviour_{i}",
                "title": goal,
                "action": f"Practice {goal.lower()} consistently.",
                "why": "Anchoring micro-habits builds durable adherence over time.",
            }
            for i, goal in enumerate(behaviour_plan.get("goals", []))
        ]
        if is_behaviour_active
        else []
    )

    # 6. Safety & Clinical Escalation
    raw_status = safety_status or (safety_result or {}).get("status")
    has_safety_eval = raw_status is not None
    safety_code = raw_status or "NOT_ASSESSED"
    safety_label = (
        "Safety review completed — CLEAR"
        if safety_code == "ALLOW"
        else (
            "Recommendation modified for safety"
            if safety_code == "MODIFY"
            else (
                "Recommendation paused for safety"
                if safety_code == "PAUSE"
                else (
                    "Clinical escalation — Referral recommended"
                    if safety_code == "REFER"
                    else "Not yet evaluated"
                )
            )
        )
    )
    self_reported_health = (
        ((user_state.get("medical_context") or {}).get("data") or {}).get("self_reported")
        if (user_state.get("medical_context") or {}).get("available")
        else None
    )
    reported_concerns = reported_health_concerns(self_reported_health)
    # confirmed_reports is a container ({"reports": [...]}) that exists
    # even when empty, so its presence is not evidence of a report. Only a
    # non-empty reports list counts -- the same test the Orchestrator
    # applies before handing anything to the Safety Gate.
    _confirmed_container = (
        ((user_state.get("medical_context") or {}).get("data") or {}).get("confirmed_reports")
        if (user_state.get("medical_context") or {}).get("available")
        else None
    )
    confirmed_reports = (
        _confirmed_container
        if isinstance(_confirmed_container, dict) and _confirmed_container.get("reports")
        else None
    )

    safety_evidence = [
        "Reported at onboarding: "
        + (
            ", ".join(concern.replace("_", " ") for concern in reported_concerns)
            if reported_concerns
            else "no health conditions reported"
        ),
        "Confirmed medical report on file: " + ("yes" if confirmed_reports else "no"),
        "Declared difficulty of every candidate exercise is checked against this "
        "gate's ceiling before a plan is stored.",
    ]
    safety_missing = _missing_safety_information(
        need_profile, confirmed_reports, self_reported_health
    )

    safety_reason = (
        (safety_result or {}).get("reason")
        or safety_status_message(safety_code)
        if has_safety_eval
        else "Safety Gate screens all recommendations before plans are approved."
    )

    team = {
        "exercise": {
            "id": "exercise_activity",
            "alias": "exercise",
            "name": "Exercise & Physical Activity",
            "title": "Exercise & Physical Activity",
            "subtitle": "Build healthier movement and activity routines",
            "icon": "🏃",
            "evaluated": exercise_evaluated,
            "active": is_exercise_active,
            "status": exercise_status,
            "status_label": exercise_label,
            "focus": "Daily walking, step volume & sedentary reduction",
            "reason": exercise_dec.get("reason"),
            "evidence": exercise_evidence,
            "findings": activity_domain["activity_findings"],
            "progression": activity_domain["progression"],
            "constraints": activity_domain["constraints"],
            "missing_information": exercise_missing,
            "confidence": activity_domain["confidence"],
            "recommendations": exercise_recs,
        },
        "physio": {
            "id": "physio",
            "alias": "physio",
            "name": "Physiotherapy & Movement",
            "title": "Physiotherapy & Movement",
            "subtitle": "Exercises matched to your movement assessment",
            "icon": "🧑‍⚕️",
            "evaluated": has_physio_eval,
            "active": is_physio_active,
            "status": physio_status,
            "status_label": physio_label,
            "focus": "Upper-body mobility, balance & functional strength",
            "reason": physio_reason,
            # This dict previously repeated "evidence" and
            # "recommendations"; the later pair won, so the card always
            # rendered an empty programme and a generic evidence line no
            # matter what the Physio Agent had selected. One key each now,
            # carrying the agent's real output.
            "evidence": physio_evidence,
            "assessed_movements": assessed_movements,
            "not_assessed_movements": not_assessed_movements,
            "recommendations": physio_recs,
            # What to show on the card itself: the exercises, with the
            # detail needed to recognise and tick one off.
            "exercises": physio_programme if is_physio_active else [],
        },
        "nutrition": {
            "id": "nutrition",
            "alias": "nutrition",
            "name": "Nutrition & Lifestyle",
            "title": "Nutrition & Lifestyle",
            "subtitle": "Everyday nutrition and lifestyle support",
            "icon": "🍎",
            "evaluated": has_nutrition_eval,
            "active": is_nutrition_active,
            "status": nutrition_status,
            "status_label": nutrition_label,
            "focus": "Everyday dietary patterns, hydration & meal regularity",
            "reason": nutrition_reason,
            "evidence": (need_profile.get("nutrition_need") or {}).get("evidence", [])
            or nutrition_evidence_view["evidence_used"],
            # With nothing answered this is INSUFFICIENT_EVIDENCE plus the
            # specific questions still unanswered -- not generic advice to
            # eat well, which would be a recommendation with no evidence.
            "evidence_status": nutrition_evidence_view["status"],
            "missing_information": nutrition_evidence_view["missing_information"],
            "confidence": nutrition_evidence_view["confidence"],
            "recommendations": nutrition_recs,
        },
        "recovery": {
            "id": "recovery",
            "alias": "recovery",
            "name": "Recovery & Care",
            "title": "Recovery & Care",
            "subtitle": "Support rest, recovery, and sustainable routines",
            "icon": "🌙",
            "evaluated": recovery_evaluated,
            "active": is_recovery_active,
            "status": recovery_status,
            "status_label": recovery_label,
            "focus": "Restorative sleep, movement spacing & workload pacing",
            "reason": recovery_dec.get("reason"),
            "evidence": recovery_evidence,
            "findings": recovery_domain["recovery_findings"],
            "constraint": recovery_constraint,
            "missing_information": recovery_missing,
            "confidence": recovery_domain["confidence"],
            "recommendations": recovery_recs,
        },
        "behaviour": {
            "id": "behaviour",
            "alias": "behaviour",
            "name": "Behaviour & Adherence",
            "title": "Behaviour & Adherence",
            "subtitle": "Build habits that are easier to maintain",
            "icon": "🧠",
            "evaluated": has_behaviour_eval,
            "active": is_behaviour_active,
            "status": behaviour_status,
            "status_label": behaviour_label,
            "focus": "Micro-habit formation, movement breaks & routine consistency",
            "reason": behaviour_reason,
            "evidence": (need_profile.get("behaviour_need") or {}).get("evidence", []),
            "recommendations": behaviour_recs,
        },
        "safety": {
            "id": "safety",
            "alias": "safety",
            "name": "Safety & Clinical Escalation",
            "title": "Safety & Clinical Escalation",
            "subtitle": "Review recommendations for safety and escalation needs",
            "icon": "🛡️",
            "evaluated": has_safety_eval,
            "active": True,
            "status": safety_code,
            "status_label": safety_label,
            "focus": "Clinical screening, contraindications & exercise boundary safety",
            "reason": safety_reason,
            # This line used to claim self-reported conditions were
            # screened when the gate did not read them at all. The gate now
            # does read them (safety/rules.py), and this describes exactly
            # the three inputs it uses -- nothing more.
            "evidence": safety_evidence,
            "level": STATUS_TO_LEVEL.get(safety_code),
            "missing_safety_information": safety_missing,
            "flags": (safety_result or {}).get("flags", []),
            "actions": (safety_result or {}).get("actions", []),
            "requires_referral": (safety_result or {}).get("requires_referral", False),
            "recommendations": [],
        },
    }

    return list(team.values())


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
        "assessment_summary": {
            "status": "NONE_COMPLETED",
            "tests_completed": 0,
            "tests_total": len(_ASSESSMENT_TEST_IDS),
            "completed_tests": [],
            "remaining_tests": list(_ASSESSMENT_TEST_IDS),
            "tests": {t: "not_started" for t in _ASSESSMENT_TEST_IDS},
        },
    }
