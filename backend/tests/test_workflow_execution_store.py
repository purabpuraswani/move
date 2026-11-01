import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import SQLiteClient
import workflow_execution.store as store


class WorkflowExecutionStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.client = SQLiteClient(Path(self.directory.name) / "history.sqlite3")
        self.collection = self.client["workflow_executions"]
        self.patcher = patch.object(store, "workflow_executions_collection", self.collection)
        self.patcher.start()
        store.ensure_indexes()

    def tearDown(self):
        self.patcher.stop()
        self.client.close()
        self.directory.cleanup()

    def test_upsert_is_idempotent_and_results_are_user_scoped(self):
        first = store.save_execution("user-a", "retry-1", {
            "workflow_id": "wf-1",
            "agent_executions": {
                "exercise_activity": {"findings": {"activity_findings": [{"finding": "actual activity"}], "activity_recommendations": [{"id": "steps"}]}},
                "recovery": {"findings": {"recovery_findings": [{"finding": "actual recovery"}], "constraint": {"limit_progression": False}}},
                "progress": {"findings": {
                    "physical_comparison": {"status": "NOT_ENOUGH_DATA", "evidence": []},
                    "adaptation_recommendation": "REASSESS",
                }},
            },
            "selected_agents": ["progress", "physio"],
            "orchestrator_decision": {"progress_dispatch": "physio"},
        })
        second = store.save_execution("user-a", "retry-1", {
            "workflow_id": "wf-1",
            "agent_executions": {
                "exercise_activity": {"findings": {"activity_findings": [{"finding": "actual activity"}], "activity_recommendations": [{"id": "steps"}]}},
                "recovery": {"findings": {"recovery_findings": [{"finding": "actual recovery"}], "constraint": {"limit_progression": False}}},
                "progress": {"findings": {
                    "physical_comparison": {"status": "NOT_ENOUGH_DATA", "evidence": []},
                    "adaptation_recommendation": "REASSESS",
                }},
            },
            "selected_agents": ["progress", "physio"],
            "orchestrator_decision": {"progress_dispatch": "physio"},
        })
        store.save_execution("user-b", "retry-1", {"workflow_id": "wf-2"})

        self.assertEqual(first["_id"], second["_id"])
        self.assertEqual(len(store.list_executions("user-a")), 1)
        self.assertEqual(store.latest_execution("user-a")["workflow_id"], "wf-1")
        self.assertEqual(
            store.latest_execution("user-a")["agent_executions"]["progress"]["findings"]["physical_comparison"]["status"],
            "NOT_ENOUGH_DATA",
        )
        history = store.latest_execution("user-a")["agent_executions"]
        self.assertEqual(history["exercise_activity"]["findings"]["activity_recommendations"][0]["id"], "steps")
        self.assertFalse(history["recovery"]["findings"]["constraint"]["limit_progression"])
        self.assertEqual(store.latest_execution("user-b")["workflow_id"], "wf-2")
        self.assertIsNone(store.get_execution("user-a", "other-user-key"))


if __name__ == "__main__":
    unittest.main()
