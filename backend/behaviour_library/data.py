"""Four general behaviour-change guidance topics, as data — one per real
questionnaire signal already read by
need_assessment.rules.assess_behaviour_need() (daily_sitting_hours,
daily_screen_hours, exercise_days, and exercise_days*exercise_minutes as a
weekly-volume proxy).

Drafted from one public, freely citable source:

    WHO Guidelines    World Health Organization, "WHO guidelines on
                       physical activity and sedentary behaviour" (2020),
                       who.int/publications-detail-redirect/9789240015128.
                       General recommendation: adults should limit the
                       amount of time spent being sedentary, and replace
                       sedentary time with physical activity of any
                       intensity, for additional health benefit.

Every `guidance`/`practical_goal_examples`/`common_barriers`/`safety_notes`
string below is this project's own plain-language adaptation, not a
verbatim quotation and not a claim of WHO endorsement or review. `reference`
records the source each entry was adapted from. None of these four topics
names or claims to treat a mental health condition, a motivational
disorder, or any diagnosis.
"""

WHO_SEDENTARY_BEHAVIOUR_REFERENCE = (
    "World Health Organization – WHO guidelines on physical activity and "
    "sedentary behaviour (2020), who.int/publications-detail-redirect/"
    "9789240015128 – general recommendation to limit sedentary time and "
    "replace it with activity of any intensity"
)

BEHAVIOUR_TOPICS = [
    {
        "topic_id": "take_regular_movement_breaks",
        "name": "Take Regular Movement Breaks",
        "category": "movement_breaks",
        "target_signal": "daily_sitting_hours",
        "guidance": [
            "General guidance is to limit total sedentary time where "
            "practical, and to replace some sitting time with standing or "
            "movement of any intensity through the day.",
            "A short break to stand, stretch, or walk during a long "
            "period of sitting is a common, low-effort way to do this.",
        ],
        "practical_goal_examples": [
            "Stand up and move for one to two minutes once each hour "
            "during the work day.",
            "Take a short walk during a lunch break instead of sitting "
            "the whole time.",
        ],
        "common_barriers": [
            "A desk job with back-to-back meetings or tasks.",
            "Forgetting to break up sitting time without a reminder.",
        ],
        "safety_notes": [
            "This is general population-level guidance, not a claim that "
            "this user has any specific condition related to sitting.",
        ],
        "reference": WHO_SEDENTARY_BEHAVIOUR_REFERENCE,
    },
    {
        "topic_id": "build_screen_time_boundaries",
        "name": "Build Screen-Time Boundaries",
        "category": "screen_time",
        "target_signal": "daily_screen_hours",
        "guidance": [
            "Screen time is often a large share of sedentary time; setting "
            "a boundary around recreational (non-work) screen time is one "
            "practical way to open room for movement.",
            "Pairing screen use with a small amount of movement (for "
            "example, standing during a call) can help when eliminating "
            "screen time is not realistic.",
        ],
        "practical_goal_examples": [
            "Set a specific stop time for recreational screen use on "
            "workdays.",
            "Stand or stretch during at least one video call or show per "
            "day.",
        ],
        "common_barriers": [
            "Screens are often required for work, not just leisure.",
            "Habitual or automatic screen use (picking up a phone without "
            "deciding to).",
        ],
        "safety_notes": [
            "This is a general habit suggestion, not an assessment of "
            "problematic technology use or any related condition.",
        ],
        "reference": WHO_SEDENTARY_BEHAVIOUR_REFERENCE,
    },
    {
        "topic_id": "increase_exercise_frequency_gradually",
        "name": "Increase Exercise Frequency Gradually",
        "category": "exercise_frequency",
        "target_signal": "exercise_days",
        "guidance": [
            "Where current exercise frequency is low, a gradual increase "
            "in the number of active days per week — rather than a large "
            "jump — is a common, sustainable approach.",
            "Starting from whatever is realistic (even one additional day "
            "a week) tends to support longer-term adherence better than "
            "an ambitious plan that is hard to keep up.",
        ],
        "practical_goal_examples": [
            "Add one more active day this week compared to a typical "
            "week.",
            "Pick a fixed day and time for a short activity session and "
            "keep it for two weeks.",
        ],
        "common_barriers": [
            "Limited time or energy after work or other responsibilities.",
            "Not having an established routine to build the new day "
            "into.",
        ],
        "safety_notes": [
            "A gradual increase is suggested specifically because a large, "
            "sudden increase in activity is a more common source of "
            "overuse strain — this is a pacing suggestion, not a medical "
            "clearance to exercise.",
        ],
        "reference": WHO_SEDENTARY_BEHAVIOUR_REFERENCE,
    },
    {
        "topic_id": "anchor_activity_to_an_existing_routine",
        "name": "Anchor Activity to an Existing Routine",
        "category": "routine_building",
        "target_signal": "weekly_exercise_minutes",
        "guidance": [
            "Attaching a new activity to something already part of the "
            "daily routine (a habit anchor) is a commonly used, practical "
            "way to make a new habit more likely to stick than relying on "
            "willpower alone.",
            "Small, consistent sessions across the week are a reasonable "
            "way to build total weekly activity time gradually.",
        ],
        "practical_goal_examples": [
            "Do a short activity session right after an existing daily "
            "habit (for example, right after morning coffee).",
            "Keep sessions short (5-10 minutes) at first and build up "
            "duration over time.",
        ],
        "common_barriers": [
            "No existing daily routine consistent enough to anchor to.",
            "Low motivation on days when the routine is disrupted.",
        ],
        "safety_notes": [
            "This is a habit-formation suggestion, not a therapeutic "
            "intervention, and does not diagnose or address a motivation "
            "or mood condition.",
        ],
        "reference": WHO_SEDENTARY_BEHAVIOUR_REFERENCE,
    },
]
