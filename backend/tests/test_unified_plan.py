"""Tests for the five-specialist unified plan (workflow/response.py).

These are the acceptance criteria of the adaptive-system rebuild, written as
executable checks:

* exactly five specialists, and Exercise & Movement is one of them rather
  than an exercise specialist beside a physiotherapy specialist;
* selection comes from this user's own evidence, and differs between users;
* NOT_ASSESSED stays distinct from "assessed and fine";
* exercise items come only from the existing 20-exercise intervention
  library, by library id;
* every plan item carries a position, a specialist, a section, a domain plan
  id where one exists, a domain item id where one exists, and an action the
  client can follow without deciding anything itself;
* the Safety specialist's ALLOW / MODIFY / PAUSE / REFER verdict reaches the
  plan;
* recorded results are read back into tracking and progress, so the next
  plan can adapt from them.
"""

import unittest

from exercise_library.catalog import list_exercise_ids
from orchestration.specialists import (
    ACTION_COMPLETE_HABIT,
    ACTION_LOG_NUTRITION,
    ACTION_START_EXERCISE,
    ACTION_VIEW_GUIDANCE,
    BEHAVIOUR_ADHERENCE,
    EXERCISE_MOVEMENT,
    NUTRITION_LIFESTYLE,
    RECOVERY_CARE,
    SAFETY_PRACTITIONER,
    SPECIALIST_ORDER,
)
from workflow.response import (
    build_specialists_team,
    build_unified_plan,
    never_run_response,
    serialise_workflow_state,
)


def _safety(status="ALLOW", **overrides):
    result = {
        "status": status,
        "reason": f"Safety outcome {status}.",
        "flags": [],
        "actions": [],
        "requires_referral": status == "REFER",
        "blocked_recommendation_ids": [],
        "modified_recommendation_ids": [],
    }
    result.update(overrides)

    return result


def _needs(**levels):
    data = {"evidence": ["recorded evidence"]}

    profile = {
        dimension: {**data, "level": level}
        for dimension, level in levels.items()
    }

    return {"available": True, "data": profile}


def _exercise_plan(exercise_ids, *, plan_id="plan_1", version=1, progress=False):
    exercises = []

    for exercise_id in exercise_ids:
        exercises.append(
            {
                "exercise_id": exercise_id,
                "sets": 2,
                "repetitions": 8,
                "rationale": f"{exercise_id} matched your movement evidence.",
                "target_need": "mobility_need",
                "difficulty": "beginner",
                "decision_type": "PROGRESS" if progress else "ADD",
            }
        )

    return {
        "available": True,
        "data": {
            "plans": [
                {
                    "plan_id": plan_id,
                    "plan_version": version,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "goal": "Move more freely.",
                    "exercise_ids": list(exercise_ids),
                    "exercises": exercises,
                    "decisions": [],
                    "selection_mode": "need_based",
                    "capabilities_targeted": ["mobility"],
                }
            ]
        },
    }


def _topic_plan(section_goals, *, plan_id, key="goals"):
    return {
        "available": True,
        "data": {
            "plans": [
                {
                    "plan_id": plan_id,
                    "plan_version": 1,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "goal": "A goal",
                    "topic_ids": [goal["topic_id"] for goal in section_goals],
                    key: section_goals,
                    "decisions": [],
                }
            ]
        },
    }


