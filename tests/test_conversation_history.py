import unittest

from frontend.conversation_history import (
    MAX_SESSION_CONVERSATIONS,
    conversation_title,
    upsert_conversation,
)


class ConversationHistoryTest(unittest.TestCase):
    def test_title_uses_first_user_question_and_truncates(self):
        messages = [
            {"role": "assistant", "content": {"answer": "ready"}},
            {"role": "user", "content": "가" * 40},
        ]
        title = conversation_title(messages)
        self.assertEqual(len(title), 34)
        self.assertTrue(title.endswith("…"))

    def test_upsert_is_newest_first_and_deep_copies_messages(self):
        messages = [{"role": "user", "content": "첫 질문"}]
        conversations = upsert_conversation(
            [],
            conversation_id="one",
            messages=messages,
            last_result={"status": "success"},
            updated_at="2026-07-27T00:00:00+00:00",
        )
        messages[0]["content"] = "변경됨"
        self.assertEqual(
            conversations[0]["messages"][0]["content"],
            "첫 질문",
        )

        updated = upsert_conversation(
            conversations,
            conversation_id="two",
            messages=[{"role": "user", "content": "두 번째"}],
            last_result={"status": "empty"},
            updated_at="2026-07-27T00:01:00+00:00",
        )
        self.assertEqual([item["id"] for item in updated], ["two", "one"])

    def test_history_is_bounded(self):
        conversations = []
        for index in range(MAX_SESSION_CONVERSATIONS + 3):
            conversations = upsert_conversation(
                conversations,
                conversation_id=str(index),
                messages=[{"role": "user", "content": str(index)}],
                last_result=None,
            )
        self.assertEqual(len(conversations), MAX_SESSION_CONVERSATIONS)


if __name__ == "__main__":
    unittest.main()
