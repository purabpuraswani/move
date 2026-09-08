"""Real, ownership-scoped, append-only persistence for user food logs.

Mirrors backend/exercise_assessment/'s split exactly: schema.py validates a
submitted entry and never touches a database; store.py stores and reads
entries with ownership enforced in every query, and never re-validates
content.

Food logs are deliberately NOT a User State section. Phase 5 set the
precedent with exercise results: user-submitted, accumulating, per-event
data lives in its own collection and is read directly by whatever needs it
(there, the Progress Agent; here, nutrition_agent/adherence.py), rather
than being threaded through user_state/schema.py — which keeps
build_user_state()'s section list and schema version stable.

Nothing here calculates a calorie total for a user, judges a food as good
or bad, or turns a log into a clinical claim.
"""
