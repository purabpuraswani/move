"""Assembling a real User State for run_workflow(), given source documents
and whatever User State was already persisted for this user.

`assemble_user_state_from_documents` is the pure, testable core: it takes
already-fetched documents (a profile document, a physical assessment
document, a confirmed-medical-reports document — exactly the shapes
`user_state/schema.py::build_user_state()` already expects), reconciles
them with the previously persisted User State, and returns a fully
-populated User State with `current_needs` recomputed.

Populating `current_needs` here — not left for the caller, and not left to
`run_workflow()` — matches how every existing test in this project wires a
User State before calling `run_workflow()` (see
`tests/test_orchestrator_workflow.py`): `run_workflow()` itself never
invokes Need Assessment; per its own module docstring, Need Assessment runs
"only if current_needs is not already populated". A caller building a User
State from scratch for a real user therefore has to run it once, here,
before the Orchestrator ever sees the state.


THE MERGE RULE
==============

Every section of the User State belongs to exactly one of four classes,
and the class decides who wins when the freshly-built state and the
persisted state disagree. This table is the rule; `_SECTION_CLASSES`
below is the same table in code, and `validate_section_classification()`
fails loudly if a section is ever added to the schema without being
classified here.

1. SOURCE-DERIVED — always taken from the source documents, never from the
   persisted state.

       basic_profile, questionnaire, physical_assessment,
       medical_context, nutrition

   These are projections of documents that live in their own collections
   and have their own write paths. The persisted copy is a snapshot of an
   older projection, so preferring it would let stale data override newer
   source evidence — for instance keeping yesterday's assessment after the
   user completed a new one today. The freshly built value always wins,
   including when the fresh value is *unavailable*: a source document that
   has gone away is a real change, not a reason to resurrect a stale copy.

2. PERSISTED WORKFLOW STATE — carried forward from the persisted state,
   because nothing in the source documents can reproduce it.

       exercise_history, nutrition_plan, behaviour, adherence,
       progress, safety

   These are written only by the workflow itself (orchestrator/
   state_update.py's apply_physio_plan / apply_nutrition_plan /
   apply_behaviour_plan, and the sections reserved for later phases).
   `build_user_state()` has no source for them at all and emits an
   unavailable placeholder, so before this merge existed every run
   silently discarded every plan the previous run had created — the
   defect this module's fix addresses. A persisted section is carried
   forward when it is available; an unavailable persisted section leaves
   the fresh placeholder in place, so a placeholder's explanatory `reason`
   is never lost.

3. DERIVED / RECOMPUTED — never carried forward, always recomputed from
   the merged state.

       current_needs

   It is a pure function of the source-derived sections
   (need_assessment/rules.py reads physical_assessment, questionnaire,
   nutrition and medical_context). Carrying it forward would pin a user's
   needs to the evidence available the first time they ever ran the
   workflow. It is recomputed *after* the merge, so it always describes
   the state actually handed to the Orchestrator.

4. NOT YET COLLECTED — no source and no writer yet; the placeholder from
   `build_user_state()` stands.

       lifestyle

APPEND-ONLY HISTORY. Within class 2, the per-plan history lists
(`exercise_history.data.plans`, `nutrition_plan.data.plans`,
`behaviour.data.plans`) are append-only. This module never rewrites,
reorders, truncates or de-duplicates them: it carries the persisted
section forward whole, and `apply_*_plan` then appends one record and
computes `plan_version` as `len(previous_plans) + 1`. That is what makes
plan versions monotonic across runs — with the merge missing, every run
started from an empty history and every plan was version 1 forever.

BASELINE ASSESSMENT. Untouched by any of this, by construction. The
baseline is not a User State section: it is the user's oldest document in
the assessments collection, read directly by
`assessments.store.baseline_assessment()` (ASCENDING, first). Nothing in
this module, in `build_user_state()`, or in the workflow writes to that
collection, so reassessment adds a new document and leaves the comparison
anchor exactly where it was, byte for byte.

This module imports nothing that requires `pymongo`/`bson` — no database
collection, no ObjectId — so it can be unit-tested in an environment where
those packages are not installed (this project's own sandbox). The only
place that actually reaches into MongoDB is `routes/workflow.py`'s
`build_user_state_for_user()`, a thin wrapper around this function.
"""

from need_assessment.assessment import run_need_assessment
from user_state.schema import SECTION_NAMES, build_user_state, validate_user_state

SOURCE_DERIVED_SECTIONS = (
    "basic_profile",
    "questionnaire",
    "physical_assessment",
    "medical_context",
    "nutrition",
)

PERSISTED_WORKFLOW_SECTIONS = (
    "exercise_history",
    "nutrition_plan",
    "behaviour",
    "adherence",
    "progress",
    "safety",
)

