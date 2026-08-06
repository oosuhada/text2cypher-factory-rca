from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.conversations import ConversationStore
from frontend.design_system import Role
from frontend.navigation import apply_navigation_request
from frontend.session_state import (
    initialize_session_state,
    open_conversation_state,
    start_new_conversation_state,
    switch_project_state,
    sync_active_conversation_state,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def turn(question: str, answer: str) -> list[dict]:
    return [
        {"role": "user", "content": question},
        {
            "role": "assistant",
            "content": {
                "question": question,
                "answer": answer,
                "status": "success",
                "rows": [{"answer": answer}],
                "row_count": 1,
            },
        },
    ]


class StreamlitSessionStateContractTest(unittest.TestCase):
    def setUp(self):
        self._temp = TemporaryDirectory()
        self.store = ConversationStore(
            Path(self._temp.name) / "conversations.sqlite3"
        )

    def tearDown(self):
        self._temp.cleanup()

    def test_refresh_and_reinitialization_do_not_duplicate_messages(self):
        state: dict = {}
        initialize_session_state(state, self.store)
        state["messages"] = turn("설비 상태를 보여줘.", "정상입니다.")
        state["last_result"] = state["messages"][1]["content"]
        sync_active_conversation_state(state, self.store)

        refreshed: dict = {}
        initialize_session_state(refreshed, self.store)
        initialize_session_state(refreshed, self.store)

        self.assertEqual(len(refreshed["messages"]), 2)
        self.assertEqual(len(refreshed["conversations"]), 1)
        self.assertEqual(
            self.store.list("cip-dmd")[0]["messages"],
            refreshed["messages"],
        )

    def test_project_switch_restores_each_project_conversation(self):
        state: dict = {}
        initialize_session_state(state, self.store)
        state["messages"] = turn("공정 이력을 보여줘.", "CNC milling")
        state["last_result"] = state["messages"][1]["content"]

        self.assertTrue(
            switch_project_state(state, "equipment-history", self.store)
        )
        self.assertEqual(state["messages"], [])
        state["messages"] = turn("정비 이력을 보여줘.", "2026-07-01")
        state["last_result"] = state["messages"][1]["content"]

        self.assertTrue(switch_project_state(state, "cip-dmd", self.store))
        self.assertEqual(
            state["messages"][0]["content"],
            "공정 이력을 보여줘.",
        )
        self.assertTrue(
            switch_project_state(state, "equipment-history", self.store)
        )
        self.assertEqual(
            state["messages"][0]["content"],
            "정비 이력을 보여줘.",
        )

    def test_new_and_reopened_conversation_keep_one_active_history(self):
        state: dict = {}
        initialize_session_state(state, self.store)
        state["messages"] = turn("첫 질문", "첫 답변")
        sync_active_conversation_state(state, self.store)
        first_id = state["active_conversation_id"]

        start_new_conversation_state(state, self.store)
        state["messages"] = turn("두 번째 질문", "두 번째 답변")
        sync_active_conversation_state(state, self.store)

        self.assertEqual(len(state["conversations"]), 2)
        self.assertTrue(open_conversation_state(state, first_id))
        self.assertEqual(state["messages"][0]["content"], "첫 질문")
        self.assertFalse(open_conversation_state(state, "missing"))


class StreamlitNavigationStateContractTest(unittest.TestCase):
    def test_programmatic_navigation_updates_pending_state_and_url(self):
        navigation_source = (
            PROJECT_ROOT / "frontend" / "navigation.py"
        ).read_text(encoding="utf-8")
        function_source = navigation_source[
            navigation_source.index("def navigate_to_page("):
            navigation_source.index("\n\ndef workspace_url(")
        ]
        self.assertIn(
            'st.session_state["pending_page"] = page',
            function_source,
        )
        self.assertIn(
            'st.session_state["consumed_workspace_query"] = workspace_key',
            function_source,
        )
        self.assertIn(
            'st.query_params["workspace"] = workspace_key',
            function_source,
        )

    def test_url_and_pending_navigation_increment_widget_revision_once(self):
        state = {
            "active_page": "Home",
            "navigation_widget_revision": 0,
        }

        page, allowed = apply_navigation_request(
            state,
            Role.ADMIN,
            "query_studio",
        )
        self.assertEqual(page, "Query Studio")
        self.assertIn("Graph Explorer", allowed)
        self.assertEqual(state["navigation_widget_revision"], 1)

        page, _ = apply_navigation_request(
            state,
            Role.ADMIN,
            "query_studio",
        )
        self.assertEqual(page, "Query Studio")
        self.assertEqual(state["navigation_widget_revision"], 1)

        state["pending_page"] = "Projects"
        page, _ = apply_navigation_request(state, Role.ADMIN, None)
        self.assertEqual(page, "Projects")
        self.assertEqual(state["navigation_widget_revision"], 2)

    def test_role_change_falls_back_to_home_for_hidden_workspace(self):
        state = {
            "active_page": "Admin",
            "navigation_widget_revision": 0,
        }

        page, allowed = apply_navigation_request(
            state,
            Role.VIEWER,
            None,
        )

        self.assertEqual(page, "Home")
        self.assertNotIn("Admin", allowed)


if __name__ == "__main__":
    unittest.main()
