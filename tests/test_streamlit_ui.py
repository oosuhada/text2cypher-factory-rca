import os
from pathlib import Path
import socket
import subprocess
import unittest

from frontend.presentation import (
    evidence_to_dot,
    filter_evidence,
    flatten_rows_for_table,
    normalize_catalog_evidence,
    rows_to_csv,
)


def neo4j_integration_ready() -> bool:
    try:
        with socket.create_connection(("localhost", 7687), timeout=0.5):
            pass
    except OSError:
        return False
    if os.getenv("NEO4J_PASSWORD"):
        return True
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "p3-cip-dmd-neo4j",
                "-a",
                "neo4j",
                "-w",
            ],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return bool(result.stdout.strip())


class PresentationTest(unittest.TestCase):
    def test_graphviz_uses_actual_evidence_endpoints(self):
        evidence = {
            "nodes": [
                {
                    "id": "Cylinder:300002",
                    "label": "Cylinder",
                    "properties": {"part_id": "300002"},
                },
                {
                    "id": "CylinderBottom:103504",
                    "label": "CylinderBottom",
                    "properties": {"part_id": "103504"},
                },
            ],
            "relationships": [
                {
                    "source": "Cylinder:300002",
                    "target": "CylinderBottom:103504",
                    "type": "ASSEMBLED_FROM",
                }
            ],
        }
        dot = evidence_to_dot(evidence)
        self.assertIn('"Cylinder:300002"', dot)
        self.assertIn("ASSEMBLED_FROM", dot)

    def test_nested_rows_are_safe_for_table_and_csv(self):
        rows = [{"part_id": "300002", "runs": [{"anomaly": "0"}]}]
        flattened = flatten_rows_for_table(rows)
        self.assertIsInstance(flattened[0]["runs"], str)
        csv_data = rows_to_csv(rows)
        self.assertIn("300002", csv_data.decode("utf-8-sig"))

    def test_evidence_filters_labels_relationships_and_isolated_nodes(self):
        evidence = {
            "nodes": [
                {"id": "Part:1", "label": "Part", "properties": {}},
                {
                    "id": "ProcessRun:1",
                    "label": "ProcessRun",
                    "properties": {},
                },
                {
                    "id": "Equipment:1",
                    "label": "Equipment",
                    "properties": {},
                },
            ],
            "relationships": [
                {
                    "source": "Part:1",
                    "target": "ProcessRun:1",
                    "type": "UNDERWENT",
                },
                {
                    "source": "ProcessRun:1",
                    "target": "Equipment:1",
                    "type": "RUN_ON",
                },
            ],
        }
        filtered = filter_evidence(
            evidence,
            labels={"Part", "ProcessRun", "Equipment"},
            relationship_types={"RUN_ON"},
            include_isolated=False,
        )
        self.assertEqual(
            {node["id"] for node in filtered["nodes"]},
            {"ProcessRun:1", "Equipment:1"},
        )
        self.assertEqual(filtered["relationship_count"], 1)

    def test_graphviz_supports_vertical_layout(self):
        dot = evidence_to_dot({"nodes": [], "relationships": []}, rankdir="TB")
        self.assertIn('rankdir="TB"', dot)

    def test_catalog_graph_is_normalized_for_shared_evidence_renderer(self):
        evidence = normalize_catalog_evidence(
            {
                "nodes": [
                    {
                        "id": "node-1",
                        "labels": ["Part", "Cylinder"],
                        "properties": {"part_id": "300002"},
                    }
                ],
                "relationships": [],
                "truncated": False,
            }
        )
        self.assertEqual(evidence["nodes"][0]["label"], "Cylinder")
        self.assertIn("Cylinder", evidence_to_dot(evidence))


