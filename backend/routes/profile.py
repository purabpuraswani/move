from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Form, status
from pymongo.errors import PyMongoError

from auth.deps import get_current_user
from database import db
from config import REPORT_MAX_UPLOAD_BYTES
from nutrition_library import check_in
from routes.profile_spec import (
    EDITABLE_KEYS,
    ProfileValidationError,
    USER_FIELD_KEYS,
    calculate_bmi,
    describe,
    validate_changes,
)

import os
from datetime import datetime
from uuid import uuid4


router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"]
)


UPLOAD_DIR = "uploads"


@router.post("/complete")
def complete_profile(
    current_user: dict = Depends(get_current_user),

    age: int = Form(...),
    sex: str = Form(...),

    height_cm: float = Form(...),
    weight_kg: float = Form(...),

    daily_sitting_hours: float = Form(...),
    daily_screen_hours: float = Form(...),

    sleep_hours: float = Form(...),
    sleep_quality: str = Form(...),

    daily_steps: int = Form(...),

    exercise_days: int = Form(...),
    exercise_minutes: int = Form(...),

    work_type: str = Form(...),

    diabetes: str = Form(...),
    hypertension: str = Form(...),
    heart_condition: str = Form(...),

    previous_injury: str = Form(...),
    joint_pain: str = Form(...),
    back_neck_pain: str = Form(...),

    other_conditions: str = Form(""),

    # Optional, added in Phase 4 for the Nutrition Agent. Optional (not
    # required, unlike every field above) so the existing onboarding form,
    # which does not send these yet, keeps working unchanged — a UI to
    # actually collect them is separate, later work (see docs/architecture.md's
    # Phase 4 "known limitations"). Self-reported estimates, not food-tracking
    # data, mirroring exactly how daily_sitting_hours etc. above are collected.
    meal_pattern: str | None = Form(None),
    fruit_vegetable_servings: float | None = Form(None),
    water_glasses_per_day: float | None = Form(None),
    processed_food_frequency: str | None = Form(None),

    documents: list[UploadFile] | None = File(None)
):

    # Identity comes from the verified token, never from the request body.
    # get_current_user has already confirmed this user exists.
    user_id = str(current_user["_id"])


    # Calculate BMI
    height_m = height_cm / 100

    bmi = weight_kg / (height_m * height_m)


    # Save profile
    profile = {

        "user_id": user_id,

        "age": age,
        "sex": sex,

        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "bmi": round(bmi, 2),

        "daily_sitting_hours": daily_sitting_hours,
        "daily_screen_hours": daily_screen_hours,

        "sleep_hours": sleep_hours,
        "sleep_quality": sleep_quality,

        "daily_steps": daily_steps,

        "exercise_days": exercise_days,
        "exercise_minutes": exercise_minutes,

        "work_type": work_type,

        "meal_pattern": meal_pattern,
        "fruit_vegetable_servings": fruit_vegetable_servings,
        "water_glasses_per_day": water_glasses_per_day,
        "processed_food_frequency": processed_food_frequency,

        "health": {

            "diabetes": diabetes,
            "hypertension": hypertension,
            "heart_condition": heart_condition,

            "previous_injury": previous_injury,
            "joint_pain": joint_pain,
            "back_neck_pain": back_neck_pain,

            "other_conditions": other_conditions
        },

        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


    # Replace existing profile if present
    db["health_profiles"].update_one(
        {"user_id": user_id},
        {"$set": profile},
        upsert=True
    )


    # Save documents
    if documents:

        user_upload_dir = os.path.join(
            UPLOAD_DIR,
            user_id
        )

        os.makedirs(
            user_upload_dir,
            exist_ok=True
        )


        for document in documents:

            if not document.filename:
                continue


            allowed_extensions = [
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png"
            ]

            extension = os.path.splitext(
                document.filename
            )[1].lower()


            if extension not in allowed_extensions:
                continue


            # Generated name, not the client-supplied one: an uploaded
            # filename is untrusted input and must never reach a filesystem path.
            stored_filename = f"{uuid4().hex}{extension}"


            file_path = os.path.join(
                user_upload_dir,
                stored_filename
            )


            # Phase 6 security fix: this upload path had no size cap,
            # unlike reports/storage.py's own upload path. Reuses the same
            # REPORT_MAX_UPLOAD_BYTES limit (config.py) rather than
            # inventing a second, separate one for the same concern
            # (an oversized file exhausting disk space). Written in
            # bounded chunks, and rejected/cleaned up mid-write rather
            # than after the fact, exactly like reports/storage.py's own
            # check.
            total_written = 0
            oversized = False

            with open(file_path, "wb") as buffer:
                while True:
                    chunk = document.file.read(1024 * 1024)

                    if not chunk:
                        break

                    total_written += len(chunk)

                    if total_written > REPORT_MAX_UPLOAD_BYTES:
                        oversized = True
                        break

                    buffer.write(chunk)

            if oversized:
                os.remove(file_path)
                continue


            document_record = {

                "user_id": user_id,

                "filename": document.filename,

                "stored_filename": stored_filename,

                "file_type": document.content_type,

                "path": file_path,

                "uploaded_at": datetime.utcnow()
            }


            db["health_documents"].insert_one(
                document_record
            )


    return {
        "message": "Profile completed successfully",
        "bmi": round(bmi, 2)
    }


# Fields the dashboard needs, and nothing else.
#
# The stored profile also holds self-reported health answers (diabetes, joint
# pain, and so on). Those are not sent to the browser here, because no screen
# that reads this endpoint needs them, and health information should not travel
# further than the feature that actually uses it.
LIFESTYLE_FIELDS = (
    "daily_sitting_hours",
    "daily_screen_hours",
    "sleep_hours",
    "sleep_quality",
    "daily_steps",
    "exercise_days",
    "exercise_minutes",
    "work_type",
    "bmi",
    "age",
    "sex"
)


@router.get("/summary")
def profile_summary(
    current_user: dict = Depends(get_current_user)
):
    """The lifestyle answers this user gave during setup.

    These are self-reported values from onboarding, not measurements and not
    anything this application observed. A screen showing them has to label them
    that way, because "8.2 hours sitting" is something the user told us once,
    not something tracked today.

    A user who has not completed onboarding gets complete=False rather than
    zeros, so the interface can say there is nothing yet instead of inventing
    values.
    """

    user_id = str(current_user["_id"])

    profile = db["health_profiles"].find_one(
        {"user_id": user_id}
    )


    if not profile:

        return {
            "complete": False,
            "profile": None
        }


    summary = {
        field: profile.get(field)
        for field in LIFESTYLE_FIELDS
        if profile.get(field) is not None
    }


    updated_at = profile.get("updated_at")


    return {
        "complete": True,

        "profile": summary,

        "updatedAt": (
            updated_at.isoformat()
            if hasattr(updated_at, "isoformat")
            else None
        )
    }


# ---------------------------------------------------------------------------
# The editable profile
#
# Three endpoints over the SAME profile document the onboarding write above
# maintains: read it, change part of it, and read/patch the Nutrition &
# Lifestyle check-in. Nothing is stored anywhere else, so the User State the
# Orchestrator reads (user_state/schema.py, via the profile document) picks up a
# change here on the next run without any extra plumbing.
# ---------------------------------------------------------------------------


PROFILE_WRITE_FAILED = (
    "Your profile could not be saved right now. This is a server or database "
    "problem, so nothing was changed."
)


def _database_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=PROFILE_WRITE_FAILED,
    )


