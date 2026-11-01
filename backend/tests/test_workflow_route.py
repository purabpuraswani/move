"""Tests for Phase 6's workflow wiring: workflow/assembly.py,
workflow/response.py, user_state/store.py, and routes/workflow.py.

Split, like the modules themselves, into logic that needs no database
(workflow/assembly.py, workflow/response.py — no pymongo/bson import at
all, and exercised here for real, never skipped) and logic that talks to
MongoDB (user_state/store.py, routes/workflow.py), which is guarded with
this project's established pymongo/bson self-skip pattern (see
tests/test_report_pipeline_integration.py, tests/test_food_log_store.py)
since SQLite storage replaces pymongo/bson in this project
network access here — the same already-documented constraint as the `mcp`
package).
"""

import importlib.util
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from exercise_library.catalog import list_exercise_ids
from nutrition_library.catalog import list_topic_ids as list_nutrition_topic_ids
from behaviour_library.catalog import list_topic_ids as list_behaviour_topic_ids
from user_state.schema import validate_user_state
from workflow.assembly import assemble_user_state_from_documents
from workflow.response import (
    SAFETY_STATUS_MESSAGES,
    safety_status_message,
    serialise_workflow_state,
)
from routes.workflow import _latest_execution_response
from routes import workflow as workflow_route

FORBIDDEN_KEYS = {
    "workflow_id",
    "request_id",
    "agent_run_id",
    "tool_call_id",
    "mcp_session_id",
}


def _scan_for_forbidden_keys(value, found=None):
    """Recursively collect any forbidden internal-orchestration key name
    found anywhere in `value` (a JSON-shaped dict/list/scalar tree)."""

    if found is None:
        found = set()

    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in FORBIDDEN_KEYS:
                found.add(key)
            _scan_for_forbidden_keys(sub_value, found)
    elif isinstance(value, list):
        for item in value:
            _scan_for_forbidden_keys(item, found)

    return found


class WorkflowNutritionInputTests(unittest.TestCase):
    def test_latest_saved_food_logs_are_loaded_even_without_an_existing_plan(self):
        meal = {"meal": "breakfast", "food_name": "idli", "quantity": "2", "notes": "", "recorded_at": "2026-11-01T08:00:00Z"}
        with (
            patch.object(workflow_route, "latest_valid_assessment", return_value=None),
            patch.object(workflow_route, "baseline_assessment", return_value=None),
            patch.object(workflow_route, "previous_assessment", return_value=None),
            patch.object(workflow_route, "list_exercise_results", return_value=[]),
            patch.object(workflow_route, "list_food_log_entries", return_value=[meal]) as list_logs,
        ):
            inputs = workflow_route._progress_inputs({}, "user-1")
        self.assertEqual(inputs["nutrition_food_log_entries"], [meal])
        self.assertIsNone(inputs["nutrition_food_log_current_period"])
        list_logs.assert_called_once_with("user-1", limit=100)


# ---------------------------------------------------------------------------
# workflow/assembly.py — pure, real tests, no pymongo/bson import anywhere
# in the call chain (build_user_state / run_need_assessment are both pure).
# ---------------------------------------------------------------------------


class AssembleUserStateFromDocumentsTests(unittest.TestCase):
    def test_no_documents_produces_a_valid_but_all_unavailable_state(self):
        state = assemble_user_state_from_documents()

        validate_user_state(state)

        self.assertFalse(state["basic_profile"]["available"])
        self.assertFalse(state["physical_assessment"]["available"])
        self.assertFalse(state["medical_context"]["available"])
        # current_needs is populated by Need Assessment even when nothing
        # else is available — every dimension NOT_ASSESSED, never omitted.
        self.assertTrue(state["current_needs"]["available"])
        needs = state["current_needs"]["data"]
        self.assertEqual(needs["mobility_need"]["level"], "NOT_ASSESSED")

    def test_a_low_shoulder_elevation_reading_drives_current_needs_high(self):
        profile_doc = {"age": 45, "sex": "female"}
        assessment_doc = {
            "protocol_version": "1.0.0",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "tests": {
                "shoulder": {
                    "status": "completed",
                    "measurements": {
                        "left": {"finalElevationDeg": 40},
                        "right": {"finalElevationDeg": 42},
                        "observableDifferenceDeg": 2,
                    },
                },
                "ftsst": {"status": "not_started"},
                "balance": {"status": "not_started"},
            },
        }
        confirmed_reports_doc = {"reports": []}

        state = assemble_user_state_from_documents(
            profile_doc=profile_doc,
            assessment_doc=assessment_doc,
            confirmed_reports_doc=confirmed_reports_doc,
        )

        validate_user_state(state)

        self.assertTrue(state["basic_profile"]["available"])
        self.assertTrue(state["physical_assessment"]["available"])
        self.assertTrue(state["current_needs"]["available"])
        self.assertEqual(
            state["current_needs"]["data"]["mobility_need"]["level"], "HIGH"
        )

    def test_confirmed_reports_reach_medical_context(self):
        confirmed_reports_doc = {
            "hasConfirmedReports": True,
            "reportCount": 1,
            "reports": [{"title": "Blood panel", "values": []}],
        }

        state = assemble_user_state_from_documents(
            confirmed_reports_doc=confirmed_reports_doc
        )

        validate_user_state(state)

        self.assertTrue(state["medical_context"]["available"])
        reports = state["medical_context"]["data"]["confirmed_reports"]["reports"]
        self.assertEqual(reports, [{"title": "Blood panel", "values": []}])


