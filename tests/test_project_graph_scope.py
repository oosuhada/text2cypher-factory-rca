import unittest

from backend.app.services.graph_service import GraphCatalogService


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
