"""Pure, deterministic functions over the exercise library.

These are exactly the functions backend/mcp_servers/exercise_server.py
exposes as MCP tools (search_exercises, get_exercise_details,
check_exercise_constraints). They are written and tested here, independent
of MCP, so the domain logic — what a "search" or a "constraint check" even
means for this library — is verifiable without the MCP SDK installed.

None of these functions touch a database, call a model, or make a decision
about what a specific user should do; that is the future Physio Agent's job,
reading from the Need Profile (backend/need_assessment/). These functions
only answer questions about the library itself.
"""

from exercise_library.data import EXERCISES
from exercise_library.schema import validate_exercise

# Validated once, at import time, so a malformed entry in data.py fails
# loudly on startup rather than surfacing as a confusing lookup bug later.
for _exercise in EXERCISES:
    validate_exercise(_exercise)

_BY_ID = {exercise["exercise_id"]: exercise for exercise in EXERCISES}


class ExerciseNotFoundError(LookupError):
    """Raised when a requested exercise_id does not exist in the library."""


def list_exercise_ids() -> list:
    return [exercise["exercise_id"] for exercise in EXERCISES]


def search_exercises(
    *,
    target_capability: str = None,
    target_body_area: str = None,
    difficulty: str = None,
    category: str = None,
    movenet_implemented_only: bool = False,
) -> list:
    """Return the exercises matching every given filter.

    Every filter is optional; calling this with no filters returns the whole
    library. An unrecognised filter value (e.g. a typo'd capability name)
    is not an error — it simply matches nothing, the same as a search that
    is too narrow, since a caller (a future agent) should be able to try a
    speculative filter without the call failing outright.
    """

    results = list(EXERCISES)

    if target_capability is not None:
        results = [e for e in results if target_capability in e["target_capability"]]

    if target_body_area is not None:
        results = [e for e in results if target_body_area in e["target_body_area"]]

    if difficulty is not None:
        results = [e for e in results if e["difficulty"] == difficulty]

    if category is not None:
        results = [e for e in results if e["category"] == category]

    if movenet_implemented_only:
        results = [e for e in results if e["movenet_support"]["implemented"]]

    return results


def get_exercise_details(exercise_id: str) -> dict:
    """Return the full exercise document. Raises ExerciseNotFoundError."""

    exercise = _BY_ID.get(exercise_id)

    if exercise is None:
        raise ExerciseNotFoundError(
            f"no exercise with id {exercise_id!r} exists in the library"
        )

    return exercise


def check_exercise_constraints(exercise_id: str) -> dict:
    """Return the safety-relevant information for one exercise.

    Deliberately a read of what is already in the library
    (`safety_constraints`, `equipment`, `difficulty`), not a personalised
    judgment about whether a specific user should do this exercise — that
    combination (this exercise's constraints against a specific user's Need
    Profile / medical context) is Physio Agent + Safety Agent work, not
    this function's. Raises ExerciseNotFoundError for an unknown id.
    """

    exercise = get_exercise_details(exercise_id)

    return {
        "exerciseId": exercise["exercise_id"],
        "difficulty": exercise["difficulty"],
        "equipmentRequired": exercise["equipment"],
        "safetyConstraints": exercise["safety_constraints"],
        "commonMistakes": exercise["common_mistakes"],
    }
