"""The interface the Nutrition Agent talks to, and an honest test double for it.

Mirrors physio_agent/tool_client.py exactly. `NutritionToolClient` is the
seam: the Nutrition Agent is written against this interface only, never
against nutrition_library directly. In production the only implementation
that may be wired in is `McpNutritionToolClient` (mcp_client.py) — a real
MCP client. `InProcessNutritionToolClient`, defined below, is TEST-ONLY: it
calls the exact same underlying nutrition_library.catalog functions that
mcp_servers/nutrition_server.py's tools wrap, in-process — a standard test
double, never a fake protocol. It must never be constructed outside
backend/tests/.
"""

from abc import ABC, abstractmethod


class NutritionToolClient(ABC):
    """What the Nutrition Agent expects, whatever sits behind it."""

    @abstractmethod
    def search_nutrition_guidance(
        self, *, target_signal: str = None, category: str = None
    ) -> dict:
        """Mirrors search_nutrition_guidance_tool. Returns {"topics", "count", "metadata"}."""

    @abstractmethod
    def get_nutrition_topic_details(self, topic_id: str) -> dict:
        """Mirrors get_nutrition_topic_details_tool. Returns {"topic", "metadata"} or {"error", "metadata"}."""

    # The four food tools below are declared here so every implementation
    # has one agreed signature, but they are NOT @abstractmethod: the two
    # guidance tools above are what the Nutrition Agent's plan-selection
    # actually requires, and making these abstract would retroactively
    # break every existing minimal test double that legitimately
    # implements only that pair. The default is an explicit refusal, never
    # a silent empty result that a caller could mistake for "no data".

    def search_food(self, query: str) -> dict:
        """Mirrors search_food_tool. Returns the search_foods_all_sources shape
        plus "metadata" — including which secondary food sources were
        unavailable, never a faked result from one."""

        raise NotImplementedError(
            f"{type(self).__name__} does not implement search_food"
        )

    def get_food_details(self, food_id: str) -> dict:
        """Mirrors get_food_details_tool. Returns {"food", "metadata"} (food may
        be None when the id is not in the curated dataset) or {"error", "metadata"}."""

        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_food_details"
        )

    def record_food_log(self, entry: dict, *, user_id: str, plan_id: str = None) -> dict:
        """Mirrors record_food_log_tool. Returns {"entry", "metadata"} or {"error", "metadata"}."""

        raise NotImplementedError(
            f"{type(self).__name__} does not implement record_food_log"
        )

    def calculate_food_adherence(
        self, plan_record: dict, food_log_entries: list, *, period_start=None, period_end=None
    ) -> dict:
        """Mirrors calculate_food_adherence_tool. Returns {"adherence", "metadata"} or {"error", "metadata"}."""

        raise NotImplementedError(
            f"{type(self).__name__} does not implement calculate_food_adherence"
        )


class InProcessNutritionToolClient(NutritionToolClient):
    """TEST-ONLY. See module docstring — never construct this outside tests."""

    def __init__(self, *, workflow_id: str, request_id: str):
        from mcp_servers.observability import tool_call_metadata
        from orchestration.ids import TraceContext, start_agent_run

        from nutrition_library.catalog import (
            NutritionTopicNotFoundError,
            get_food,
            get_nutrition_topic_details,
            search_foods,
            search_nutrition_guidance,
        )

        self._NutritionTopicNotFoundError = NutritionTopicNotFoundError
        self._catalog_search = search_nutrition_guidance
        self._catalog_get_details = get_nutrition_topic_details
        self._catalog_search_foods = search_foods
        self._catalog_get_food = get_food
        self._tool_call_metadata = tool_call_metadata

        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
        self._trace = start_agent_run(parent)

    def search_nutrition_guidance(self, **kwargs) -> dict:
        results = self._catalog_search(**kwargs)

        return {
            "topics": results,
            "count": len(results),
            "metadata": self._tool_call_metadata(self._trace),
        }

    def get_nutrition_topic_details(self, topic_id: str) -> dict:
        try:
            topic = self._catalog_get_details(topic_id)

        except self._NutritionTopicNotFoundError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"topic": topic, "metadata": self._tool_call_metadata(self._trace)}

    def search_food(self, query: str) -> dict:
        result = self._catalog_search_foods(query)

        return {**result, "metadata": self._tool_call_metadata(self._trace)}

    def get_food_details(self, food_id: str) -> dict:
        food = self._catalog_get_food(food_id)

        if food is None:
            return {
                "food": None,
                "reason": (
                    f"{food_id!r} is not in this project's curated Indian food "
                    "composition dataset, and the secondary sources that might "
                    "know it are unavailable in this environment"
                ),
                "metadata": self._tool_call_metadata(self._trace),
            }

        return {"food": food, "metadata": self._tool_call_metadata(self._trace)}

    def record_food_log(self, entry: dict, *, user_id: str, plan_id: str = None) -> dict:
        """Validate and persist one food log entry.

        Validation is real and always runs (food_log/schema.py needs no
        database). Persistence goes through the real, unmodified
        food_log.store, imported lazily here so that merely constructing
        this client — which the Nutrition Agent's own tests do — never
        requires pymongo to be installed. A persistence failure is
        returned as {"error": ...}, never swallowed into a fake success.
        """

        from food_log.schema import FoodLogValidationError, validate_food_log_entry

        try:
            document = validate_food_log_entry(entry)

        except FoodLogValidationError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        try:
            from food_log.store import save_food_log_entry

            saved = save_food_log_entry(user_id, document, plan_id=plan_id)

        except Exception as error:  # noqa: BLE001 — reported, never hidden
            return {
                "error": f"food log entry could not be stored: {error}",
                "metadata": self._tool_call_metadata(self._trace),
            }

        from food_log.store import serialise_food_log_entry

        return {
            "entry": serialise_food_log_entry(saved),
            "metadata": self._tool_call_metadata(self._trace),
        }

    def calculate_food_adherence(
        self, plan_record: dict, food_log_entries: list, *, period_start=None, period_end=None
    ) -> dict:
        from nutrition_agent.adherence import (
            FoodLogAdherenceError,
            compute_food_log_adherence,
        )

        try:
            adherence = compute_food_log_adherence(
                plan_record,
                food_log_entries,
                period_start=period_start,
                period_end=period_end,
            )

        except FoodLogAdherenceError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"adherence": adherence, "metadata": self._tool_call_metadata(self._trace)}
