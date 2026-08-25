from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from database import db

import os
import shutil
from datetime import datetime


router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"]
)


UPLOAD_DIR = "uploads"


@router.post("/complete")
async def complete_profile(
    user_id: str = Form(...),

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

    documents: list[UploadFile] | None = File(None)
):

    # Check user exists
    user = db["users"].find_one({
        "_id": __import__("bson").ObjectId(user_id)
    })

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )


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


            stored_filename = (
                f"{datetime.utcnow().timestamp()}_"
                f"{document.filename}"
            )


            file_path = os.path.join(
                user_upload_dir,
                stored_filename
            )


            with open(file_path, "wb") as buffer:

                shutil.copyfileobj(
                    document.file,
                    buffer
                )


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