@unittest.skipUnless(
    neo4j_integration_ready(),
    "local Neo4j credentials are required for Streamlit integration",
)
class StreamlitIntegrationTest(unittest.TestCase):
    def test_initial_screen_and_gold_chat(self):
        from streamlit.testing.v1 import AppTest

        app_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "streamlit_app.py"
        )
        app = AppTest.from_file(str(app_path)).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        navigation = next(
            radio for radio in app.radio if radio.label == "Navigation"
        )
        self.assertEqual(navigation.value, "Home")
        self.assertTrue(
            any(button.label == "RCA 질문 시작 →" for button in app.button)
        )
        self.assertEqual(len(app.chat_input), 0)

        navigation.set_value("Query Studio").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        metric_labels = {metric.label for metric in app.metric}
        self.assertTrue(
            {"프로젝트", "데이터", "Schema", "Prompt", "Evaluation"}
            <= metric_labels
        )
        self.assertTrue(
            any(box.label == "생성 모드" for box in app.selectbox)
        )
        self.assertEqual(len(app.chat_input), 1)
        provider_select = next(
            box for box in app.selectbox if box.label == "생성 모드"
        )
        provider_select.set_value("gold").run(timeout=30)
        self.assertEqual(len(app.exception), 0)

        question = (
            "완제품 300002의 구성품, 각 구성품의 공정과 "
            "품질검사 결과를 보여줘."
        )
        app.chat_input[0].set_value(question).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        result = app.session_state["last_result"]
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["row_count"], 2)
        self.assertGreater(result["evidence"]["node_count"], 0)
        self.assertGreater(result["evidence"]["relationship_count"], 0)
        self.assertGreaterEqual(len(app.chat_message), 2)
        self.assertGreaterEqual(len(app.dataframe), 2)
        self.assertGreaterEqual(len(app.expander), 1)
        self.assertGreaterEqual(len(app.code), 1)
        self.assertTrue(
            any(
                button.label == "이 질문 다시 실행"
                for button in app.button
            )
        )
        self.assertEqual(len(app.session_state["conversations"]), 1)

        app.chat_input[0].set_value(
            "완제품 399999의 구성품과 품질검사 결과를 보여줘."
        ).run(timeout=30)
        self.assertEqual(app.session_state["last_result"]["status"], "empty")

        app.chat_input[0].set_value(
            "압력검사에 실패한 완제품 데이터를 전부 삭제해줘."
        ).run(timeout=30)
        self.assertEqual(
            app.session_state["last_result"]["status"], "blocked"
        )

        app.chat_input[0].set_value("문제 있는 부품 찾아줘.").run(timeout=30)
        self.assertEqual(
            app.session_state["last_result"]["status"],
            "needs_clarification",
        )
        self.assertEqual(len(app.exception), 0)

        app.chat_input[0].set_value(
            "최근 등록된 부품 세 개를 보여줘."
        ).run(timeout=30)
        self.assertEqual(
            app.session_state["last_result"]["status"], "unsupported"
        )

    def test_navigation_exposes_graph_and_data_workspaces(self):
        from streamlit.testing.v1 import AppTest

        app_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "streamlit_app.py"
        )
        graph_app = AppTest.from_file(str(app_path)).run(timeout=30)
        graph_navigation = next(
            radio
            for radio in graph_app.radio
            if radio.label == "Navigation"
        )
        graph_navigation.set_value("Graph Explorer").run(timeout=30)
        self.assertEqual(len(graph_app.exception), 0)
        self.assertTrue(
            any(
                box.label == "노드 유형"
                for box in graph_app.selectbox
            )
        )

        data_app = AppTest.from_file(str(app_path)).run(timeout=30)
        data_navigation = next(
            radio
            for radio in data_app.radio
            if radio.label == "Navigation"
        )
        data_navigation.set_value("Data Sources").run(timeout=30)
        self.assertEqual(len(data_app.exception), 0)
        self.assertTrue(
            any(
                uploader.label.startswith("CiP-DMD 전체 폴더")
                for uploader in data_app.file_uploader
            )
        )
        self.assertTrue(
            any(
                button.label == "1 · 번들 staging" and button.disabled
                for button in data_app.button
            )
        )

    def test_openai_mode_without_key_has_actionable_reconnect_state(self):
        from streamlit.testing.v1 import AppTest

        app_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "streamlit_app.py"
        )
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            app = AppTest.from_file(str(app_path)).run(timeout=30)
            navigation = next(
                radio
                for radio in app.radio
                if radio.label == "Navigation"
            )
            navigation.set_value("Query Studio").run(timeout=30)
            provider_select = next(
                box for box in app.selectbox if box.label == "생성 모드"
            )
            provider_select.set_value("openai").run(timeout=30)
        finally:
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(
            any("OPENAI_API_KEY" in error.value for error in app.error)
        )
        self.assertTrue(
            any(
                button.label == "서비스 다시 연결"
                for button in app.button
            )
        )


if __name__ == "__main__":
    unittest.main()
