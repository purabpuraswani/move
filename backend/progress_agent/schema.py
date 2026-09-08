"""Progress-specific vocabularies and a findings-shape validator.

Reuses orchestration.agent_result.build_agent_result for the outer Agent
Result envelope (agent="progress" is already in KNOWN_AGENT_IDS since
Phase 0) — this module only defines what is specific to Progress: the
adaptation recommendation vocabulary, and a light structural check on the
`findings` dict this agent builds, mirroring the discipline
physio_agent/plan_schema.py and safety/schema.py already apply to their
own agent-specific shapes.
"""

from progress_agent.comparison import PROGRESS_DIRECTIONS
from progress_agent.nutrition_progress import NUTRITION_PROGRESS_STATUSES

# What the Progress Agent may recommend to the Orchestrator. The Progress
# Agent never acts on this itself — see progress_agent/agent.py and
# orchestrator/orchestrator.py's docstrings on why Progress cannot bypass
# the Orchestrator or invent an exercise/goal of its own.
ADAPTATION_RECOMMENDATIONS = (
    "CONTINUE",   # keep the current plan(s) unchanged
    "PROGRESS",   # performance improved with good adherence — advance difficulty/volume
    "MAINTAIN",   # stable performance, or improved-but-adherence-uncertain — hold steady
    "REGRESS",    # performance declined — reduce difficulty/volume
    "MODIFY",     # adherence is the limiting factor, not performance — change the approach
    "REASSESS",   # not enough recent/reliable data to decide at all
)

# Nutrition-specific adaptation vocabulary (Phase 6) — see
# progress_agent/nutrition_progress.py's module docstring for why
# PROGRESS/REGRESS are excluded: those are physical-difficulty concepts
# with no nutrition equivalent.
NUTRITION_ADAPTATION_RECOMMENDATIONS = ("CONTINUE", "MAINTAIN", "MODIFY", "REASSESS")


class ProgressFindingsValidationError(ValueError):
    """Raised when a Progress Agent's findings dict is malformed."""


def _fail(message: str):
    raise ProgressFindingsValidationError(message)


def validate_progress_findings(findings: dict) -> None:
    """Structural check only — never judges whether the *comparison itself*
    is clinically meaningful, the same limit compare_metric's own docstring
    states.
    """

    if not isinstance(findings, dict):
        _fail("findings must be an object")

    required = {"physical_comparison", "overall_direction", "adherence", "adaptation_recommendation", "reassessment"}
    missing = required - set(findings)

    if missing:
        _fail(f"findings missing field(s): {', '.join(sorted(missing))}")

    # nutrition_progress (Phase 6) is optional and, unlike the fields
    # above, may be entirely absent from a pre-Phase-6 caller's findings
    # dict — only validated when the key is present and not None, kept
    # explicitly separate from the physical-comparison fields above (see
    # progress_agent/nutrition_progress.py's module docstring).
    if findings.get("nutrition_progress") is not None:
        nutrition_progress = findings["nutrition_progress"]

        if not isinstance(nutrition_progress, dict):
            _fail("nutrition_progress must be an object or null")

        nutrition_required = {
            "status", "adherence_rate", "current_adherence_status",
            "previous_adherence_status", "evidence", "confidence",
            "adaptation_recommendation", "adaptation_reason",
        }
        nutrition_missing = nutrition_required - set(nutrition_progress)

        if nutrition_missing:
            _fail(f"nutrition_progress missing field(s): {', '.join(sorted(nutrition_missing))}")

        if nutrition_progress["status"] not in NUTRITION_PROGRESS_STATUSES:
            _fail(f"nutrition_progress.status must be one of {', '.join(NUTRITION_PROGRESS_STATUSES)}")

        if nutrition_progress["adaptation_recommendation"] not in NUTRITION_ADAPTATION_RECOMMENDATIONS:
            _fail(
                "nutrition_progress.adaptation_recommendation must be one of "
                f"{', '.join(NUTRITION_ADAPTATION_RECOMMENDATIONS)}"
            )

    if findings["overall_direction"] not in PROGRESS_DIRECTIONS:
        _fail(f"overall_direction must be one of {', '.join(PROGRESS_DIRECTIONS)}")

    if findings["adaptation_recommendation"] not in ADAPTATION_RECOMMENDATIONS:
        _fail(f"adaptation_recommendation must be one of {', '.join(ADAPTATION_RECOMMENDATIONS)}")

    reassessment = findings["reassessment"]

    if not isinstance(reassessment, dict) or set(reassessment) != {"required", "reason"}:
        _fail("reassessment must be an object with exactly 'required' and 'reason'")

    if not isinstance(reassessment["required"], bool):
        _fail("reassessment.required must be a boolean")

    if not isinstance(reassessment["reason"], str) or not reassessment["reason"].strip():
        _fail("reassessment.reason must be a non-empty string")
