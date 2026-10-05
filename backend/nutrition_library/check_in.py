"""The Nutrition & Lifestyle check-in: six questions, and what answers mean.

MoveWell's nutrition specialist could only ever report NOT_ASSESSED for most
users, because the four self-reported nutrition fields existed on the profile
but nothing in the product ever asked for them. This module is the ask: six
selectable questions, short enough to finish, and each one mapped onto a field
this project already stores or onto one new field that is genuinely new
information.

Two rules shaped it.

**No second storage.** Where a question already has a field, the question
writes that field. Fruit and vegetable *frequency* is stored as the
servings-per-day number the onboarding form already collects
(`fruit_vegetable_servings`), and water *band* as the glasses-per-day number
(`water_glasses_per_day`), so `need_assessment/rules.py`'s existing thresholds
keep working unchanged and no parallel vocabulary exists. Only three keys are
new, because only three questions had nothing behind them:
`meals_per_day`, `eating_out_frequency` and `nutrition_goal`.

**A goal is not evidence.** `nutrition_goal` is the user saying what they want
to work on. It is stored and it reaches the Nutrition Agent as context, but it
is never counted as a need factor: a stated goal is not a finding about
anybody's diet, and turning it into one would be exactly the kind of invention
this project refuses. `PREFERENCE_KEYS` marks it as such.

This module is the single definition of the check-in, so the endpoint that
serves the questions, the endpoint that validates the answers and the need
assessment that reads them cannot drift apart.
"""

MEALS_PER_DAY = "meals_per_day"
FRUIT_VEGETABLE_SERVINGS = "fruit_vegetable_servings"
WATER_GLASSES_PER_DAY = "water_glasses_per_day"
PROCESSED_FOOD_FREQUENCY = "processed_food_frequency"
EATING_OUT_FREQUENCY = "eating_out_frequency"
NUTRITION_GOAL = "nutrition_goal"

# The eating-out bands, as a closed vocabulary. Anything else counts as an
# unread answer rather than being guessed at.
EATING_OUT_TRIGGER_VALUES = frozenset(
    {"three_to_five_a_week", "almost_daily"}
)
EATING_OUT_KNOWN_VALUES = frozenset({"rarely", "one_to_two_a_week"}) | (
    EATING_OUT_TRIGGER_VALUES
)

# What the user said they want to work on. Stored, shown, and handed to the
# agent as context; never a need factor.
GOAL_VALUES = frozenset(
    {"balanced_eating", "hydration", "healthy_lifestyle", "weight_management"}
)

# Six questions, in the order they are asked. `preference: True` marks a
# question whose answer is a preference rather than a nutrition finding.
QUESTIONS = (
    {
        "key": MEALS_PER_DAY,
        "label": "Meals per day",
        "prompt": "How many meals do you usually eat in a day?",
        "options": (
            {"value": 2, "label": "1–2"},
            {"value": 3, "label": "3"},
            {"value": 4, "label": "4+"},
        ),
    },
    {
        "key": FRUIT_VEGETABLE_SERVINGS,
        "label": "Fruit & vegetables",
        "prompt": "How often do you eat fruit or vegetables?",
        # Stored as servings/day, the field onboarding already collects, so the
        # existing threshold applies to this answer too.
        "options": (
            {"value": 1, "label": "Rarely"},
            {"value": 2, "label": "Sometimes"},
            {"value": 3, "label": "Most days"},
            {"value": 5, "label": "Daily"},
        ),
    },
    {
        "key": WATER_GLASSES_PER_DAY,
        "label": "Water",
        "prompt": "How much water do you drink in a day?",
        # A band, stored in the glasses/day field so one threshold still
        # decides what counts as low.
        "options": (
            {"value": 3, "label": "Under 1 L"},
            {"value": 6, "label": "1–2 L"},
            {"value": 9, "label": "2–3 L"},
            {"value": 12, "label": "3 L or more"},
        ),
    },
    {
        "key": PROCESSED_FOOD_FREQUENCY,
        "label": "Sugary / processed snacks",
        "prompt": "How often do you eat sugary or highly processed snacks?",
        "options": (
            {"value": "rarely", "label": "Rarely"},
            {"value": "sometimes", "label": "Sometimes"},
            {"value": "often", "label": "Often"},
            {"value": "daily", "label": "Daily"},
        ),
    },
    {
        "key": EATING_OUT_FREQUENCY,
        "label": "Eating out",
        "prompt": "How often do you eat out or order in?",
        "options": (
            {"value": "rarely", "label": "Rarely"},
            {"value": "one_to_two_a_week", "label": "1–2× a week"},
            {"value": "three_to_five_a_week", "label": "3–5× a week"},
            {"value": "almost_daily", "label": "Almost daily"},
        ),
    },
    {
        "key": NUTRITION_GOAL,
        "label": "Main goal",
        "prompt": "What would you most like to work on?",
        "preference": True,
        "options": (
            {"value": "balanced_eating", "label": "Balanced eating"},
            {"value": "hydration", "label": "Hydration"},
            {"value": "healthy_lifestyle", "label": "Healthy lifestyle"},
            {"value": "weight_management", "label": "Weight management"},
        ),
    },
)

