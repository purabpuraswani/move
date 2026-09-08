"""Persistence for the User State run_workflow() produces (Phase 6).

One document per user, upserted in place — this is deliberately NOT a
history collection like `assessments_collection`/`exercise_results_collection`.
The User State's own sections already keep their own per-plan history
internally (`exercise_history.data.plans`, `nutrition_plan.data.plans`,
`behaviour.data.plans` — see orchestrator/state_update.py), so this
collection's only job is "what does this user currently have", read back
by `GET /api/workflow/latest`. A second, parallel history here would be a
second source of truth for the same fact and is deliberately not built.

The Safety Result a run produced is stored alongside the User State (as
`last_safety_result`) rather than inside it: `user_state/schema.py`'s
`safety` section is reserved for a not-yet-built deterministic
safety/escalation section of its own (see NOT_YET_COLLECTED["safety"]) and
is not the same thing as one run's Safety Gate outcome, so overloading it
here would misrepresent that section's real, still-unpopulated status.

Ownership discipline matches every other store in this project: every read
and write is keyed by `user_id`, and the id is never accepted from
anywhere but the caller (the authenticated user, resolved from their own
token by auth/deps.get_current_user) — never from a request body or query
string.
"""

from datetime import datetime, timezone

from database import user_state_collection


def ensure_indexes():
    """Create the index the read/write paths rely on. Safe to run
    repeatedly: createIndex is a no-op when the index already exists."""

    user_state_collection.create_index(
        "user_id", unique=True, name="user_id_unique"
    )


def save_user_state(user_id: str, state: dict, *, safety_result: dict = None) -> dict:
    """Persist the given User State (and the Safety Result that produced
    it, if any) as this user's current state. Upserts in place — a second
    call for the same user replaces the previous document, it never
    accumulates a duplicate."""

    now = datetime.now(timezone.utc)

    set_fields = {
        "user_id": user_id,
        "state": state,
        "updated_at": now,
    }
    if safety_result is not None:
        set_fields["last_safety_result"] = safety_result

    result = user_state_collection.update_one(
        {"user_id": user_id},
        {
            "$set": set_fields,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    saved = user_state_collection.find_one({"user_id": user_id})

    return {
        "document": saved,
        "created": result.upserted_id is not None,
    }


def get_user_state(user_id: str):
    """This user's currently persisted User State document, or None if
    run_workflow() has never been run (and its result persisted) for
    them."""

    return user_state_collection.find_one({"user_id": user_id})

