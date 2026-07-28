import unittest

from frontend.conversation_history import (
    MAX_SESSION_CONVERSATIONS,
    conversation_title,
    deduplicate_conversation_turns,
    upsert_conversation,
)


class ConversationHistoryTest(unittest.TestCase):
    def test_large_repeated_fixture_leak_is_deduplicated(self):
        first_response = {
            "question": "설비 상태를 보여줘.",
            "answer": "정상입니다.",
            "status": "success",
            "cypher": "MATCH (n) RETURN n",
            "rows": [{"status": "normal"}],
            "row_count": 1,
            "evidence": {"nodes": [], "relationships": []},
            "provider": "gold",
            "validation": {"elapsed_ms": 10},
        }
        second_response = {
            **first_response,
            "validation": {"elapsed_ms": 999},
            "usage": {"total_tokens": 100},
        }
        messages = []
        for repeat in range(20):
            messages.extend(
                [
                    {"role": "user", "content": "설비 상태를 보여줘."},
                    {
                        "role": "assistant",
                        "content": (
                            first_response
                            if repeat == 0
                            else second_response
                        ),
                    },
                ]
            )

        normalized = deduplicate_conversation_turns(messages)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(
            normalized[1]["content"]["validation"]["elapsed_ms"], 10
        )

    def test_short_intentional_rerun_remains_in_history(self):
        response = {
            "question": "설비 상태를 보여줘.",
            "answer": "정상입니다.",
            "status": "success",
            "rows": [{"status": "normal"}],
        }
        messages = [
            {"role": "user", "content": "설비 상태를 보여줘."},
            {"role": "assistant", "content": response},
            {"role": "user", "content": "설비 상태를 보여줘."},
            {"role": "assistant", "content": response},
        ]

        self.assertEqual(len(deduplicate_conversation_turns(messages)), 4)

    def test_changed_results_remain_as_separate_turns(self):
        messages = [
            {"role": "user", "content": "불량 수를 보여줘."},
            {
                "role": "assistant",
                "content": {
                    "question": "불량 수를 보여줘.",
                    "answer": "1건입니다.",
                    "status": "success",
                    "rows": [{"count": 1}],
                },
            },
            {"role": "user", "content": "불량 수를 보여줘."},
            {
                "role": "assistant",
                "content": {
                    "question": "불량 수를 보여줘.",
                    "answer": "2건입니다.",
                    "status": "success",
                    "rows": [{"count": 2}],
                },
            },
        ]

        self.assertEqual(len(deduplicate_conversation_turns(messages)), 4)

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
