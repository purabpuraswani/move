"""What is getting in the way, and the smallest change that addresses it.

The Behaviour & Adherence specialist's distinctive question is not "what
should this person do?" -- that belongs to Physio (which exercise) and to
Exercise & Physical Activity (how much). It is "will they actually do it,
and if not, what is in the way?". This module answers only that, from two
sources and no others:

  * the user's own recorded actions, as counted by
    behaviour_agent/adherence.py; and
  * the `common_barriers` the behaviour library already publishes for the
    topics this user's plan actually selected.

Nothing here invents a barrier, and nothing here recommends an exercise.
An absence of recorded actions is reported as an absence of evidence, not
as a user who is failing to keep up -- a plan a user has not had time to
record is not a plan they have abandoned.
"""

from behaviour_agent.adherence import ADHERED, INSUFFICIENT_DATA, NOT_ADHERED, NOT_LOGGED

# A plan with more goals than this, in the presence of real evidence that
# the user is not keeping up, is treated as a plan worth shrinking before
# anything is added to it. A system decision, not a behavioural finding.
MAX_GOALS_WHEN_STRUGGLING = 2


def identify_barriers(adherence: dict, topics: list) -> list:
    """Barriers, each tied to the evidence that produced it."""

    barriers = []
    status = (adherence or {}).get("status")

    if status == NOT_ADHERED:
        barriers.append(
            {
                "barrier": "inconsistent_adherence",
                "source": "recorded_actions",
                "evidence": (adherence or {}).get("summary")
                or "Recorded actions show fewer completions than the plan asked for.",
            }
        )
    elif status in (NOT_LOGGED, INSUFFICIENT_DATA):
        barriers.append(
            {
                "barrier": "not_enough_recorded_evidence",
                "source": "recorded_actions",
                "evidence": (adherence or {}).get("summary")
                or "Not enough recorded actions yet to say how the plan is going.",
            }
        )

    for topic in topics or []:
        for text in topic.get("common_barriers") or []:
            barriers.append(
                {
                    "barrier": "known_barrier_for_topic",
                    "source": f"behaviour_library:{topic.get('topic_id')}",
                    "evidence": text,
                }
            )

    return barriers


def behaviour_interventions(adherence: dict, barriers: list, goal_count: int) -> list:
    """Adherence interventions. Never an exercise, never a dose.

    Each one changes the *shape* of the plan or the cue around it -- how
    many goals there are, how small the first step is, what triggers it --
    which is this specialist's own lever. Recommending more exercise in
    response to missed exercise would simply be the Exercise specialist's
    advice repeated louder.
    """

    status = (adherence or {}).get("status")
    barrier_types = {entry["barrier"] for entry in barriers or []}
    interventions = []

    if "inconsistent_adherence" in barrier_types:
        if goal_count > MAX_GOALS_WHEN_STRUGGLING:
            interventions.append(
                {
                    "id": "reduce_plan_complexity",
                    "intervention": (
                        f"Cut back from {goal_count} active habit goals to "
                        f"{MAX_GOALS_WHEN_STRUGGLING} and keep the two you are most "
                        "likely to repeat."
                    ),
                    "addresses": "inconsistent_adherence",
                }
            )

        interventions.append(
            {
                "id": "shrink_first_action",
                "intervention": (
                    "Halve the size of the first action so that starting takes under two "
                    "minutes; a started habit can grow, a skipped one cannot."
                ),
                "addresses": "inconsistent_adherence",
            }
        )
        interventions.append(
            {
                "id": "attach_habit_trigger",
                "intervention": (
                    "Attach each remaining goal to something you already do every day, so "
                    "the cue is the existing routine rather than remembering."
                ),
                "addresses": "inconsistent_adherence",
            }
        )

    if "not_enough_recorded_evidence" in barrier_types:
        interventions.append(
            {
                "id": "record_one_action",
                "intervention": (
                    "Record each goal as you do it for the next week. Without that there is "
                    "nothing to review, and the plan stays a guess."
                ),
                "addresses": "not_enough_recorded_evidence",
            }
        )

    if status == ADHERED and goal_count:
        interventions.append(
            {
                "id": "keep_current_routine",
                "intervention": (
                    "Keep the routine as it is. It is being followed, so the useful change "
                    "is none."
                ),
                "addresses": "sustained_adherence",
            }
        )

    return interventions
