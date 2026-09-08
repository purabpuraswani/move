"""The interface the Behaviour Agent talks to, and an honest test double.

Mirrors physio_agent/tool_client.py and nutrition_agent/tool_client.py
exactly. `InProcessBehaviourToolClient` is TEST-ONLY — never construct it
outside backend/tests/.
"""

from abc import ABC, abstractmethod


class BehaviourToolClient(ABC):
    """What the Behaviour Agent expects, whatever sits behind it."""

    @abstractmethod
    def search_behaviour_guidance(
        self, *, target_signal: str = None, category: str = None
    ) -> dict:
        """Mirrors search_behaviour_guidance_tool. Returns {"topics", "count", "metadata"}."""

    @abstractmethod
    def get_behaviour_topic_details(self, topic_id: str) -> dict:
        """Mirrors get_behaviour_topic_details_tool. Returns {"topic", "metadata"} or {"error", "metadata"}."""


class InProcessBehaviourToolClient(BehaviourToolClient):
    """TEST-ONLY. See module docstring — never construct this outside tests."""

    def __init__(self, *, workflow_id: str, request_id: str):
        from mcp_servers.observability import tool_call_metadata
        from orchestration.ids import TraceContext, start_agent_run

        from behaviour_library.catalog import (
            BehaviourTopicNotFoundError,
            get_behaviour_topic_details,
            search_behaviour_guidance,
        )

        self._BehaviourTopicNotFoundError = BehaviourTopicNotFoundError
        self._catalog_search = search_behaviour_guidance
        self._catalog_get_details = get_behaviour_topic_details
        self._tool_call_metadata = tool_call_metadata

        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
        self._trace = start_agent_run(parent)

    def search_behaviour_guidance(self, **kwargs) -> dict:
        results = self._catalog_search(**kwargs)

        return {
            "topics": results,
            "count": len(results),
            "metadata": self._tool_call_metadata(self._trace),
        }

    def get_behaviour_topic_details(self, topic_id: str) -> dict:
        try:
            topic = self._catalog_get_details(topic_id)

        except self._BehaviourTopicNotFoundError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"topic": topic, "metadata": self._tool_call_metadata(self._trace)}
