"""The interface the Physio Agent talks to, and an honest test double for it.

`ExerciseToolClient` is the seam: the Physio Agent (agent.py) is written
against this interface only, never against `exercise_library` or
`exercise_assessment` directly. In production the only implementation that
may be wired in is `McpExerciseToolClient` (mcp_client.py) — a real MCP
client, calling the real Exercise MCP Server over a real Streamable HTTP
session. Bypassing MCP by handing the agent something else in production
would be exactly what the project's rules forbid.

`InProcessExerciseToolClient`, defined below, is NOT that. It exists only
so this project's own test suite can verify the Physio Agent's actual
decision-making (which capability it searches for, how it applies the
safety gate, how it builds a plan) deterministically, in an environment
where the `mcp` package itself cannot be installed (see mcp_client.py and
backend/mcp_servers/__init__.py for why). It implements exactly the same
interface by calling the exact same underlying functions
(`exercise_library.catalog`, `exercise_assessment.schema`) that
`backend/mcp_servers/exercise_server.py`'s tools wrap — so a test using it
is exercising the real tool *implementation*, just not the real MCP
*transport*. It is a standard test double, not a fake protocol: nothing
about it pretends a handshake, a session, or a wire-format response
occurred. It must never be constructed outside `backend/tests/`.
"""

from abc import ABC, abstractmethod


class ExerciseToolClient(ABC):
    """What the Physio Agent expects, whatever sits behind it."""

    @abstractmethod
    def search_exercises(
        self,
        *,
        target_capability: str = None,
        target_body_area: str = None,
        difficulty: str = None,
        category: str = None,
        movenet_implemented_only: bool = False,
    ) -> dict:
        """Mirrors search_exercises_tool. Returns {"exercises", "count", "metadata"}."""

    @abstractmethod
    def get_exercise_details(self, exercise_id: str) -> dict:
        """Mirrors get_exercise_details_tool. Returns {"exercise", "metadata"} or {"error", "metadata"}."""

    @abstractmethod
    def check_exercise_constraints(self, exercise_id: str) -> dict:
        """Mirrors check_exercise_constraints_tool. Returns the constraints dict or {"error", "metadata"}."""


class InProcessExerciseToolClient(ExerciseToolClient):
    """TEST-ONLY. See module docstring — never construct this outside tests."""

    def __init__(self, *, workflow_id: str, request_id: str):
        # Deferred import: this module is imported by agent.py, which must
        # be importable even when `mcp` is not installed. Keeping the
        # exercise_library/exercise_assessment imports (and the tool_call
        # metadata helper) local to this class means a plain,
        # non-MCP-installed environment can still import the Physio Agent
        # module and use this test double.
        from mcp_servers.observability import tool_call_metadata
        from orchestration.ids import TraceContext, start_agent_run

        from exercise_library.catalog import (
            ExerciseNotFoundError,
            check_exercise_constraints,
            get_exercise_details,
            search_exercises,
        )

        self._ExerciseNotFoundError = ExerciseNotFoundError
        self._catalog_search = search_exercises
        self._catalog_get_details = get_exercise_details
        self._catalog_check_constraints = check_exercise_constraints
        self._tool_call_metadata = tool_call_metadata

        # A real (agent_run_id-bearing) TraceContext, so metadata this
        # double returns is not distinguishable in shape from what the
        # real MCP client would attach — only its mcp_session_id, which is
        # honestly always None here (no real MCP session exists).
        parent = TraceContext(workflow_id=workflow_id, request_id=request_id)
        self._trace = start_agent_run(parent)

    def search_exercises(self, **kwargs) -> dict:
        results = self._catalog_search(**kwargs)

        return {
            "exercises": results,
            "count": len(results),
            "metadata": self._tool_call_metadata(self._trace),
        }

    def get_exercise_details(self, exercise_id: str) -> dict:
        try:
            exercise = self._catalog_get_details(exercise_id)

        except self._ExerciseNotFoundError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {"exercise": exercise, "metadata": self._tool_call_metadata(self._trace)}

    def check_exercise_constraints(self, exercise_id: str) -> dict:
        try:
            constraints = self._catalog_check_constraints(exercise_id)

        except self._ExerciseNotFoundError as error:
            return {"error": str(error), "metadata": self._tool_call_metadata(self._trace)}

        return {**constraints, "metadata": self._tool_call_metadata(self._trace)}
