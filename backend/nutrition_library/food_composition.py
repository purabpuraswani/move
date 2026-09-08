"""A curated, structured approximation of common Indian food composition.

HONEST PROVENANCE — read this before using any number below.

Every record in `FOOD_COMPOSITION` is this project's OWN curated,
plain-structured approximation of the typical composition of a common
Indian food, written from general nutrition knowledge and informed by the
general shape of published Indian food composition data. It is explicitly
NOT a verbatim reproduction, extract, or transcription of ICMR-NIN's
Indian Food Composition Tables (IFCT 2017), which is the standard
reference this project targets and which is licensed, not freely
redistributable, and could not be downloaded or checked against from this
development environment (this sandbox has no network egress at all —
confirmed: outbound HTTPS is refused by a proxy and `pip install` fails
the same way).

The numbers here are therefore REASONABLE ESTIMATES for a stated serving,
not laboratory-verified values, and they must not be presented to a user
as official IFCT figures. `source` is "IFCT_ADAPTED" and `source_version`
is "curated-approximate-v1" precisely so that no consumer of this module
can mistake it for the real dataset. The same honest-adaptation discipline
nutrition_library/data.py's USDA_MYPLATE_REFERENCE docstring already uses
applies here.

Anyone with the real IFCT 2017 dataset should replace FOOD_COMPOSITION
wholesale; nothing else in this package depends on these specific numbers,
only on the record shape.

Nothing in this module diagnoses a deficiency, prescribes a diet, sets a
calorie target, or claims dietitian review.

SECONDARY SOURCES (Open Food Facts, USDA FoodData Central) are declared in
`SECONDARY_SOURCES` as structurally present and honestly UNAVAILABLE in
this environment. No function here fabricates a result for them, and none
of them is ever called — there is no network to call them over.
"""

SOURCE = "IFCT_ADAPTED"
SOURCE_VERSION = "curated-approximate-v1"

CATEGORIES = (
    "cereal_grain",
    "pulse_legume",
    "vegetable",
    "fruit",
    "dairy",
    "prepared_dish",
    "beverage",
)

NUTRIENT_FIELDS = (
    "energy_kcal",
    "protein_g",
    "carbohydrate_g",
    "fat_g",
    "fiber_g",
)

REQUIRED_FIELDS = (
    "food_id",
    "food_name",
    "category",
    "serving_basis",
    "nutrients",
    "source",
    "source_version",
)

# Secondary sources this interface is structurally ready to consult, and
# honestly cannot in this environment. `available` is False everywhere and
# is never flipped to True by code that did not actually make a real call.
SECONDARY_SOURCES = {
    "open_food_facts": {
        "available": False,
        "reason": (
            "no network egress in this environment; would call the Open "
            "Food Facts API for packaged/branded foods"
        ),
    },
    "usda_fdc": {
        "available": False,
        "reason": (
            "no network egress in this environment; would call USDA "
            "FoodData Central for foods not in the curated Indian dataset"
        ),
    },
}


def _food(food_id, food_name, category, serving_basis, kcal, protein, carbs, fat, fiber):
    return {
        "food_id": food_id,
        "food_name": food_name,
        "category": category,
        "serving_basis": serving_basis,
        "nutrients": {
            "energy_kcal": kcal,
            "protein_g": protein,
            "carbohydrate_g": carbs,
            "fat_g": fat,
            "fiber_g": fiber,
        },
        "source": SOURCE,
        "source_version": SOURCE_VERSION,
    }


