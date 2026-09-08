"""Storage and retrieval for assessment sessions.

Two rules shape this module.

Ownership is enforced in the query, not after it. Every read filters on
user_id as well as _id, so a user id from the caller's token is the only thing
that can select a document. A lookup by id alone that is checked afterwards is
one forgotten branch away from leaking another user's results, so it is not
done that way anywhere here.

Results accumulate. Assessments are stored one document per session from the
outset, never overwritten in place, so a user can have as many as they like and
change over time can be looked at later. The only exception is re-submitting
the same session id, which updates that session rather than creating a
duplicate: a client retrying after a dropped connection should not produce two
records of one session.
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from database import assessments_collection

# Fields needed to list sessions. Measurements are excluded so the history view
# does not pull every number for every session it lists.
LIST_PROJECTION = {
    "session_id": 1,
    "protocol_version": 1,
    "started_at": 1,
    "completed_at": 1,
    "created_at": 1,
    "summary": 1,
    "tests.shoulder.status": 1,
    "tests.ftsst.status": 1,
    "tests.balance.status": 1,
}

DEFAULT_HISTORY_LIMIT = 20
MAX_HISTORY_LIMIT = 100


class AssessmentNotFoundError(LookupError):
    """Raised when no assessment matches both the id and the owner."""


def ensure_indexes():
    """Create the indexes the read paths rely on.

    Called from application startup. Safe to run repeatedly: createIndex is a
    no-op when the index already exists.
    """

    # Every list and latest query is "this user's sessions, newest first".
    assessments_collection.create_index(
        [("user_id", ASCENDING), ("started_at", DESCENDING)],
        name="user_started_at",
    )

    # Makes re-submitting a session an update rather than a duplicate, and
    # makes that guarantee hold even if two requests race.
    assessments_collection.create_index(
        [("user_id", ASCENDING), ("session_id", ASCENDING)],
        name="user_session_unique",
        unique=True,
    )


def _object_id(value, label: str = "assessment id") -> ObjectId:
    try:
        return ObjectId(value)

    except (InvalidId, TypeError):
        raise AssessmentNotFoundError(f"{label} is not a valid id") from None


def save_assessment(user_id: str, document: dict) -> dict:
    """Store a validated assessment for the authenticated user.

    `document` comes from validate_assessment_payload. The user id and the
    server timestamp are attached here rather than taken from the request, so
    neither can be set by the client.
    """

    now = datetime.now(timezone.utc)

    stored = {
        **document,
        "user_id": user_id,
        "updated_at": now,
    }

    result = assessments_collection.update_one(
        {"user_id": user_id, "session_id": document["session_id"]},
        {
            "$set": stored,
            # Preserved across a re-submission so the original save time is not
            # rewritten by a retry.
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    saved = assessments_collection.find_one(
        {"user_id": user_id, "session_id": document["session_id"]}
    )

    if saved is None:
        # Only reachable if the document was removed between write and read.
        raise AssessmentNotFoundError("the assessment could not be read back")

    return {
        "document": saved,
        "created": result.upserted_id is not None,
    }


def latest_assessment(user_id: str):
    """The user's most recent session, or None if they have never done one."""

    return assessments_collection.find_one(
        {"user_id": user_id},
        sort=[("started_at", DESCENDING)],
    )


def baseline_assessment(user_id: str):
    """The user's FIRST completed session — their immutable baseline.

    Baseline is defined positionally, as the oldest session on record, and
    is only ever read, never written or reordered here. That is what makes
    it immutable in practice: nothing in this module can promote a later
    session to baseline, so a reassessment adds a new document and leaves
    the comparison anchor exactly where it was.

    Returns the full document (measurements included, unlike
    list_assessments' projection) because the Progress Agent compares
    actual measured values, not session headers.
    """

    return assessments_collection.find_one(
        {"user_id": user_id},
        sort=[("started_at", ASCENDING)],
    )


def previous_assessment(user_id: str):
    """The session immediately before the most recent one, or None.

    Used as the Progress Agent's short-interval comparison point, distinct
    from baseline: "since last time" and "since the very beginning" are
    different questions and the agent is given both. Returns None when the
    user has done fewer than two sessions, which the agent reads as
    NOT_ENOUGH_DATA rather than comparing a session against itself.
    """

    sessions = list(
        assessments_collection.find({"user_id": user_id})
        .sort("started_at", DESCENDING)
        .limit(2)
    )

    return sessions[1] if len(sessions) > 1 else None