def _user_object_id(user_id: str):
    from bson import ObjectId

    return ObjectId(user_id)


def _profile_document(user_id: str):
    return db["health_profiles"].find_one({"user_id": user_id}) or {}


def _profile_response(user_id: str, *, message: str = None) -> dict:
    """The editable profile as the browser sees it: sections with values, never
    the stored document itself, and never the health answers."""

    document = _profile_document(user_id)
    user = db.users.find_one({"_id": _user_object_id(user_id)}) or {}

    values = dict(document)
    values["name"] = user.get("name")

    updated_at = document.get("updated_at")

    response = {
        "complete": bool(document),
        "sections": describe(values),
        "bmi": document.get("bmi"),
        "updatedAt": (
            updated_at.isoformat() if hasattr(updated_at, "isoformat") else None
        ),
        "nutritionCheckIn": {
            "complete": check_in.is_complete(document),
            "unanswered": check_in.unanswered_keys(document),
        },
    }

    if message:
        response["message"] = message

    return response


@router.get("")
def read_profile(current_user: dict = Depends(get_current_user)):
    """The caller's editable profile, section by section.

    A user who has not completed onboarding gets `complete: false` and empty
    values rather than zeros, so the editor can say there is nothing yet
    instead of inventing numbers.
    """

    return _profile_response(str(current_user["_id"]))


