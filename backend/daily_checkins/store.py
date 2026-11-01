"""Authenticated-user scoped daily check-in history (one merged record/day)."""
from datetime import datetime, timezone
from database import daily_checkins_collection, ASCENDING, DESCENDING


def save_daily_checkin(user_id, date, values):
    query = {"user_id": user_id, "date": date}
    current = daily_checkins_collection.find_one(query) or {}
    merged = {**current, **values, "user_id": user_id, "date": date,
              "updated_at": datetime.now(timezone.utc)}
    daily_checkins_collection.update_one(query, {"$set": merged}, upsert=True)
    return daily_checkins_collection.find_one(query)


def list_daily_checkins(user_id, limit=90):
    return list(daily_checkins_collection.find({"user_id": user_id}).sort("date", DESCENDING).limit(limit))


def serialise(document):
    return {key: document.get(key) for key in (
        "date", "sleep_hours", "sleep_quality", "stress_level", "recovery_difficulty",
        "steps", "sitting_minutes", "walking_minutes", "movement_breaks",
        "fruit_vegetable_servings", "water_intake_ml")}
