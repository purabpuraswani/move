"""The Need Profile shape: dimensions, levels, and per-dimension validation.

A Need Profile has six need dimensions, a safety status, an overall summary,
and metadata:

    mobility_need, stability_need, functional_movement_need,
    behaviour_need, nutrition_need, exercise_need,
    safety_status, overall_summary, metadata

Every dimension entry (including safety_status) shares one envelope:

    {
      "level": "LOW" | "MEDIUM" | "HIGH" | "NOT_ASSESSED",
      "score": 0.0-1.0 or null,
      "evidence": [ "..." ],
      "confidence": "NONE" | "LOW" | "MEDIUM" | "HIGH",
    }

NOT_ASSESSED is a fourth, distinct level, not a synonym for LOW. "There is
not enough information" and "the information says this need is low" are
different findings and this schema will not let them collapse into one:
validate_need_entry() below refuses a NOT_ASSESSED entry that carries a score
(there is nothing to score) and refuses an assessed entry with no evidence
(a level with no stated reason is not explainable).

`score`, where present, is a plain 0-1 number reflecting how far the
evidence sits from the system's own decision thresholds (see rules.py for
what those thresholds are and, importantly, that they are project decisions,
not clinical cutoffs). It is deliberately not reported to more than two
decimal places — a completed sit-to-stand timing does not carry enough
precision to justify a third.
"""

NEED_LEVELS = ("LOW", "MEDIUM", "HIGH", "NOT_ASSESSED")

CONFIDENCE_LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH")

NEED_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
    "behaviour_need",
    "nutrition_need",
    "exercise_need",
)

# safety_status uses the same entry envelope as a need dimension but is kept
# out of NEED_DIMENSIONS: it is a status, not an intervention-need dimension,
# and the future Orchestrator is expected to treat it differently (as an
# escalation gate, not as a "run this specialist agent" signal).
TOP_LEVEL_SECTIONS = NEED_DIMENSIONS + ("safety_status",)

NEED_PROFILE_SCHEMA_VERSION = "0.1.0"


class NeedAssessmentValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Need Profile
    or a valid dimension entry within one."""


def _fail(message: str):
    raise NeedAssessmentValidationError(message)


def build_need_entry(
    *, level: str, evidence, confidence: str, score=None
) -> dict:
    """Construct one dimension/status entry. Raises on an inconsistent shape.

    Rounds `score` to 2 decimal places rather than trusting the caller to —
    the "no artificial precision" rule is enforced here, once, rather than
    depended on at every call site in rules.py.
    """

    entry = {
        "level": level,
        "score": None if score is None else round(float(score), 2),
        "evidence": list(evidence) if evidence else [],
        "confidence": confidence,
    }

    validate_need_entry(entry)

    return entry


def validate_need_entry(entry) -> None:
    if not isinstance(entry, dict):
        _fail("a need entry must be an object")

    expected_keys = {"level", "score", "evidence", "confidence"}

    if set(entry) != expected_keys:
        _fail(
            "a need entry must have exactly the keys "
            "level/score/evidence/confidence"
        )

    if entry["level"] not in NEED_LEVELS:
        _fail(f"level must be one of {', '.join(NEED_LEVELS)}")

    if entry["confidence"] not in CONFIDENCE_LEVELS:
        _fail(f"confidence must be one of {', '.join(CONFIDENCE_LEVELS)}")

    if not isinstance(entry["evidence"], list) or any(
        not isinstance(item, str) or not item for item in entry["evidence"]
    ):
        _fail("evidence must be a list of non-empty strings")

    score = entry["score"]

    if score is not None:
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            _fail("score must be null or a number")

        if not 0.0 <= float(score) <= 1.0:
            _fail("score must be between 0.0 and 1.0")

    # The two rules that keep NOT_ASSESSED from quietly becoming LOW, or a
    # level from being reported with nothing behind it.
    if entry["level"] == "NOT_ASSESSED":
        if score is not None:
            _fail("a NOT_ASSESSED entry cannot carry a score")

        if entry["confidence"] != "NONE":
            _fail("a NOT_ASSESSED entry must have confidence NONE")

        if not entry["evidence"]:
            _fail(
                "a NOT_ASSESSED entry must still explain why (evidence must "
                "not be empty)"
            )

    else:
        if not entry["evidence"]:
            _fail(
                f"a {entry['level']} entry must carry at least one piece of "
                "evidence"
            )

        if entry["confidence"] == "NONE":
            _fail(
                f"a {entry['level']} entry cannot have confidence NONE — use "
                "NOT_ASSESSED instead if there is nothing to be confident "
                "about"
            )


def validate_need_profile(profile) -> None:
    """Raise NeedAssessmentValidationError if `profile` is not well-formed."""

    if not isinstance(profile, dict):
        _fail("a Need Profile must be an object")

    if profile.get("assessmentVersion") != NEED_PROFILE_SCHEMA_VERSION:
        _fail(
            "assessmentVersion is missing or does not match "
            f"{NEED_PROFILE_SCHEMA_VERSION!r}"
        )

    missing = [name for name in TOP_LEVEL_SECTIONS if name not in profile]

    if missing:
        _fail(f"missing section(s): {', '.join(missing)}")

    for name in TOP_LEVEL_SECTIONS:
        validate_need_entry(profile[name])

    if not isinstance(profile.get("overallSummary"), dict):
        _fail("overallSummary must be an object")

    metadata = profile.get("metadata")

    if not isinstance(metadata, dict):
        _fail("metadata must be an object")

    for key in ("assessmentVersion", "generatedAt", "workflowId", "requestId"):
        value = metadata.get(key)

        if not isinstance(value, str) or not value:
            _fail(f"metadata.{key} is required and must be a non-empty string")
