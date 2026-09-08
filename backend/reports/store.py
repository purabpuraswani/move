"""Storage and retrieval for medical reports.

Same two rules as the assessment store: ownership is part of every query, never
a check performed afterwards, and stored documents are serialised explicitly
rather than returned as they are.

There is a third rule here that assessments do not need. A report holds health
information, so what leaves this module depends on who is asking. The list and
detail views serve the person reviewing their own report and include the
candidate values with their provenance. The confirmed view, which is what
anything generating guidance is allowed to read, contains only what the user
confirmed and refuses to return anything at all for a report that has not
reached the confirmed status. That refusal is the trust boundary in code.
"""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING

from database import db
from reports.schema import (
    STATUS_CONFIRMED,
    STATUS_NEEDS_REVIEW,
    TRUSTED_STATUSES,
    ReportValidationError,
    can_confirm,
    check_transition,
    confirmed_values,
    review_progress,
)

reports_collection = db["medical_reports"]

# Enough to list reports without pulling every transcribed value for each one.
LIST_PROJECTION = {
    "title": 1,
    "report_date": 1,
    "facility": 1,
    "source": 1,
    "status": 1,
    "created_at": 1,
    "updated_at": 1,
    "confirmed_at": 1,
    "review_submitted_at": 1,
    "file.extension": 1,
    "file.size_bytes": 1,
    "extraction.provider": 1,
    "extraction.error": 1,
    "extraction.completed_at": 1,
    "fields.key": 1,
    "fields.review.decision": 1,
}

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class ReportNotFoundError(LookupError):
    """Raised when no report matches both the id and the owner."""


class ReportStateError(RuntimeError):
    """Raised when an action does not apply to the report's current state."""


def ensure_indexes():
    """Create the indexes the read paths rely on. Safe to run repeatedly."""

    reports_collection.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="user_created_at",
    )

    # Fetching a user's confirmed reports is the query the guidance layer makes
    # on every request, so it gets its own index.
    reports_collection.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
        name="user_status_created_at",
    )


def _object_id(value) -> ObjectId:
    try:
        return ObjectId(value)

    except (InvalidId, TypeError):
        raise ReportNotFoundError("report id is not a valid id") from None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def create_report(document: dict) -> dict:
    result = reports_collection.insert_one(dict(document))

    stored = reports_collection.find_one(
        {"_id": result.inserted_id, "user_id": document["user_id"]}
    )

    if stored is None:
        raise ReportNotFoundError("the report could not be read back")

    return stored


def _update(user_id: str, report_id, changes: dict) -> dict:
    """Apply changes to one report, scoped to its owner."""

    identifier = report_id if isinstance(report_id, ObjectId) else _object_id(report_id)

    changes = {**changes, "updated_at": _now()}

    updated = reports_collection.find_one_and_update(
        {"_id": identifier, "user_id": user_id},
        {"$set": changes},
        return_document=True,
    )

    if updated is None:
        raise ReportNotFoundError("No report found with that id")

    return updated


def mark_extraction_started(user_id: str, report_id, status: str) -> dict:
    report = get_report(user_id, report_id)

    check_transition(report["status"], status)

    return _update(
        user_id,
        report["_id"],
        {
            "status": status,
            "extraction.attempted_at": _now(),
            "extraction.error": None,
        },
    )


def save_extraction_result(user_id: str, report_id, result: dict) -> dict:
    """Store candidate fields and move the report to needs_review.

    The status goes straight past extracted to needs_review because that is what
    is true: values exist and a person has to check them. Keeping a separate
    resting state for "extracted but nobody has been asked yet" would only
    describe the same obligation in a way the interface has to translate.
    """

    report = get_report(user_id, report_id)

    check_transition(report["status"], STATUS_NEEDS_REVIEW)

    note = result.get("document_note")

    return _update(
        user_id,
        report["_id"],
        {
            "status": STATUS_NEEDS_REVIEW,
            "fields": result["fields"],
            "extraction.completed_at": result.get("extracted_at") or _now(),
            "extraction.provider": result.get("provider"),
            "extraction.model": result.get("model"),
            "extraction.rejected_fields": result.get("rejected") or [],
            "extraction.document_readable": result.get("document_readable"),
            "extraction.document_note": note,
            "extraction.error": None,
            # A new extraction replaces the values, so any earlier review of
            # different values no longer applies.
            "review_submitted_at": None,
            "confirmed_at": None,
        },
    )


def save_extraction_failure(user_id: str, report_id, message: str, status: str) -> dict:
    report = get_report(user_id, report_id)

    check_transition(report["status"], status)

    return _update(
        user_id,
        report["_id"],
        {
            "status": status,
            "extraction.completed_at": _now(),
            "extraction.error": message[:500],
        },
    )


