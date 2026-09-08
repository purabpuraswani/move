"""Six general dietary guidance themes adapted from ICMR-NIN (2024).

Kept deliberately SEPARATE from data.py (which holds this project's
USDA MyPlate-derived topics) and from food_composition.py (which holds
food composition numbers, a different kind of content entirely), so a
reader can always tell which reference a given topic came from.

HONEST PROVENANCE, the same discipline data.py's docstring already uses:

    Every guidance / practical_goal_examples / common_barriers /
    safety_notes string below is this project's OWN plain-language
    adaptation of the broad, publicly known general themes of ICMR-NIN's
    Dietary Guidelines for Indians (2024) — eat a variety of foods, stay
    physically active, moderate salt/sugar/fat, prefer whole and
    minimally-processed foods, drink enough water, be aware of portions.
    It is NOT a verbatim quotation or a reproduction of that document
    (which could not be downloaded or checked against from this
    development environment — no network egress), and it is not a claim
    that ICMR-NIN endorses this wording or reviewed this project.

These topics reuse the EXACT shape of nutrition_library/schema.py's
existing topic document (topic_id, name, category, target_signal,
guidance, practical_goal_examples, common_barriers, safety_notes,
reference) and its existing closed vocabularies, so catalog.py can serve
both sets through one interface and validate them with one validator —
`reference` is what distinguishes the two sets.

None of these topics names a nutrient deficiency, a disease, or a
diagnosis, and none is a prescribed diet, calorie target, or supplement
recommendation.
"""

ICMR_NIN_REFERENCE = (
    "ICMR-NIN Dietary Guidelines for Indians (2024) — general themes, "
    "adapted in this project's own words (not a verbatim quotation)"
)