FOOD_COMPOSITION = [
    # --- cereals and grains -------------------------------------------
    _food("rice_cooked_white", "Rice (white, cooked)", "cereal_grain", "1 katori (~150g cooked)", 195, 4.0, 43.0, 0.4, 0.6),
    _food("rice_cooked_brown", "Rice (brown, cooked)", "cereal_grain", "1 katori (~150g cooked)", 200, 4.5, 41.0, 1.6, 2.4),
    _food("roti_wheat", "Roti / Chapati (whole wheat, no ghee)", "cereal_grain", "1 roti (~40g)", 105, 3.2, 20.0, 1.2, 2.6),
    _food("paratha_plain", "Paratha (plain, pan-cooked with oil)", "cereal_grain", "1 paratha (~60g)", 200, 4.0, 26.0, 8.5, 2.8),
    _food("bajra_roti", "Bajra roti (pearl millet)", "cereal_grain", "1 roti (~45g)", 120, 3.4, 21.0, 2.0, 3.2),
    _food("jowar_roti", "Jowar roti (sorghum)", "cereal_grain", "1 roti (~45g)", 115, 3.1, 22.0, 1.4, 2.8),
    _food("ragi_porridge", "Ragi porridge (finger millet, cooked)", "cereal_grain", "1 bowl (~200g cooked)", 150, 4.0, 30.0, 1.4, 4.0),
    _food("oats_cooked", "Oats (cooked in water)", "cereal_grain", "1 bowl (~200g cooked)", 155, 5.5, 27.0, 3.0, 4.0),
    _food("wheat_daliya", "Daliya (broken wheat, cooked)", "cereal_grain", "1 bowl (~200g cooked)", 175, 5.5, 35.0, 1.0, 4.5),
    _food("bread_whole_wheat", "Whole wheat bread", "cereal_grain", "2 slices (~55g)", 140, 5.0, 25.0, 2.0, 3.2),

    # --- pulses and legumes -------------------------------------------
    _food("dal_toor_cooked", "Toor dal (arhar, cooked, lightly tempered)", "pulse_legume", "1 katori (~150g cooked)", 145, 8.0, 20.0, 3.2, 4.5),
    _food("dal_moong_cooked", "Moong dal (cooked)", "pulse_legume", "1 katori (~150g cooked)", 130, 8.5, 18.0, 2.4, 4.2),
    _food("dal_masoor_cooked", "Masoor dal (red lentil, cooked)", "pulse_legume", "1 katori (~150g cooked)", 140, 8.8, 19.5, 2.6, 4.8),
    _food("dal_chana_cooked", "Chana dal (cooked)", "pulse_legume", "1 katori (~150g cooked)", 165, 8.5, 24.0, 3.4, 6.0),
    _food("rajma_cooked", "Rajma (kidney beans, cooked curry)", "pulse_legume", "1 katori (~150g cooked)", 175, 9.0, 25.0, 4.0, 7.0),
    _food("chole_cooked", "Chole (chickpea curry)", "pulse_legume", "1 katori (~150g cooked)", 190, 9.0, 27.0, 5.5, 7.5),
    _food("sprouted_moong", "Sprouted moong (raw/steamed)", "pulse_legume", "1 katori (~100g)", 100, 7.0, 15.0, 0.6, 3.5),
    _food("soya_chunks_cooked", "Soya chunks (cooked)", "pulse_legume", "1 katori (~100g cooked)", 130, 15.0, 10.0, 2.0, 3.0),

    # --- vegetables ---------------------------------------------------
    _food("mixed_vegetable_sabzi", "Mixed vegetable sabzi (lightly cooked in oil)", "vegetable", "1 katori (~150g cooked)", 110, 3.0, 13.0, 5.0, 4.0),
    _food("palak_cooked", "Palak / spinach (cooked)", "vegetable", "1 katori (~150g cooked)", 70, 3.5, 6.0, 3.5, 3.2),
    _food("bhindi_sabzi", "Bhindi (okra) sabzi", "vegetable", "1 katori (~150g cooked)", 115, 2.5, 12.0, 6.0, 4.5),
    _food("baingan_bharta", "Baingan bharta (roasted aubergine)", "vegetable", "1 katori (~150g cooked)", 120, 2.5, 12.0, 7.0, 4.5),
    _food("aloo_sabzi", "Aloo sabzi (potato, cooked in oil)", "vegetable", "1 katori (~150g cooked)", 175, 3.0, 27.0, 6.0, 3.0),
    _food("gobhi_sabzi", "Gobhi (cauliflower) sabzi", "vegetable", "1 katori (~150g cooked)", 95, 3.0, 9.0, 5.0, 3.5),
    _food("lauki_sabzi", "Lauki (bottle gourd) sabzi", "vegetable", "1 katori (~150g cooked)", 70, 1.5, 7.0, 4.0, 2.0),
    _food("carrot_raw", "Carrot (raw)", "vegetable", "1 medium (~80g)", 33, 0.8, 7.5, 0.2, 2.2),
    _food("cucumber_raw", "Cucumber (raw)", "vegetable", "1 cup sliced (~100g)", 16, 0.6, 3.5, 0.1, 0.6),
    _food("tomato_raw", "Tomato (raw)", "vegetable", "1 medium (~100g)", 20, 0.9, 4.0, 0.2, 1.2),
    _food("green_salad", "Green salad (undressed mixed raw vegetables)", "vegetable", "1 plate (~120g)", 35, 1.5, 6.5, 0.3, 2.5),

    # --- fruits -------------------------------------------------------
    _food("banana", "Banana", "fruit", "1 medium (~100g edible)", 95, 1.2, 23.0, 0.3, 1.8),
    _food("apple", "Apple (with skin)", "fruit", "1 medium (~150g)", 78, 0.4, 20.0, 0.3, 3.2),
    _food("papaya", "Papaya (ripe, cubed)", "fruit", "1 katori (~150g)", 60, 0.8, 15.0, 0.2, 2.4),
    _food("guava", "Guava", "fruit", "1 medium (~100g)", 68, 2.5, 14.0, 0.6, 5.0),
    _food("orange", "Orange (segments)", "fruit", "1 medium (~130g edible)", 60, 1.2, 14.5, 0.2, 3.0),
    _food("mango", "Mango (ripe, cubed)", "fruit", "1 katori (~150g)", 100, 1.0, 25.0, 0.5, 2.4),
    _food("watermelon", "Watermelon (cubed)", "fruit", "1 katori (~150g)", 45, 0.9, 11.0, 0.2, 0.6),
    _food("pomegranate", "Pomegranate (arils)", "fruit", "1 katori (~120g)", 95, 1.8, 22.0, 1.4, 4.5),
    _food("grapes", "Grapes", "fruit", "1 katori (~100g)", 68, 0.7, 17.0, 0.3, 1.0),

    # --- dairy --------------------------------------------------------
    _food("milk_toned", "Milk (toned, cow)", "dairy", "1 glass (~200ml)", 120, 6.4, 9.6, 6.0, 0.0),
    _food("curd_dahi", "Curd / dahi (from toned milk)", "dairy", "1 katori (~150g)", 105, 5.5, 7.5, 5.5, 0.0),
    _food("paneer", "Paneer (plain, cubed)", "dairy", "1 serving (~50g)", 145, 9.0, 2.0, 11.0, 0.0),
    _food("buttermilk_chaas", "Buttermilk / chaas (lightly salted)", "dairy", "1 glass (~200ml)", 45, 2.5, 4.5, 1.5, 0.0),
    _food("ghee", "Ghee", "dairy", "1 teaspoon (~5g)", 45, 0.0, 0.0, 5.0, 0.0),

    # --- prepared dishes ----------------------------------------------
    _food("poha", "Poha (flattened rice, cooked)", "prepared_dish", "1 bowl (~150g cooked)", 250, 4.5, 42.0, 7.0, 2.5),
    _food("upma", "Upma (semolina, cooked)", "prepared_dish", "1 bowl (~150g cooked)", 250, 5.5, 38.0, 8.5, 2.5),
    _food("idli", "Idli (steamed)", "prepared_dish", "2 idli (~120g)", 155, 4.5, 32.0, 0.6, 1.6),
    _food("dosa_plain", "Dosa (plain, pan-cooked with oil)", "prepared_dish", "1 dosa (~100g)", 175, 4.0, 27.0, 5.5, 1.5),
    _food("sambar", "Sambar (lentil and vegetable)", "prepared_dish", "1 katori (~150g)", 120, 5.0, 15.0, 4.0, 4.0),
    _food("khichdi", "Khichdi (rice and moong dal)", "prepared_dish", "1 bowl (~200g cooked)", 240, 8.5, 40.0, 5.0, 4.0),
    _food("vegetable_pulao", "Vegetable pulao", "prepared_dish", "1 bowl (~200g cooked)", 290, 6.0, 46.0, 9.0, 3.0),
    _food("chana_chaat", "Chana chaat (boiled chickpea salad)", "prepared_dish", "1 katori (~150g)", 185, 9.0, 26.0, 4.5, 7.0),
    _food("egg_boiled", "Egg (boiled)", "prepared_dish", "1 egg (~50g)", 72, 6.3, 0.4, 5.0, 0.0),
    _food("chicken_curry", "Chicken curry (home style)", "prepared_dish", "1 katori (~150g)", 220, 20.0, 5.0, 13.0, 1.0),
    _food("fish_curry", "Fish curry (home style)", "prepared_dish", "1 katori (~150g)", 180, 19.0, 4.0, 9.5, 0.8),
    _food("samosa", "Samosa (deep fried)", "prepared_dish", "1 piece (~60g)", 235, 3.5, 25.0, 13.0, 2.0),
    _food("peanut_roasted", "Roasted peanuts", "prepared_dish", "1 small handful (~25g)", 145, 6.5, 4.0, 12.0, 2.0),

    # --- beverages ----------------------------------------------------
    _food("water", "Water", "beverage", "1 glass (~250ml)", 0, 0.0, 0.0, 0.0, 0.0),
    _food("tea_with_milk_sugar", "Tea with milk and sugar", "beverage", "1 cup (~150ml)", 90, 2.0, 12.0, 3.5, 0.0),
    _food("coffee_with_milk_sugar", "Coffee with milk and sugar", "beverage", "1 cup (~150ml)", 95, 2.2, 12.5, 3.8, 0.0),
    _food("lemon_water_unsweetened", "Lemon water (unsweetened)", "beverage", "1 glass (~250ml)", 8, 0.1, 2.0, 0.0, 0.2),
    _food("sugar_sweetened_soft_drink", "Sugar-sweetened soft drink", "beverage", "1 can (~300ml)", 130, 0.0, 33.0, 0.0, 0.0),
    _food("fresh_lime_soda_sweet", "Fresh lime soda (sweetened)", "beverage", "1 glass (~250ml)", 100, 0.2, 25.0, 0.0, 0.2),
]


