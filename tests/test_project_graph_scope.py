import unittest

from backend.app.services.graph_service import (
    GraphCatalogService,
    node_search_contract,
)
from frontend.app_services import _DirectProjectGraph


class FakeResult:
    def __iter__(self):
        return iter([])

    def single(self):
        return None


class FakeSession:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def run(self, query, **kwargs):
        self.calls.append((str(query), kwargs))
        return FakeResult()


class FakeDriver:
    def __init__(self):
        self.calls = []

    def session(self, **_kwargs):
        return FakeSession(self.calls)


class ProjectGraphScopeTest(unittest.TestCase):
    def test_search_contract_includes_inherited_properties(self):
        identity, properties = node_search_contract(
            {
                "nodes": [
                    {
                        "label": "Part",
                        "identity": "part_id",
                        "properties": {
                            "part_id": "STRING",
                            "part_type": "STRING",
                        },
                    },
                    {
                        "label": "Cylinder",
                        "identity": "part_id",
                        "extends": "Part",
                        "properties": {"serial": "STRING"},
                    },
                ]
            },
            "Cylinder",
        )
        self.assertEqual(identity, "part_id")
        self.assertEqual(
            properties, ("part_id", "part_type", "serial")
        )

    def test_generic_search_and_subgraph_include_project_scope(self):
        driver = FakeDriver()
        graph = GraphCatalogService(driver)
        graph.search_nodes(
            "MaintenanceEvent",
            "repair",
            project_id="equipment-history",
            identity_property="event_id",
            search_properties=("event_id", "event_type"),
        )
        graph.subgraph(
            "MaintenanceEvent",
            "ME-001",
            project_id="equipment-history",
            identity_property="event_id",
        )
        self.assertEqual(len(driver.calls), 2)
        for query, parameters in driver.calls:
            self.assertIn("project_id", query)
            self.assertEqual(parameters["project_id"], "equipment-history")

    def test_search_and_subgraph_include_dataset_version_scope(self):
        driver = FakeDriver()
        graph = GraphCatalogService(driver)
        graph.search_nodes(
            "Equipment",
            "CNC-001",
            project_id="predictive-maintenance-v2",
            dataset_version_id="dsv-v3-1",
            identity_property="source_identity",
            search_properties=("source_identity", "asset_id"),
        )
        graph.subgraph(
            "Equipment",
            "CNC-001",
            project_id="predictive-maintenance-v2",
            dataset_version_id="dsv-v3-1",
            identity_property="source_identity",
        )
        self.assertEqual(len(driver.calls), 2)
        for query, parameters in driver.calls:
            self.assertIn("dataset_version_id", query)
            self.assertEqual(parameters["dataset_version_id"], "dsv-v3-1")

    def test_direct_streamlit_adapter_cannot_drop_project_scope(self):
        class RecordingGraph:
            def __init__(self):
                self.calls = []

            def search_nodes(self, *args, **kwargs):
                self.calls.append(("search", args, kwargs))
                return {"nodes": []}

            def subgraph(self, *args, **kwargs):
                self.calls.append(("subgraph", args, kwargs))
                return {"nodes": [], "relationships": []}

        graph = RecordingGraph()
        adapter = _DirectProjectGraph(
            graph=graph,
            project_id="equipment-history",
            contract={
                "nodes": [
                    {
                        "label": "MaintenanceEvent",
                        "identity": "event_id",
                        "properties": {
                            "event_id": "STRING",
                            "event_type": "STRING",
                        },
                    }
                ]
            },
        )
        adapter.search_nodes("MaintenanceEvent", "repair", 10)
        adapter.subgraph("MaintenanceEvent", "ME-001", 2, 50)
        for _name, _args, kwargs in graph.calls:
            self.assertEqual(
                kwargs["project_id"], "equipment-history"
            )
            self.assertEqual(
                kwargs["identity_property"], "event_id"
            )
