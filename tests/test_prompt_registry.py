from pathlib import Path
import unittest

from backend.app.agent.prompt_registry import PromptRegistry


class PromptRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.registry = PromptRegistry(cls.project_root)

    def test_existing_projects_have_separate_versioned_contracts(self):
        cip = self.registry.load("cip-dmd")
        equipment = self.registry.load("equipment-history")

        self.assertEqual(cip.schema_version, "1.1")
        self.assertEqual(equipment.schema_version, "1.0")
        self.assertNotEqual(cip.examples_path, equipment.examples_path)
        self.assertIn("project_id 'cip-dmd'", cip.schema_context)
        self.assertIn(
            "project_id 'equipment-history'",
            equipment.schema_context,
        )
        self.assertEqual(len(cip.fingerprint), 64)
        self.assertEqual(len(equipment.fingerprint), 64)

    def test_contract_metadata_exposes_reproducibility_versions(self):
        metadata = self.registry.load("equipment-history").metadata()
        self.assertEqual(metadata["project_id"], "equipment-history")
        self.assertEqual(metadata["prompt_version"], "text2cypher-v1")
        self.assertEqual(metadata["evaluation_version"], "1.0")
        self.assertEqual(len(metadata["prompt_template_sha256"]), 64)
        self.assertTrue(metadata["prompt_fingerprint"])

    def test_unknown_project_has_no_implicit_prompt_fallback(self):
        with self.assertRaises(KeyError):
            self.registry.load("unknown-project")


if __name__ == "__main__":
    unittest.main()
