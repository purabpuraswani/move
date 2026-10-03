"""The shape of a medical report record, and the rule that makes it trustworthy.

A report holds two different kinds of information and the whole design turns on
keeping them apart:

A *candidate* is what automated extraction read off the document. It is a guess.
It may be wrong, it may be a misread decimal point, it may be a value belonging
to a different row of the table. Nothing downstream may use it.

A *confirmed* value is what the user, having looked at their own document, says
the value is. Only confirmed values are passed to anything that generates
guidance.

The candidate is written once by the extraction step and never edited
afterwards. The user's review is recorded separately, alongside it. That means
the original machine reading is always still visible next to the human one,
which is what allows a wrong extraction to be noticed later instead of quietly
becoming the truth.

What this module does not do is interpret anything. A value is transcribed as
text, with the unit as printed and, where the document prints one, the reference
range as printed on that document. A printed range is a transcription of the
issuing laboratory's own statement, not a threshold invented here, and it is
named accordingly. No value is ever compared against anything, marked high or
low, or turned into a score.
"""

import re
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Statuses
# ---------------------------------------------------------------------------

STATUS_UPLOADED = "uploaded"
STATUS_PROCESSING = "processing"
STATUS_EXTRACTED = "extracted"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_CONFIRMED = "confirmed"
STATUS_FAILED = "failed"

REPORT_STATUSES = (
    STATUS_UPLOADED,
    STATUS_PROCESSING,
    STATUS_EXTRACTED,
    STATUS_NEEDS_REVIEW,
    STATUS_CONFIRMED,
    STATUS_FAILED,
)

# The single definition of the trust boundary. Anything reading report data for
# downstream use must filter on this and nothing else.
TRUSTED_STATUSES = (STATUS_CONFIRMED,)

# What may follow what. Extraction can be retried from a failure or from an
# unreviewed extraction; a confirmed report is terminal unless the user
# explicitly reopens it, which is modelled as confirmed -> needs_review.
#
# processing -> needs_review is the ordinary success path. A successful read
# produces values that a person has to check, and that obligation is what
# needs_review names, so there is nothing for the report to rest at in between.
# extracted remains reachable for a caller that wants to store values before
# asking anyone to look at them, but this build does not use it.
ALLOWED_TRANSITIONS = {
    STATUS_UPLOADED: (STATUS_PROCESSING, STATUS_NEEDS_REVIEW, STATUS_FAILED),
    STATUS_PROCESSING: (STATUS_EXTRACTED, STATUS_NEEDS_REVIEW, STATUS_FAILED),
    STATUS_EXTRACTED: (STATUS_NEEDS_REVIEW, STATUS_PROCESSING, STATUS_FAILED),
    STATUS_NEEDS_REVIEW: (STATUS_CONFIRMED, STATUS_NEEDS_REVIEW, STATUS_PROCESSING),
    STATUS_CONFIRMED: (STATUS_NEEDS_REVIEW,),
    STATUS_FAILED: (STATUS_PROCESSING, STATUS_NEEDS_REVIEW),
}


# ---------------------------------------------------------------------------
# Field vocabulary
# ---------------------------------------------------------------------------

# Deliberately descriptive rather than clinical. In particular the category for
# a diagnosis is named for what it actually is: something printed on the
# document, recorded as such. This application does not diagnose, and a field
# name that implied otherwise would be the first step towards behaving as if it
# did.
CATEGORY_LAB_RESULT = "lab_result"
CATEGORY_VITAL_SIGN = "vital_sign"
CATEGORY_MEDICATION = "medication"
CATEGORY_DIAGNOSIS_ON_REPORT = "diagnosis_listed_on_report"
CATEGORY_NOTE_TEXT = "clinical_note_text"
CATEGORY_REPORT_METADATA = "report_metadata"

FIELD_CATEGORIES = (
    CATEGORY_LAB_RESULT,
    CATEGORY_VITAL_SIGN,
    CATEGORY_MEDICATION,
    CATEGORY_DIAGNOSIS_ON_REPORT,
    CATEGORY_NOTE_TEXT,
    CATEGORY_REPORT_METADATA,
)