# ---------------------------------------------------------------------------
# workflow/response.py::safety_status_message — pure, real tests.
# ---------------------------------------------------------------------------


class SafetyStatusMessageTests(unittest.TestCase):
    def test_every_real_safety_status_has_a_distinct_plain_language_message(self):
        # safety/schema.py's SAFETY_STATUSES, verbatim, so this test breaks
        # loudly if that tuple ever gains/loses a value this module has not
        # been updated for.
        real_statuses = ("ALLOW", "MODIFY", "PAUSE", "REFER", "NOT_ASSESSED")

        self.assertEqual(set(SAFETY_STATUS_MESSAGES), set(real_statuses))

        messages = [safety_status_message(status) for status in real_statuses]
        self.assertEqual(len(messages), len(set(messages)))

        for message in messages:
            self.assertIsInstance(message, str)
            self.assertTrue(message)

    def test_refer_reads_as_a_referral_not_an_allow(self):
        message = safety_status_message("REFER")
        self.assertIn("professional", message.lower())

    def test_none_means_not_yet_assessed(self):
        self.assertEqual(safety_status_message(None), "Not yet assessed.")

    def test_an_unrecognised_status_falls_back_rather_than_raising(self):
        # Defensive: never guesses a new safety semantic, never raises.
        self.assertEqual(safety_status_message("SOMETHING_NEW"), "Not yet assessed.")


# ---------------------------------------------------------------------------
# workflow/response.py::serialise_workflow_state — pure, real tests.
# ---------------------------------------------------------------------------


def _state_with_plans(*, exercise_ids, nutrition_topic_ids, behaviour_topic_ids):
    return {
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "exercise_history": {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [
                    {
                        "plan_id": "plan_1",
                        "plan_version": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "goal": "Improve shoulder mobility",
                        "exercise_ids": exercise_ids,
                        "source": "physio_agent",
                        # Deliberately includes real internal ids, exactly
                        # like orchestrator/state_update.py's real record —
                        # the forbidden-key scan below proves the
                        # serializer strips these rather than passing them
                        # through.
                        "agent_run_id": "run_deadbeef",
                        "recorded_at": "2026-01-01T00:00:01+00:00",
                        "adaptation_reason": None,
                        "triggered_by": None,
                    }
                ],
            },
        },
        "nutrition_plan": {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [
                    {
                        "plan_id": "nplan_1",
                        "plan_version": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "goal": "Build a regular meal pattern",
                        "topic_ids": nutrition_topic_ids,
                        "source": "nutrition_agent",
                        "agent_run_id": "run_cafef00d",
                        "recorded_at": "2026-01-01T00:00:01+00:00",
                        "adaptation_reason": None,
                        "triggered_by": None,
                    }
                ],
            },
        },
        "behaviour": {
            "available": True,
            "reason": None,
            "data": {
                "schemaVersion": "0.1.0",
                "plans": [
                    {
                        "plan_id": "bplan_1",
                        "plan_version": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "goal": "Move more often",
                        "topic_ids": behaviour_topic_ids,
                        "source": "behaviour_agent",
                        "agent_run_id": "run_facade00",
                        "recorded_at": "2026-01-01T00:00:01+00:00",
                        "adaptation_reason": "Progress Agent recommended MODIFY",
                        "triggered_by": "progress_agent",
                    }
                ],
            },
        },
    }


