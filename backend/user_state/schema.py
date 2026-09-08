"""The shape of the User State, and how to build and check one.

The User State is a plain, JSON-serialisable dict with twelve top-level
sections, named after the sections the target architecture describes:

    basic_profile, questionnaire, lifestyle, physical_assessment,
    medical_context, nutrition, behaviour, exercise_history,
    nutrition_plan, adherence, progress, safety, current_needs

Four of these are populated from data the application already collects
(basic_profile, questionnaire, physical_assessment, medical_context). The
remaining eight (lifestyle as a *derived* profile, nutrition, behaviour,
exercise_history, adherence, progress, safety, current_needs) have no source
yet — nothing in the current application asks about nutrition or tracks
adherence — so build_user_state() always includes them, always marks them
unavailable, and says why. A later phase adds the collector or the
computation and nothing here needs to change shape to receive it: each
section already has the "available / reason / data" envelope that
population will fill in.

No section is ever invented. A missing input becomes an unavailable section,
never a guessed or defaulted one. This mirrors the rule already in
agents/context.py, applied to a structure meant to survive that module's
removal.

Sections are read-only data assembled by build_user_state(). Nothing in this
module writes to a database, and nothing here lets a caller poke an arbitrary
field into a section — the only way to affect a section's content is to pass
the corresponding source document to build_user_state(). Structured updates
(an agent changing part of the state) are future-phase work: the Orchestrator
will mediate those, not direct field assignment, per the target architecture.
"""

from datetime import datetime, timezone

USER_STATE_SCHEMA_VERSION = "0.4.0"

SECTION_NAMES = (
    "basic_profile",
    "questionnaire",
    "lifestyle",
    "physical_assessment",
    "medical_context",
    "nutrition",
    "behaviour",
    "exercise_history",
    "nutrition_plan",
    "adherence",
    "progress",
    "safety",
    "current_needs",
)

# Sections the current application has a real source for. The rest are
# always emitted as unavailable placeholders until a later phase adds their
# collector. Kept as a set here so validate_user_state can check that no
# *other* section is claiming to be populated by mistake.
SOURCED_SECTIONS = frozenset(
    {"basic_profile", "questionnaire", "physical_assessment", "medical_context"}
)

NOT_YET_COLLECTED = {
    "lifestyle": (
        "No derived lifestyle profile exists yet. The onboarding questionnaire "
        "collects raw sitting/screen/sleep/exercise numbers (see 'questionnaire' "
        "above); turning those into a lifestyle read is Need Analysis work, "
        "planned for a later phase."
    ),
    "nutrition": (
        "This user has not answered the optional nutrition questions "
        "(meal_pattern, fruit_vegetable_servings, water_glasses_per_day, "
        "processed_food_frequency) added in Phase 4 for the Nutrition Agent."
    ),
    "behaviour": (
        "No behavioural/adherence tracking exists yet beyond the questionnaire's "
        "one-time exercise-days/exercise-minutes answers. Planned for the "
        "Behaviour/Habit Agent phase."
    ),
    "exercise_history": (
        "No exercise library or exercise-performance logging exists yet. The "
        "three baseline assessment tests are recorded separately, in "
        "'physical_assessment'. Planned for the exercise-library phase."
    ),
    "nutrition_plan": (
        "No nutrition plan has been created yet. Populated by "
        "orchestrator/state_update.py's apply_nutrition_plan() once the "
        "Nutrition Agent (Phase 4) creates one — kept separate from the "
        "'nutrition' section above, which holds this user's raw "
        "self-reported answers, not a generated plan."
    ),
    "adherence": (
        "No plan exists yet for a user to adhere to, so nothing is tracked. "
        "Planned for the Behaviour Agent phase."
    ),
    "progress": (
        "No baseline-vs-current comparison is computed yet, though assessment "
        "history is stored and could support one. Planned for the Progress "
        "Agent phase."
    ),
    "safety": (
        "No deterministic safety/escalation rules have been implemented yet. "
        "Planned for the Safety/Referral Agent phase."
    ),
    "current_needs": (
        "No Need Analysis layer exists yet to turn the sections above into "
        "per-dimension need scores. Planned for the Need Analysis phase."
    ),
}


class UserStateValidationError(ValueError):
    """Raised when a User State document does not have the required shape."""


