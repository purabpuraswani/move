import atexit

from pymongo import MongoClient

from config import MONGODB_DB_NAME, MONGODB_URI


# serverSelectionTimeoutMS keeps a wrong or unreachable URI from hanging for
# the default 30 seconds before reporting the problem.
# For development on Windows with MongoDB Atlas, disable SSL verification
client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    retryWrites=False
)

db = client[MONGODB_DB_NAME]


# The client is created once at import and lives for the whole process, which
# is the right lifetime for a connection pool -- but nothing was closing it,
# so every test run ended with pymongo's "Unclosed MongoClient" ResourceWarning
# and its socket-cleanup traceback.
#
# Registering the close at exit keeps that lifetime exactly as it was (nothing
# here opens, reuses or shortens a connection differently) and only adds the
# teardown that was missing. It is deliberately not a context manager or a
# per-request client: that would change the pooling behaviour every module
# importing these collections relies on.
atexit.register(client.close)

users_collection = db["users"]

# One document per assessment session, never overwritten in place, so a user
# accumulates a history rather than a single current result.
assessments_collection = db["assessments"]

# One document per submitted exercise performance result (Phase 5). Same
# discipline as assessments_collection: never overwritten in place, so this
# is the real, structured performance history the Progress Agent reads —
# not the "plan was created" record `exercise_history` (a User State
# section) already keeps.
exercise_results_collection = db["exercise_results"]

# One document per logged food/meal entry. Same append-only, ownership-scoped
# discipline as exercise_results_collection, and deliberately NOT a User State
# section for the same reason exercise results are not: per-event
# user-submitted data belongs in its own collection, read directly by whoever
# needs it (nutrition_agent/adherence.py), which keeps build_user_state()'s
# section list and schema version stable.
food_log_collection = db["food_log"]

# Recorded behaviour actions -- the user saying they did (or skipped) a
# habit goal their plan set. Append-only, exactly like food_log_collection
# and exercise_results_collection: one document per action, never
# overwritten, so "how has this been going" is answered from records rather
# than from a running total that could drift from them.
behaviour_log_collection = db["behaviour_log"]

# One document per user, holding the current persisted User State plus the
# most recent Safety Result produced for it (Phase 6). Unlike
# assessments_collection/exercise_results_collection, this is deliberately
# NOT an append-only history collection — the User State's own sections
# (exercise_history, nutrition_plan, behaviour) already keep per-plan
# history internally; this collection tracks "what this user currently
# has", upserted in place, read back by GET /api/workflow/latest
# (routes/workflow.py, user_state/store.py).
user_state_collection = db["user_state"]
