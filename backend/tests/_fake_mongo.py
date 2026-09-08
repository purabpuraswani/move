"""An in-memory stand-in for the one collection reports/store.py talks to.

Not a general MongoDB emulator. It implements exactly the operations
reports/store.py calls — insert_one, find_one, find_one_and_update, find
(with sort/skip/limit), delete_one, count_documents, create_index — with
just enough of $set (including dotted paths) and $in to exercise the real,
unmodified store module end to end without a live database.

This mirrors the project's existing pattern of a test-only fake standing in
for an external dependency (see physio_agent/tool_client.py's
InProcessProgressToolClient, used the same way by
test_physio_agent_mcp_integration.py): the code under test is the real
module, unmodified: only the collection it is handed is swapped out. Real
bson.ObjectId is used for ids so the same test works whether pymongo is
actually installed or not; nothing here parses Mongo query syntax beyond
what reports/store.py itself ever sends.
"""

import copy

from bson import ObjectId

ASCENDING = 1
DESCENDING = -1


def _get_path(doc, path):
    node = doc

    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None

        node = node[part]

    return node


def _set_path(doc, path, value):
    parts = path.split(".")
    node = doc

    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}

        node = node[part]

    node[parts[-1]] = value


_RANGE_OPERATORS = {"$gte", "$gt", "$lte", "$lt"}


def _matches(doc, query):
    for key, expected in (query or {}).items():
        if key == "_id":
            actual = doc.get("_id")

            if isinstance(expected, dict) and "$in" in expected:
                if not any(str(actual) == str(value) for value in expected["$in"]):
                    return False

            elif str(actual) != str(expected):
                return False

            continue

        actual = _get_path(doc, key)

        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False

        elif isinstance(expected, dict) and _RANGE_OPERATORS & set(expected):
            # Range comparison, added for food_log/store.py's recorded_at
            # filter. Still not a Mongo emulator: only the operators that
            # store module actually sends are understood.
            for operator, bound in expected.items():
                if operator not in _RANGE_OPERATORS:
                    raise NotImplementedError(
                        f"tests/_fake_mongo.py does not implement {operator!r}"
                    )

                if actual is None:
                    return False

                if operator == "$gte" and not actual >= bound:
                    return False

                if operator == "$gt" and not actual > bound:
                    return False

                if operator == "$lte" and not actual <= bound:
                    return False

                if operator == "$lt" and not actual < bound:
                    return False

        elif actual != expected:
            return False

    return True


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, field, direction=ASCENDING):
        def key(doc):
            value = _get_path(doc, field)
            missing = value is None

            return (missing, 0 if missing else value, doc.get("__seq", 0))

        self._docs.sort(key=key, reverse=(direction == DESCENDING))

        return self

    def skip(self, n):
        self._docs = self._docs[n:]

        return self

    def limit(self, n):
        self._docs = self._docs[:n]

        return self

    def __iter__(self):
        return iter(self._docs)


class FakeReportsCollection:
    """Stands in for reports.store.reports_collection in a test."""

    def __init__(self):
        self._docs = {}
        self._seq = 0

    def create_index(self, *_args, **_kwargs):
        return "fake_index"

    def insert_one(self, document):
        doc = copy.deepcopy(document)
        doc["_id"] = ObjectId()
        self._seq += 1
        doc["__seq"] = self._seq
        self._docs[str(doc["_id"])] = doc

        class _Result:
            inserted_id = doc["_id"]

        return _Result()

    def find_one(self, query=None):
        for doc in self._docs.values():
            if _matches(doc, query or {}):
                return copy.deepcopy(doc)

        return None

    def find_one_and_update(self, query, update, return_document=True):
        for doc in self._docs.values():
            if _matches(doc, query or {}):
                for path, value in (update.get("$set") or {}).items():
                    _set_path(doc, path, value)

                return copy.deepcopy(doc)

        return None

    def delete_one(self, query):
        for key, doc in list(self._docs.items()):
            if _matches(doc, query or {}):
                del self._docs[key]

                class _Result:
                    deleted_count = 1

                return _Result()

        class _Result:
            deleted_count = 0

        return _Result()

    def count_documents(self, query=None):
        return sum(1 for doc in self._docs.values() if _matches(doc, query or {}))

    def find(self, query=None, _projection=None):
        docs = [
            copy.deepcopy(doc)
            for doc in self._docs.values()
            if _matches(doc, query or {})
        ]

        return FakeCursor(docs)


class FakeFoodLogCollection(FakeReportsCollection):
    """Stands in for food_log.store.food_log_collection in a test.

    food_log/store.py sends exactly the operations FakeReportsCollection
    already implements (insert_one, find with sort/skip/limit,
    find_one, count_documents, create_index) plus a $gte/$lte range on
    recorded_at, handled by _matches above. Subclassed rather than aliased
    so a reader of a food-log test sees which collection is being faked.
    """