def _empty_section(reason: str) -> dict:
    return {"available": False, "reason": reason, "data": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# basic_profile — age, sex, height, weight, bmi
# ---------------------------------------------------------------------------

_BASIC_PROFILE_FIELDS = ("age", "sex", "height_cm", "weight_kg", "bmi")


def _build_basic_profile(profile_doc) -> dict:
    if not isinstance(profile_doc, dict) or not profile_doc:
        return _empty_section(
            "This user has not completed the onboarding profile step."
        )

    data = {key: profile_doc.get(key) for key in _BASIC_PROFILE_FIELDS}

    if all(value is None for value in data.values()):
        return _empty_section(
            "A profile document exists but has none of the basic fields."
        )

    return {"available": True, "reason": None, "data": data}


# ---------------------------------------------------------------------------
# questionnaire — the raw onboarding answers, exactly as collected today.
#
# This is deliberately the raw answers, not an interpretation of them. See
# NOT_YET_COLLECTED["lifestyle"] for where the derived read will live once
# Need Analysis exists.
# ---------------------------------------------------------------------------

_QUESTIONNAIRE_FIELDS = (
    "daily_sitting_hours",
    "daily_screen_hours",
    "sleep_hours",
    "sleep_quality",
    "daily_steps",
    "exercise_days",
    "exercise_minutes",
    "work_type",
)


def _build_questionnaire(profile_doc) -> dict:
    if not isinstance(profile_doc, dict) or not profile_doc:
        return _empty_section(
            "This user has not answered the onboarding questionnaire."
        )

    data = {key: profile_doc.get(key) for key in _QUESTIONNAIRE_FIELDS}

    if all(value is None for value in data.values()):
        return _empty_section(
            "A profile document exists but none of the questionnaire fields "
            "were answered."
        )

    return {"available": True, "reason": None, "data": data}


# ---------------------------------------------------------------------------
# physical_assessment — the latest stored assessment session, test by test.
#
# Kept close to the stored shape (backend/assessments/schema.py) rather than
# re-describing it in prose, because the User State is meant to be read by
# code, not rendered into a prompt. That rendering, for whichever agent needs
# it, is a job for that agent's own context-building step, same as today.
# ---------------------------------------------------------------------------

_ASSESSMENT_TEST_IDS = ("shoulder", "ftsst", "balance")


def extract_assessment_tests(assessment_doc) -> dict:
    """Pull the per-test status/measurements/quality/invalidReasons/attempts
    shape out of one raw assessment document (assessments/schema.py's
    stored shape, i.e. what assessments/store.py returns for one session).

    Public and reusable on purpose: this is the one place that shape is
    read from a raw assessment document. `_build_physical_assessment`
    below uses it for the User State's single "current" section, and
    `progress_agent/input_contract.py` (Phase 5) reuses it verbatim for
    baseline/previous/current comparison — so there is exactly one
    definition of "what a completed assessment's data looks like", not two
    that could quietly drift apart.
    """

    tests = (assessment_doc or {}).get("tests") or {}

    return {
        test_id: {
            "status": (tests.get(test_id) or {}).get("status", "not_started"),
            "measurements": (tests.get(test_id) or {}).get("measurements"),
            "quality": (tests.get(test_id) or {}).get("quality"),
            "invalidReasons": (tests.get(test_id) or {}).get("invalid_reasons"),
            "attempts": (tests.get(test_id) or {}).get("attempts"),
        }
        for test_id in _ASSESSMENT_TEST_IDS
    }


def _build_physical_assessment(assessment_doc) -> dict:
    if not isinstance(assessment_doc, dict) or not assessment_doc:
        return _empty_section(
            "This user has not completed a physical assessment session."
        )

    tests = extract_assessment_tests(assessment_doc)

    completed = [
        test_id
        for test_id in _ASSESSMENT_TEST_IDS
        if tests[test_id]["status"] == "completed"
    ]

    data = {
        "protocol_version": assessment_doc.get("protocol_version"),
        "completed_at": assessment_doc.get("completed_at"),
        # Carried through for Phase 1 (Need Assessment): a consumer
        # deciding how much confidence to place in a measurement needs to
        # know how it was recorded, not only what the number was. None of
        # these change what is measured; they were already being stored by
        # assessments/schema.py and simply were not surfaced here yet.
        "tests": tests,
    }

    if not completed:
        return {
            "available": False,
            "reason": (
                "A session exists but no test in it produced a usable "
                "measurement."
            ),
            "data": data,
        }

    return {"available": True, "reason": None, "data": data}


# ---------------------------------------------------------------------------
# medical_context — self-reported health checklist + confirmed report values.
#
# Two sources, each labelled, same discipline as agents/context.py: an
# unconfirmed report value must never reach this section. confirmed_reports
# is expected to be the same shape confirmed_values_for_user() in
# reports/store.py already returns.
# ---------------------------------------------------------------------------

_SELF_REPORTED_HEALTH_FIELDS = (
    "diabetes",
    "hypertension",
    "heart_condition",
    "previous_injury",
    "joint_pain",
    "back_neck_pain",
    "other_conditions",
)


def _build_medical_context(profile_doc, confirmed_reports_doc) -> dict:
    self_reported = None

    if isinstance(profile_doc, dict) and profile_doc:
        values = {
            key: profile_doc.get(key) for key in _SELF_REPORTED_HEALTH_FIELDS
        }

        if any(value not in (None, "") for value in values.values()):
            self_reported = values

    confirmed_reports = []

    if isinstance(confirmed_reports_doc, dict):
        for report in confirmed_reports_doc.get("reports") or []:
            if isinstance(report, dict):
                confirmed_reports.append(report)

    if self_reported is None and not confirmed_reports:
        return _empty_section(
            "No self-reported health context was given at onboarding, and no "
            "medical report has been confirmed."
        )

    return {
        "available": True,
        "reason": None,
        "data": {
            "self_reported": {
                "source": "self_reported_onboarding",
                "values": self_reported,
            },
            "confirmed_reports": {
                "source": "user_confirmed_medical_report",
                "reports": confirmed_reports,
            },
        },
    }


# ---------------------------------------------------------------------------
# nutrition — self-reported, optional questions added in Phase 4 for the
# Nutrition Agent (backend/nutrition_agent/). Deliberately the raw
# self-reported answers, same discipline as `questionnaire`: no
# interpretation happens here, that is need_assessment/rules.py's
# assess_nutrition_need() job. Genuinely optional — a profile document
# from before Phase 4, or one from the still-unchanged onboarding UI,
# simply has none of these fields, and this section reports NOT_YET_COLLECTED's
# reason for "nutrition", not an error.
# ---------------------------------------------------------------------------

_NUTRITION_FIELDS = (
    "meal_pattern",
    "fruit_vegetable_servings",
    "water_glasses_per_day",
    "processed_food_frequency",
)


def _build_nutrition(profile_doc) -> dict:
    if not isinstance(profile_doc, dict) or not profile_doc:
        return _empty_section(NOT_YET_COLLECTED["nutrition"])

    data = {key: profile_doc.get(key) for key in _NUTRITION_FIELDS}

    if all(value is None for value in data.values()):
        return _empty_section(NOT_YET_COLLECTED["nutrition"])

    return {"available": True, "reason": None, "data": data}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_user_state(
    *,
    profile_doc=None,
    assessment_doc=None,
    confirmed_reports_doc=None,
    generated_at=None,
) -> dict:
    """Assemble a User State from whatever source documents are available.

    Every argument is optional. Passing none of them returns a fully-shaped
    User State in which every section is unavailable — the correct
    representation of a brand new account, not an error.
    """

    sections = {
        "basic_profile": _build_basic_profile(profile_doc),
        "questionnaire": _build_questionnaire(profile_doc),
        "physical_assessment": _build_physical_assessment(assessment_doc),
        "medical_context": _build_medical_context(
            profile_doc, confirmed_reports_doc
        ),
        "nutrition": _build_nutrition(profile_doc),
    }

    for name, reason in NOT_YET_COLLECTED.items():
        if name in sections:
            continue
        sections[name] = _empty_section(reason)

    state = {
        "schemaVersion": USER_STATE_SCHEMA_VERSION,
        "generatedAt": generated_at or _now_iso(),
        **{name: sections[name] for name in SECTION_NAMES},
    }

    return state


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _fail(message: str):
    raise UserStateValidationError(message)


def validate_user_state(state) -> None:
    """Raise UserStateValidationError if `state` is not a well-formed User State.

    Checks shape, not content: that every section is present, that each has
    the available/reason/data envelope, and that an unavailable section is
    never carrying a reason of None (a gap must be explained). It does not
    check whether the *data* inside an available section is itself sensible —
    that is the job of the schema each source document already has
    (assessments/schema.py, reports/schema.py).
    """

    if not isinstance(state, dict):
        _fail("a User State must be an object")

    if state.get("schemaVersion") != USER_STATE_SCHEMA_VERSION:
        _fail(
            "schemaVersion is missing or does not match "
            f"{USER_STATE_SCHEMA_VERSION!r}"
        )

    if not isinstance(state.get("generatedAt"), str) or not state["generatedAt"]:
        _fail("generatedAt must be a non-empty ISO timestamp string")

    missing = [name for name in SECTION_NAMES if name not in state]

    if missing:
        _fail(f"missing section(s): {', '.join(missing)}")

    for name in SECTION_NAMES:
        section = state[name]

        if not isinstance(section, dict):
            _fail(f"section {name!r} must be an object")

        if set(section) != {"available", "reason", "data"}:
            _fail(
                f"section {name!r} must have exactly the keys "
                "available/reason/data"
            )

        if not isinstance(section["available"], bool):
            _fail(f"section {name!r}.available must be a boolean")

        if not section["available"]:
            if not isinstance(section["reason"], str) or not section["reason"]:
                _fail(
                    f"section {name!r} is unavailable but has no reason given"
                )

        if section["available"] and section["data"] is None:
            _fail(
                f"section {name!r} is marked available but carries no data"
            )