RECOMPUTED_SECTIONS = ("current_needs",)

NOT_YET_COLLECTED_SECTIONS = ("lifestyle",)

# The sections whose `data.plans` list is append-only history. Named here
# only so the guard below can assert they are all class 2 — the appending
# itself is orchestrator/state_update.py's job.
APPEND_ONLY_HISTORY_SECTIONS = (
    "exercise_history",
    "nutrition_plan",
    "behaviour",
)

_SECTION_CLASSES = {
    **{name: "source_derived" for name in SOURCE_DERIVED_SECTIONS},
    **{name: "persisted_workflow_state" for name in PERSISTED_WORKFLOW_SECTIONS},
    **{name: "recomputed" for name in RECOMPUTED_SECTIONS},
    **{name: "not_yet_collected" for name in NOT_YET_COLLECTED_SECTIONS},
}


class UserStateMergeError(ValueError):
    """Raised when the merge rule and the User State schema have drifted
    apart — a section exists that this module does not know how to
    reconcile, or classifies twice."""


def validate_section_classification() -> None:
    """Every schema section is classified exactly once, and nothing is
    classified that is not a section.

    Called at import time (below) so adding a section to
    `user_state/schema.py` without deciding whether it survives a rebuild
    fails immediately and loudly, rather than silently defaulting to
    "discarded" — which is precisely how plans were being lost.
    """

    classified = set(_SECTION_CLASSES)
    schema_sections = set(SECTION_NAMES)

    unclassified = schema_sections - classified

    if unclassified:
        raise UserStateMergeError(
            "User State section(s) not classified by the merge rule in "
            "workflow/assembly.py: " + ", ".join(sorted(unclassified))
        )

    unknown = classified - schema_sections

    if unknown:
        raise UserStateMergeError(
            "workflow/assembly.py classifies section(s) that are not in the "
            "User State schema: " + ", ".join(sorted(unknown))
        )

    total = (
        len(SOURCE_DERIVED_SECTIONS)
        + len(PERSISTED_WORKFLOW_SECTIONS)
        + len(RECOMPUTED_SECTIONS)
        + len(NOT_YET_COLLECTED_SECTIONS)
    )

    if total != len(schema_sections):
        raise UserStateMergeError(
            "a User State section is classified more than once by the merge "
            "rule in workflow/assembly.py"
        )

    for name in APPEND_ONLY_HISTORY_SECTIONS:
        if _SECTION_CLASSES.get(name) != "persisted_workflow_state":
            raise UserStateMergeError(
                f"append-only history section {name!r} must be persisted "
                "workflow state, or its history is discarded on every run"
            )


validate_section_classification()


def merge_persisted_sections(fresh_state: dict, persisted_state) -> dict:
    """Apply the merge rule to one freshly-built state and one persisted
    state, returning a new dict. Neither argument is mutated.

    `persisted_state` is None for a user who has never had a workflow run
    persisted, in which case the fresh state is returned unchanged (a copy).
    """

    merged = dict(fresh_state)

    if not isinstance(persisted_state, dict) or not persisted_state:
        return merged

    for name in PERSISTED_WORKFLOW_SECTIONS:
        section = persisted_state.get(name)

        if not isinstance(section, dict):
            continue

        if not section.get("available"):
            # An unavailable persisted section carries no information the
            # fresh placeholder does not already carry, and the fresh one's
            # `reason` is the current, accurate explanation.
            continue

        merged[name] = section

    return merged


def assemble_user_state_from_documents(
    *,
    profile_doc=None,
    assessment_doc=None,
    confirmed_reports_doc=None,
    persisted_state=None,
    generated_at=None,
) -> dict:
    """Build a full, Need-Assessed User State from already-fetched documents
    and the previously persisted User State.

    Every argument is optional, exactly like `build_user_state()` itself —
    a brand new account with none of these produces a fully-shaped User
    State in which every section is unavailable (and `current_needs` is
    then whatever Need Assessment concludes from an all-unavailable state,
    never invented, never skipped).

    `persisted_state` is the `state` sub-document of this user's stored
    workflow state (`user_state.store.get_user_state()`), or None. Passing
    it is what keeps previously created plans — and their version history —
    alive across runs; omitting it reproduces the pre-fix behaviour of
    discarding them.
    """

    state = build_user_state(
        profile_doc=profile_doc,
        assessment_doc=assessment_doc,
        confirmed_reports_doc=confirmed_reports_doc,
        generated_at=generated_at,
    )

    state = merge_persisted_sections(state, persisted_state)

    # The merged state must still be a well-formed User State before Need
    # Assessment reads it — a persisted document that has drifted from the
    # current schema is a real problem and is surfaced here, not carried
    # silently into the Orchestrator.
    validate_user_state(state)

    return run_need_assessment(state)
