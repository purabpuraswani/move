"""Persistent SQLite document collections used by the backend.

The application stores JSON-shaped records in SQLite tables. SQLite is part
of Python's standard library, so local development needs no database server.
The small collection interface keeps the existing ownership-scoped store
modules readable while all data is persisted in ``backend/movewell.sqlite3``.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ASCENDING = 1
DESCENDING = -1


class InvalidId(ValueError):
    """An invalid 24-character document id."""


class ObjectId(str):
    """Small BSON-compatible identifier type backed by a random 24-hex id."""

    def __new__(cls, value: str | None = None):
        value = value or uuid.uuid4().hex[:24]
        if not isinstance(value, str) or len(value) != 24:
            raise InvalidId("document ids must be 24 hexadecimal characters")
        try:
            int(value, 16)
        except ValueError:
            raise InvalidId("document ids must be 24 hexadecimal characters") from None
        return str.__new__(cls, value.lower())


class StorageError(Exception):
    """Base class for persistence errors handled by API routes."""


class DuplicateKeyError(StorageError):
    """Raised when a declared unique index would be violated."""


@dataclass
class InsertOneResult:
    inserted_id: ObjectId


@dataclass
class UpdateResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: ObjectId | None = None


@dataclass
class DeleteResult:
    deleted_count: int = 0


def _encode(value: Any):
    if isinstance(value, ObjectId):
        return {"__sqlite_type__": "object_id", "value": str(value)}
    if isinstance(value, datetime):
        return {"__sqlite_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    return value


def _decode(value: Any):
    if isinstance(value, dict):
        kind = value.get("__sqlite_type__")
        if kind == "object_id":
            return ObjectId(value["value"])
        if kind == "datetime":
            return datetime.fromisoformat(value["value"])
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _get_path(document: dict, path: str):
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _set_path(document: dict, path: str, value: Any):
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        if not isinstance(target.get(part), dict):
            target[part] = {}
        target = target[part]
    target[parts[-1]] = copy.deepcopy(value)


def _unset_path(document: dict, path: str):
    parts = path.split(".")
    target = document
    for part in parts[:-1]:
        target = target.get(part)
        if not isinstance(target, dict):
            return
    target.pop(parts[-1], None)


def _compare(actual: Any, condition: Any) -> bool:
    if not isinstance(condition, dict) or not any(str(key).startswith("$") for key in condition):
        return actual == condition
    for operator, expected in condition.items():
        try:
            if operator == "$in":
                if not any(item in (actual if isinstance(actual, list) else [actual]) for item in expected):
                    return False
            elif operator == "$nin":
                if any(item in (actual if isinstance(actual, list) else [actual]) for item in expected):
                    return False
            elif operator == "$exists":
                if (actual is not None) != bool(expected):
                    return False
            elif operator == "$ne":
                if actual == expected:
                    return False
            elif operator == "$eq":
                if actual != expected:
                    return False
            elif operator == "$gt" and not (actual is not None and actual > expected):
                return False
            elif operator == "$gte" and not (actual is not None and actual >= expected):
                return False
            elif operator == "$lt" and not (actual is not None and actual < expected):
                return False
            elif operator == "$lte" and not (actual is not None and actual <= expected):
                return False
            elif operator not in {"$in", "$nin", "$exists", "$ne", "$eq", "$gt", "$gte", "$lt", "$lte"}:
                raise ValueError(f"SQLite document store does not support {operator}")
        except TypeError:
            return False
    return True


def _matches(document: dict, query: dict | None) -> bool:
    for key, condition in (query or {}).items():
        if key == "$or":
            if not any(_matches(document, item) for item in condition):
                return False
        elif key == "$and":
            if not all(_matches(document, item) for item in condition):
                return False
        elif not _compare(_get_path(document, key), condition):
            return False
    return True


def _project(document: dict, projection: dict | None):
    if not projection:
        return document
    included = [key for key, enabled in projection.items() if enabled]
    if included:
        result = {}
        for path in included:
            value = _get_path(document, path)
            if value is not None:
                _set_path(result, path, value)
        if projection.get("_id", 1) and "_id" in document:
            result["_id"] = document["_id"]
        return result
    result = copy.deepcopy(document)
    for path, enabled in projection.items():
        if not enabled:
            _unset_path(result, path)
    return result


class Cursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction=ASCENDING):
        fields = [(field, direction)] if isinstance(field, str) else list(field)
        for name, order in reversed(fields):
            self.documents.sort(
                key=lambda doc: (_get_path(doc, name) is None, _get_path(doc, name)),
                reverse=order == DESCENDING,
            )
        return self

    def skip(self, amount):
        self.documents = self.documents[max(0, amount):]
        return self

    def limit(self, amount):
        if amount:
            self.documents = self.documents[:amount]
        return self

    def __iter__(self):
        return iter(self.documents)


class SQLiteCollection:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.table = f"collection_{name}"
        self.unique_indexes: list[tuple[str, ...]] = []
        with self.client.lock:
            self.client.connection.execute(
                f'CREATE TABLE IF NOT EXISTS "{self.table}" '
                '(id TEXT PRIMARY KEY, document TEXT NOT NULL)'
            )

    def _all(self):
        try:
            rows = self.client.connection.execute(
                f'SELECT document FROM "{self.table}"'
            ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(f"Could not read SQLite collection {self.name}: {error}") from error
        return [_decode(json.loads(row[0])) for row in rows]

    def _save(self, document):
        payload = json.dumps(_encode(document), separators=(",", ":"), ensure_ascii=False)
        try:
            self.client.connection.execute(
                f'INSERT INTO "{self.table}" (id, document) VALUES (?, ?) '
                'ON CONFLICT(id) DO UPDATE SET document=excluded.document',
                (str(document["_id"]), payload),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateKeyError(f"Unique value already exists in {self.name}") from error
        except sqlite3.Error as error:
            raise StorageError(f"Could not write SQLite collection {self.name}: {error}") from error

    def _check_unique(self, document, exclude_id=None):
        others = [item for item in self._all() if str(item.get("_id")) != str(exclude_id)]
        for fields in self.unique_indexes:
            values = tuple(_get_path(document, field) for field in fields)
            if any(tuple(_get_path(item, field) for field in fields) == values for item in others):
                raise DuplicateKeyError(f"unique index violation in {self.name}: {fields}")

    def create_index(self, keys, name=None, unique=False, **_options):
        fields = tuple(key for key, _direction in keys) if isinstance(keys, list) else (keys,)
        index_name = name or "_".join(fields)
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", index_name)
        expressions = []
        for field in fields:
            path = "$." + field.replace("'", "''")
            expressions.append(f"json_extract(document, '{path}')")
        kind = "UNIQUE " if unique else ""
        try:
            self.client.connection.execute(
                f'CREATE {kind}INDEX IF NOT EXISTS "idx_{self.table}_{safe_name}" '
                f'ON "{self.table}" ({", ".join(expressions)})'
            )
            self.client.connection.commit()
        except sqlite3.IntegrityError as error:
            raise DuplicateKeyError(f"Existing data violates unique index {index_name}") from error
        except sqlite3.Error as error:
            raise StorageError(f"Could not create SQLite index {index_name}: {error}") from error
        if unique and fields not in self.unique_indexes:
            self.unique_indexes.append(fields)
        return index_name

    def insert_one(self, document):
        saved = copy.deepcopy(document)
        saved.setdefault("_id", ObjectId())
        with self.client.lock:
            self._check_unique(saved)
            self._save(saved)
            self.client.connection.commit()
        return InsertOneResult(saved["_id"])

    def find(self, query=None, projection=None):
        with self.client.lock:
            documents = [_project(doc, projection) for doc in self._all() if _matches(doc, query)]
        return Cursor(documents)

    def find_one(self, query=None, projection=None, sort=None):
        cursor = self.find(query, projection)
        if sort:
            cursor.sort(sort)
        return next(iter(cursor), None)

    def count_documents(self, query=None):
        with self.client.lock:
            return sum(_matches(doc, query) for doc in self._all())

    def _apply_update(self, document, update, inserting=False):
        if not any(str(key).startswith("$") for key in update):
            result = copy.deepcopy(update)
            result.setdefault("_id", document.get("_id", ObjectId()))
            return result
        result = copy.deepcopy(document)
        if inserting:
            for path, value in update.get("$setOnInsert", {}).items():
                _set_path(result, path, value)
        for path, value in update.get("$set", {}).items():
            _set_path(result, path, value)
        for path in update.get("$unset", {}):
            _unset_path(result, path)
        for path, value in update.get("$inc", {}).items():
            _set_path(result, path, (_get_path(result, path) or 0) + value)
        for path, value in update.get("$push", {}).items():
            current = _get_path(result, path) or []
            current = list(current)
            current.append(copy.deepcopy(value))
            _set_path(result, path, current)
        for path, value in update.get("$addToSet", {}).items():
            current = list(_get_path(result, path) or [])
            if value not in current:
                current.append(copy.deepcopy(value))
            _set_path(result, path, current)
        return result

    def update_one(self, query, update, upsert=False):
        with self.client.lock:
            for old in self._all():
                if _matches(old, query):
                    new = self._apply_update(old, update)
                    self._check_unique(new, old.get("_id"))
                    self._save(new)
                    self.client.connection.commit()
                    return UpdateResult(1, int(new != old))
            if not upsert:
                return UpdateResult()
            base = {key: value for key, value in query.items() if not key.startswith("$") and not isinstance(value, dict)}
            new = self._apply_update({**base, "_id": ObjectId()}, update, inserting=True)
            self._check_unique(new)
            self._save(new)
            self.client.connection.commit()
            return UpdateResult(upserted_id=new["_id"])

    def update_many(self, query, update):
        with self.client.lock:
            matched = [doc for doc in self._all() if _matches(doc, query)]
            for old in matched:
                new = self._apply_update(old, update)
                self._check_unique(new, old.get("_id"))
                self._save(new)
            self.client.connection.commit()
            return UpdateResult(len(matched), sum(self._apply_update(doc, update) != doc for doc in matched))

    def find_one_and_update(self, query, update, return_document=True):
        with self.client.lock:
            old = self.find_one(query)
            if old is None:
                return None
            self.update_one(query, update)
            return self.find_one(query) if return_document else old

    def delete_one(self, query):
        with self.client.lock:
            for doc in self._all():
                if _matches(doc, query):
                    self.client.connection.execute(
                        f'DELETE FROM "{self.table}" WHERE id=?', (str(doc["_id"]),)
                    )
                    self.client.connection.commit()
                    return DeleteResult(1)
        return DeleteResult()


class SQLiteDatabase:
    def __init__(self, client):
        self.client = client

    def __getitem__(self, name):
        return self.client.collection(name)


class SQLiteClient:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.lock = threading.RLock()
        self.collections = {}

    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = SQLiteCollection(self, name)
        return self.collections[name]

    def __getitem__(self, name):
        return SQLiteDatabase(self)[name]

    def close(self):
        self.connection.close()


load_dotenv(Path(__file__).with_name(".env"))

_database_path = Path(
    os.getenv("SQLITE_PATH", str(Path(__file__).with_name("movewell.sqlite3")))
)
if not _database_path.is_absolute():
    _database_path = Path(__file__).parent / _database_path
client = SQLiteClient(_database_path)
db = SQLiteDatabase(client)

users_collection = db["users"]
assessments_collection = db["assessments"]
exercise_results_collection = db["exercise_results"]
food_log_collection = db["food_log"]
behaviour_log_collection = db["behaviour_log"]
daily_checkins_collection = db["daily_checkins"]
user_state_collection = db["user_state"]
workflow_executions_collection = db["workflow_executions"]
password_reset_tokens_collection = db["password_reset_tokens"]

# Email uniqueness is required by signup; enforce it in the local store too.
users_collection.create_index("email", unique=True, name="email_unique")
