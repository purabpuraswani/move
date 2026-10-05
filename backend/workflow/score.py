"""The MoveWell Score: your own results, said as one number you can follow.

WHY THIS EXISTS, AND WHAT IT IS NOT
===================================
Every other number in MoveWell is a measurement — an arm elevation in degrees, a
sit-to-stand time, a hold in seconds. Nobody can hold six of those in their head
and tell whether they are getting better. So this module adds the one thing the
product was missing: a single 0-100 view of the same evidence, which moves in one
direction, and which the whole app can be organised around.

It is NOT a new assessment, a new threshold, or a clinical measure. It is a
restatement of what `need_assessment` already decided:

    need score 0.00 -> 100   (nothing in this domain needs attention)
    need score 1.00 ->   0   (this domain is at the far end of the project's own
                              markers)

Each domain's need score already comes from a real measurement or a real answer,
against thresholds that `need_assessment/rules.py` documents as project decisions
rather than clinical cut-offs. This module inverts that number for presentation
and averages the domains that were actually assessed. It computes no threshold of
its own and reads no data `need_assessment` did not already produce.

THE RULES THAT KEEP IT HONEST
=============================
* A domain with no usable evidence is `NOT_ASSESSED`, carries **no value at all**,
  and is excluded from the average rather than counted as zero. "We do not know"
  must never look like "you scored badly".
* The overall score exists only when at least one **measured** movement domain
  was assessed. A number built only from questionnaire answers would read as a
  health score while being a summary of what somebody typed, so it is not shown;
  the answered domains still show their own values.
* The band wording ("You're doing well overall") is derived from the *levels* the
  need assessment already assigned, not from new cut points on this 0-100 number.
* The method is returned with the score, because a number a user is asked to
  follow should come with an explanation of where it came from.
"""

NEED_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
    "behaviour_need",
    "nutrition_need",
    "exercise_need",
)

# What each dimension is called to a person. "Functional movement" rather than
# "functional movement need": the score reads as an ability, not a deficit.
DOMAIN_LABELS = {
    "mobility_need": "Mobility",
    "stability_need": "Stability",
    "functional_movement_need": "Functional movement",
    "behaviour_need": "Behaviour",
    "nutrition_need": "Nutrition",
    "exercise_need": "Activity",
}

# Which domains are measured on the user's own device by the movement
# assessment, and which come from what they told us. Shown per domain, because
# a number derived from three camera checks and a number derived from four
# questions should not look alike.
MEASURED_DOMAINS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
)
ANSWERED_DOMAINS = (
    "behaviour_need",
    "nutrition_need",
    "exercise_need",
)

SOURCE_MEASURED = "measured"
SOURCE_ANSWERED = "answered"

# Band wording, keyed on the levels the need assessment already produced. No new
# numeric cut points: a HIGH anywhere means there is a domain at the far end of
# this project's markers, whatever the average happens to be.
BAND_GOING_WELL = "GOING_WELL"
BAND_STEADY = "STEADY"
BAND_ROOM_TO_IMPROVE = "ROOM_TO_IMPROVE"

BAND_MESSAGES = {
    BAND_GOING_WELL: "You're doing well overall.",
    BAND_STEADY: "You're doing well overall, with a couple of areas worth working on.",
    BAND_ROOM_TO_IMPROVE: "There's clear room to improve in one area.",
}

METHOD = (
    "Worked out from your own results: each movement check and each answer you "
    "gave is compared against MoveWell's own markers, and the areas you have "
    "not been assessed for are left out rather than counted against you. It is "
    "a way of following your own progress, not a medical measurement."
)

# The order domains are listed in, so the same score always reads the same way.
DOMAIN_ORDER = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
    "behaviour_need",
    "nutrition_need",
    "exercise_need",
)


def _domain_value(entry) -> int:
    """The 0-100 view of one need entry. Higher is better."""

    need = entry.get("score")

    return int(round((1.0 - float(need)) * 100))


def _source_of(dimension: str) -> str:
    return (
        SOURCE_MEASURED if dimension in MEASURED_DOMAINS else SOURCE_ANSWERED
    )


def _focus_statement(dimension: str, level: str) -> str:
    """One sentence naming a focus area, from the level that produced it."""

    label = DOMAIN_LABELS[dimension]
    measured = dimension in MEASURED_DOMAINS

    if level == "HIGH":
        origin = "Your latest assessment" if measured else "What you told us"
        return (
            f"{origin} suggests {label.lower()} is where MoveWell can help most "
            "right now."
        )

    origin = "your latest assessment" if measured else "your answers"
    return (
        f"{label} came out as a focus area in {origin}, so MoveWell has built "
        "your plan around it."
    )