class FiveSpecialistTeamTests(unittest.TestCase):
    def test_team_is_exactly_five_specialists_in_order(self):
        team = build_specialists_team({})

        self.assertEqual(len(team), 5)
        self.assertEqual([card["id"] for card in team], list(SPECIALIST_ORDER))

    def test_exercise_and_movement_is_one_specialist(self):
        team = build_specialists_team({})
        ids = {card["id"] for card in team}

        self.assertIn(EXERCISE_MOVEMENT, ids)
        # The two removed user-facing specialists must not come back as
        # cards of their own under any id.
        for removed in ("exercise_activity", "physio", "exercise", "movement"):
            self.assertNotIn(removed, ids)

    def test_removed_specialist_names_are_not_presented(self):
        team = build_specialists_team({})
        titles = " ".join(card["title"] for card in team)

        self.assertNotIn("Physiotherapy", titles)
        self.assertNotIn("Physical Activity", titles)
        self.assertNotIn("Clinical Escalation", titles)
        self.assertIn("Safety & Practitioner Recommendation", titles)

    def test_every_card_is_either_selected_reviewed_or_unassessed(self):
        team = build_specialists_team({})

        for card in team:
            self.assertIn(
                card["status"], ("ACTIVE", "EVALUATED_NOT_REQUIRED", "NOT_ASSESSED")
            )
            self.assertIsInstance(card["reason"], str)
            self.assertTrue(card["reason"], f"{card['id']} has no reason")


class DynamicSelectionTests(unittest.TestCase):
    """Different users must get different specialists, from their own data."""

    def test_high_movement_need_selects_exercise_movement(self):
        card = next(
            c
            for c in build_specialists_team(
                {"current_needs": _needs(mobility_need="HIGH")}
            )
            if c["id"] == EXERCISE_MOVEMENT
        )

        self.assertEqual(card["status"], "ACTIVE")

    def test_low_movement_need_with_high_behaviour_need_selects_differently(self):
        state = {
            "current_needs": _needs(
                mobility_need="LOW",
                stability_need="LOW",
                functional_movement_need="LOW",
                behaviour_need="HIGH",
            ),
            "questionnaire": {
                "available": True,
                "data": {"daily_steps": 9000, "daily_sitting_hours": 5, "exercise_days": 4},
            },
        }

        cards = {card["id"]: card for card in build_specialists_team(state)}

        self.assertEqual(cards[EXERCISE_MOVEMENT]["status"], "EVALUATED_NOT_REQUIRED")
        self.assertEqual(cards[BEHAVIOUR_ADHERENCE]["status"], "ACTIVE")

    def test_poor_sleep_selects_recovery_and_limits_progression(self):
        state = {
            "current_needs": _needs(mobility_need="HIGH"),
            "questionnaire": {
                "available": True,
                "data": {"sleep_duration_hours": 5.0, "sleep_quality": "poor"},
            },
        }

        plan = build_unified_plan(state, safety_result=_safety())

        recovery = next(
            card
            for card in plan["specialists"]
            if card["id"] == RECOVERY_CARE
        )

        self.assertEqual(recovery["status"], "ACTIVE")
        self.assertTrue(
            any(
                constraint["source"] == RECOVERY_CARE
                and constraint["type"] == "limit_progression"
                for constraint in plan["constraints"]
            )
        )

    def test_not_assessed_is_not_low(self):
        card = next(
            c
            for c in build_specialists_team({})
            if c["id"] == NUTRITION_LIFESTYLE
        )

        self.assertEqual(card["status"], "NOT_ASSESSED")
        self.assertNotEqual(card["status"], "EVALUATED_NOT_REQUIRED")

    def test_unanswered_questionnaire_does_not_activate_nutrition(self):
        state = {"current_needs": _needs(nutrition_need="NOT_ASSESSED")}
        cards = {card["id"]: card for card in build_specialists_team(state)}

        self.assertEqual(cards[NUTRITION_LIFESTYLE]["status"], "NOT_ASSESSED")


