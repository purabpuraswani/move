"""Pure, deterministic functions over the behaviour guidance library.

Mirrors exercise_library/catalog.py and nutrition_library/catalog.py
exactly. These are the functions backend/mcp_servers/behaviour_server.py
exposes as MCP tools.
"""

from behaviour_library.data import BEHAVIOUR_TOPICS
from behaviour_library.schema import validate_behaviour_topic

for _topic in BEHAVIOUR_TOPICS:
    validate_behaviour_topic(_topic)

_BY_ID = {topic["topic_id"]: topic for topic in BEHAVIOUR_TOPICS}
_BY_SIGNAL = {}
for _topic in BEHAVIOUR_TOPICS:
    _BY_SIGNAL.setdefault(_topic["target_signal"], []).append(_topic)


class BehaviourTopicNotFoundError(LookupError):
    """Raised when a requested topic_id does not exist in the library."""


def list_topic_ids() -> list:
    return [topic["topic_id"] for topic in BEHAVIOUR_TOPICS]


def search_behaviour_guidance(
    *, target_signal: str = None, category: str = None
) -> list:
    results = list(BEHAVIOUR_TOPICS)

    if target_signal is not None:
        results = [t for t in results if t["target_signal"] == target_signal]

    if category is not None:
        results = [t for t in results if t["category"] == category]

    return results


def get_behaviour_topic_details(topic_id: str) -> dict:
    topic = _BY_ID.get(topic_id)

    if topic is None:
        raise BehaviourTopicNotFoundError(
            f"no behaviour guidance topic with id {topic_id!r} exists in the library"
        )

    return topic


def topics_for_signal(target_signal: str) -> list:
    return list(_BY_SIGNAL.get(target_signal, []))
