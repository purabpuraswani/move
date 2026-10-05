"""The five user-facing MoveWell specialists, defined once.

MoveWell has more domain modules than it has specialists a person talks
about. Two of them reason about movement from different evidence — the
Physio Agent over camera-measured movement needs, the Exercise & Physical
Activity Agent over self-reported daily volume — and the product presents
them as one coach, because to the person using it there is only one
question ("what should I do about moving more?"). Safety is a supervisor
rather than a planner, so its card reports a decision (ALLOW / MODIFY /
PAUSE / REFER) rather than a programme.

This module is the single place that mapping is written down. The API
response, the plan screen and this project's own tests all read it, so a
specialist cannot be described one way to the user and another way in the
pipeline. Nothing here reads a database, calls a model or decides anything
about a user: it is naming and ordering only.

`LEGACY_ID_ALIASES` exists so that an id stored by an earlier version of
this application — `physio`, `exercise_activity`, `nutrition`, `behaviour`,
`recovery`, `safety` — still resolves to the one specialist that absorbed
it, instead of a persisted plan or a bookmarked URL silently pointing at
nothing.
"""

# --- The five ids -----------------------------------------------------------

EXERCISE_MOVEMENT = "exercise_movement"
NUTRITION_LIFESTYLE = "nutrition_lifestyle"
BEHAVIOUR_ADHERENCE = "behaviour_adherence"
RECOVERY_CARE = "recovery_care"
SAFETY_PRACTITIONER = "safety_practitioner"

# Presentation order, and the order the team is assembled in. The three
# plan-producing specialties come first (movement, nutrition, habits), then
# recovery, then the supervisor whose verdict qualifies all of them.
SPECIALIST_ORDER = (
    EXERCISE_MOVEMENT,
    NUTRITION_LIFESTYLE,
    BEHAVIOUR_ADHERENCE,
    RECOVERY_CARE,
    SAFETY_PRACTITIONER,
)

# --- The plan sections ------------------------------------------------------
#
# A section is one actionable part of the unified plan. `exercise_programme`
# and `activity_volume` both belong to the Exercise & Movement specialist:
# the first is the exercise prescription selected from the 20-exercise
# intervention library, the second is the daily-volume guidance that comes
# from the activity evidence. They are separate sections because they are
# different kinds of action (perform this / walk that much), not because
# they are different specialists.

SECTION_EXERCISE_PROGRAMME = "exercise_programme"
SECTION_ACTIVITY_VOLUME = "activity_volume"
SECTION_NUTRITION_GOALS = "nutrition_goals"
SECTION_HABIT_GOALS = "habit_goals"
SECTION_RECOVERY_GUIDANCE = "recovery_guidance"
SECTION_SAFETY_GUIDANCE = "safety_guidance"

# --- The action kinds -------------------------------------------------------
#
# What pressing the button on a plan item actually does. Every one of these
# maps to a route in the client that already exists; none of them is
# decoration on a card that only contains text.

ACTION_START_EXERCISE = "start_exercise"
ACTION_COMPLETE_HABIT = "complete_habit"
ACTION_LOG_NUTRITION = "log_nutrition"
ACTION_VIEW_GUIDANCE = "view_guidance"

