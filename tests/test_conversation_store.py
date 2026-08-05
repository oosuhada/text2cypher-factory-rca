from pathlib import Path
import tempfile
import unittest

from backend.app.conversations import ConversationStore


class ConversationStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ConversationStore(
            Path(self.temp.name) / "conversations.sqlite3"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_project_history_survives_reopen_and_is_searchable(self):
        conversation = {
            "id": "conversation-1",
            "title": "압력검사 실패 제품",
            "messages": [
                {"role": "user", "content": "압력검사 실패 제품을 보여줘."},
                {
                    "role": "assistant",
                    "content": {"status": "success", "row_count": 19},
                },
            ],
            "last_result": {"status": "success", "row_count": 19},
            "created_at": "2026-07-28T00:00:00+00:00",
            "updated_at": "2026-07-28T00:01:00+00:00",
        }
        self.store.save("cip-dmd", conversation)

        reopened = ConversationStore(self.store.path)
        rows = reopened.list("cip-dmd", search="압력검사")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["last_result"]["row_count"], 19)
        self.assertEqual(reopened.list("equipment-history"), [])

    def test_upsert_preserves_created_at_and_delete_is_project_scoped(self):
        base = {
            "id": "conversation-1",
            "title": "처음 질문",
            "messages": [{"role": "user", "content": "처음 질문"}],
            "last_result": None,
            "created_at": "2026-07-28T00:00:00+00:00",
            "updated_at": "2026-07-28T00:01:00+00:00",
        }
        self.store.save("cip-dmd", base)
        self.store.save(
            "cip-dmd",
            {
                **base,
                "title": "수정된 질문",
                "updated_at": "2026-07-28T00:02:00+00:00",
            },
        )
        stored = self.store.get("cip-dmd", "conversation-1")
        self.assertEqual(stored["title"], "수정된 질문")
        self.assertEqual(stored["created_at"], base["created_at"])
        self.assertEqual(self.store.delete_project("cip-dmd"), 1)
        self.assertEqual(self.store.list("cip-dmd"), [])

    def test_empty_conversation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "비어 있는 대화"):
            self.store.save(
                "cip-dmd",
                {"id": "empty", "title": "empty", "messages": []},
            )


if __name__ == "__main__":
    unittest.main()