CATEGORY_LABELS = {
    CATEGORY_LAB_RESULT: "Laboratory result",
    CATEGORY_VITAL_SIGN: "Vital sign",
    CATEGORY_MEDICATION: "Medication",
    CATEGORY_DIAGNOSIS_ON_REPORT: "Listed on the report",
    CATEGORY_NOTE_TEXT: "Text from the report",
    CATEGORY_REPORT_METADATA: "About the report",
}

SOURCE_AI_EXTRACTION = "ai_extraction"
SOURCE_USER_ENTRY = "user_entry"

FIELD_SOURCES = (SOURCE_AI_EXTRACTION, SOURCE_USER_ENTRY)

DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_CORRECTED = "corrected"
DECISION_REJECTED = "rejected"

DECISIONS = (
    DECISION_PENDING,
    DECISION_ACCEPTED,
    DECISION_CORRECTED,
    DECISION_REJECTED,
)

# Decisions that put a value on the trusted side of the boundary.
INCLUDED_DECISIONS = (DECISION_ACCEPTED, DECISION_CORRECTED)

# The onboarding health-background condition a report was uploaded against.
# Only a label for what the user said the document is about: it says nothing
# about what the document contains, and nothing is inferred from it.
REPORT_CONDITIONS = (
    "diabetes",
    "hypertension",
    "heart_condition",
    "previous_injury",
    "joint_pain",
    "back_neck_pain",
    "other",
)


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_FIELDS = 200
MAX_KEY_LENGTH = 64
MAX_LABEL_LENGTH = 120
MAX_VALUE_LENGTH = 500
MAX_UNIT_LENGTH = 40
MAX_RANGE_LENGTH = 120
MAX_QUOTE_LENGTH = 600
MAX_NOTE_LENGTH = 500
MAX_TITLE_LENGTH = 160

KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")


class ReportValidationError(ValueError):
    """Raised when a report payload cannot be stored as given."""


# ---------------------------------------------------------------------------
# Small validators
#
# Every one of these rejects rather than repairs. Silently coercing a value the
# client did not send is how a stored number ends up being something nobody
# ever wrote down.
# ---------------------------------------------------------------------------


def _text(value, *, label, limit, required=False):
    if value is None:
        if required:
            raise ReportValidationError(f"{label} is required")

        return None

    if not isinstance(value, str):
        raise ReportValidationError(f"{label} must be text")

    cleaned = value.strip()

    if not cleaned:
        if required:
            raise ReportValidationError(f"{label} is required")

        return None

    if len(cleaned) > limit:
        raise ReportValidationError(
            f"{label} is longer than {limit} characters"
        )

    return cleaned


def _confidence(value, *, label="confidence"):
    """A number between 0 and 1, or nothing at all.

    Absent confidence is a legitimate answer and is stored as None. It is not
    turned into 0, which would read as "certainly wrong", nor into 1.
    """

    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportValidationError(f"{label} must be a number between 0 and 1")

    number = float(value)

    if number != number or number in (float("inf"), float("-inf")):
        raise ReportValidationError(f"{label} must be a real number")

    if not 0.0 <= number <= 1.0:
        raise ReportValidationError(f"{label} must be between 0 and 1")

    return round(number, 3)


def _page(value):
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportValidationError("page must be a whole number")

    if value < 1 or value > 500:
        raise ReportValidationError("page must be between 1 and 500")

    return value


def _choice(value, allowed, *, label, default=None):
    if value is None and default is not None:
        return default

    if value not in allowed:
        raise ReportValidationError(
            f"{label} must be one of: {', '.join(allowed)}"
        )

    return value


def _key(value):
    key = _text(value, label="field key", limit=MAX_KEY_LENGTH, required=True)

    if not KEY_PATTERN.match(key):
        raise ReportValidationError(
            f"{key!r} is not a valid field key. Use lowercase letters, "
            "numbers and underscores."
        )

    return key