class ExerciseSelectionTests(unittest.TestCase):
    def test_every_exercise_item_is_a_library_id(self):
        library = set(list_exercise_ids())

        plan = build_unified_plan(
            {"exercise_history": _exercise_plan(["chair-sit-to-stand", "wall-sit"])},
            safety_result=_safety(),
        )

        exercises = [item for item in plan["items"] if item["kind"] == "exercise"]

        self.assertEqual(len(exercises), 2)

        for item in exercises:
            self.assertIn(item["item_id"], library)
            self.assertEqual(item["metadata"]["exercise_id"], item["item_id"])

    def test_baseline_tests_never_appear_as_intervention_exercises(self):
        library = set(list_exercise_ids())
        plan = build_unified_plan(
            {"exercise_history": _exercise_plan(["chair-sit-to-stand"])},
            safety_result=_safety(),
        )

        for item in plan["items"]:
            self.assertNotIn(item["item_id"], ("shoulder", "ftsst", "balance"))
            if item["kind"] == "exercise":
                self.assertIn(item["item_id"], library)

    def test_exercise_action_preserves_exercise_plan_and_item_ids(self):
        plan = build_unified_plan(
            {
                "exercise_history": _exercise_plan(
                    ["chair-sit-to-stand"], plan_id="plan_xyz"
                )
            },
            safety_result=_safety(),
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["plan_id"], "plan_xyz")
        self.assertEqual(item["item_id"], "chair-sit-to-stand")
        self.assertEqual(item["action"]["kind"], ACTION_START_EXERCISE)
        self.assertIn("/exercise/chair-sit-to-stand", item["action"]["route"])
        self.assertIn("planId=plan_xyz", item["action"]["route"])
        self.assertIn("itemId=chair-sit-to-stand", item["action"]["route"])

    def test_no_workflow_or_mongo_identifiers_are_exposed(self):
        plan = build_unified_plan(
            {"exercise_history": _exercise_plan(["wall-sit"])},
            safety_result=_safety(),
        )

        keys = set()

        def collect(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    keys.add(key)
                    collect(nested)
            elif isinstance(value, (list, tuple)):
                for nested in value:
                    collect(nested)

        collect(plan)

        for forbidden in ("workflow_id", "request_id", "agent_run_id", "_id"):
            self.assertNotIn(forbidden, keys)


class ItemContractTests(unittest.TestCase):
    def _full_state(self):
        return {
            "current_needs": _needs(
                mobility_need="HIGH", behaviour_need="HIGH", nutrition_need="MEDIUM"
            ),
            "physical_assessment": {
                "available": True,
                "data": {
                    "tests": {
                        "shoulder": {"status": "completed"},
                        "ftsst": {"status": "completed"},
                        "balance": {"status": "completed"},
                    }
                },
            },
            "questionnaire": {
                "available": True,
                "data": {
                    "daily_steps": 3000,
                    "daily_sitting_hours": 9,
                    "exercise_days": 1,
                    "sleep_duration_hours": 5.5,
                    "sleep_quality": "poor",
                },
            },
            "exercise_history": _exercise_plan(
                ["chair-sit-to-stand", "wall-sit"], plan_id="plan_ex"
            ),
            "nutrition_plan": _topic_plan(
                [
                    {
                        "topic_id": "hydration",
                        "practical_goal": "Keep water within reach",
                        "rationale": "You reported low water intake",
                    }
                ],
                plan_id="nutrition_p1",
            ),
            "behaviour": _topic_plan(
                [
                    {
                        "topic_id": "movement_breaks",
                        "practical_goal": "Take a 5-minute break every hour",
                        "rationale": "You reported long sitting blocks",
                    }
                ],
                plan_id="habit_p1",
            ),
        }

    def test_every_item_carries_the_plan_contract(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        self.assertTrue(plan["items"])

        for index, item in enumerate(plan["items"], start=1):
            self.assertEqual(item["position"], index)
            self.assertIn(item["specialist"], SPECIALIST_ORDER)
            self.assertTrue(item["section"])
            self.assertIn("plan_id", item)
            self.assertIn("item_id", item)
            self.assertIn("metadata", item)
            self.assertIn("action", item)
            self.assertIn("tracking", item)
            self.assertIn("progress", item)
            self.assertTrue(item["title"])

    def test_actions_are_only_the_four_real_kinds(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        kinds = {item["action"]["kind"] for item in plan["items"]}

        self.assertTrue(
            kinds.issubset(
                {
                    ACTION_START_EXERCISE,
                    ACTION_COMPLETE_HABIT,
                    ACTION_LOG_NUTRITION,
                    ACTION_VIEW_GUIDANCE,
                }
            ),
            kinds,
        )

    def test_the_four_actionable_domains_each_offer_an_action(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        kinds = {item["action"]["kind"] for item in plan["items"]}

        self.assertIn(ACTION_START_EXERCISE, kinds)
        self.assertIn(ACTION_COMPLETE_HABIT, kinds)
        self.assertIn(ACTION_LOG_NUTRITION, kinds)
        self.assertIn(ACTION_VIEW_GUIDANCE, kinds)

    def test_sections_expose_the_eight_presented_fields(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        for section in plan["sections"]:
            for field in (
                "status",
                "status_label",
                "why_active",
                "why_inactive",
                "current_focus",
                "decision",
                "actions",
                "tracking",
                "progress",
                "next_step",
            ):
                self.assertIn(field, section)

            self.assertTrue(section["why_active"] or section["why_inactive"])

    def test_sections_actions_are_the_flat_items_themselves(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        seen = []

        for section in plan["sections"]:
            for item in section["actions"]:
                seen.append(item["position"])

        self.assertEqual(seen, [item["position"] for item in plan["items"]])

    def test_domain_plan_ids_are_preserved_per_item(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())

        by_specialist = {}

        for item in plan["items"]:
            by_specialist.setdefault(item["specialist"], set()).add(item["plan_id"])

        self.assertEqual(by_specialist[EXERCISE_MOVEMENT] - {None}, {"plan_ex"})
        self.assertEqual(by_specialist[NUTRITION_LIFESTYLE] - {None}, {"nutrition_p1"})
        self.assertEqual(by_specialist[BEHAVIOUR_ADHERENCE] - {None}, {"habit_p1"})

    def test_habit_items_identify_their_topic(self):
        plan = build_unified_plan(self._full_state(), safety_result=_safety())
        item = next(
            i for i in plan["items"] if i["specialist"] == BEHAVIOUR_ADHERENCE
        )

        self.assertEqual(item["item_id"], "movement_breaks")
        self.assertEqual(item["metadata"]["topic_id"], "movement_breaks")


class SafetyAffectsThePlanTests(unittest.TestCase):
    def _state(self):
        return {
            "current_needs": _needs(mobility_need="HIGH"),
            "exercise_history": _exercise_plan(["chair-sit-to-stand"]),
        }

    def test_allow_leaves_every_action_available(self):
        plan = build_unified_plan(self._state(), safety_result=_safety("ALLOW"))
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertFalse(item.get("withheld"))
        self.assertEqual(item["action"]["kind"], ACTION_START_EXERCISE)
        self.assertFalse(plan["safety"]["constrains_plan"])

    def test_modify_annotates_the_named_item_and_is_recorded(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(
                "MODIFY",
                modified_recommendation_ids=["chair-sit-to-stand"],
                actions=["add_medical_disclaimer"],
            ),
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertTrue(plan["safety"]["constrains_plan"])
        self.assertEqual(item["metadata"]["safety"]["status"], "MODIFY")
        self.assertFalse(item["metadata"]["safety"]["withheld"])
        self.assertEqual(item["metadata"]["safety"]["note"], "Safety outcome MODIFY.")
        self.assertTrue(plan["constraints"])

    def test_pause_withholds_the_named_item(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(
                "PAUSE",
                blocked_recommendation_ids=["chair-sit-to-stand"],
                actions=["pause_recommendation:chair-sit-to-stand"],
            ),
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertTrue(item["withheld"])
        self.assertNotEqual(item["action"]["kind"], ACTION_START_EXERCISE)
        self.assertIn("safety-practitioner", item["action"]["route"])

    def test_refer_withholds_every_action(self):
        plan = build_unified_plan(
            self._state(), safety_result=_safety("REFER", actions=["refer_to_professional"])
        )

        self.assertTrue(plan["items"])

        for item in plan["items"]:
            if item["kind"] == "safety_guidance":
                self.assertEqual(item["action"]["kind"], ACTION_VIEW_GUIDANCE)
            else:
                self.assertTrue(item["withheld"], item["title"])

        self.assertTrue(plan["safety"]["requires_referral"])

    def test_safety_card_reports_the_four_possible_verdicts(self):
        for status in ("ALLOW", "MODIFY", "PAUSE", "REFER"):
            card = next(
                c
                for c in build_specialists_team(
                    {}, safety_status=status, safety_result=_safety(status)
                )
                if c["id"] == SAFETY_PRACTITIONER
            )

            self.assertEqual(card["status"], status)
            self.assertTrue(card["status_label"])

    def test_not_assessed_safety_is_not_a_pass(self):
        plan = build_unified_plan({})

        self.assertEqual(plan["safety"]["status"], "NOT_ASSESSED")
        self.assertFalse(plan["safety"]["constrains_plan"])


class TrackingAndAdaptationTests(unittest.TestCase):
    def _state(self):
        return {
            "current_needs": _needs(mobility_need="HIGH", behaviour_need="HIGH"),
            "exercise_history": _exercise_plan(
                ["chair-sit-to-stand"], plan_id="plan_ex"
            ),
            "behaviour": _topic_plan(
                [
                    {
                        "topic_id": "movement_breaks",
                        "practical_goal": "Take a movement break",
                        "rationale": "Long sitting blocks",
                    }
                ],
                plan_id="habit_p1",
            ),
        }

    def test_previous_results_produce_progress_on_the_item(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ex",
                        "status": "completed",
                        "measurements": {"repetitions": 8, "completion": 1.0},
                        "recorded_at": "2026-01-02T10:00:00+00:00",
                    },
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ex",
                        "status": "incomplete",
                        "measurements": {"repetitions": 6, "completion": 0.75},
                        "recorded_at": "2026-01-01T10:00:00+00:00",
                    },
                ]
            },
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["progress"]["direction"], "IMPROVING")
        self.assertEqual(item["progress"]["from"], 6)
        self.assertEqual(item["progress"]["to"], 8)
        self.assertEqual(item["tracking"]["recorded"], 2)

    def test_one_result_is_not_enough_to_claim_progress(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ex",
                        "status": "completed",
                        "measurements": {"repetitions": 8},
                        "recorded_at": "2026-01-02T10:00:00+00:00",
                    }
                ]
            },
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["progress"]["direction"], "NOT_ENOUGH_DATA")

    def test_a_result_recorded_against_another_plan_is_not_counted(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_OTHER",
                        "status": "completed",
                        "measurements": {"repetitions": 8},
                        "recorded_at": "2026-01-02T10:00:00+00:00",
                    }
                ]
            },
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["tracking"]["status"], "NOT_RECORDED")

    def test_a_result_carrying_the_item_id_is_counted_for_that_item(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ex",
                        "item_id": "chair-sit-to-stand",
                        "status": "completed",
                        "measurements": {"repetitions": 8},
                        "recorded_at": "2026-01-02T10:00:00+00:00",
                    }
                ]
            },
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["tracking"]["status"], "COMPLETED")
        self.assertEqual(item["tracking"]["recorded"], 1)

    def test_a_result_recorded_for_a_different_item_is_not_counted(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ex",
                        "item_id": "some_other_item",
                        "status": "completed",
                        "measurements": {"repetitions": 8},
                        "recorded_at": "2026-01-02T10:00:00+00:00",
                    }
                ]
            },
        )
        item = next(i for i in plan["items"] if i["kind"] == "exercise")

        self.assertEqual(item["tracking"]["status"], "NOT_RECORDED")

    def test_nothing_recorded_is_reported_as_not_recorded(self):
        plan = build_unified_plan(self._state(), safety_result=_safety())

        for item in plan["items"]:
            if item["kind"] in ("exercise", "habit_goal"):
                self.assertEqual(item["tracking"]["status"], "NOT_RECORDED")

    def test_behaviour_records_drive_habit_tracking(self):
        plan = build_unified_plan(
            self._state(),
            safety_result=_safety(),
            tracking={
                "behaviour_actions": [
                    {
                        "topic_id": "movement_breaks",
                        "plan_id": "habit_p1",
                        "status": "completed",
                        "recorded_at": "2026-01-02T09:00:00+00:00",
                    },
                    {
                        "topic_id": "movement_breaks",
                        "plan_id": "habit_p1",
                        "status": "skipped",
                        "recorded_at": "2026-01-01T09:00:00+00:00",
                    },
                ]
            },
        )
        item = next(
            i for i in plan["items"] if i["specialist"] == BEHAVIOUR_ADHERENCE
        )

        self.assertEqual(item["tracking"]["recorded"], 2)
        self.assertEqual(item["tracking"]["completed"], 1)

    def test_adaptation_reason_surfaces_in_progress(self):
        state = self._state()
        state["exercise_history"]["data"]["plans"][0]["plan_version"] = 3
        state["exercise_history"]["data"]["plans"][0][
            "adaptation_reason"
        ] = "Moved up after two completed sessions."

        plan = build_unified_plan(state, safety_result=_safety())
        section = next(
            s for s in plan["sections"] if s["specialist"] == EXERCISE_MOVEMENT
        )

        self.assertEqual(section["progress"]["plan_version"], 3)
        self.assertEqual(
            section["progress"]["adaptation_reason"],
            "Moved up after two completed sessions.",
        )


