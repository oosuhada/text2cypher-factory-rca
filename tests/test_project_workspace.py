from datetime import datetime, timezone
import unittest

from frontend.project_context import (
    empty_project_context,
    restore_project_context,
    snapshot_project_context,
)
from frontend.project_workspace import (
    filter_projects,
    next_action_presentation,
    project_destination_page,
    relative_updated_at,
    status_presentation,
)


class ProjectWorkspaceTest(unittest.TestCase):
    def test_filter_prioritizes_favorite_and_active_projects(self):
        projects = [
            {
                "project_id": "plain",
                "name": "Plain",
                "status": "draft",
                "favorite": 0,
                "is_active": False,
            },
            {
                "project_id": "favorite",
                "name": "Semiconductor Yield",
                "status": "ready",
                "favorite": 1,
                "is_active": False,
            },
            {
                "project_id": "active",
                "name": "Active",
                "status": "ready",
                "favorite": 0,
                "is_active": True,
            },
        ]
        filtered = filter_projects(
            projects, search="yield", statuses={"ready"}
        )
        self.assertEqual(
            [project["project_id"] for project in filtered], ["favorite"]
        )
        ordered = filter_projects(projects)
        self.assertEqual(ordered[0]["project_id"], "favorite")
        self.assertEqual(ordered[1]["project_id"], "active")

    def test_project_context_is_fully_isolated_and_deep_copied(self):
        state = empty_project_context()
        state["messages"] = [{"role": "user", "content": "project-a"}]
        state["explorer_result"] = {"nodes": [{"id": "a"}]}
        state["query_filters"] = {"status": "success"}
        snapshot = snapshot_project_context(state)

        state["messages"][0]["content"] = "mutated"
        restore_project_context(state, None)
        self.assertEqual(state["messages"], [])
        self.assertIsNone(state["explorer_result"])

        restore_project_context(state, snapshot)
        self.assertEqual(state["messages"][0]["content"], "project-a")
        self.assertEqual(state["query_filters"], {"status": "success"})

    def test_status_next_action_and_relative_time_copy(self):
        self.assertEqual(status_presentation("ready")["progress"], 100)
        self.assertEqual(
            next_action_presentation("upload")["page"], "Data Sources"
        )
        now = datetime(2026, 7, 28, 3, 0, tzinfo=timezone.utc)
        self.assertEqual(
            relative_updated_at(
                "2026-07-28T02:30:00+00:00",
                now=now,
            ),
            "30분 전",
        )

    def test_project_destination_opens_query_when_ready(self):
        self.assertEqual(
            project_destination_page(
                {"can_query": True, "next_action": "upload"}
            ),
            "Query Studio",
        )

    def test_project_destination_opens_next_required_workspace(self):
        self.assertEqual(
            project_destination_page(
                {"can_query": False, "next_action": "upload"}
            ),
            "Data Sources",
        )
        self.assertEqual(
            project_destination_page(
                {"can_query": False, "next_action": "validate"}
            ),
            "Pipeline",
        )
        self.assertEqual(
            project_destination_page(
                {"can_query": False, "next_action": "evaluate"}
            ),
            "Evaluations",
        )


if __name__ == "__main__":
    unittest.main()
