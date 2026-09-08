"""The one place that reads a Need Profile and says what the *evidence*
looks like — assessed, unassessed, or triggering — plus the single
deterministic rule for the conservative starter pathway.

Why this module exists
----------------------
Before it, two different places each re-derived "is there a physical need
here?" from a Need Profile: `orchestrator/decision.py` (whether to run the
Physio Agent at all) and `physio_agent/agent.py` (which capabilities to
search for). Both used the same MEDIUM/HIGH test, and both silently
treated NOT_ASSESSED exactly like LOW. That is the defect this module
exists to remove: LOW means "we measured it and found no meaningful
deficit"; NOT_ASSESSED means "we could not measure it at all". Those are
different findings and this project's Need schema
(need_assessment/schema.py) already refuses to let them collapse — the
consumers of that schema simply were not honouring the distinction.

It lives in `orchestration/` rather than in `orchestrator/` because both
the Orchestrator and the Physio Agent import it, and `orchestrator/`
imports the agent. `orchestration/` is the shared, dependency-free layer
(ids.py, agent_result.py) that both sides already depend on.

What this module does NOT do
----------------------------
It never upgrades a level. NOT_ASSESSED stays NOT_ASSESSED in the Need
Profile, in the Agent Result's `need_levels`, and in everything derived
from them. Nothing here invents a measurement, a score, a deficit, or a
confidence. The starter pathway below decides only *whether it is
reasonable to offer a conservative, beginner-level plan*, never *that a
deficit exists*.
"""

# The three physical Need dimensions the Physio Agent is responsible for.
# Kept here (rather than re-listed in decision.py and agent.py) so there is
# one definition, not three that can drift.
PHYSICAL_NEED_DIMENSIONS = (
    "mobility_need",
    "stability_need",
    "functional_movement_need",
)

# A dimension at one of these levels is a real, measured need that requires
# specialist intervention. Unchanged from the original rule.
TRIGGERING_LEVELS = ("MEDIUM", "HIGH")

# A dimension at one of these levels was actually evaluated. LOW is here:
# "measured, no meaningful deficit" is evidence. NOT_ASSESSED is not.
ASSESSED_LEVELS = ("LOW", "MEDIUM", "HIGH")

NOT_ASSESSED = "NOT_ASSESSED"


def _level_of(need_profile, dimension):
    """The recorded level for one dimension, or None when the profile does
    not carry that dimension at all (a malformed or partial profile — never
    silently read as LOW)."""

    if not need_profile:
        return None

    entry = need_profile.get(dimension)

    if not isinstance(entry, dict):
        return None

    return entry.get("level")


def evidence_summary(need_profile, dimensions=PHYSICAL_NEED_DIMENSIONS) -> dict:
    """What the Need Profile actually establishes, split three ways.

    Returns::

        {
          "levels":     {dimension: level},            # every dimension present
          "triggering": {dimension: level},            # MEDIUM/HIGH only
          "assessed":   {dimension: level},            # LOW/MEDIUM/HIGH
          "unassessed": (dimension, ...),              # NOT_ASSESSED or absent
        }

    A dimension the profile does not carry is reported as unassessed, which
    is the honest reading: nothing established it.
    """

    levels = {}
    unassessed = []

    for dimension in dimensions:
        level = _level_of(need_profile, dimension)

        if level is None or level == NOT_ASSESSED:
            unassessed.append(dimension)

            if level is not None:
                levels[dimension] = level

            continue

        levels[dimension] = level

    return {
        "levels": levels,
        "triggering": {
            dimension: level
            for dimension, level in levels.items()
            if level in TRIGGERING_LEVELS
        },
        "assessed": {
            dimension: level
            for dimension, level in levels.items()
            if level in ASSESSED_LEVELS
        },
        "unassessed": tuple(unassessed),
    }


def unassessed_evidence(need_profile, dimensions=PHYSICAL_NEED_DIMENSIONS) -> dict:
    """`{dimension: [evidence strings]}` for the unassessed dimensions —
    the Need Assessment's own stated reason it could not evaluate each one.

    Used to tell a user *what* is missing without this module writing a
    sentence of its own about their body. The strings come from
    need_assessment/rules.py, which produced them from real data (or the
    real absence of it); nothing is added here.
    """

    summary = evidence_summary(need_profile, dimensions)
    result = {}

    for dimension in summary["unassessed"]:
        entry = (need_profile or {}).get(dimension)
        evidence = entry.get("evidence") if isinstance(entry, dict) else None
        result[dimension] = list(evidence) if evidence else []

    return result


# ---------------------------------------------------------------------------
# The conservative starter pathway
# ---------------------------------------------------------------------------
#
# THE RULE, in full, so it can be reviewed without reading the code:
#
#   A conservative starter plan applies when, and only when, ALL FOUR of
#   these are true of the physical need dimensions:
#
#     1. No dimension is at MEDIUM or HIGH.
#        (If one were, this is an ordinary evidence-based selection and the
#        starter pathway is irrelevant.)
#     2. At least one dimension is NOT_ASSESSED.
#        (Something could not be measured. With everything measured and
#        nothing above LOW, "no plan is needed" is a true and complete
#        answer, and inventing a plan would be dishonest.)
#     3. At least one dimension WAS assessed.
#        (There is real evidence from a real session. With nothing measured
#        at all, this system knows nothing about the person and must say so
#        and ask for a usable assessment — never guess.)
#     4. No exercise plan exists for this user yet.
#        (The starter plan exists to stop a completed assessment
#        dead-ending at an empty screen. Once a plan exists that job is
#        done, and re-running the workflow on unchanged evidence must not
#        mint a new plan version every time the page is refreshed.)
#
# Condition 3 is what keeps this conservative rather than speculative, and
# condition 1 is what keeps it from ever competing with a real finding.
#
# What the starter plan may then be built from is deliberately narrow, and
# enforced in physio_agent/agent.py rather than here: beginner difficulty
# only, a hard cap well below MAX_EXERCISES_PER_PLAN, every entry carrying
# a rationale that states in words that it is precautionary and not a
# finding of impairment, and the whole plan still passing the same Safety
# Gate as any other. The Need Profile is not modified: the unassessed
# dimensions remain NOT_ASSESSED everywhere.
#
# Deliberately NOT extended to Nutrition or Behaviour. Those two dimensions
# are NOT_ASSESSED when the user has not answered the onboarding questions
# that feed them (need_assessment/rules.py reads `questionnaire` and
# `nutrition`, both from the profile document). The honest response to an
# unanswered question is to ask it, not to prescribe around it — so those
# stay unselected and the Plan screen's next action points at onboarding.
# The physical case is different in kind: the user *did* the work, the
# camera could not read part of it, and asking them to repeat it is a real
# next action that the starter plan sits alongside rather than replaces.


def conservative_starter_applies(need_profile, *, exercise_plan_exists=False) -> bool:
    """The rule documented immediately above, as one boolean."""

    summary = evidence_summary(need_profile)

    if summary["triggering"]:
        return False

    if not summary["unassessed"]:
        return False

    if not summary["assessed"]:
        return False

    return not exercise_plan_exists


def starter_dimensions(need_profile) -> tuple:
    """The dimensions a starter plan is built around: exactly the ones that
    could not be assessed.

    These are the capabilities this system has been unable to rule anything
    in or out about, so a beginner-level, precautionary option is offered
    for them. The assessed-LOW dimensions are excluded on purpose — those
    were measured and showed no deficit, and prescribing for them would be
    inventing a need the evidence contradicts.
    """

    return evidence_summary(need_profile)["unassessed"]