class FoodCompositionValidationError(ValueError):
    """Raised when a food composition record does not have a valid shape."""


def validate_food_record(record) -> None:
    """Raise FoodCompositionValidationError if `record` is malformed.

    Structural only — it cannot and does not verify that a nutrient value
    is nutritionally accurate. See this module's docstring: these are
    curated estimates, not measured values.
    """

    if not isinstance(record, dict):
        raise FoodCompositionValidationError("a food record must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in record]

    if missing:
        raise FoodCompositionValidationError(
            f"food record is missing field(s): {', '.join(missing)}"
        )

    unexpected = set(record) - set(REQUIRED_FIELDS)

    if unexpected:
        raise FoodCompositionValidationError(
            f"food record has unexpected field(s): {', '.join(sorted(unexpected))}"
        )

    food_id = record["food_id"]

    if (
        not isinstance(food_id, str)
        or not food_id
        or not all(ch.islower() or ch.isdigit() or ch == "_" for ch in food_id)
    ):
        raise FoodCompositionValidationError("food_id must be a non-empty snake_case string")

    if not isinstance(record["food_name"], str) or not record["food_name"].strip():
        raise FoodCompositionValidationError("food_name must be a non-empty string")

    if record["category"] not in CATEGORIES:
        raise FoodCompositionValidationError(
            f"category must be one of {', '.join(CATEGORIES)}"
        )

    if not isinstance(record["serving_basis"], str) or not record["serving_basis"].strip():
        raise FoodCompositionValidationError("serving_basis must be a non-empty string")

    nutrients = record["nutrients"]

    if not isinstance(nutrients, dict):
        raise FoodCompositionValidationError("nutrients must be an object")

    if set(nutrients) != set(NUTRIENT_FIELDS):
        raise FoodCompositionValidationError(
            f"nutrients must have exactly the fields {', '.join(NUTRIENT_FIELDS)}"
        )

    for field, value in nutrients.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise FoodCompositionValidationError(
                f"nutrients.{field} must be a non-negative number, got {value!r}"
            )

    if record["source"] != SOURCE:
        raise FoodCompositionValidationError(f"source must be {SOURCE!r}")

    if record["source_version"] != SOURCE_VERSION:
        raise FoodCompositionValidationError(f"source_version must be {SOURCE_VERSION!r}")


for _record in FOOD_COMPOSITION:
    validate_food_record(_record)

_BY_ID = {record["food_id"]: record for record in FOOD_COMPOSITION}

if len(_BY_ID) != len(FOOD_COMPOSITION):  # pragma: no cover — a data typo guard
    raise FoodCompositionValidationError("duplicate food_id in FOOD_COMPOSITION")


def list_food_ids() -> list:
    return [record["food_id"] for record in FOOD_COMPOSITION]


def get_food_composition(food_id):
    """Return the curated record for `food_id`, or None if there is none.

    Returns None rather than raising, so a caller looking a food up by a
    user-typed id gets an honest "not in the curated dataset" instead of
    an exception path — and never a guessed nearest match.
    """

    if not isinstance(food_id, str):
        return None

    return _BY_ID.get(food_id)


def search_food_composition(query) -> list:
    """Case-insensitive substring match over food_name and category.

    Deterministic and dumb on purpose: no fuzzy matching, no ranking
    model, no spelling correction. An empty/blank query returns the whole
    curated dataset, in its declared order; a query matching nothing
    returns an empty list rather than a nearest guess.
    """

    if query is None or (isinstance(query, str) and not query.strip()):
        return list(FOOD_COMPOSITION)

    if not isinstance(query, str):
        return []

    needle = query.strip().lower()

    return [
        record
        for record in FOOD_COMPOSITION
        if needle in record["food_name"].lower() or needle in record["category"].lower()
    ]


def search_foods_all_sources(query) -> dict:
    """Search every food source this project knows about, and say plainly
    which of them actually answered.

    Only the curated Indian dataset can answer here. The secondary sources
    are reported as consulted-but-unavailable with their real reason, so a
    caller (and a user) can tell the difference between "no such food" and
    "we could not reach the source that would know". No entry in
    `results` ever comes from a source marked unavailable.
    """

    results = search_food_composition(query)

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "primary_source": {
            "name": "curated_indian_food_composition",
            "source": SOURCE,
            "source_version": SOURCE_VERSION,
            "available": True,
        },
        "secondary_sources_consulted": SECONDARY_SOURCES,
    }