SPECIALISTS = {
    EXERCISE_MOVEMENT: {
        "id": EXERCISE_MOVEMENT,
        "slug": "exercise-movement",
        "name": "Exercise & Movement",
        "title": "Exercise & Movement",
        "subtitle": "Your personalised movement coach",
        "icon": "🏃",
        "domain": "movement",
        "focus": (
            "Upper-body mobility, standing balance, everyday movement and "
            "daily activity volume"
        ),
        "sections": (
            SECTION_EXERCISE_PROGRAMME,
            SECTION_ACTIVITY_VOLUME,
        ),
        "primary_action": ACTION_START_EXERCISE,
    },
    NUTRITION_LIFESTYLE: {
        "id": NUTRITION_LIFESTYLE,
        "slug": "nutrition-lifestyle",
        "name": "Nutrition & Lifestyle",
        "title": "Nutrition & Lifestyle",
        "subtitle": "Everyday nutrition and lifestyle support",
        "icon": "🍎",
        "domain": "nutrition",
        "focus": "Everyday dietary patterns, hydration and meal regularity",
        "sections": (SECTION_NUTRITION_GOALS,),
        "primary_action": ACTION_LOG_NUTRITION,
    },
    BEHAVIOUR_ADHERENCE: {
        "id": BEHAVIOUR_ADHERENCE,
        "slug": "behaviour-adherence",
        "name": "Behaviour & Adherence",
        "title": "Behaviour & Adherence",
        "subtitle": "Habits that are actually maintainable",
        "icon": "🧠",
        "domain": "behaviour",
        "focus": "Small repeatable habits, movement breaks and routine consistency",
        "sections": (SECTION_HABIT_GOALS,),
        "primary_action": ACTION_COMPLETE_HABIT,
    },
    RECOVERY_CARE: {
        "id": RECOVERY_CARE,
        "slug": "recovery-care",
        "name": "Recovery & Care",
        "title": "Recovery & Care",
        "subtitle": "Rest, recovery and sustainable pacing",
        "icon": "🌙",
        "domain": "recovery",
        "focus": "Restorative sleep, movement spacing and workload pacing",
        "sections": (SECTION_RECOVERY_GUIDANCE,),
        "primary_action": ACTION_VIEW_GUIDANCE,
    },
    SAFETY_PRACTITIONER: {
        "id": SAFETY_PRACTITIONER,
        "slug": "safety-practitioner",
        "name": "Safety & Practitioner Recommendation",
        "title": "Safety & Practitioner Recommendation",
        "subtitle": "Reviews every recommendation before you see it",
        "icon": "🛡️",
        "domain": "safety",
        "focus": (
            "Screening recommendations against your confirmed medical "
            "information and exercise constraints"
        ),
        "sections": (SECTION_SAFETY_GUIDANCE,),
        "primary_action": ACTION_VIEW_GUIDANCE,
    },
}

# An id written by an earlier version of this application, and the one
# specialist that now covers it. Read only where a stored id or a URL has to
# be understood — never used to add a sixth card back into the team.
LEGACY_ID_ALIASES = {
    "exercise_activity": EXERCISE_MOVEMENT,
    "physio": EXERCISE_MOVEMENT,
    "exercise": EXERCISE_MOVEMENT,
    "movement": EXERCISE_MOVEMENT,
    "activity": EXERCISE_MOVEMENT,
    "nutrition": NUTRITION_LIFESTYLE,
    "diet": NUTRITION_LIFESTYLE,
    "behaviour": BEHAVIOUR_ADHERENCE,
    "behavior": BEHAVIOUR_ADHERENCE,
    "habits": BEHAVIOUR_ADHERENCE,
    "daily_habits": BEHAVIOUR_ADHERENCE,
    "recovery": RECOVERY_CARE,
    "sleep": RECOVERY_CARE,
    "safety": SAFETY_PRACTITIONER,
    "clinical": SAFETY_PRACTITIONER,
    "safety_clinical_escalation": SAFETY_PRACTITIONER,
}


def canonical_id(specialist_id):
    """The five-specialist id for any id this application has ever used, or
    None when nothing recognises it. Never guesses: an unknown id is
    unknown."""

    if not isinstance(specialist_id, str) or not specialist_id:
        return None

    if specialist_id in SPECIALISTS:
        return specialist_id

    return LEGACY_ID_ALIASES.get(specialist_id.strip().lower())


def definition(specialist_id: str) -> dict:
    """The static definition of one of the five specialists. Raises KeyError
    for anything else — there is no sixth specialist to fall back to."""

    return SPECIALISTS[specialist_id]


def describe_all() -> list:
    """Every specialist, in presentation order, as copies."""

    return [dict(SPECIALISTS[specialist_id]) for specialist_id in SPECIALIST_ORDER]


def route_for(specialist_id: str) -> str:
    """The client route that shows one specialist's detail. Derived from the
    definition's own slug, so a link and a card cannot disagree."""

    return f"/specialist/{SPECIALISTS[specialist_id]['slug']}"
