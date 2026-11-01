from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Body

from auth.deps import get_current_user
from database import db
from config import REPORT_MAX_UPLOAD_BYTES

import os
from datetime import datetime, timezone
from uuid import uuid4
import json


def _parse_optional_string_list(value: str | None, field: str) -> list[str] | None:
    """Read JSON list form fields while preserving missing (None) vs [] (none)."""
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"{field} must be a JSON array of strings") from error
    if not isinstance(parsed, list) or any(
        not isinstance(item, str) or not item.strip() for item in parsed
    ):
        raise HTTPException(status_code=422, detail=f"{field} must be a JSON array of non-empty strings")
    return [item.strip() for item in parsed]


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
    stress_level: str | None = Form(None),
    recovery_difficulties: str | None = Form(None),

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

    # Optional self-reported dietary-pattern context for the Nutrition Agent.
    # Older clients may omit these fields; they remain unknown rather than
    # being converted into a negative answer.
    meal_pattern: str | None = Form(None),
    fruit_vegetable_servings: float | None = Form(None),
    water_glasses_per_day: float | None = Form(None),
    processed_food_frequency: str | None = Form(None),
    # JSON arrays let profile clients submit multiple values. Omitted fields
    # stay unknown; [] is an explicit no-allergy/no-restriction answer.
    food_preferences: str | None = Form(None),
    dietary_restrictions: str | None = Form(None),
    food_allergies: str | None = Form(None),
    nutrition_goals: str | None = Form(None),
    # Optional Behaviour Agent context; comma-separated values are decoded
    # into profile lists, and an omitted field remains unknown.
    behaviour_motivation: str | None = Form(None),
    preferred_habits: str | None = Form(None),
    reported_behaviour_barriers: str | None = Form(None),
    daily_routines: str | None = Form(None),
    preferred_habit_changes: str | None = Form(None),

    documents: list[UploadFile] | None = File(None)
):

    # Identity comes from the verified token, never from the request body.
    # get_current_user has already confirmed this user exists.
    user_id = str(current_user["_id"])


    # Calculate BMI
    height_m = height_cm / 100

    bmi = weight_kg / (height_m * height_m)


    nutrition_context = {
        field: _parse_optional_string_list(value, field)
        for field, value in (
            ("food_preferences", food_preferences),
            ("dietary_restrictions", dietary_restrictions),
            ("food_allergies", food_allergies),
            ("nutrition_goals", nutrition_goals),
        )
    }
    behaviour_context = {
        "behaviour_motivation": (
            behaviour_motivation.strip() if behaviour_motivation and behaviour_motivation.strip() else None
        ),
        "preferred_habits": _parse_optional_string_list(preferred_habits, "preferred_habits"),
        "reported_behaviour_barriers": _parse_optional_string_list(
            reported_behaviour_barriers, "reported_behaviour_barriers"
        ),
        "daily_routines": _parse_optional_string_list(daily_routines, "daily_routines"),
        "preferred_habit_changes": _parse_optional_string_list(
            preferred_habit_changes, "preferred_habit_changes"
        ),
    }
    normalized_stress = (stress_level or "").strip().lower() or None
    if normalized_stress not in (None, "low", "moderate", "high"):
        raise HTTPException(status_code=422, detail="stress_level must be low, moderate, or high")
    recovery_context = {
        "stress_level": normalized_stress,
        "recovery_difficulties": _parse_optional_string_list(
            recovery_difficulties, "recovery_difficulties"
        ),
    }

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
        **recovery_context,

        "daily_steps": daily_steps,

        "exercise_days": exercise_days,
        "exercise_minutes": exercise_minutes,

        "work_type": work_type,

        "meal_pattern": meal_pattern,
        "fruit_vegetable_servings": fruit_vegetable_servings,
        "water_glasses_per_day": water_glasses_per_day,
        "processed_food_frequency": processed_food_frequency,
        **nutrition_context,
        **behaviour_context,

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


PROFILE_EDIT_FIELDS = (
    "age", "sex", "height_cm", "weight_kg", "daily_sitting_hours",
    "daily_screen_hours", "sleep_hours", "sleep_quality", "stress_level",
    "recovery_difficulties", "daily_steps", "exercise_days", "exercise_minutes",
    "work_type", "meal_pattern", "fruit_vegetable_servings",
    "water_glasses_per_day", "processed_food_frequency", "food_preferences",
    "dietary_restrictions", "food_allergies", "nutrition_goals",
    "behaviour_motivation", "preferred_habits", "reported_behaviour_barriers",
    "daily_routines", "preferred_habit_changes", "health",
)