def build_movewell_score(user_state: dict) -> dict:
    """The score block for one User State.

    Pure: no I/O, no clock, no model. The same state always produces the same
    score, which is what makes it safe to show a user and to compare across
    sessions.
    """

    section = (user_state or {}).get("current_needs") or {}
    data = (section.get("data") or {}) if section.get("available") else {}

    domains = []
    assessed_values = []
    assessed_measured = 0
    highest_level = "LOW"
    focus_candidates = []

    for dimension in DOMAIN_ORDER:
        entry = data.get(dimension)

        if not isinstance(entry, dict):
            continue

        level = entry.get("level")
        need = entry.get("score")
        assessed = level not in (None, "NOT_ASSESSED") and need is not None

        domain = {
            "key": dimension,
            "label": DOMAIN_LABELS[dimension],
            "source": _source_of(dimension),
            "assessed": bool(assessed),
            "value": _domain_value(entry) if assessed else None,
            "level": level if assessed else "NOT_ASSESSED",
            # The need assessment's own reason for this level, untouched. It is
            # the same wording the specialist screens already show.
            "evidence": list(entry.get("evidence") or []),
        }

        domains.append(domain)

        if not assessed:
            continue

        assessed_values.append(domain["value"])

        if dimension in MEASURED_DOMAINS:
            assessed_measured += 1

        if level == "HIGH":
            highest_level = "HIGH"
        elif level == "MEDIUM" and highest_level != "HIGH":
            highest_level = "MEDIUM"

        focus_candidates.append((float(need), dimension, level))

    # Only a measured movement domain can carry the headline number: a score
    # built from questionnaire answers alone would be a summary of what somebody
    # typed, presented as a health score.
    available = assessed_measured > 0 and bool(assessed_values)

    if not available:
        return {
            "available": False,
            "value": None,
            "band": None,
            "message": None,
            "focus": None,
            "focus_statement": None,
            "domains": domains,
            "previous": None,
            "change": None,
            "method": METHOD,
        }

    value = int(round(sum(assessed_values) / len(assessed_values)))

    band = {
        "HIGH": BAND_ROOM_TO_IMPROVE,
        "MEDIUM": BAND_STEADY,
        "LOW": BAND_GOING_WELL,
    }[highest_level]

    focus = None
    focus_statement = None

    if focus_candidates:
        # The greatest need wins. Ties fall to the domain order above, so the
        # same evidence always names the same focus.
        need, dimension, level = max(
            focus_candidates, key=lambda item: (item[0], -DOMAIN_ORDER.index(item[1]))
        )

        focus = {"key": dimension, "label": DOMAIN_LABELS[dimension], "level": level}
        focus_statement = _focus_statement(dimension, level)

    return {
        "available": True,
        "value": value,
        "band": band,
        "message": BAND_MESSAGES[band],
        "focus": focus,
        "focus_statement": focus_statement,
        "domains": domains,
        "previous": None,
        "change": None,
        "method": METHOD,
    }


def with_previous(
    score: dict,
    previous_value,
    previous_recorded_at=None,
    previous_domains=None,
) -> dict:
    """Attach the previous score, and the change, when one exists.

    Kept separate from `build_movewell_score` because the previous score comes
    from a different session (a different User State), which this module has no
    business fetching. `change` is null rather than zero when there is nothing to
    compare: "no change measured" and "no previous measurement" are different
    statements, and a `0` would collapse them.

    `previous_domains` is `{dimension: value}` from that earlier session. Where
    it is supplied, each domain carries its own `previous_value` and `change`, so
    a screen can say which area moved rather than only that the total did.
    """

    score = dict(score)
    per_domain = previous_domains or {}

    domains = []

    for domain in score.get("domains") or []:
        earlier = per_domain.get(domain["key"])

        if isinstance(earlier, (int, float)) and not isinstance(earlier, bool):
            domain = {
                **domain,
                "previous_value": int(earlier),
                "change": (
                    int(domain["value"]) - int(earlier)
                    if domain.get("value") is not None
                    else None
                ),
            }
        else:
            domain = {**domain, "previous_value": None, "change": None}

        domains.append(domain)

    score["domains"] = domains

    previous = None

    if isinstance(previous_value, (int, float)) and not isinstance(previous_value, bool):
        previous = {
            "value": int(previous_value),
            "recorded_at": previous_recorded_at,
        }

    score["previous"] = previous
    score["change"] = (
        int(score["value"]) - previous["value"]
        if previous is not None and score.get("value") is not None
        else None
    )

    return score