def save_review(user_id: str, report_id, fields: list) -> dict:
    """Store the user's corrections. Does not confirm anything.

    Saving a review and confirming it are separate calls on purpose. A user can
    work through a long report over more than one sitting, and the values stay
    outside the trust boundary for the whole of that time.
    """

    report = get_report(user_id, report_id)

    check_transition(report["status"], STATUS_NEEDS_REVIEW)

    return _update(
        user_id,
        report["_id"],
        {
            "status": STATUS_NEEDS_REVIEW,
            "fields": fields,
            "review_submitted_at": _now(),
            # Editing a confirmed report withdraws the confirmation. The
            # alternative would leave guidance running on values the user has
            # since said were wrong.
            "confirmed_at": None,
        },
    )


def confirm_report(user_id: str, report_id) -> dict:
    """Move a reviewed report across the trust boundary.

    The only place a report becomes confirmed. Everything it checks is about
    the user having done the reviewing, not about the values being plausible,
    because plausibility is not something this application is in a position to
    judge.
    """

    report = get_report(user_id, report_id)

    if report.get("review_submitted_at") is None:
        raise ReportStateError(
            "These values have not been reviewed yet. Check them, save your "
            "changes, and then confirm."
        )

    ready, reason = can_confirm(report.get("fields") or [])

    if not ready:
        raise ReportStateError(reason)

    check_transition(report["status"], STATUS_CONFIRMED)

    return _update(
        user_id,
        report["_id"],
        {"status": STATUS_CONFIRMED, "confirmed_at": _now()},
    )


def reopen_report(user_id: str, report_id) -> dict:
    """Take a confirmed report back out of the trusted set for further edits.

    Refuses for anything not currently confirmed. Withdrawing a confirmation
    that was never given is not a harmless no-op: it would let an interface show
    a reopen action wherever it liked and get a success back, and the reply
    "this report is not confirmed" would be true both before and after. Saying
    so plainly means a caller that has lost track of the state finds out.
    """

    report = get_report(user_id, report_id)

    if report["status"] not in TRUSTED_STATUSES:
        raise ReportStateError(
            "This report is not confirmed, so there is nothing to reopen. It is "
            "already open for editing."
        )

    check_transition(report["status"], STATUS_NEEDS_REVIEW)

    return _update(
        user_id,
        report["_id"],
        {"status": STATUS_NEEDS_REVIEW, "confirmed_at": None},
    )


def delete_report(user_id: str, report_id) -> dict:
    """Remove a report, returning it so its file can be deleted too."""

    report = get_report(user_id, report_id)

    reports_collection.delete_one({"_id": report["_id"], "user_id": user_id})

    return report


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def get_report(user_id: str, report_id) -> dict:
    identifier = report_id if isinstance(report_id, ObjectId) else _object_id(report_id)

    document = reports_collection.find_one({"_id": identifier, "user_id": user_id})

    if document is None:
        raise ReportNotFoundError("No report found with that id")

    return document


def list_reports(user_id: str, limit: int = DEFAULT_LIMIT, skip: int = 0) -> list:
    cursor = (
        reports_collection.find({"user_id": user_id}, LIST_PROJECTION)
        .sort("created_at", DESCENDING)
        .skip(max(0, skip))
        .limit(max(1, min(limit, MAX_LIMIT)))
    )

    return list(cursor)


def count_reports(user_id: str) -> int:
    return reports_collection.count_documents({"user_id": user_id})


