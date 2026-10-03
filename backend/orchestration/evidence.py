"""Evidence states, and the one place a domain view is built from them.

Every specialist in this system reasons from a *domain view* of the User
State rather than from the whole thing. This module is the shared
vocabulary those views are written in, so "we have this", "the user never
told us" and "we tried to measure it and could not" stay three different
facts all the way from the User State to the specialist card a user reads.

    KNOWN         a real value the user gave or the system measured.
    MISSING       nothing was collected. Not a zero, not a low value.
    NOT_ASSESSED  a measurement was attempted or offered and produced no
                  usable value (an invalid recording, a skipped check).

MISSING and NOT_ASSESSED are deliberately distinct: "you have not answered
the sleep question" is answerable by asking, while "the camera could not
read your balance check" is answerable by trying again, and neither is
evidence of a deficit. Nothing here infers, defaults or fills a value --
`signal()` records what was found and says so.
"""

KNOWN = "KNOWN"
MISSING = "MISSING"
NOT_ASSESSED = "NOT_ASSESSED"

EVIDENCE_STATES = (KNOWN, MISSING, NOT_ASSESSED)

# A specialist's own summary of what it could establish. INSUFFICIENT_EVIDENCE
# is a real, reportable outcome -- never replaced by generic advice.
STATUS_ASSESSED = "ASSESSED"
STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

DOMAIN_STATUSES = (STATUS_ASSESSED, STATUS_INSUFFICIENT_EVIDENCE)


def signal(name: str, value, *, label: str, unit: str = None, state: str = None) -> dict:
    """One piece of domain evidence, with its state recorded alongside it.

    `state` is derived (KNOWN when a value is present, MISSING when it is
    not) unless the caller passes one explicitly -- which is how a
    NOT_ASSESSED measurement is distinguished from an unanswered question.
    """

    resolved = state or (KNOWN if value is not None else MISSING)

    if resolved not in EVIDENCE_STATES:
        raise ValueError(f"unknown evidence state: {resolved}")

    return {
        "name": name,
        "label": label,
        "value": value if resolved == KNOWN else None,
        "unit": unit,
        "state": resolved,
    }


def known(signals: dict) -> dict:
    """The subset of a view's signals that actually carry a value."""

    return {name: entry for name, entry in signals.items() if entry["state"] == KNOWN}


def missing_labels(signals: dict) -> list:
    """Human-readable labels for everything this domain still needs.

    This is what a specialist reports instead of inventing a recommendation:
    the specific questions that would let it say something real.
    """

    return [
        entry["label"]
        for entry in signals.values()
        if entry["state"] in (MISSING, NOT_ASSESSED)
    ]


def evidence_lines(signals: dict) -> list:
    """One readable line per KNOWN signal, for a specialist's evidence list.

    Only measured or self-reported values appear. A missing signal never
    becomes a line claiming a value of zero.
    """

    lines = []

    for entry in signals.values():
        if entry["state"] != KNOWN:
            continue

        value = entry["value"]
        unit = f" {entry['unit']}" if entry["unit"] else ""
        lines.append(f"{entry['label']}: {value}{unit}")

    return lines


def confidence_from(signals: dict) -> float:
    """How much of this domain's evidence is actually present, 0.0-1.0.

    A blunt but honest measure: the share of the domain's signals that are
    KNOWN. It is never a confidence in the recommendation being *correct*,
    only in how much was known when it was made.
    """

    if not signals:
        return 0.0

    return round(len(known(signals)) / len(signals), 2)