class SerialiseWorkflowStateTests(unittest.TestCase):
    def test_legacy_execution_snapshot_is_rebuilt_from_saved_results_without_rerunning(self):
        explanations = {
            agent_id: {
                "agent_identifier": agent_id,
                "selection_status": "SELECTED" if agent_id == "physio" else "NOT SELECTED",
                "reason_for_selection": "Saved selection reason.",
                "evidence_used": ["Saved evidence."],
                "missing_required_information": [],
                "context_readiness": "READY" if agent_id == "physio" else "NOT_APPLICABLE",
                "execution_eligibility": agent_id == "physio",
            }
            for agent_id in ("physio", "nutrition", "behaviour", "recovery", "exercise_activity", "progress")
        }
        user_state = {
            "generatedAt": "2026-11-01T00:00:00+00:00",
            "physical_assessment": {"available": True, "data": {
                "session_id": "session-1",
                "tests": {
                    "shoulder": {"status": "completed", "measurements": {"left": {"finalElevationDeg": 150}, "right": {"finalElevationDeg": 148}}},
                    "balance": {"status": "completed", "measurements": {"left": {"attempted": True, "valid": True, "holdDurationSeconds": 20}, "right": {"attempted": True, "valid": True, "holdDurationSeconds": 19}}},
                },
            }},
            "current_needs": {"available": True, "data": {
                "mobility_need": {"level": "LOW", "evidence": []},
                "stability_need": {"level": "LOW", "evidence": []},
                "functional_movement_need": {"level": "NOT_ASSESSED", "evidence": ["Not in active protocol"]},
                "nutrition_need": {"level": "NOT_ASSESSED", "evidence": ["Optional questions missing"]},
                "behaviour_need": {"level": "NOT_ASSESSED", "evidence": []},
            }},
        }
        execution = {
            "created_at": datetime(2026, 11, 1, 8, 30, tzinfo=timezone.utc),
            "response": {"plan_state": {"missing": [
                {"capability": "Functional movement"}, {"capability": "Eating patterns"}
            ]}},
            "agent_executions": {"physio": {
                "agent": "physio", "status": "completed",
                "findings": {"rejected_candidates": [{
                    "exercise_id": "wall-supported-balance",
                    "safety_evaluation": {
                        "status": "DEFERRED_CONTEXT_REQUIRED",
                        "additional_information_required": ["Clarify reported injury history"],
                    },
                }]},
                "recommendations": [],
            }},
            "errors": [],
        }

        response = _latest_execution_response(
            user_state,
            execution,
            selection_explanations=explanations,
            last_safety_result={"status": "NOT_ASSESSED", "blocked_recommendation_ids": []},
        )

        journey = {item["id"]: item for item in response["agent_journey"]}
        self.assertTrue(response["available"])
        self.assertEqual(response["workflow_created_at"], "2026-11-01T08:30:00+00:00")
        self.assertEqual(len(journey), 6)
        self.assertEqual(journey["physio"]["status"], "COMPLETED")
        self.assertEqual(len(journey["physio"]["findings"]["rejected_candidates"]), 1)
        self.assertEqual(journey["physio"]["reason"], "Saved selection reason.")
        self.assertEqual(journey["physio"]["missing_information"], ["Clarify reported injury history"])
        self.assertEqual(response["plan_state"]["missing"], [])
        self.assertEqual(response["workflow_outcome"]["status"], "MORE_INFORMATION_REQUIRED")

    def test_agent_journey_uses_actual_execution_and_gate_approved_recommendations(self):
        explanations = {
            "exercise_activity": {
                "selection_status": "SELECTED",
                "reason_for_selection": "Recorded sedentary behaviour.",
                "evidence_used": ["Sitting time was reported."],
                "missing_required_information": [],
                "context_readiness": "READY",
                "execution_eligibility": True,
            },
            "physio": {
                "selection_status": "NOT SELECTED",
                "reason_for_selection": "No movement limitation was found.",
                "evidence_used": [],
                "missing_required_information": [],
                "context_readiness": "NOT_APPLICABLE",
                "execution_eligibility": False,
            },
        }
        executions = {
            "exercise_activity": {
                "agent": "exercise_activity",
                "status": "completed",
                "findings": {"activity_findings": [{"finding": "Sitting time reported."}]},
                "recommendations": [{"id": "approved", "title": "Approved option"}],
            }
        }
        response = serialise_workflow_state(
            {"generatedAt": "2026-01-01T00:00:00+00:00"},
            agent_executions=executions,
            selection_explanations=explanations,
            approved_recommendations=[{"id": "approved", "agent": "exercise_activity", "title": "Approved option"}],
        )
        journey = {item["id"]: item for item in response["agent_journey"]}

        self.assertEqual(len(journey), 6)
        self.assertEqual(journey["exercise_activity"]["status"], "COMPLETED")
        self.assertEqual(journey["exercise_activity"]["findings"], executions["exercise_activity"]["findings"])
        self.assertEqual(journey["exercise_activity"]["recommendations"][0]["id"], "approved")
        self.assertEqual(journey["physio"]["status"], "NOT_SELECTED")
        self.assertEqual(response["workflow_outcome"]["status"], "PARTIAL_PLAN_READY")

    def test_assessment_summary_counts_only_the_two_active_checks(self):
        state = {
            "generatedAt": "2026-01-01T00:00:00+00:00",
            "physical_assessment": {
                "available": True,
                "data": {
                    "session_id": "latest-session-1",
                    "tests": {
                        "shoulder": {"status": "completed", "measurements": {
                            "left": {"finalElevationDeg": 166.2},
                            "right": {"finalElevationDeg": 154.9},
                        }},
                        "ftsst": {"status": "completed"},
                        "balance": {"status": "skipped"},
                    }
                },
            },
        }

        summary = serialise_workflow_state(state)["assessment_summary"]

        self.assertEqual(summary["tests_completed"], 1)
        self.assertEqual(summary["tests_total"], 2)
        self.assertEqual(summary["session_key"], "latest-session-1")
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertEqual(set(summary["tests"]), {"shoulder", "balance"})
        self.assertEqual(summary["measured_results"]["shoulder"]["unit"], "degrees")
        self.assertEqual(
            summary["measured_results"]["shoulder"]["measurements"]["left"]["finalElevationDeg"],
            166.2,
        )
        self.assertNotIn("balance", summary["measured_results"])

    def test_no_plans_yet_is_represented_honestly(self):
        response = serialise_workflow_state(
            {"generatedAt": "2026-01-01T00:00:00+00:00"}, safety_status=None
        )

        self.assertFalse(response["exercise_plan"]["available"])
        self.assertIn("message", response["exercise_plan"])
        self.assertFalse(response["nutrition_plan"]["available"])
        self.assertFalse(response["behaviour_plan"]["available"])
        self.assertEqual(response["safety_status"], "Not yet assessed.")

    def test_real_plan_ids_resolve_to_real_library_names(self):
        exercise_id = list_exercise_ids()[0]
        nutrition_topic_id = list_nutrition_topic_ids()[0]
        behaviour_topic_id = list_behaviour_topic_ids()[0]

        state = _state_with_plans(
            exercise_ids=[exercise_id],
            nutrition_topic_ids=[nutrition_topic_id],
            behaviour_topic_ids=[behaviour_topic_id],
        )

        response = serialise_workflow_state(state, safety_status="MODIFY")

        self.assertTrue(response["exercise_plan"]["available"])
        self.assertEqual(response["exercise_plan"]["exercise_count"], 1)
        # A real name, not a bare id echoed back.
        self.assertNotEqual(response["exercise_plan"]["exercises"][0], exercise_id)

        self.assertTrue(response["nutrition_plan"]["available"])
        self.assertNotEqual(
            response["nutrition_plan"]["goals"][0], nutrition_topic_id
        )

        self.assertTrue(response["behaviour_plan"]["available"])
        self.assertNotEqual(
            response["behaviour_plan"]["goals"][0], behaviour_topic_id
        )
        self.assertEqual(
            response["behaviour_plan"]["adaptation_reason"],
            "Progress Agent recommended MODIFY",
        )

        self.assertEqual(
            response["safety_status"],
            "Some recommendations need review before you follow them.",
        )

    def test_an_unknown_exercise_id_is_not_exposed_as_an_active_recommendation(self):
        state = _state_with_plans(
            exercise_ids=["not_a_real_exercise_id"],
            nutrition_topic_ids=[],
            behaviour_topic_ids=[],
        )

        response = serialise_workflow_state(state)

        self.assertFalse(response["exercise_plan"]["available"])
        self.assertNotIn("not_a_real_exercise_id", str(response))

    def test_response_never_carries_a_forbidden_internal_orchestration_key(self):
        exercise_id = list_exercise_ids()[0]
        nutrition_topic_id = list_nutrition_topic_ids()[0]
        behaviour_topic_id = list_behaviour_topic_ids()[0]

        state = _state_with_plans(
            exercise_ids=[exercise_id],
            nutrition_topic_ids=[nutrition_topic_id],
            behaviour_topic_ids=[behaviour_topic_id],
        )

        response = serialise_workflow_state(state, safety_status="REFER")

        found = _scan_for_forbidden_keys(response)

        self.assertEqual(
            found,
            set(),
            f"forbidden internal orchestration key(s) leaked into the "
            f"user-facing response: {found}",
        )

    def test_only_the_newest_plan_version_is_summarised(self):
        state = _state_with_plans(
            exercise_ids=[list_exercise_ids()[0]],
            nutrition_topic_ids=[],
            behaviour_topic_ids=[],
        )
        newer_exercise_id = list_exercise_ids()[1]
        state["exercise_history"]["data"]["plans"].append(
            {
                "plan_id": "plan_2",
                "plan_version": 2,
                "created_at": "2026-02-01T00:00:00+00:00",
                "goal": "Progress the plan",
                "exercise_ids": [newer_exercise_id],
                "source": "physio_agent",
                "agent_run_id": "run_00000000",
                "recorded_at": "2026-02-01T00:00:01+00:00",
                "adaptation_reason": "Progress Agent recommended PROGRESS",
                "triggered_by": "progress_agent",
            }
        )

        response = serialise_workflow_state(state)

        self.assertEqual(response["exercise_plan"]["exercise_count"], 1)
        self.assertEqual(
            response["exercise_plan"]["adaptation_reason"],
            "Progress Agent recommended PROGRESS",
        )


