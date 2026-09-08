"""Four general nutrition guidance topics, as data — one per Phase 4
self-reported signal (user_state/schema.py's `nutrition` section).

Drafted from a single public, freely citable source aimed at general
dietary patterns for the general adult population — not a clinical or
disease-specific guideline:

    USDA MyPlate    U.S. Department of Agriculture's current dietary
                     guidance system (myplate.gov), reflecting the Dietary
                     Guidelines for Americans. Confirmed to publish general
                     patterns this project draws on: filling half your
                     plate with fruits and vegetables, and choosing water
                     over sugary drinks.

Every `guidance`/`practical_goal_examples`/`common_barriers`/`safety_notes`
string below is this project's own plain-language adaptation — not a
verbatim quotation, and not a claim that USDA endorses this exact wording
or reviewed this project. `reference` records the source each entry was
adapted from. None of these four topics names a nutrient deficiency, a
disease, or a diagnosis, and none is a prescribed diet or calorie target.
"""

USDA_MYPLATE_REFERENCE = (
    "U.S. Department of Agriculture – MyPlate general dietary guidance "
    "(myplate.gov), reflecting the Dietary Guidelines for Americans"
)

NUTRITION_TOPICS = [
    {
        "topic_id": "build_a_regular_meal_pattern",
        "name": "Build a Regular Meal Pattern",
        "category": "meal_regularity",
        "target_signal": "meal_pattern",
        "guidance": [
            "Aim for a consistent number of meals at roughly similar times "
            "each day, rather than skipping meals or eating at very "
            "irregular times.",
            "A planned small snack can help if a long gap between meals "
            "leads to skipping the next one.",
        ],
        "practical_goal_examples": [
            "Eat breakfast within two hours of waking, most days this week.",
            "Plan tomorrow's lunch tonight, so it isn't skipped.",
        ],
        "common_barriers": [
            "A busy or unpredictable work schedule.",
            "Not having food prepared or available when hungry.",
        ],
        "safety_notes": [
            "This is a general wellness suggestion, not a prescribed "
            "eating schedule or calorie plan.",
            "This project does not assess or address disordered eating; "
            "someone concerned about their relationship with food should "
            "speak with a doctor or registered dietitian.",
        ],
        "reference": USDA_MYPLATE_REFERENCE,
    },
    {
        "topic_id": "increase_fruit_vegetable_intake",
        "name": "Increase Fruit and Vegetable Intake",
        "category": "fruit_vegetable_intake",
        "target_signal": "fruit_vegetable_servings",
        "guidance": [
            "A commonly used general target is filling about half of each "
            "plate with fruits and vegetables across the day.",
            "Frozen and canned (no-sugar-added / low-sodium) fruits and "
            "vegetables count and can be a practical, lower-cost option.",
        ],
        "practical_goal_examples": [
            "Add one extra serving of vegetables to dinner this week.",
            "Keep a piece of fruit somewhere visible as a snack option.",
        ],
        "common_barriers": [
            "Cost or availability of fresh produce.",
            "Limited time to prepare fresh fruits and vegetables.",
        ],
        "safety_notes": [
            "This is a general population-level pattern, not a target "
            "tailored to any medical condition (for example, kidney or "
            "GI conditions can change what is appropriate) — a user with "
            "a relevant confirmed medical condition should check with a "
            "doctor or dietitian before changing intake substantially.",
        ],
        "reference": USDA_MYPLATE_REFERENCE,
    },
    {
        "topic_id": "build_a_hydration_habit",
        "name": "Build a Hydration Habit",
        "category": "hydration",
        "target_signal": "water_glasses_per_day",
        "guidance": [
            "A general suggestion is choosing water over sugar-sweetened "
            "drinks as the main daily beverage.",
            "Keeping a water bottle within reach through the day is a "
            "common practical way to increase intake gradually.",
        ],
        "practical_goal_examples": [
            "Have a glass of water with each meal this week.",
            "Replace one sugar-sweetened drink a day with water.",
        ],
        "common_barriers": [
            "Forgetting to drink water across a busy day.",
            "Preferring the taste of sweetened beverages.",
        ],
        "safety_notes": [
            "This is general guidance, not a fluid-intake target for "
            "someone with a heart, kidney, or other condition where fluid "
            "intake is medically restricted — anyone with a relevant "
            "confirmed medical condition should follow their clinician's "
            "guidance instead.",
        ],
        "reference": USDA_MYPLATE_REFERENCE,
    },
    {
        "topic_id": "reduce_processed_food_frequency",
        "name": "Reduce Highly Processed Food Frequency",
        "category": "processed_food_reduction",
        "target_signal": "processed_food_frequency",
        "guidance": [
            "A general pattern is limiting how often highly processed, "
            "high-sugar, or high-sodium packaged foods make up a meal, "
            "in favor of less processed options when practical.",
            "Small, gradual swaps (for example, plain instead of "
            "flavored/sweetened versions of a food) tend to be more "
            "sustainable than an all-or-nothing change.",
        ],
        "practical_goal_examples": [
            "Swap one processed snack a day for a fruit, vegetable, or "
            "nuts.",
            "Cook one more meal at home this week than usual.",
        ],
        "common_barriers": [
            "Processed food is often more convenient and shelf-stable.",
            "Cost, time, or skill barriers to cooking from less-processed "
            "ingredients.",
        ],
        "safety_notes": [
            "This is a general wellness suggestion, not a restrictive "
            "diet, and it does not name or exclude any specific food "
            "group as unsafe.",
        ],
        "reference": USDA_MYPLATE_REFERENCE,
    },
]