QUESTION_KEYS = tuple(question["key"] for question in QUESTIONS)

# Answers that describe what the user wants, rather than what they do. Excluded
# from the need assessment's factors.
PREFERENCE_KEYS = tuple(
    question["key"] for question in QUESTIONS if question.get("preference")
)

# Answers the need assessment may count as evidence.
FACTOR_KEYS = tuple(key for key in QUESTION_KEYS if key not in PREFERENCE_KEYS)

_BY_KEY = {question["key"]: question for question in QUESTIONS}

_OPTION_VALUES = {
    question["key"]: tuple(option["value"] for option in question["options"])
    for question in QUESTIONS
}


class CheckInAnswerError(ValueError):
    """Raised when an answer cannot be accepted for a check-in question."""


def describe() -> list:
    """The check-in as the client should render it: labels, prompts, options.

    Sent to the browser so the questions and their allowed answers are defined
    once, in the same module the validation uses.
    """

    return [
        {
            "key": question["key"],
            "label": question["label"],
            "prompt": question["prompt"],
            "preference": bool(question.get("preference")),
            "options": [dict(option) for option in question["options"]],
        }
        for question in QUESTIONS
    ]


def normalise_answer(key, value):
    """The stored form of one answer, or raise CheckInAnswerError.

    A value that is not one of the question's own options is refused rather
    than coerced, and a question the check-in does not ask is refused rather
    than stored.
    """

    if key not in _BY_KEY:
        raise CheckInAnswerError(f"{key!r} is not a nutrition check-in question")

    if value is None or value == "":
        return None

    allowed = _OPTION_VALUES[key]

    for option in allowed:
        # Values arrive from JSON, so an int option may arrive as a float. The
        # comparison is made on the number, not on the type, and the stored
        # value is always the option's own.
        if option == value:
            return option

        if isinstance(option, (int, float)) and isinstance(value, (int, float)):
            if not isinstance(value, bool) and float(option) == float(value):
                return option

    raise CheckInAnswerError(
        f"{key!r} must be one of: "
        + ", ".join(str(option) for option in allowed)
    )


def answered(profile_doc) -> dict:
    """The check-in answers present on one profile document."""

    if not isinstance(profile_doc, dict):
        return {}

    found = {}

    for key in QUESTION_KEYS:
        value = profile_doc.get(key)

        if value is None or value == "":
            continue

        try:
            found[key] = normalise_answer(key, value)
        except CheckInAnswerError:
            # A stored value this build no longer recognises is reported as
            # unanswered rather than being reinterpreted.
            continue

    return found


def unanswered_keys(profile_doc) -> list:
    present = answered(profile_doc)

    return [key for key in QUESTION_KEYS if key not in present]


def is_complete(profile_doc) -> bool:
    """Whether every question has an accepted answer."""

    return not unanswered_keys(profile_doc)
