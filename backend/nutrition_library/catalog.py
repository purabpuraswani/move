"""Pure, deterministic functions over the nutrition guidance library.

Mirrors exercise_library/catalog.py exactly. These are the functions
backend/mcp_servers/nutrition_server.py exposes as MCP tools
(search_nutrition_guidance, get_nutrition_topic_details). None of these
functions touch a database, call a model, or make a decision about what a
specific user should do — that is the Nutrition Agent's job, reading from
the Need Profile (backend/need_assessment/) and the user's own answered
signals.
"""

from nutrition_library import food_composition
from nutrition_library.data import NUTRITION_TOPICS
from nutrition_library.guidance_icmr_nin import ICMR_NIN_TOPICS
from nutrition_library.schema import validate_nutrition_topic

# Both guidance sets are validated by the same validator and served
# through the same functions. They are kept as two separate constants (and
# two separate modules) so a caller can always tell which published
# reference a topic was adapted from — `reference` on each topic says so
# explicitly. NUTRITION_TOPICS is listed first everywhere, so adding the
# ICMR-NIN set never changes which topic an existing caller sees first.
ALL_NUTRITION_TOPICS = list(NUTRITION_TOPICS) + list(ICMR_NIN_TOPICS)

for _topic in ALL_NUTRITION_TOPICS:
    validate_nutrition_topic(_topic)

_BY_ID = {topic["topic_id"]: topic for topic in ALL_NUTRITION_TOPICS}

if len(_BY_ID) != len(ALL_NUTRITION_TOPICS):  # pragma: no cover — data typo guard
    raise ValueError("duplicate topic_id across the nutrition guidance sets")

_BY_SIGNAL = {}
for _topic in ALL_NUTRITION_TOPICS:
    _BY_SIGNAL.setdefault(_topic["target_signal"], []).append(_topic)


class NutritionTopicNotFoundError(LookupError):
    """Raised when a requested topic_id does not exist in the library."""


def list_topic_ids() -> list:
    return [topic["topic_id"] for topic in ALL_NUTRITION_TOPICS]


def search_nutrition_guidance(
    *, target_signal: str = None, category: str = None, include_icmr: bool = True
) -> list:
    """Return the guidance topics matching every given filter.

    All filters are optional; calling with none returns the whole
    library. An unrecognised filter value matches nothing, same discipline
    as exercise_library.catalog.search_exercises.

    `include_icmr` (default True) includes the ICMR-NIN 2024 general-theme
    topics (guidance_icmr_nin.py) alongside the original USDA MyPlate-derived
    topics (data.py). The MyPlate topics are always returned first, so a
    caller that takes results[0] — the Nutrition Agent does — keeps the
    exact behaviour it had before the ICMR-NIN set existed. Pass
    include_icmr=False to search only the original set.
    """

    results = list(ALL_NUTRITION_TOPICS) if include_icmr else list(NUTRITION_TOPICS)

    if target_signal is not None:
        results = [t for t in results if t["target_signal"] == target_signal]

    if category is not None:
        results = [t for t in results if t["category"] == category]

    return results


def get_nutrition_topic_details(topic_id: str) -> dict:
    """Return the full guidance topic. Raises NutritionTopicNotFoundError."""

    topic = _BY_ID.get(topic_id)

    if topic is None:
        raise NutritionTopicNotFoundError(
            f"no nutrition guidance topic with id {topic_id!r} exists in the library"
        )

    return topic


def topics_for_signal(target_signal: str) -> list:
    """Return the guidance topic(s) relevant to one Phase 4 nutrition signal.

    Used by the Nutrition Agent to go directly from a triggering signal
    (e.g. "fruit_vegetable_servings") to the guidance for it, without a
    caller needing to know the category taxonomy.
    """

    return list(_BY_SIGNAL.get(target_signal, []))


def search_foods(query) -> dict:
    """Search every food source for `query`.

    A thin wrapper over food_composition.search_foods_all_sources, so the
    MCP tool and the Nutrition Agent's tool client both go through this
    catalog module the same way they do for guidance. The return value
    always names which sources actually answered — the secondary sources
    (Open Food Facts, USDA FoodData Central) are reported as unavailable in
    this environment rather than silently omitted or faked.
    """

    return food_composition.search_foods_all_sources(query)


def get_food(food_id: str):
    """Return one curated food composition record, or None if there is no
    such food_id. Returns None rather than raising, matching
    food_composition.get_food_composition — a food a user typed that is not
    in the curated dataset is a normal, honest outcome, not an error, and
    is never answered with a guessed nearest match.
    """

    return food_composition.get_food_composition(food_id)
