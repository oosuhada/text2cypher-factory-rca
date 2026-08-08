from __future__ import annotations

import unittest

from backend.app.services.bootstrap import ServiceBundle
from backend.app.tools import ToolRegistry, ToolSpec
from backend.app.tools.capabilities import (
    GraphQueryInput,
    QueryToolOutput,
    SearchDocsInput,
    SearchDocsOutput,
)


class FakeAgent:
    metadata = {"project_id": "equipment-history"}


class FakeQuery:
    agent = FakeAgent()


class DocumentToolOrchestrationTest(unittest.TestCase):
    def setUp(self):
        self.calls: list[str] = []
        tools = ToolRegistry()

        def graph(payload, context):
            self.calls.append("graph")
            return {
                "question": payload.question,
                "status": "success",
                "answer": "그래프 조회 결과 2건입니다.",
                "rows": [{"maintenance_id": "M-1"}],
                "row_count": 1,
                "validation": {"tool_trace": []},
                "evidence": {
                    "nodes": [],
                    "relationships": [],
                    "node_count": 0,
                    "relationship_count": 0,
                },
            }

        def docs(payload, context):
            self.calls.append("docs")
            match = {
                "document_id": "press-manual",
                "title": "프레스 정비 매뉴얼",
                "version": "2.0",
                "page_number": 1,
                "text": "압력 안정화 시험을 10분 수행한다.",
                "citation_id": "press-manual@2.0:p1",
            }
            return {
                "project_id": context.project_id,
                "query": payload.query,
                "status": "success",
                "answer": "[press-manual@2.0:p1] 압력 안정화 시험을 10분 수행한다.",
                "framework": "LlamaIndex",
                "framework_version": "0.14.23",
                "index_version": "llamaindex-rag-v1",
                "top_k": payload.top_k,
                "matches": [match],
                "citations": [{"citation_id": match["citation_id"]}],
            }

        tools.register(
            ToolSpec(
                name="graph_query_tool",
                description="Graph",
                input_model=GraphQueryInput,
                output_model=QueryToolOutput,
                handler=graph,
            )
        )
        tools.register(
            ToolSpec(
                name="search_docs_tool",
                description="Docs",
                input_model=SearchDocsInput,
                output_model=SearchDocsOutput,
                handler=docs,
            )
        )
        self.bundle = ServiceBundle(
            driver=None,
            query=FakeQuery(),
            fallback_query=None,
            dashboard=None,
            provider="gold",
            model_name="gold-lookup",
            tools=tools,
        )

    def test_document_only_question_calls_only_llamaindex_tool(self):
        result = self.bundle.query_with_fallback(
            "유압 펌프 교체 후 점검 절차를 매뉴얼에서 알려줘.",
            roles=("Analyst",),
        )

        self.assertEqual(self.calls, ["docs"])
        self.assertEqual(result["provider"], "llamaindex")
        self.assertEqual(result["cypher"], "")
        self.assertEqual(len(result["evidence"]["documents"]), 1)
        self.assertEqual(
            result["validation"]["tool_trace"][0]["tool"],
            "search_docs_tool",
        )

    def test_hybrid_question_calls_graph_and_documents(self):
        result = self.bundle.query_with_fallback(
            "EQ-PRESS-01의 정비 이력과 매뉴얼 점검 절차를 같이 알려줘.",
            roles=("Analyst",),
        )

        self.assertEqual(self.calls, ["docs", "graph"])
        self.assertEqual(result["status"], "success")
        self.assertIn("그래프 조회 결과", result["answer"])
        self.assertIn("문서 근거", result["answer"])
        self.assertEqual(len(result["evidence"]["documents"]), 1)
        self.assertEqual(
            [trace["tool"] for trace in result["validation"]["tool_trace"][:2]],
            ["graph_query_tool", "search_docs_tool"],
        )

    def test_graph_only_question_does_not_search_documents(self):
        result = self.bundle.query_with_fallback(
            "EQ-PRESS-01의 정비 이력을 날짜순으로 보여줘.",
            roles=("Analyst",),
        )

        self.assertEqual(self.calls, ["graph"])
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["evidence"].get("documents"), None)


if __name__ == "__main__":
    unittest.main()