# ---------------------------------------------------------------------------
# Database-backed pieces: user_state/store.py and routes/workflow.py.
# Guarded with this project's established pymongo/bson self-skip pattern —
# see tests/test_food_log_store.py's module docstring for the exact same
# discipline applied here.
# ---------------------------------------------------------------------------

PYMONGO_AVAILABLE = (
    importlib.util.find_spec("database") is not None
)

PYMONGO_SKIP_REASON = (
    "pymongo/bson are not installed in this environment (no PyPI network "
    "access in this sandbox); install them in the project's real .venv "
    "(where user_state/store.py and routes/workflow.py already run "
    "against a real MongoDB) to run these persistence/route tests instead "
    "of skipping them"
)

if PYMONGO_AVAILABLE:
    from unittest import mock

    from user_state import store as user_state_store

    class _FakeUserStateCollection:
        """Just enough of a MongoDB collection for user_state/store.py:
        update_one with upsert (a single $set + $setOnInsert), and
        find_one by user_id. Not a general emulator — mirrors this
        project's existing tests/_fake_mongo.py pattern, kept local since
        that module's FakeReportsCollection does not support upsert."""

        def __init__(self):
            self._docs = {}

        def create_index(self, *_args, **_kwargs):
            return "fake_index"

        def update_one(self, query, update, upsert=False):
            user_id = query["user_id"]
            existing = self._docs.get(user_id)

            class _Result:
                upserted_id = None

            result = _Result()

            if existing is None:
                if not upsert:
                    return result

                doc = {"user_id": user_id}
                doc.update(update.get("$setOnInsert") or {})
                doc.update(update.get("$set") or {})
                self._docs[user_id] = doc
                result.upserted_id = user_id
            else:
                existing.update(update.get("$set") or {})

            return result

        def find_one(self, query):
            return self._docs.get(query["user_id"])

    @unittest.skipUnless(PYMONGO_AVAILABLE, PYMONGO_SKIP_REASON)
    class UserStateStoreTests(unittest.TestCase):
        def setUp(self):
            self.fake_collection = _FakeUserStateCollection()
            self._patch = mock.patch.object(
                user_state_store, "user_state_collection", self.fake_collection
            )
            self._patch.start()
            self.addCleanup(self._patch.stop)

        def test_get_user_state_is_none_before_any_run_is_saved(self):
            self.assertIsNone(user_state_store.get_user_state("user_1"))

        def test_save_then_get_round_trips_the_state_and_safety_result(self):
            state = {"generatedAt": "2026-01-01T00:00:00+00:00"}
            safety_result = {"status": "ALLOW"}
            selection_explanations = {
                "physio": {
                    "agent_identifier": "physio",
                    "selection_status": "NOT SELECTED",
                    "execution_eligibility": False,
                }
            }

            user_state_store.save_user_state(
                "user_1", state, safety_result=safety_result,
                selection_explanations=selection_explanations,
            )
            saved = user_state_store.get_user_state("user_1")

            self.assertEqual(saved["state"], state)
            self.assertEqual(saved["last_safety_result"], safety_result)
            self.assertEqual(saved["last_selection_explanations"], selection_explanations)

        def test_saving_twice_for_the_same_user_replaces_not_duplicates(self):
            user_state_store.save_user_state("user_1", {"v": 1})
            user_state_store.save_user_state("user_1", {"v": 2})

            saved = user_state_store.get_user_state("user_1")
            self.assertEqual(saved["state"], {"v": 2})

        def test_users_are_isolated_from_each_other(self):
            user_state_store.save_user_state(
                "user_1", {"v": "one"},
                selection_explanations={"agent": {"selection_status": "SELECTED"}},
            )
            user_state_store.save_user_state(
                "user_2", {"v": "two"},
                selection_explanations={"agent": {"selection_status": "NOT SELECTED"}},
            )

            self.assertEqual(
                user_state_store.get_user_state("user_1")["state"], {"v": "one"}
            )
            self.assertEqual(
                user_state_store.get_user_state("user_2")["state"], {"v": "two"}
            )
            self.assertEqual(
                user_state_store.get_user_state("user_1")["last_selection_explanations"]["agent"]["selection_status"],
                "SELECTED",
            )
            self.assertEqual(
                user_state_store.get_user_state("user_2")["last_selection_explanations"]["agent"]["selection_status"],
                "NOT SELECTED",
            )