@router.patch("")
def update_profile(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Apply a partial change to the caller's profile.

    Only the fields sent are touched, so a save from one section cannot wipe
    another. A value outside a field's own range or vocabulary is refused with
    400 rather than clamped — and nothing is written when any field in the
    request is rejected, so a partial edit never lands half-applied.
    """

    user_id = str(current_user["_id"])

    changes = payload.get("fields") if isinstance(payload, dict) else None

    if changes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Send the fields to change, e.g. {"fields": {"daily_steps": 6000}}',
        )

    try:
        cleaned = validate_changes(changes)
    except ProfileValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from None

    if not cleaned:
        return _profile_response(user_id, message="Nothing to change.")

    document = _profile_document(user_id)

    updates = {
        key: value for key, value in cleaned.items() if key in EDITABLE_KEYS
    }

    # BMI is derived, never accepted from the client: it is recomputed from
    # whichever of the two stored values is now in force.
    height = updates.get("height_cm", document.get("height_cm"))
    weight = updates.get("weight_kg", document.get("weight_kg"))

    if "height_cm" in updates or "weight_kg" in updates:
        updates["bmi"] = calculate_bmi(height, weight)

    updates["updated_at"] = datetime.utcnow()

    try:
        db["health_profiles"].update_one(
            {"user_id": user_id}, {"$set": updates}, upsert=True
        )

        name = cleaned.get("name")

        if name is not None and "name" in USER_FIELD_KEYS:
            db.users.update_one(
                {"_id": _user_object_id(user_id)},
                {"$set": {"name": name}},
            )
    except PyMongoError as error:
        raise _database_error() from error

    return _profile_response(
        user_id,
        message=(
            "Your profile was updated. Future plan reviews will use the new "
            "information."
        ),
    )


@router.get("/nutrition-check-in")
def read_nutrition_check_in(current_user: dict = Depends(get_current_user)):
    """The Nutrition & Lifestyle check-in: six questions and this user's
    answers.

    The questions and their allowed answers come from the server
    (nutrition_library/check_in.py), so the form cannot offer an answer the
    validation would refuse.
    """

    document = _profile_document(str(current_user["_id"]))
    answers = check_in.answered(document)

    return {
        "questions": check_in.describe(),
        "answers": answers,
        "answeredCount": len(answers),
        "questionCount": len(check_in.QUESTION_KEYS),
        "complete": check_in.is_complete(document),
        "unanswered": check_in.unanswered_keys(document),
    }


@router.patch("/nutrition-check-in")
def update_nutrition_check_in(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Save check-in answers.

    Stored in the same profile document the User State's `nutrition` section is
    built from, which is what makes a completed check-in reach the Need
    Assessment and the Nutrition specialist on the next run. Nothing is
    interpreted here: this endpoint stores what the user selected.
    """

    user_id = str(current_user["_id"])

    answers = payload.get("answers") if isinstance(payload, dict) else None

    if not isinstance(answers, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Send the answers, e.g. {"answers": {"meals_per_day": 3}}',
        )

    cleaned = {}

    for key, value in answers.items():
        try:
            cleaned[key] = check_in.normalise_answer(key, value)
        except check_in.CheckInAnswerError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
            ) from None

    if not cleaned:
        return {
            "message": "Nothing to save.",
            **read_nutrition_check_in(current_user),
        }

    updates = {key: value for key, value in cleaned.items() if value is not None}
    updates["updated_at"] = datetime.utcnow()

    try:
        db["health_profiles"].update_one(
            {"user_id": user_id}, {"$set": updates}, upsert=True
        )
    except PyMongoError as error:
        raise _database_error() from error

    document = _profile_document(user_id)
    answers_now = check_in.answered(document)

    return {
        "message": (
            "Thanks — your nutrition check-in was saved. MoveWell will use it "
            "the next time your plan is prepared."
        ),
        "questions": check_in.describe(),
        "answers": answers_now,
        "answeredCount": len(answers_now),
        "questionCount": len(check_in.QUESTION_KEYS),
        "complete": check_in.is_complete(document),
        "unanswered": check_in.unanswered_keys(document),
    }