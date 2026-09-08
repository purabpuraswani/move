"""Reading the three sources a context is built from.

Kept apart from agents/context.py so that the assembly and rendering rules can be
tested without a database, and so there is exactly one function in the codebase
that fetches data on an agent's behalf. An agent that wanted something else would
have to add it here, in the open.

What is read is narrow by design. The newest movement session rather than the
history, because guidance about a session from four months ago that presents
itself as current is worse than no guidance. Confirmed report values only, which
is not a filter applied here but a property of the function being called:
`confirmed_values_for_user` refuses to serialise anything else. And a count of
the user's reports, purely so a context can say how many are still waiting to be
confirmed without ever touching what is in them.

Ownership is in every query, as everywhere else in this project: the user id
comes from the caller, which got it from a verified token, and no read here can
be satisfied by a document belonging to somebody else.
"""

from agents.context import build_context
from assessments.store import latest_assessment, serialise_assessment
from database import db
from reports.store import confirmed_values_for_user, count_reports

profiles_collection = db["health_profiles"]

# The onboarding answers. Written by routes/profile.py, read here.
PROFILE_FILTER_FIELD = "user_id"


def load_profile(user_id: str):
    """The user's onboarding answers, or None."""

    return profiles_collection.find_one({PROFILE_FILTER_FIELD: user_id})


def load_assessment(user_id: str):
    """The newest movement session, serialised, or None."""

    document = latest_assessment(user_id)

    if document is None:
        return None

    return serialise_assessment(document)


def load_context(user_id: str) -> dict:
    """Everything the agents may read about this user, assembled once.

    Called once per request that needs guidance, so the three sources are read
    together and both agents see the same picture. Running them against contexts
    fetched at different moments would let one refer to a report the other had
    never seen.
    """

    confirmed = confirmed_values_for_user(user_id)

    return build_context(
        profile_summary=load_profile(user_id),
        assessment=load_assessment(user_id),
        confirmed_reports=confirmed,
        report_totals={"total": count_reports(user_id)},
    )
