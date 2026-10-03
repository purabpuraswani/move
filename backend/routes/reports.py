"""Medical report endpoints.

The pipeline these routes expose is: upload, store, extract candidates, show
them to the user, let the user correct them, let the user confirm them, and only
then treat them as usable.

Nothing here shortens that sequence. Extraction writes candidates and moves the
report to needs_review; it cannot write a confirmed value. Confirmation is its
own request, made by the user, and it is refused unless every value has been
looked at. The confirmed view is a separate endpoint from the review view, so
"what the machine read" and "what the user attests to" are never the same
response.

When no AI provider is configured, extraction says so with a 503 and the report
stays exactly as it was uploaded. Values are never filled in to make the flow
appear to work.
"""

from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pymongo.errors import PyMongoError

from auth.deps import get_current_user
from reports.extraction import (
    ExtractionFailed,
    ExtractionUnavailable,
    extract_candidates,
    extraction_status,
)
from reports.schema import (
    CATEGORY_LABELS,
    FIELD_CATEGORIES,
    MAX_FIELDS,
    STATUS_FAILED,
    STATUS_PROCESSING,
    REPORT_STATUSES,
    ReportValidationError,
    apply_review,
    build_report_document,
)
from reports.storage import (
    StorageError,
    UploadRejected,
    cleanup_directory_if_empty,
    get_storage,
)
from reports.store import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ReportNotFoundError,
    ReportStateError,
    confirm_report,
    confirmed_values_for_user,
    count_reports,
    create_report,
    delete_report,
    get_report,
    list_reports,
    mark_extraction_started,
    reopen_report,
    save_extraction_failure,
    save_extraction_result,
    save_review,
    serialise_report,
    serialise_report_listing,
)


router = APIRouter(
    prefix="/api/reports",
    tags=["Medical reports"]
)


DATABASE_UNAVAILABLE = (
    "Your reports could not be reached right now. This is a server or database "
    "problem, not a problem with your report."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=DATABASE_UNAVAILABLE
    )


def _not_found() -> HTTPException:
    # Identical for a report that does not exist and one belonging to someone
    # else, so an id cannot be used to learn whether it is in use.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No report found with that id"
    )


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_report(
    current_user: dict = Depends(get_current_user),

    file: UploadFile | None = File(None),

    title: str | None = Form(None),
    report_date: str | None = Form(None),
    facility: str | None = Form(None),

    # Which onboarding health-background answer the file was attached to, if
    # any. Validated against REPORT_CONDITIONS when the record is built.
    condition: str | None = Form(None),

    # A report can also be created with no file, for someone holding a paper
    # copy who would rather type the values in. That path exists so the pipeline
    # can be used without an AI provider without anything being fabricated: the
    # values come from the person reading their own document.
    source: str = Form("upload"),
):
    """Create a report, either from an uploaded file or for manual entry."""

    user_id = str(current_user["_id"])

    storage = get_storage()
    stored_file = None

    if source == "upload":
        if file is None or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Choose a file to upload, or start a report for entering "
                    "values by hand instead."
                ),
            )

        try:
            stored_file = storage.save(user_id, file.filename, file.file)

        except UploadRejected as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            ) from error

        except StorageError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The file could not be stored. {error}"
            ) from error

    try:
        document = build_report_document(
            user_id=user_id,
            title=title,
            report_date=report_date,
            facility=facility,
            file_record=stored_file.as_record() if stored_file else None,
            source=source,
            now=_now(),
            condition=condition,
        )

    except ReportValidationError as error:
        # The file is removed again: a record that was never created should not
        # leave an orphan on disk.
        if stored_file:
            storage.delete(stored_file.key)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from error

    try:
        stored = create_report(document)

    except PyMongoError as error:
        if stored_file:
            storage.delete(stored_file.key)

        raise _database_error() from error

    return {
        "message": "Report uploaded" if stored_file else "Report started",
        "report": serialise_report(stored),
        "extraction": extraction_status(),
    }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