# A full fastapi.testclient.TestClient-based end-to-end route test would
# additionally need `httpx` (checked the same honest way, per this
# project's own guidance, with `importlib.util.find_spec("httpx")`) — not
# used here because `_build_tool_clients` below is exercised directly,
# without going through the HTTP layer at all, which is enough to prove
# the ImportError -> clean 503 behaviour without adding an httpx
# dependency to this test.
@unittest.skipUnless(PYMONGO_AVAILABLE, PYMONGO_SKIP_REASON)
class WorkflowRouteImportClientBuildingTests(unittest.TestCase):
    """Route-level behaviour that needs a real Mongo-shaped environment to
    import routes/workflow.py at all — its import chain goes through
    auth/deps.py -> database.py -> pymongo. Unavailable in this sandbox
    (see module docstring), so this class is skipped here and exercised
    for real wherever the project's actual dependencies are installed.
    """

    def test_build_tool_clients_raises_importerror_for_the_caller_to_convert(self):
        """`_build_tool_clients()` deliberately does NOT convert the failure
        itself -- its docstring says so, and `run_user_workflow()` catches
        ImportError and raises the 503.

        This test previously asserted that `_build_tool_clients()` raised
        HTTPException directly, which the function has never done. It passed
        unnoticed only because the whole class self-skips without pymongo,
        so it never actually ran until the suite was run in an environment
        that has it. The guarantee it was reaching for is real, so it is
        split across this test and the next rather than dropped: this one
        pins where the failure is raised, the next pins that what the user
        finally sees is clean.
        """

        import routes.workflow as workflow_route

        with self.assertRaises(ImportError):
            with mock.patch.dict(
                "sys.modules",
                {
                    "physio_agent.mcp_client": None,
                    "physio_agent.tool_client": None,
                },
            ):
                workflow_route._build_tool_clients(
                    workflow_id="wf_test",
                    request_id="req_test",
                    need_physio=True,
                    need_behaviour=False,
                    need_nutrition=False,
                    need_progress=False,
                )

    def test_the_user_facing_unavailable_message_leaks_no_technical_detail(self):
        """The other half: whatever the route says when the recommendation
        engine cannot be built must not mention the missing package, the
        exception type, or a server URL. A user reading it learns that the
        feature is unavailable, not how the backend is wired."""

        import routes.workflow as workflow_route

        message = workflow_route.RECOMMENDATION_ENGINE_UNAVAILABLE.lower()

        for leak in ("mcp", "importerror", "traceback", "localhost", "modulenotfound"):
            self.assertNotIn(leak, message)

        # And it must actually say something useful rather than be empty.
        self.assertGreater(len(message.strip()), 20)


if __name__ == "__main__":
    unittest.main()
