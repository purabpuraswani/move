"""The Progress Agent's structured input contract, and how it is built.

Mirrors physio_agent/input_contract.py's data-minimization discipline.
The Orchestrator (or, in this project's own tests, a test fixture standing
in for it) builds this from real, already-stored data — never from raw
webcam frames or MoveNet keypoints, which cannot even reach this contract:
`baseline_assessment`/`previous_assessment`/`current_assessment` are each
either None or one raw assessment document (assessments/schema.py's
stored shape, exactly what assessments/store.py already returns for one
session — the same shape `user_state.schema.extract_assessment_tests`
already knows how to read).

`exercise_history` is the User State's own `exercise_history` section data
(the plan-creation records orchestrator/state_update.py already writes) —
never fabricated performance data. `exercise_results` is the new,
Phase-5-added real performance history (exercise_assessment/store.py).
`previous_plan`/`current_plan` are two specific plan records out of that
same history (the caller picks which two — typically the two most recent
versions of one agent's plan), so the Progress Agent can be told "compare
these two plans" without guessing which pair matters.

Phase 6 addition — nutrition progress, kept as its own, clearly separate
set of fields rather than overloading the physical ones above:
`nutrition_plan` is one nutrition_plan history record (the User State's
own `nutrition_plan` section, orchestrator/state_update.py's
apply_nutrition_plan output shape). `nutrition_food_log_previous_period`
and `nutrition_food_log_current_period` are each a list of already-stored
food_log documents (food_log/store.py's shape) covering one observation
window each; `nutrition_period_previous`/`nutrition_period_current` are
each `{"start": ..., "end": ...}` naming that window. Comparing two
periods (rather than a single snapshot) is what lets nutrition progress
describe a *trend in logged adherence* — never a physical or health
outcome claim, and never fabricated from a single period alone. All five
default to None: a caller with no nutrition context to report (most
runs) gets a Progress Agent result with `findings["nutrition_progress"]
is None`, never a guessed value.
"""

from orchestration.pose_boundary import find_pose_or_media_violation

REQUIRED_FIELDS = (
    "workflow_id",
    "request_id",
    "agent_run_id",
    "baseline_assessment",
    "previous_assessment",
    "current_assessment",
    "exercise_history",
    "exercise_results",
    "adherence",
    "previous_plan",
    "current_plan",
    "current_needs",
    "nutrition_plan",
    "nutrition_food_log_previous_period",
    "nutrition_food_log_current_period",
    "nutrition_period_previous",
    "nutrition_period_current",
)



class ProgressAgentInputValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Progress Agent input."""


def _fail(message: str):
    raise ProgressAgentInputValidationError(message)


def build_progress_agent_input(
    *,
    workflow_id: str,
    request_id: str,
    agent_run_id: str,
    baseline_assessment: dict = None,
    previous_assessment: dict = None,
    current_assessment: dict = None,
    exercise_history: dict = None,
    exercise_results: list = None,
    adherence: dict = None,
    previous_plan: dict = None,
    current_plan: dict = None,
    current_needs: dict = None,
    nutrition_plan: dict = None,
    nutrition_food_log_previous_period: list = None,
    nutrition_food_log_current_period: list = None,
    nutrition_period_previous: dict = None,
    nutrition_period_current: dict = None,
) -> dict:
    """Build the Progress Agent input. Unlike the other agents' input
    builders, this one does not read a User State directly (there is no
    single User State section holding "assessment history" — see
    docs/architecture.md's Phase 5 section for why) — the caller passes
    each already-fetched piece explicitly, so it is unambiguous which
    baseline/previous/current documents were actually used.
    """

    payload = {
        "workflow_id": workflow_id,
        "request_id": request_id,
        "agent_run_id": agent_run_id,
        "baseline_assessment": baseline_assessment,
        "previous_assessment": previous_assessment,
        "current_assessment": current_assessment,
        "exercise_history": exercise_history,
        "exercise_results": exercise_results if exercise_results is not None else [],
        "adherence": adherence,
        "previous_plan": previous_plan,
        "current_plan": current_plan,
        "current_needs": current_needs,
        "nutrition_plan": nutrition_plan,
        "nutrition_food_log_previous_period": (
            nutrition_food_log_previous_period
            if nutrition_food_log_previous_period is not None
            else []
        ),
        "nutrition_food_log_current_period": (
            nutrition_food_log_current_period
            if nutrition_food_log_current_period is not None
            else []
        ),
        "nutrition_period_previous": nutrition_period_previous,
        "nutrition_period_current": nutrition_period_current,
    }

    validate_progress_agent_input(payload)

    return payload


def validate_progress_agent_input(payload) -> None:
    if not isinstance(payload, dict):
        _fail("a Progress Agent input must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in payload]

    if missing:
        _fail(f"missing field(s): {', '.join(missing)}")

    unexpected = set(payload) - set(REQUIRED_FIELDS)

    if unexpected:
        _fail(f"unexpected field(s): {', '.join(sorted(unexpected))}")

    for key in ("workflow_id", "request_id", "agent_run_id"):
        if not isinstance(payload[key], str) or not payload[key]:
            _fail(f"{key} must be a non-empty string")

    for key in (
        "baseline_assessment", "previous_assessment", "current_assessment",
        "exercise_history", "adherence", "previous_plan", "current_plan",
        "current_needs", "nutrition_plan", "nutrition_period_previous",
        "nutrition_period_current",
    ):
        if payload[key] is not None and not isinstance(payload[key], dict):
            _fail(f"{key} must be null or an object")

    if not isinstance(payload["exercise_results"], list):
        _fail("exercise_results must be a list")

    for key in ("nutrition_food_log_previous_period", "nutrition_food_log_current_period"):
        if not isinstance(payload[key], list):
            _fail(f"{key} must be a list")

    # Same second line of defence every other agent input contract applies,
    # from one shared implementation (orchestration/pose_boundary.py): nothing
    # shaped like raw pose/frame/video data may cross this boundary, while the
    # scalar quality summaries a real assessment carries still pass.
    violation = find_pose_or_media_violation(payload)

    if violation:
        _fail(f"Progress Agent input {violation}")
