from fastapi import APIRouter, Depends, UploadFile, File, Form

from auth.deps import get_current_user
from database import db
from config import REPORT_MAX_UPLOAD_BYTES

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