ICMR_NIN_TOPICS = [
    {
        "topic_id": "eat_a_variety_of_foods",
        "name": "Eat a Variety of Foods Across the Day",
        "category": "fruit_vegetable_intake",
        "target_signal": "fruit_vegetable_servings",
        "guidance": [
            "A widely repeated general theme is that no single food covers "
            "everything the body needs, so eating a variety across the day "
            "— cereals, pulses, vegetables, fruits, and a dairy or protein "
            "food — is more useful than focusing on any one item.",
            "Vegetables and fruits of different colours across a week is a "
            "simple, practical way to add variety without counting "
            "anything.",
        ],
        "practical_goal_examples": [
            "Include at least two different vegetables in one meal a day "
            "this week.",
            "Add one fruit you have not eaten this week to your shopping.",
        ],
        "common_barriers": [
            "Cooking the same two or three dishes on repeat out of habit "
            "or time pressure.",
            "Seasonal availability and cost of some produce.",
        ],
        "safety_notes": [
            "This is a general population-level pattern, not a target "
            "tailored to any medical condition.",
            "Anyone who has been told by a clinician to limit a particular "
            "food group should follow that advice instead of this general "
            "guidance.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
    {
        "topic_id": "pair_eating_with_daily_activity",
        "name": "Pair Regular Eating with Daily Physical Activity",
        "category": "meal_regularity",
        "target_signal": "meal_pattern",
        "guidance": [
            "A recurring general theme is that eating patterns and daily "
            "physical activity are discussed together, not separately — "
            "regular meals and regular movement support each other.",
            "Short, routine activity built into an ordinary day (walking, "
            "stairs, household work) is the form most people can actually "
            "sustain.",
        ],
        "practical_goal_examples": [
            "Take a ten-minute walk after one meal a day this week.",
            "Keep meal times roughly consistent on working days.",
        ],
        "common_barriers": [
            "Long sitting hours and an unpredictable schedule.",
            "Treating activity as something that needs a gym or a spare "
            "hour.",
        ],
        "safety_notes": [
            "This is general wellness guidance, not an exercise "
            "prescription — this project's own movement guidance is "
            "handled separately and is still general, not clinical.",
            "Anyone with pain, dizziness, or a clinician's restriction on "
            "activity should follow that restriction.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
    {
        "topic_id": "moderate_salt_sugar_and_fat",
        "name": "Moderate Salt, Sugar, and Cooking Fat",
        "category": "processed_food_reduction",
        "target_signal": "processed_food_frequency",
        "guidance": [
            "A general theme is moderating added salt, added sugar, and "
            "cooking fat rather than eliminating any of them — the amount "
            "and how often, not a ban.",
            "Much of the added salt and sugar in a typical day comes from "
            "packaged snacks and sweetened drinks rather than from the "
            "kitchen, so that is often the easier place to reduce first.",
        ],
        "practical_goal_examples": [
            "Stop adding extra salt at the table this week.",
            "Halve the sugar in your usual tea or coffee for one week.",
        ],
        "common_barriers": [
            "Taste preferences built up over years feel bland at first "
            "when reduced.",
            "Salt and sugar in ready-made foods are hard to see.",
        ],
        "safety_notes": [
            "This is a general wellness suggestion, not a sodium or sugar "
            "target for anyone managing a specific condition.",
            "Anyone whose clinician has given them a specific salt, sugar, "
            "or fat instruction should follow that instead.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
    {
        "topic_id": "prefer_minimally_processed_foods",
        "name": "Prefer Whole and Minimally-Processed Foods",
        "category": "processed_food_reduction",
        "target_signal": "processed_food_frequency",
        "guidance": [
            "A general theme is preferring whole or lightly processed "
            "foods — whole grains, pulses, fresh vegetables and fruit — "
            "over heavily processed packaged products, most of the time.",
            "Swapping one item at a time (a whole grain for a refined one, "
            "a fruit for a packaged snack) is more sustainable than "
            "changing everything at once.",
        ],
        "practical_goal_examples": [
            "Replace one refined-grain item a day with a whole-grain one.",
            "Keep a washed fruit visible so it is the easy snack.",
        ],
        "common_barriers": [
            "Packaged food is more convenient and stores longer.",
            "Whole-grain options are not always available or affordable "
            "locally.",
        ],
        "safety_notes": [
            "This is a general pattern, not a restrictive diet, and it "
            "does not label any food as unsafe.",
            "People with digestive conditions may have been advised to "
            "limit high-fibre whole grains; that advice comes first.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
    {
        "topic_id": "drink_enough_safe_water",
        "name": "Drink Enough Safe Water Through the Day",
        "category": "hydration",
        "target_signal": "water_glasses_per_day",
        "guidance": [
            "A general theme is drinking enough safe water spread through "
            "the day, with water rather than sweetened drinks as the "
            "default beverage.",
            "Needs rise in hot weather and with physical work, so the same "
            "fixed number of glasses does not fit every day.",
        ],
        "practical_goal_examples": [
            "Keep a filled water bottle at your desk and refill it once "
            "before lunch.",
            "Drink a glass of water with every meal this week.",
        ],
        "common_barriers": [
            "Forgetting during a busy day.",
            "Not having safe drinking water conveniently at hand.",
        ],
        "safety_notes": [
            "This is general guidance, not a fluid target for anyone whose "
            "fluid intake is medically restricted (for example some heart "
            "or kidney conditions) — their clinician's instruction comes "
            "first.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
    {
        "topic_id": "practise_portion_awareness",
        "name": "Practise Portion Awareness at Meals",
        "category": "meal_regularity",
        "target_signal": "meal_pattern",
        "guidance": [
            "A general theme is being aware of how much is on the plate "
            "and eating at a relaxed pace, rather than counting or "
            "restricting.",
            "Serving from a smaller plate or bowl, and pausing before a "
            "second helping, are the practical forms of this idea most "
            "commonly suggested.",
        ],
        "practical_goal_examples": [
            "Serve dinner in a katori/plate rather than eating from the "
            "serving dish this week.",
            "Eat one meal a day without a screen in front of you.",
        ],
        "common_barriers": [
            "Eating quickly between tasks.",
            "Social and family settings where portions are served for you.",
        ],
        "safety_notes": [
            "This is a general wellness suggestion, never a calorie limit "
            "or a weight-loss instruction.",
            "This project does not assess or address disordered eating; "
            "anyone worried about their relationship with food should "
            "speak with a doctor or registered dietitian.",
        ],
        "reference": ICMR_NIN_REFERENCE,
    },
]