def confirmed_reports(user_id: str, limit: int = MAX_LIMIT) -> list:
    """Every report this user has confirmed, newest first.

    The status filter is in the query rather than applied to the results,
    following the same reasoning as ownership: a filter that has to be
    remembered is a filter that can be forgotten.
    """

    cursor = (
        reports_collection.find(
            {"user_id": user_id, "status": {"$in": list(TRUSTED_STATUSES)}}
        )
        .sort("created_at", DESCENDING)
        .limit(max(1, min(limit, MAX_LIMIT)))
    )

    return list(cursor)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _isoformat(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    return str(value)


def _serialise_field(field: dict) -> dict:
    candidate = field.get("candidate") or {}
    review = field.get("review") or {}
    provenance = field.get("provenance") or {}

    return {
        "key": field.get("key"),
        "label": field.get("label"),
        "category": field.get("category"),
        # What the machine read. Sent alongside the user's version so the
        # review screen can show both and the difference stays visible.
        "candidate": {
            "value": candidate.get("value"),
            "unit": candidate.get("unit"),
            "printedReferenceRange": candidate.get("printed_reference_range"),
            "quotedText": candidate.get("quoted_text"),
            "page": candidate.get("page"),
            "confidence": candidate.get("confidence"),
        },
        "review": {
            "value": review.get("value"),
            "unit": review.get("unit"),
            "printedReferenceRange": review.get("printed_reference_range"),
            "decision": review.get("decision", "pending"),
            "note": review.get("note"),
            "reviewedAt": _isoformat(review.get("reviewed_at")),
        },
        "provenance": {
            "source": provenance.get("source"),
            "provider": provenance.get("provider"),
            "model": provenance.get("model"),
            "recordedAt": _isoformat(
                provenance.get("extracted_at") or provenance.get("recorded_at")
            ),
        },
    }


def _serialise_file(file_record) -> dict:
    """File metadata only.

    The storage key is deliberately absent: the browser has no use for it, and
    a key that never reaches the client cannot be replayed by one.
    """

    if not file_record:
        return None

    return {
        "extension": file_record.get("extension"),
        "sizeBytes": file_record.get("size_bytes"),
    }


def serialise_report(document: dict) -> dict:
    """Full report for its owner's review screen."""

    fields = document.get("fields") or []
    extraction = document.get("extraction") or {}
    status = document.get("status")

    ready, reason = can_confirm(fields)

    return {
        "id": str(document["_id"]),
        "title": document.get("title"),
        "reportDate": _isoformat(document.get("report_date")),
        "facility": document.get("facility"),
        "source": document.get("source"),
        "status": status,
        # Stated explicitly rather than left for the client to infer from the
        # status string, so every screen agrees on what is trusted.
        "isConfirmed": status in TRUSTED_STATUSES,
        "file": _serialise_file(document.get("file")),
        "fields": [_serialise_field(field) for field in fields],
        "progress": review_progress(fields),
        "canConfirm": ready,
        "confirmBlockedReason": reason,
        "extraction": {
            "attemptedAt": _isoformat(extraction.get("attempted_at")),
            "completedAt": _isoformat(extraction.get("completed_at")),
            "provider": extraction.get("provider"),
            "model": extraction.get("model"),
            "error": extraction.get("error"),
            "documentReadable": extraction.get("document_readable"),
            "documentNote": extraction.get("document_note"),
            "droppedFieldCount": len(extraction.get("rejected_fields") or []),
        },
        "reviewSubmittedAt": _isoformat(document.get("review_submitted_at")),
        "confirmedAt": _isoformat(document.get("confirmed_at")),
        "createdAt": _isoformat(document.get("created_at")),
        "updatedAt": _isoformat(document.get("updated_at")),
    }


def serialise_report_listing(document: dict) -> dict:
    """One entry in the reports list: no values, only where it has got to."""

    fields = document.get("fields") or []
    extraction = document.get("extraction") or {}
    status = document.get("status")

    return {
        "id": str(document["_id"]),
        "title": document.get("title"),
        "reportDate": _isoformat(document.get("report_date")),
        "facility": document.get("facility"),
        "source": document.get("source"),
        "status": status,
        "isConfirmed": status in TRUSTED_STATUSES,
        "file": _serialise_file(document.get("file")),
        "progress": review_progress(fields),
        "extractionError": extraction.get("error"),
        "createdAt": _isoformat(document.get("created_at")),
        "confirmedAt": _isoformat(document.get("confirmed_at")),
    }


def serialise_confirmed_report(document: dict) -> dict:
    """A confirmed report, in the form downstream features may read.

    Refuses outright for anything not confirmed. A caller that reaches here with
    the wrong document has a bug, and returning an empty result would hide it;
    raising means the mistake is found while it is still cheap.
    """

    status = document.get("status")

    if status not in TRUSTED_STATUSES:
        raise ReportStateError(
            f"Report {document.get('_id')} has status {status!r} and has not "
            "been confirmed by the user, so its values must not be used."
        )

    return {
        "id": str(document["_id"]),
        "title": document.get("title"),
        "reportDate": _isoformat(document.get("report_date")),
        "facility": document.get("facility"),
        "confirmedAt": _isoformat(document.get("confirmed_at")),
        "values": [
            {
                "key": value["key"],
                "label": value["label"],
                "category": value["category"],
                "value": value["value"],
                "unit": value["unit"],
                "printedReferenceRange": value["printed_reference_range"],
                "wasCorrectedByUser": value["was_corrected"],
                "originalSource": value["original_source"],
            }
            for value in confirmed_values(document.get("fields") or [])
        ],
    }


def confirmed_values_for_user(user_id: str) -> dict:
    """Everything this user has confirmed, ready for the guidance layer.

    Returned as a described structure rather than a bare list so a caller can
    tell "nothing confirmed yet" from "nothing found", and say so honestly
    instead of proceeding as though the user had no findings.
    """

    reports = confirmed_reports(user_id)

    serialised = [serialise_report_values(report) for report in reports]

    return {
        "hasConfirmedReports": bool(serialised),
        "reportCount": len(serialised),
        "reports": serialised,
    }


def serialise_report_values(document: dict) -> dict:
    return serialise_confirmed_report(document)


def validate_limit(limit, skip) -> tuple:
    """Bounds for list queries, applied here as well as in the route."""

    try:
        limit = int(limit)
        skip = int(skip)

    except (TypeError, ValueError):
        raise ReportValidationError("limit and skip must be whole numbers") from None

    return max(1, min(limit, MAX_LIMIT)), max(0, skip)
