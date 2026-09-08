"""Real unit tests for the pure, testable pieces behind routes/dashboard.py
(dashboard/serialisers.py): safe_account_info() (excludes password_hash),
flatten_plan_history() (real plan-version flattening across all three
plan-producing agents), and mcp_status_report() (honest install-status +
real tool names). No pymongo/bson/fastapi import happens in these tests --
dashboard/serialisers.py has none, so these run unconditionally, not
skip-guarded.
"""

import unittest

from dashboard.serialisers import (
    FORBIDDEN_ACCOUNT_FIELDS,
    _MCP_SERVER_TOOLS,
    flatten_plan_history,
    mcp_status_report,
    safe_account_info,
)


class SafeAccountInfoTests(unittest.TestCase):
    def test_password_hash_is_excluded(self):
        user_doc = {
            "_id": "abc123",
            "email": "person@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "is_staff": True,
            "password_hash": "supersecrethash",
        }
        info = safe_account_info(user_doc)
        self.assertNotIn("password_hash", info)
        for field in FORBIDDEN_ACCOUNT_FIELDS:
            self.assertNotIn(field, info)

    def test_real_fields_are_present(self):
        user_doc = {
            "_id": "abc123",
            "email": "person@example.com",
            "created_at": "2026-01-01T00:00:00Z",
            "is_staff": False,
            "password_hash": "x",
        }
        info = safe_account_info(user_doc)
        self.assertEqual(info["user_id"], "abc123")
        self.assertEqual(info["email"], "person@example.com")
        self.assertEqual(info["created_at"], "2026-01-01T00:00:00Z")
        self.assertFalse(info["is_staff"])

    def test_none_user_doc_returns_none(self):
        self.assertIsNone(safe_account_info(None))

    def test_missing_is_staff_defaults_false(self):
        info = safe_account_info({"_id": "x", "email": "e", "created_at": "c"})
        self.assertFalse(info["is_staff"])


class FlattenPlanHistoryTests(unittest.TestCase):
    def test_empty_user_state_produces_empty_lists_for_every_agent(self):
        history = flatten_plan_history({})
        self.assertEqual(history, {"physio": [], "nutrition": [], "behaviour": []})

    def test_unavailable_section_produces_empty_list(self):
        state = {"exercise_history": {"available": False, "reason": "not yet", "data": None}}
        history = flatten_plan_history(state)
        self.assertEqual(history["physio"], [])

    def test_real_plan_versions_are_flattened_unredacted(self):
        state = {
            "exercise_history": {
                "available": True,
                "reason": None,
                "data": {
                    "plans": [
                        {
                            "plan_id": "p1",
                            "plan_version": 1,
                            "created_at": "2026-01-01T00:00:00Z",
                            "goal": "Improve balance",
                            "adaptation_reason": None,
                            "triggered_by": None,
                            "source": "physio_agent",
                            "agent_run_id": "run_1",
                            "exercise_ids": ["ex1", "ex2"],
                        },
                        {
                            "plan_id": "p2",
                            "plan_version": 2,
                            "created_at": "2026-02-01T00:00:00Z",
                            "goal": "Improve balance",
                            "adaptation_reason": "Progress Agent recommended PROGRESS",
                            "triggered_by": "progress_agent",
                            "source": "physio_agent",
                            "agent_run_id": "run_2",
                            "exercise_ids": ["ex1", "ex3"],
                        },
                    ]
                },
            }
        }
        history = flatten_plan_history(state)
        self.assertEqual(len(history["physio"]), 2)
        self.assertEqual(history["physio"][0]["plan_version"], 1)
        self.assertEqual(history["physio"][1]["plan_version"], 2)
        self.assertEqual(history["physio"][1]["adaptation_reason"], "Progress Agent recommended PROGRESS")
        self.assertEqual(history["physio"][1]["triggered_by"], "progress_agent")
        self.assertEqual(history["physio"][1]["selected_ids"], ["ex1", "ex3"])
        self.assertEqual(history["nutrition"], [])
        self.assertEqual(history["behaviour"], [])

    def test_nutrition_and_behaviour_use_topic_ids(self):
        state = {
            "nutrition_plan": {
                "available": True,
                "reason": None,
                "data": {
                    "plans": [
                        {
                            "plan_id": "n1",
                            "plan_version": 1,
                            "created_at": "2026-01-01T00:00:00Z",
                            "goal": "g",
                            "adaptation_reason": None,
                            "triggered_by": None,
                            "source": "nutrition_agent",
                            "agent_run_id": "run_n1",
                            "topic_ids": ["t1"],
                        }
                    ]
                },
            }
        }
        history = flatten_plan_history(state)
        self.assertEqual(history["nutrition"][0]["selected_ids"], ["t1"])


class McpStatusReportTests(unittest.TestCase):
    def test_reports_not_installed_when_mcp_unavailable(self):
        # The flag is passed explicitly rather than left to whatever the
        # machine happens to have installed. This test used to call
        # mcp_status_report() bare and pass only because `mcp` was absent;
        # installing it made the test fail without anything being wrong,
        # which means it was asserting the environment, not the behaviour.
        report = mcp_status_report(mcp_installed=False)

        self.assertFalse(report["mcp_package_installed"])
        self.assertIn("NOT INSTALLED", report["status_message"])

    def test_reports_installed_branch_when_overridden(self):
        report = mcp_status_report(mcp_installed=True)
        self.assertTrue(report["mcp_package_installed"])
        self.assertNotIn("NOT INSTALLED", report["status_message"])

    def test_every_specialist_present_with_real_tool_names(self):
        report = mcp_status_report()
        self.assertEqual(
            set(report["specialists"]),
            {"physio", "behaviour", "nutrition", "progress", "safety"},
        )
        self.assertIn("compare_assessments_tool", report["specialists"]["progress"]["real_tools"])
        self.assertIn("record_exercise_result_tool", report["specialists"]["physio"]["real_tools"])
        self.assertIn("check_safety_tool", report["specialists"]["safety"]["real_tools"])
        self.assertEqual(
            report["specialists"]["physio"]["server_module"], "mcp_servers.exercise_server"
        )
        self.assertEqual(
            report["specialists"]["safety"]["server_module"], "mcp_servers.safety_server"
        )

    def test_mcp_server_tools_table_is_internally_consistent(self):
        for agent_id, (module_name, tool_names) in _MCP_SERVER_TOOLS.items():
            self.assertTrue(module_name.startswith("mcp_servers."))
            self.assertGreater(len(tool_names), 0)


if __name__ == "__main__":
    unittest.main()