class PlanStateTests(unittest.TestCase):
    def test_empty_account_has_five_specialists_and_no_items(self):
        plan = build_unified_plan({})

        self.assertFalse(plan["available"])
        self.assertEqual(len(plan["specialists"]), 5)
        self.assertEqual(plan["items"], [])
        self.assertEqual(plan["constraints"], [])

    def test_never_run_response_carries_the_unified_plan(self):
        response = never_run_response()

        self.assertIn("unified_plan", response)
        self.assertEqual(len(response["specialists_team"]), 5)
        self.assertEqual(len(response["unified_plan"]["specialists"]), 5)
        self.assertEqual(
            [card["id"] for card in response["unified_plan"]["specialists"]],
            list(SPECIALIST_ORDER),
        )

    def test_serialise_workflow_state_includes_the_unified_plan(self):
        response = serialise_workflow_state(
            {"current_needs": _needs(mobility_need="HIGH")}
        )

        self.assertIn("unified_plan", response)
        self.assertEqual(len(response["specialists_team"]), 5)

    def test_not_assessed_section_reports_what_is_missing(self):
        plan = build_unified_plan({})
        section = next(
            s for s in plan["sections"] if s["specialist"] == NUTRITION_LIFESTYLE
        )

        self.assertFalse(section["selected"])
        self.assertIsNone(section["why_active"])
        self.assertTrue(section["why_inactive"])
        self.assertEqual(section["actions"], [])

    def test_a_specialist_with_a_plan_is_selected_even_when_not_required_now(self):
        state = {
            "current_needs": _needs(
                mobility_need="LOW",
                stability_need="LOW",
                functional_movement_need="LOW",
            ),
            "exercise_history": _exercise_plan(["wall-sit"]),
        }

        plan = build_unified_plan(state, safety_result=_safety())
        section = next(
            s for s in plan["sections"] if s["specialist"] == EXERCISE_MOVEMENT
        )

        self.assertEqual(section["status"], "EVALUATED_NOT_REQUIRED")
        self.assertTrue(section["selected"])
        self.assertTrue(section["actions"])


