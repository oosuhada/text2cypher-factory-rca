import unittest
from pathlib import Path

from backend.app.etl.adapters import (
    CipDmdAdapter,
    EtlAdapterRegistry,
)
from backend.app.etl.pipeline import EtlPipeline


class EtlAdapterTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.adapter = CipDmdAdapter()

    def test_cip_adapter_reproduces_validated_projection(self):
        pipeline = EtlPipeline(
            self.adapter, self.root / "infra" / "schema.cypher"
        )
        prepared = pipeline.dry_run(
            self.root / "data" / "raw" / "cip_dmd"
        )
        self.assertEqual(prepared.project_id, "cip-dmd")
        self.assertEqual(prepared.validation["status"], "PASS")
        self.assertEqual(prepared.payload.counts(), self.adapter.expected_counts)

    def test_registry_is_project_keyed_and_rejects_duplicates(self):
        registry = EtlAdapterRegistry([self.adapter])
        self.assertIs(registry.require("cip-dmd"), self.adapter)
        self.assertEqual(registry.projects(), ["cip-dmd"])
        with self.assertRaisesRegex(ValueError, "이미 등록"):
            registry.register(CipDmdAdapter())
        with self.assertRaisesRegex(KeyError, "없는 프로젝트"):
            registry.require("missing-project")