def list_assessments(user_id: str, limit: int = DEFAULT_HISTORY_LIMIT, skip: int = 0) -> list:
    """The user's sessions, newest first, without their measurements."""

    cursor = (
        assessments_collection.find({"user_id": user_id}, LIST_PROJECTION)
        .sort("started_at", DESCENDING)
        .skip(max(0, skip))
        .limit(max(1, min(limit, MAX_HISTORY_LIMIT)))
    )

    return list(cursor)


def count_assessments(user_id: str) -> int:
    return assessments_collection.count_documents({"user_id": user_id})


def get_assessment(user_id: str, assessment_id: str) -> dict:
    """One session belonging to this user.

    Ownership is part of the filter, so a valid id for someone else's session
    is indistinguishable from an id that does not exist.
    """

    document = assessments_collection.find_one(
        {"_id": _object_id(assessment_id), "user_id": user_id}
    )

    if document is None:
        raise AssessmentNotFoundError("No assessment found with that id")

    return document


def get_assessment_by_session(user_id: str, session_id: str) -> dict:
    """One session by its client-generated session id, scoped to the owner.

    Used to answer a re-submission of a session that is already stored.
    """

    document = assessments_collection.find_one(
        {"user_id": user_id, "session_id": session_id}
    )

    if document is None:
        raise AssessmentNotFoundError("No assessment found for that session")

    return document


# ---------------------------------------------------------------------------
# Serialisation
#
# Stored documents use snake_case, the client uses camelCase, and the mapping
# is written out explicitly. Returning stored documents directly would leak
# whatever fields happen to exist, including user_id, which the client already
# knows and has no reason to receive back.
# ---------------------------------------------------------------------------


def _isoformat(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        # pymongo returns naive UTC datetimes by default; label them so the
        # browser does not read them as local time.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    return str(value)


def _serialise_summary(summary) -> dict:
    summary = summary or {}

    return {
        "testsCompleted": summary.get("tests_completed", 0),
        "testsInvalid": summary.get("tests_invalid", 0),
        "testsSkipped": summary.get("tests_skipped", 0),
        "testsNotStarted": summary.get("tests_not_started", 0),
        "hasAnyUsableResult": summary.get("has_any_usable_result", False),
    }


def _serialise_test(test) -> dict:
    test = test or {}

    serialised = {
        "status": test.get("status", "not_started"),
        "measurements": test.get("measurements"),
        "quality": test.get("quality"),
        "invalidReasons": test.get("invalid_reasons", []),
        "attempts": test.get("attempts", 0),
    }

    if test.get("setup") is not None:
        serialised["setup"] = test["setup"]

    return serialised


def serialise_assessment(document: dict) -> dict:
    """Full session, including measurements."""

    tests = document.get("tests", {})

    return {
        "id": str(document["_id"]),
        "sessionId": document.get("session_id"),
        "protocolVersion": document.get("protocol_version"),
        "startedAt": _isoformat(document.get("started_at")),
        "completedAt": _isoformat(document.get("completed_at")),
        "createdAt": _isoformat(document.get("created_at")),
        "summary": _serialise_summary(document.get("summary")),
        "tests": {
            test_id: _serialise_test(tests.get(test_id))
            for test_id in ("shoulder", "ftsst", "balance")
        },
    }


def serialise_assessment_listing(document: dict) -> dict:
    """One entry in the history list: statuses and dates, no measurements."""

    tests = document.get("tests", {})

    return {
        "id": str(document["_id"]),
        "sessionId": document.get("session_id"),
        "protocolVersion": document.get("protocol_version"),
        "startedAt": _isoformat(document.get("started_at")),
        "completedAt": _isoformat(document.get("completed_at")),
        "summary": _serialise_summary(document.get("summary")),
        "statuses": {
            test_id: (tests.get(test_id) or {}).get("status", "not_started")
            for test_id in ("shoulder", "ftsst", "balance")
        },
    }