class PresentablePlanTests(unittest.TestCase):
    """The parts of the plan that exist so a person can read it: the summary,
    the compact team status, the empty states and the collaboration timeline."""

    def _state(self, **needs):
        return {
            "current_needs": _needs(**needs),
            "questionnaire": {
                "available": True,
                "data": {"daily_steps": 3000, "daily_sitting_hours": 9, "exercise_days": 1},
            },
            "exercise_history": _exercise_plan(
                ["chair-sit-to-stand"], plan_id="plan_ui"
            ),
        }

    def test_the_summary_names_the_areas_this_plan_is_actually_about(self):
        plan = build_unified_plan(
            self._state(
                stability_need="HIGH",
                functional_movement_need="MEDIUM",
                behaviour_need="HIGH",
            ),
            safety_result=_safety(),
        )
        summary = plan["summary"]

        self.assertIn("Balance", summary["focus_areas"])
        self.assertIn("Everyday movement", summary["focus_areas"])
        self.assertIn("Consistency", summary["focus_areas"])
        self.assertTrue(summary["headline"].startswith("Your plan is currently focused on"))
        self.assertTrue(summary["next"])

    def test_a_plan_with_nothing_selected_says_so_rather_than_inventing_a_focus(self):
        plan = build_unified_plan(
            {"current_needs": _needs(
                mobility_need="LOW",
                stability_need="LOW",
                functional_movement_need="LOW",
                behaviour_need="LOW",
                nutrition_need="LOW",
            )},
            safety_result=_safety(),
        )

        self.assertEqual(plan["summary"]["focus_areas"], [])
        self.assertIn("Nothing in your plan needs a change", plan["summary"]["headline"])

    def test_every_section_carries_a_compact_status_and_one_short_reason(self):
        plan = build_unified_plan(
            self._state(stability_need="HIGH", behaviour_need="HIGH"),
            safety_result=_safety("MODIFY", modified_recommendation_ids=["chair-sit-to-stand"]),
        )

        allowed = {
            "ACTIVE", "NOT_ASSESSED", "NOT_NEEDED",
            "REVIEWED", "MODIFIED", "PAUSED", "REFERRAL",
        }

        for section in plan["sections"]:
            self.assertIn(section["team_status"], allowed)
            self.assertTrue(section["team_status_label"])
            self.assertTrue(section["short_reason"])
            # One sentence, not a paragraph.
            self.assertLess(len(section["short_reason"]), 140)

    def test_the_safety_card_reports_its_verdict_compactly(self):
        for status, expected in (
            ("ALLOW", "REVIEWED"),
            ("MODIFY", "MODIFIED"),
            ("PAUSE", "PAUSED"),
            ("REFER", "REFERRAL"),
        ):
            plan = build_unified_plan(
                self._state(stability_need="HIGH"),
                safety_result=_safety(status),
            )
            section = next(
                s for s in plan["sections"] if s["specialist"] == SAFETY_PRACTITIONER
            )

            self.assertEqual(section["team_status"], expected)

    def test_a_not_assessed_specialist_offers_the_action_that_would_assess_it(self):
        # Nothing assessed at all: no movement measurement, no questionnaire, no
        # check-in. That is the state the nutrition specialist used to sit in
        # permanently, and the reason the check-in exists.
        plan = build_unified_plan({})

        for specialist_id, route in (
            (NUTRITION_LIFESTYLE, "/nutrition-check-in"),
            (BEHAVIOUR_ADHERENCE, "/onboarding"),
            (RECOVERY_CARE, "/onboarding"),
            (EXERCISE_MOVEMENT, "/assessment"),
        ):
            section = next(
                s for s in plan["sections"] if s["specialist"] == specialist_id
            )

            self.assertEqual(section["empty_state"]["kind"], "not_assessed")
            self.assertTrue(section["empty_state"]["message"])
            self.assertEqual(section["empty_state"]["action"]["route"], route)

    def test_a_section_with_no_records_says_what_to_do_about_it(self):
        plan = build_unified_plan(self._state(stability_need="HIGH"), safety_result=_safety())
        section = next(
            s for s in plan["sections"] if s["specialist"] == EXERCISE_MOVEMENT
        )

        self.assertEqual(section["empty_state"]["kind"], "no_records")
        self.assertIn("first session", section["empty_state"]["message"])
        self.assertEqual(section["empty_state"]["action"]["kind"], "start_exercise")
        self.assertIn("/exercise/", section["empty_state"]["action"]["route"])

    def test_a_section_with_records_has_no_empty_state(self):
        plan = build_unified_plan(
            self._state(stability_need="HIGH"),
            safety_result=_safety(),
            tracking={
                "exercise_results": [
                    {
                        "exerciseId": "chair-sit-to-stand",
                        "plan_id": "plan_ui",
                        "status": "completed",
                        "measurements": {"repetitions": 8},
                        "recorded_at": "2026-10-02T10:00:00+00:00",
                    }
                ]
            },
        )
        section = next(
            s for s in plan["sections"] if s["specialist"] == EXERCISE_MOVEMENT
        )

        self.assertIsNone(section["empty_state"])

    def test_the_safety_section_never_gets_an_empty_state(self):
        plan = build_unified_plan({})
        section = next(
            s for s in plan["sections"] if s["specialist"] == SAFETY_PRACTITIONER
        )

        self.assertIsNone(section["empty_state"])

    def test_collaboration_lists_the_specialists_that_actually_took_part(self):
        plan = build_unified_plan(
            self._state(stability_need="HIGH", behaviour_need="HIGH"),
            safety_result=_safety(),
        )
        collaboration = plan["collaboration"]
        by_specialist = {
            step["specialist"]: step
            for step in collaboration["steps"]
            if step["kind"] == "specialist"
        }

        self.assertTrue(collaboration["title"])
        self.assertEqual(len(by_specialist), 5)
        self.assertTrue(by_specialist["exercise_movement"]["participated"])
        self.assertTrue(by_specialist["behaviour_adherence"]["participated"])
        # Nutrition was never assessed, so it must not read as a contributor.
        self.assertFalse(by_specialist["nutrition_lifestyle"]["participated"])
        self.assertIn("Not assessed", by_specialist["nutrition_lifestyle"]["summary"])
        self.assertEqual(
            by_specialist["nutrition_lifestyle"]["action"]["route"],
            "/nutrition-check-in",
        )

    def test_collaboration_starts_with_the_inputs_and_ends_with_one_plan(self):
        plan = build_unified_plan(
            self._state(stability_need="HIGH"), safety_result=_safety()
        )
        steps = plan["collaboration"]["steps"]

        self.assertEqual(steps[0]["kind"], "assessment")
        self.assertEqual(steps[-1]["kind"], "synthesis")
        self.assertIn("one MoveWell plan", steps[-1]["summary"])

    def test_collaboration_never_exposes_internal_terminology(self):
        plan = build_unified_plan(
            self._state(stability_need="HIGH", behaviour_need="HIGH"),
            safety_result=_safety("MODIFY"),
        )
        text = repr(plan["collaboration"]).lower()

        for leaked in (
            "agent_run", "workflow_id", "physio", "orchestrator",
            "mcp", "prompt", "chain-of-thought", "need_profile",
        ):
            self.assertNotIn(leaked, text)


    def test_the_stated_nutrition_goal_shapes_the_focus_and_the_reason(self):
        # The goal lives in the User State's nutrition section, not in the Need
        # Profile (a preference is not a need dimension), so reading it from the
        # wrong place silently produced "eating patterns" for someone who had
        # explicitly chosen hydration. This is that regression.
        state = self._state(nutrition_need="HIGH")
        state["nutrition"] = {
            "available": True,
            "data": {
                "meals_per_day": 2,
                "water_glasses_per_day": 3,
                "nutrition_goal": "hydration",
            },
        }

        plan = build_unified_plan(state, safety_result=_safety())
        section = next(
            s for s in plan["sections"] if s["specialist"] == NUTRITION_LIFESTYLE
        )

        self.assertEqual(section["status"], "ACTIVE")
        self.assertIn("hydration", section["short_reason"].lower())
        self.assertIn("Hydration", plan["summary"]["focus_areas"])

        collaboration = {
            step["specialist"]: step
            for step in plan["collaboration"]["steps"]
            if step.get("specialist")
        }

        self.assertIn("hydration", collaboration["nutrition_lifestyle"]["summary"].lower())

    def test_without_a_stated_goal_the_focus_is_generic(self):
        plan = build_unified_plan(
            self._state(nutrition_need="HIGH"), safety_result=_safety()
        )

        self.assertIn("Eating patterns", plan["summary"]["focus_areas"])


if __name__ == "__main__":
    unittest.main()