def _iso_datetime(value, *, label):
    """Parse an ISO 8601 string into an aware datetime.

    Python 3.10's fromisoformat does not accept a trailing Z, which is exactly
    what JavaScript's toISOString produces, so it is translated first.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = _text(value, label=label, limit=64)

    if text is None:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    except ValueError:
        raise ReportValidationError(f"{label} is not a valid date") from None

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Candidate fields, as produced by extraction
# ---------------------------------------------------------------------------


def build_candidate_field(raw: dict, *, provenance: dict) -> dict:
    """One field as extraction proposes it.

    The provenance is attached by the caller, which knows what actually
    produced the value; it is never taken from the extraction output itself,
    because a model asked to describe its own reliability is not evidence.
    """

    if not isinstance(raw, dict):
        raise ReportValidationError("each extracted field must be an object")

    category = _choice(
        raw.get("category"),
        FIELD_CATEGORIES,
        label="category",
        default=CATEGORY_LAB_RESULT,
    )

    return {
        "key": _key(raw.get("key")),
        "label": _text(
            raw.get("label"), label="label", limit=MAX_LABEL_LENGTH, required=True
        ),
        "category": category,
        "candidate": {
            # Values stay as text. A report prints "13.2", "<0.01" and
            # "Not detected" in the same column, and parsing those into numbers
            # here would mean deciding what the middle one means.
            "value": _text(
                raw.get("value"), label="value", limit=MAX_VALUE_LENGTH
            ),
            "unit": _text(raw.get("unit"), label="unit", limit=MAX_UNIT_LENGTH),
            "printed_reference_range": _text(
                raw.get("printed_reference_range"),
                label="printed reference range",
                limit=MAX_RANGE_LENGTH,
            ),
            "quoted_text": _text(
                raw.get("quoted_text"),
                label="quoted text",
                limit=MAX_QUOTE_LENGTH,
            ),
            "page": _page(raw.get("page")),
            "confidence": _confidence(raw.get("confidence")),
        },
        "review": {
            "value": None,
            "unit": None,
            "printed_reference_range": None,
            "decision": DECISION_PENDING,
            "note": None,
            "reviewed_at": None,
        },
        "provenance": dict(provenance),
    }


def build_candidate_fields(raw_fields, *, provenance: dict) -> list:
    """Validate a whole extraction result.

    A malformed field is dropped rather than allowed to fail the entire
    extraction, and the reason is returned so it can be reported honestly
    instead of the user being told everything went fine.
    """

    if raw_fields is None:
        raw_fields = []

    if not isinstance(raw_fields, list):
        raise ReportValidationError("extracted fields must be a list")

    if len(raw_fields) > MAX_FIELDS:
        raise ReportValidationError(
            f"an extraction returned more than {MAX_FIELDS} fields"
        )

    fields = []
    seen = set()
    rejected = []

    for index, raw in enumerate(raw_fields):
        try:
            field = build_candidate_field(raw, provenance=provenance)

        except ReportValidationError as error:
            rejected.append(f"field {index + 1}: {error}")

            continue

        key = field["key"]

        # Reports repeat names across panels. Rather than overwrite, later
        # duplicates are suffixed so both readings survive for the user to
        # look at.
        if key in seen:
            suffix = 2

            while f"{key}_{suffix}" in seen:
                suffix += 1

            key = f"{key}_{suffix}"
            field["key"] = key

        seen.add(key)
        fields.append(field)

    return fields, rejected


# ---------------------------------------------------------------------------
# The user's review
# ---------------------------------------------------------------------------


def _same_text(left, right) -> bool:
    return (left or "").strip() == (right or "").strip()


def apply_review(existing_fields: list, submitted, *, now: datetime) -> list:
    """Record what the user said about each field.

    The submitted list is matched against the stored fields by key. Anything
    the user added that has no stored counterpart becomes a new field with
    user_entry provenance, which is how a report whose extraction is
    unavailable, or simply missed a row, can still be completed by hand.

    The decision is derived, not accepted from the client: a value identical to
    the candidate is an acceptance, a different one is a correction. That way
    the record of what changed cannot disagree with the values themselves.
    """

    if not isinstance(submitted, list):
        raise ReportValidationError("fields must be a list")

    if len(submitted) > MAX_FIELDS:
        raise ReportValidationError(f"a report cannot hold more than {MAX_FIELDS} fields")

    by_key = {field["key"]: field for field in existing_fields}
    seen = set()
    result = []

    for raw in submitted:
        if not isinstance(raw, dict):
            raise ReportValidationError("each field must be an object")

        key = _key(raw.get("key"))

        if key in seen:
            raise ReportValidationError(f"{key!r} appears twice in the submission")

        seen.add(key)

        include = raw.get("include", True)

        if not isinstance(include, bool):
            raise ReportValidationError("include must be true or false")

        value = _text(raw.get("value"), label="value", limit=MAX_VALUE_LENGTH)
        unit = _text(raw.get("unit"), label="unit", limit=MAX_UNIT_LENGTH)
        printed_range = _text(
            raw.get("printed_reference_range"),
            label="printed reference range",
            limit=MAX_RANGE_LENGTH,
        )
        note = _text(raw.get("note"), label="note", limit=MAX_NOTE_LENGTH)

        field = by_key.get(key)

        if field is None:
            # Something the user typed in themselves. There is no candidate to
            # compare against, so there is nothing to accept: it is the user's
            # own entry from the start.
            field = {
                "key": key,
                "label": _text(
                    raw.get("label"),
                    label="label",
                    limit=MAX_LABEL_LENGTH,
                    required=True,
                ),
                "category": _choice(
                    raw.get("category"),
                    FIELD_CATEGORIES,
                    label="category",
                    default=CATEGORY_LAB_RESULT,
                ),
                "candidate": {
                    "value": None,
                    "unit": None,
                    "printed_reference_range": None,
                    "quoted_text": None,
                    "page": None,
                    "confidence": None,
                },
                "provenance": {
                    "source": SOURCE_USER_ENTRY,
                    "recorded_at": now,
                },
            }

            decision = DECISION_CORRECTED if include else DECISION_REJECTED

        else:
            field = dict(field)
            candidate = field.get("candidate") or {}

            unchanged = (
                _same_text(value, candidate.get("value"))
                and _same_text(unit, candidate.get("unit"))
                and _same_text(
                    printed_range, candidate.get("printed_reference_range")
                )
            )

            if not include:
                decision = DECISION_REJECTED
            elif unchanged:
                decision = DECISION_ACCEPTED
            else:
                decision = DECISION_CORRECTED

            # A user may relabel or recategorise a field the extraction
            # mislabelled; the candidate itself stays as it was read.
            label = _text(
                raw.get("label"), label="label", limit=MAX_LABEL_LENGTH
            )

            if label:
                field["label"] = label

            if raw.get("category") is not None:
                field["category"] = _choice(
                    raw.get("category"), FIELD_CATEGORIES, label="category"
                )

        field["review"] = {
            "value": value,
            "unit": unit,
            "printed_reference_range": printed_range,
            "decision": decision,
            "note": note,
            "reviewed_at": now,
        }

        result.append(field)

    # A stored field the user did not mention is left alone rather than
    # discarded, so a partially completed review does not lose extracted data.
    for field in existing_fields:
        if field["key"] not in seen:
            result.append(field)

    return result


def confirmed_values(fields: list) -> list:
    """The fields a user has attested to, in the form downstream code may read.

    Rejected and unreviewed fields are absent entirely rather than present with
    an empty value: something the user never confirmed should not be visible to
    a caller that is only allowed to see confirmed data.
    """

    confirmed = []

    for field in fields or []:
        review = field.get("review") or {}

        if review.get("decision") not in INCLUDED_DECISIONS:
            continue

        candidate = field.get("candidate") or {}
        provenance = field.get("provenance") or {}

        confirmed.append(
            {
                "key": field.get("key"),
                "label": field.get("label"),
                "category": field.get("category"),
                "value": review.get("value"),
                "unit": review.get("unit"),
                "printed_reference_range": review.get("printed_reference_range"),
                # Kept so that anything using this value can say where it came
                # from, and so a correction remains visible as a correction.
                "confirmed_by_user": True,
                "was_corrected": review.get("decision") == DECISION_CORRECTED,
                "original_source": provenance.get("source", SOURCE_USER_ENTRY),
                "candidate_value": candidate.get("value"),
            }
        )

    return confirmed


def review_progress(fields: list) -> dict:
    """How much of the review is done, for the interface to show."""

    counts = {decision: 0 for decision in DECISIONS}

    for field in fields or []:
        decision = (field.get("review") or {}).get("decision", DECISION_PENDING)

        counts[decision] = counts.get(decision, 0) + 1

    total = sum(counts.values())

    return {
        "total": total,
        "pending": counts[DECISION_PENDING],
        "accepted": counts[DECISION_ACCEPTED],
        "corrected": counts[DECISION_CORRECTED],
        "rejected": counts[DECISION_REJECTED],
        "included": counts[DECISION_ACCEPTED] + counts[DECISION_CORRECTED],
    }


def can_confirm(fields: list) -> tuple:
    """Whether this report is ready to cross the trust boundary.

    Two conditions, both about the user rather than about the data: every field
    must have been looked at, and something must remain after the rejections.
    Confirming a report where nothing is included would record an attestation
    to nothing.
    """

    progress = review_progress(fields)

    if progress["total"] == 0:
        return False, "There is nothing to confirm yet."

    if progress["pending"]:
        return (
            False,
            f"{progress['pending']} of {progress['total']} values still need "
            "to be checked before you can confirm this report.",
        )

    if progress["included"] == 0:
        return (
            False,
            "Every value has been removed, so there is nothing left to "
            "confirm. Keep at least one value, or delete the report.",
        )

    return True, None


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def check_transition(current: str, target: str) -> None:
    """Refuse a status change that the pipeline does not allow.

    Written as an explicit table because the order of these steps is the whole
    safety property: a report must not reach confirmed without a review, and a
    single misplaced assignment elsewhere would otherwise be enough.
    """

    if target not in REPORT_STATUSES:
        raise ReportValidationError(f"{target!r} is not a report status")

    if current == target and target != STATUS_NEEDS_REVIEW:
        return

    allowed = ALLOWED_TRANSITIONS.get(current, ())

    if target not in allowed:
        raise ReportValidationError(
            f"A report that is {current!r} cannot become {target!r}."
        )


def is_trusted(status: str) -> bool:
    return status in TRUSTED_STATUSES


# ---------------------------------------------------------------------------
# The stored record
# ---------------------------------------------------------------------------


def build_report_document(
    *,
    user_id: str,
    title,
    report_date,
    facility,
    file_record,
    source: str,
    now: datetime,
    condition=None,
) -> dict:
    """A newly created report, before anything has been extracted from it."""

    if source not in ("upload", "manual_entry"):
        raise ReportValidationError("source must be upload or manual_entry")

    condition = (condition or "").strip() or None

    if condition is not None and condition not in REPORT_CONDITIONS:
        raise ReportValidationError(
            f"condition must be one of {', '.join(REPORT_CONDITIONS)}"
        )

    if source == "upload" and not file_record:
        raise ReportValidationError("an uploaded report needs a stored file")

    return {
        "user_id": user_id,
        "title": _text(title, label="title", limit=MAX_TITLE_LENGTH)
        or ("Medical report" if source == "upload" else "Values entered by hand"),
        "report_date": _iso_datetime(report_date, label="report date"),
        "facility": _text(facility, label="facility", limit=MAX_LABEL_LENGTH),
        "source": source,
        "condition": condition,
        "file": dict(file_record) if file_record else None,
        "status": STATUS_UPLOADED if source == "upload" else STATUS_NEEDS_REVIEW,
        "fields": [],
        "extraction": {
            "attempted_at": None,
            "completed_at": None,
            "provider": None,
            "model": None,
            "error": None,
            "rejected_fields": [],
        },
        "review_submitted_at": None,
        "confirmed_at": None,
        "created_at": now,
        "updated_at": now,
    }
