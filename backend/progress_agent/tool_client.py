"""The interface the Progress Agent talks to, and an honest test double.

Mirrors physio_agent/tool_client.py, nutrition_agent/tool_client.py, and
behaviour_agent/tool_client.py exactly. `InProcessProgressToolClient` is
TEST-ONLY — never construct it outside backend/tests/.
"""

from abc import ABC, abstractmethod


class ProgressToolClient(ABC):
    """What the Progress Agent expects, whatever sits behind it."""

    @abstractmethod
    def compare_assessments(
        self, *, baseline_assessment=None, previous_assessment=None, current_assessment=None
    ) -> dict:
        """Mirrors compare_assessments_tool. Returns {"comparison", "metadata"}."""

    @abstractmethod
    def calculate_adherence(self, *, plan_record, exercise_results=None) -> dict:
        """Mirrors calculate_adherence_tool. Returns {"adherence", "metadata"} or {"error", "metadata"}."""

    @abstractmethod
    def check_reassessment_required(self, *, current_assessment_completed_at=None) -> dict:
        """Mirrors check_reassessment_required_tool. Returns {"required", "reason", "metadata"}."""

    def calculate_nutrition_adherence(
        self, *, nutrition_plan, food_log_entries=None, period_start=None, period_end=None
    ) -> dict:
        """Mirrors calculate_nutrition_adherence_tool. Returns
        {"adherence", "metadata"} or {"error", "metadata"}. Concrete (not
        abstract) so existing test doubles built before Phase 6's nutrition
        extension — which only implement the three original methods above —
        keep working unchanged; a caller that actually needs this on a
        pre-Phase-6 test double gets a clear NotImplementedError rather than
        a silent wrong answer."""

        raise NotImplementedError(
            f"{type(self).__name__} does not implement calculate_nutrition_adherence()"
        )


class InProcessProgressToolClient(ProgressToolClient):
    """TEST-ONLY. See module docstring — never construct this outside tests."""

    def __init__(self, *, workflow_id: str, request_id: str):
        from mcp_servers.observability import tool_call_metadata
        from orchestration.ids import TraceContext, start_agent_run

        from progress_agent.adherence import AdherenceCalculationError, compute_plan_adherence
        from progress_agent.comparison import compare_physical_assessments
        from progress_agent.reassessment import check_reassessment_required

        from nutrition_agent.adherence import FoodLogAdherenceError, compute_food_log_adherence

        self._FoodLogAdherenceError = FoodLogAdherenceError
        self._compute_food_log_adherence = compute_food_log_adherence

        self._AdherenceCalculationError = AdherenceCalculationError
        self._compare_physical_assessments = compare_physical_assessments
        self._compute_plan_adherence = compute_plan_adherence
        self._check_reassessment_required = check_reassessment_required
        self._tool_call_metadata = tool_call_metadata

        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
        self._trace = start_agent_run(parent)

    def compare_assessments(self, *, baseline_assessment=None, previous_assessment=None, current_assessment=None) -> dict:
        comparison = self._compare_physical_assessments(
            baseline_assessment, previous_assessment, current_assessment
        )

        return {"comparison": comparison, "metadata": self._tool_call_metadata(self._trace)}

    def calculate_adherence(self, *, plan_record, exercise_results=None) -> dict:
        try:
            adherence = self._compute_plan_adherence(plan_record, exercise_results or [])

        except self._AdherenceCalculationError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"adherence": adherence, "metadata": self._tool_call_metadata(self._trace)}

    def check_reassessment_required(self, *, current_assessment_completed_at=None) -> dict:
        result = self._check_reassessment_required(current_assessment_completed_at)

        return {**result, "metadata": self._tool_call_metadata(self._trace)}

    def calculate_nutrition_adherence(
        self, *, nutrition_plan, food_log_entries=None, period_start=None, period_end=None
    ) -> dict:
        try:
            adherence = self._compute_food_log_adherence(
                nutrition_plan,
                food_log_entries or [],
                period_start=period_start,
                period_end=period_end,
            )

        except self._FoodLogAdherenceError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"adherence": adherence, "metadata": self._tool_call_metadata(self._trace)}
