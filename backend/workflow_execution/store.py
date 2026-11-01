"""Per-user history of completed orchestrator executions."""

from datetime import datetime, timezone

from database import DuplicateKeyError, workflow_executions_collection


def ensure_indexes():
    workflow_executions_collection.create_index(
        [("user_id", 1), ("execution_key", 1)],
        unique=True,
        name="user_execution_unique",
    )
    workflow_executions_collection.create_index(
        [("user_id", 1), ("created_at", -1)], name="user_created_at"
    )


def save_execution(user_id: str, execution_key: str, record: dict) -> dict:
    """Upsert by caller-owned idempotency key; retries cannot duplicate rows."""
    now = datetime.now(timezone.utc)
    saved = {**record, "user_id": user_id, "execution_key": execution_key, "updated_at": now}
    try:
        workflow_executions_collection.update_one(
            {"user_id": user_id, "execution_key": execution_key},
            {"$set": saved, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except DuplicateKeyError:
        # Concurrent retries may both reach persistence after the initial
        # lookup. The unique compound index makes the first write canonical.
        existing = get_execution(user_id, execution_key)
        if existing is not None:
            return existing
        raise
    return workflow_executions_collection.find_one(
        {"user_id": user_id, "execution_key": execution_key}
    )


def get_execution(user_id: str, execution_key: str):
    return workflow_executions_collection.find_one(
        {"user_id": user_id, "execution_key": execution_key}
    )


def latest_execution(user_id: str):
    rows = list(workflow_executions_collection.find({"user_id": user_id}).sort("created_at", -1).limit(1))
    return rows[0] if rows else None


def list_executions(user_id: str, limit: int = 20):
    return list(
        workflow_executions_collection.find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(max(1, min(int(limit), 100)))
    )
