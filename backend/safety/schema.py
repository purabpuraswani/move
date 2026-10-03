"""The Safety Result contract: what the Safety Gate returns.

    {
        "status": "ALLOW",
        "flags": [],
        "actions": [],
        "reason": "...",
        "requires_referral": False,
        "modified_recommendation_ids": [],
        "blocked_recommendation_ids": [],
    }

`status` is one of ALLOW / MODIFY / PAUSE / REFER / NOT_ASSESSED — never a
free-text status, so the Orchestrator can branch on it directly.
`modified_recommendation_ids` / `blocked_recommendation_ids` name exactly
which candidate recommendation ids (by their own id field — an
exercise_id or topic_id) were changed or removed, so a caller can tell a
MODIFY/PAUSE apart from an unchanged ALLOW by inspection, not by diffing
the whole recommendation list itself.
"""

SAFETY_STATUSES = ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED")

# The same decision, said in the vocabulary a reader (and the specialist
# card) needs: what does this mean for the user? `status` stays the
# machine-readable gate outcome every caller already branches on; `level`
# is derived from it by exactly this mapping and never set independently,
# so the two can never disagree.
SAFETY_LEVELS = ("SAFE", "CAUTION", "ESCALATE", "INSUFFICIENT_INFORMATION")

STATUS_TO_LEVEL = {
    "ALLOW": "SAFE",
    "MODIFY": "CAUTION",
    "PAUSE": "CAUTION",
    "REFER": "ESCALATE",
    "NOT_ASSESSED": "INSUFFICIENT_INFORMATION",
}

REQUIRED_FIELDS = (
    "status",
    "flags",
    "actions",
    "reason",
    "requires_referral",
    "modified_recommendation_ids",
    "blocked_recommendation_ids",
)

# Added after the fields above were already in use. Optional in the
# validator so a Safety Result written before they existed still
# validates; always present on anything build_safety_result() produces.
OPTIONAL_FIELDS = ("level", "missing_safety_information")


class SafetyResultValidationError(ValueError):
    """Raised when a value does not have the shape of a valid Safety Result."""


def _fail(message: str):
    raise SafetyResultValidationError(message)


def build_safety_result(
    *,
    status: str,
    reason: str,
    flags: list = None,
    actions: list = None,
    requires_referral: bool = False,
    modified_recommendation_ids: list = None,
    blocked_recommendation_ids: list = None,
    missing_safety_information: list = None,
) -> dict:
    """Build a validated Safety Result.

    `missing_safety_information` names the specific safety-relevant
    questions this project has no answer to. It is the difference between
    "nothing suggests a concern" and "we were never told" -- the gate
    reports the second rather than treating silence as clearance.
    """

    result = {
        "status": status,
        "flags": flags if flags is not None else [],
        "actions": actions if actions is not None else [],
        "reason": reason,
        "requires_referral": bool(requires_referral),
        "modified_recommendation_ids": (
            modified_recommendation_ids if modified_recommendation_ids is not None else []
        ),
        "blocked_recommendation_ids": (
            blocked_recommendation_ids if blocked_recommendation_ids is not None else []
        ),
        "level": STATUS_TO_LEVEL.get(status),
        "missing_safety_information": (
            missing_safety_information if missing_safety_information is not None else []
        ),
    }

    validate_safety_result(result)

    return result


def validate_safety_result(result) -> None:
    if not isinstance(result, dict):
        _fail("a Safety Result must be an object")

    missing = [field for field in REQUIRED_FIELDS if field not in result]

    if missing:
        _fail(f"Safety Result missing field(s): {', '.join(missing)}")

    unexpected = set(result) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)

    if unexpected:
        _fail(f"Safety Result has unexpected field(s): {', '.join(sorted(unexpected))}")

    if result["status"] not in SAFETY_STATUSES:
        _fail(f"status must be one of {', '.join(SAFETY_STATUSES)}")

    if not isinstance(result["reason"], str) or not result["reason"].strip():
        _fail("reason must be a non-empty string")

    if "level" in result and result["level"] != STATUS_TO_LEVEL.get(result["status"]):
        _fail(
            "level must be the mapping of status "
            f"({result['status']} -> {STATUS_TO_LEVEL.get(result['status'])}), never set independently"
        )

    for field in (
        "flags",
        "actions",
        "modified_recommendation_ids",
        "blocked_recommendation_ids",
    ) + (("missing_safety_information",) if "missing_safety_information" in result else ()):
        value = result[field]

        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _fail(f"{field} must be a list of strings")

    if not isinstance(result["requires_referral"], bool):
        _fail("requires_referral must be a boolean")

    if result["status"] == "REFER" and not result["requires_referral"]:
        _fail("a REFER status must have requires_referral=True")

    # missing_safety_information is deliberately NOT in this check: a
    # NOT_ASSESSED result naming what it still needs is the point of it.
    if result["status"] == "NOT_ASSESSED" and (
        result["flags"] or result["actions"] or result["modified_recommendation_ids"]
        or result["blocked_recommendation_ids"] or result["requires_referral"]
    ):
        _fail(
            "a NOT_ASSESSED Safety Result must carry no flags/actions/"
            "modifications/blocks/referral — NOT_ASSESSED means nothing "
            "was evaluated, not that everything passed"
        )
