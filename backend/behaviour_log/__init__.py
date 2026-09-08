"""Behaviour Action log: the evidence a habit plan is reviewed against.

Two modules, the same split every other user-submitted record in this
project uses:

    schema.py   validates one submitted action, and refuses anything it
                cannot accept -- including any adherence figure, which is
                computed from records and never submitted.
    store.py    persists and reads actions, scoped to their owner.

Nothing here interprets a record. What an action -- or an absence of one --
means is behaviour_agent/adaptation.py's job, and its rule is that no
recorded action is never read as failure.
"""