@router.post("/{report_id}/extract")
def run_extraction(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Read candidate values off the stored document.

    What this produces is a proposal. It is stored as candidate values, the
    report moves to needs_review, and nothing is usable until the user confirms
    it. A failure here leaves the file untouched and is reported as a failure.
    """

    user_id = str(current_user["_id"])

    try:
        report = get_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except PyMongoError as error:
        raise _database_error() from error

    if not report.get("file"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This report has no uploaded document, so there is nothing to "
                "read. Enter the values you want to record instead."
            ),
        )

    availability = extraction_status()

    if not availability["available"]:
        # Deliberately not a failure state. Nothing was attempted, the document
        # is fine, and the report stays where it was so extraction can be run
        # later if a key is added.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=availability["reason"],
        )

    try:
        mark_extraction_started(user_id, report["_id"], STATUS_PROCESSING)

    except ReportValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        ) from error

    except PyMongoError as error:
        raise _database_error() from error

    storage = get_storage()

    try:
        file_bytes = storage.read_bytes(report["file"]["key"])

    except StorageError as error:
        save_extraction_failure(
            user_id, report["_id"], str(error), STATUS_FAILED
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The uploaded file could not be read from storage. Try "
                "uploading it again."
            ),
        ) from error

    try:
        result = extract_candidates(
            file_bytes, report["file"].get("extension") or ""
        )

    except ExtractionUnavailable as error:
        # Configuration changed between the check above and here.
        save_extraction_failure(user_id, report["_id"], str(error), STATUS_FAILED)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error)
        ) from error

    except (ExtractionFailed, ReportValidationError) as error:
        save_extraction_failure(user_id, report["_id"], str(error), STATUS_FAILED)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"The report could not be read automatically. {error} You can "
                "enter the values yourself instead."
            ),
        ) from error

    if not result["fields"]:
        # An empty result is an honest outcome, not an error: a blurry photo or
        # a document that is not a report genuinely has nothing to transcribe.
        # It is recorded as a failure of extraction, not of the user, and the
        # manual path stays open.
        note = result.get("document_note") or (
            "No values could be read from this document."
        )

        save_extraction_failure(user_id, report["_id"], note, STATUS_FAILED)

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{note} Nothing has been saved from it. You can enter the "
                "values yourself, or upload a clearer photo or PDF."
            ),
        )

    try:
        updated = save_extraction_result(user_id, report["_id"], result)

    except (ReportValidationError, ReportNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        ) from error

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "message": (
            "Values were read from your report. Check each one against your "
            "document before confirming."
        ),
        "report": serialise_report(updated),
    }


# ---------------------------------------------------------------------------
# Reading
#
# The fixed paths are declared before /{report_id} so they are matched as
# themselves rather than as an id.
# ---------------------------------------------------------------------------


@router.get("/extraction-status")
def read_extraction_status(_current_user: dict = Depends(get_current_user)):
    """Whether automatic reading is set up on this server.

    Lets the interface offer manual entry up front instead of after a failed
    attempt. Says nothing about credentials beyond whether any exist.
    """

    return extraction_status()


@router.get("/field-categories")
def read_field_categories(_current_user: dict = Depends(get_current_user)):
    """The categories a field may have, for the manual entry form."""

    return {
        "categories": [
            {"value": category, "label": CATEGORY_LABELS[category]}
            for category in FIELD_CATEGORIES
        ],
        "maxFields": MAX_FIELDS,
    }


@router.get("/confirmed")
def read_confirmed_reports(current_user: dict = Depends(get_current_user)):
    """Only what the user has confirmed.

    This is the endpoint anything downstream reads. A report still in review
    does not appear here at all, whatever it contains.
    """

    user_id = str(current_user["_id"])

    try:
        return confirmed_values_for_user(user_id)

    except PyMongoError as error:
        raise _database_error() from error


@router.get("")
def read_reports(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """The user's reports, newest first, without their values."""

    user_id = str(current_user["_id"])

    try:
        documents = list_reports(user_id, limit=limit, skip=skip)
        total = count_reports(user_id)

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "reports": [serialise_report_listing(document) for document in documents],
        "total": total,
        "statuses": list(REPORT_STATUSES),
    }


@router.get("/{report_id}")
def read_report(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """One report with its candidate values and the user's review so far."""

    user_id = str(current_user["_id"])

    try:
        document = get_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "report": serialise_report(document),
        "extraction": extraction_status(),
    }


# ---------------------------------------------------------------------------
# Review and confirmation
# ---------------------------------------------------------------------------


@router.put("/{report_id}/fields")
def update_report_fields(
    report_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Save the user's corrections.

    Saving is not confirming. The values stay outside the trust boundary until
    a separate confirm request, so a review can be done in stages and a
    half-finished one is never mistaken for a completed one.
    """

    user_id = str(current_user["_id"])

    try:
        report = get_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except PyMongoError as error:
        raise _database_error() from error

    try:
        fields = apply_review(
            report.get("fields") or [],
            payload.get("fields"),
            now=_now(),
        )

        updated = save_review(user_id, report["_id"], fields)

    except ReportValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from error

    except ReportNotFoundError as error:
        raise _not_found() from error

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "message": "Your changes were saved. They are not confirmed yet.",
        "report": serialise_report(updated),
    }


@router.post("/{report_id}/confirm")
def confirm_report_values(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """The user's statement that these values match their document.

    The only route that moves a report into the trusted set.
    """

    user_id = str(current_user["_id"])

    try:
        updated = confirm_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except (ReportStateError, ReportValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        ) from error

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "message": (
            "These values are now confirmed and can be used for your guidance."
        ),
        "report": serialise_report(updated),
    }


@router.post("/{report_id}/reopen")
def reopen_report_values(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Take a confirmed report back for further editing.

    The confirmation is withdrawn immediately, so nothing continues to rely on
    values the user has said they want to change.
    """

    user_id = str(current_user["_id"])

    try:
        updated = reopen_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except (ReportStateError, ReportValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        ) from error

    except PyMongoError as error:
        raise _database_error() from error

    return {
        "message": "This report is open for editing again and is not confirmed.",
        "report": serialise_report(updated),
    }


@router.delete("/{report_id}")
def remove_report(
    report_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a report and its uploaded file."""

    user_id = str(current_user["_id"])

    try:
        removed = delete_report(user_id, report_id)

    except ReportNotFoundError as error:
        raise _not_found() from error

    except PyMongoError as error:
        raise _database_error() from error

    file_record = removed.get("file")

    if file_record and file_record.get("key"):
        # The record is already gone, so a failure to remove the file must not
        # fail the request. It is logged rather than raised.
        if not get_storage().delete(file_record["key"]):
            print(
                "MoveWell AI: report deleted but its stored file could not be "
                f"removed (key ending {file_record['key'][-12:]})."
            )

        cleanup_directory_if_empty(user_id)

    return {"message": "Report deleted", "id": str(removed["_id"])}