@router.get("/edit")
def read_profile_for_edit(current_user: dict = Depends(get_current_user)):
    """Editable self-reported profile fields for the authenticated user."""
    profile = db["health_profiles"].find_one({"user_id": str(current_user["_id"])})
    if not profile:
        return {"complete": False, "profile": {}}
    return {
        "complete": True,
        "profile": {
            **{field: profile.get(field) for field in PROFILE_EDIT_FIELDS if field != "health"},
            "health": profile.get("health") or {},
        },
    }


@router.patch("/edit")
def update_profile_fields(
    body: dict = Body(...), current_user: dict = Depends(get_current_user)
):
    """Patch supplied editable fields; omitted means unchanged, null means unknown.

    Empty lists are retained as explicit negative answers. Identity is always
    derived from the authenticated token.
    """
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="Provide profile fields to update")
    unexpected = set(body) - set(PROFILE_EDIT_FIELDS)
    if unexpected:
        raise HTTPException(status_code=422, detail=f"Unsupported profile field(s): {', '.join(sorted(unexpected))}")

    updates = {}
    list_fields = {
        "food_preferences", "dietary_restrictions", "food_allergies", "nutrition_goals",
        "recovery_difficulties", "preferred_habits", "reported_behaviour_barriers",
        "daily_routines", "preferred_habit_changes",
    }
    numeric_fields = {
        "age": int, "height_cm": float, "weight_kg": float,
        "daily_sitting_hours": float, "daily_screen_hours": float,
        "sleep_hours": float, "daily_steps": int, "exercise_days": int,
        "exercise_minutes": int, "fruit_vegetable_servings": float,
        "water_glasses_per_day": float,
    }
    for field, value in body.items():
        if value is None:
            updates[field] = None
            continue
        if field == "health":
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail="health must be an object")
            allowed_health_fields = {
                "diabetes", "hypertension", "heart_condition", "previous_injury",
                "joint_pain", "back_neck_pain", "other_conditions",
            }
            if set(value) - allowed_health_fields:
                raise HTTPException(status_code=422, detail="health contains an unsupported field")
            existing = db["health_profiles"].find_one({"user_id": str(current_user["_id"])}) or {}
            health = dict(existing.get("health") or {})
            for key, answer in value.items():
                if key == "other_conditions":
                    if answer is not None and not isinstance(answer, str):
                        raise HTTPException(status_code=422, detail="health.other_conditions must be text or null")
                    health[key] = answer.strip() if isinstance(answer, str) else None
                elif answer not in ("yes", "no", "prefer_not_to_say", None):
                    raise HTTPException(status_code=422, detail=f"health.{key} must be yes, no, or prefer_not_to_say")
                else:
                    health[key] = answer
            updates["health"] = health
            continue
        if field in list_fields:
            if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
                raise HTTPException(status_code=422, detail=f"{field} must be an array of non-empty strings")
            updates[field] = [item.strip() for item in value]
        elif field in numeric_fields:
            try:
                number = numeric_fields[field](value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{field} must be numeric") from None
            if number < 0:
                raise HTTPException(status_code=422, detail=f"{field} cannot be negative")
            updates[field] = number
        elif field == "stress_level":
            if value not in ("low", "moderate", "high"):
                raise HTTPException(status_code=422, detail="stress_level must be low, moderate, or high")
            updates[field] = value
        elif isinstance(value, str):
            updates[field] = value.strip()
        else:
            raise HTTPException(status_code=422, detail=f"{field} must be text")

    if not updates:
        raise HTTPException(status_code=400, detail="No profile values were provided")
    updates["updated_at"] = datetime.utcnow()
    db["health_profiles"].update_one(
        {"user_id": str(current_user["_id"])}, {"$set": updates}, upsert=True
    )
    return {"message": "Profile updated", "updated_fields": sorted(k for k in updates if k != "updated_at")}


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
    if hasattr(updated_at, "tzinfo") and updated_at.tzinfo is None:
        # Profile edits historically stored naive UTC datetimes. Mark those
        # values as UTC before returning them so browser comparisons with
        # timezone-aware workflow timestamps are consistent.
        updated_at = updated_at.replace(tzinfo=timezone.utc)


    return {
        "complete": True,

        "profile": summary,

        "updatedAt": (
            updated_at.isoformat()
            if hasattr(updated_at, "isoformat")
            else None
        )
    }
