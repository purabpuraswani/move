"""Storing what the agents produced.

A guidance run costs a model call, so the last one is kept. Without that, opening
the page would either spend money on every visit or show nothing until the user
asked again, and the second is what makes people stop asking.

Stored runs carry the fingerprint of the context they were written from. When the
user records a new assessment or confirms another report the fingerprint stops
matching, and the interface can say the guidance was written before that rather
than presenting it as current. Guidance that silently describes yesterday's data
is the failure this is here to prevent.

The same two rules as the other stores: ownership is part of every query rather
than a check afterwards, and documents are serialised explicitly on the way out.
"""

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING

from database import db

guidance_collection = db["guidance_runs"]

# One user's runs, newest first, which is the only query this store makes.
INDEX_NAME = "user_created_at"


def ensure_indexes():
    """Create the index the read path relies on. Safe to run repeatedly."""

    guidance_collection.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name=INDEX_NAME,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.isoformat()

    return value


def save_run(user_id: str, result: dict) -> dict:
    """Keep one completed run. Returns the stored document."""

    context = result.get("context") or {}

    document = {
        "user_id": user_id,
        "created_at": _now(),
        "ran": bool(result.get("ran")),
        "provider": result.get("provider"),
        "model": result.get("model"),
        # The fingerprint of the inputs, not the inputs. A copy of the report
        # values would be the same health information in a second place, and the
        # screens that own it are already responsible for it.
        "context_signature": context.get("signature"),
        "context_summary": context,
        "plan": result.get("plan"),
        "agents": result.get("agents") or {},
    }

    stored = guidance_collection.insert_one(document)

    document["_id"] = stored.inserted_id

    return document


def latest_run(user_id: str):
    """The newest run for this user, or None."""

    return guidance_collection.find_one(
        {"user_id": user_id},
        sort=[("created_at", DESCENDING)],
    )


def count_runs(user_id: str) -> int:
    return guidance_collection.count_documents({"user_id": user_id})


def serialise_run(document: dict, *, current_signature=None) -> dict:
    """One stored run, with whether it still matches the user's data."""

    signature = document.get("context_signature")

    return {
        "id": str(document["_id"]),
        "generatedAt": _isoformat(document.get("created_at")),
        "ran": bool(document.get("ran")),
        "provider": document.get("provider"),
        "model": document.get("model"),
        "context": document.get("context_summary") or {},
        "plan": document.get("plan") or {},
        "agents": document.get("agents") or {},
        # None when there is nothing to compare against, which is not the same
        # as being current and is left for the caller to phrase.
        "isStale": (
            None
            if not (signature and current_signature)
            else signature != current_signature
        ),
    }
