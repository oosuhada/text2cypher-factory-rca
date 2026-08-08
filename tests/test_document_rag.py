from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfWriter

from backend.app.rag import DocumentRagService


class DocumentRagServiceTest(unittest.TestCase):
    def test_ingestion_persists_and_reloads_llamaindex(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            service = DocumentRagService(
                root,
                "equipment-history",
                similarity_cutoff=0.0,
            )
            indexed = service.ingest(
                document_id="press-manual",
                title="프레스 정비 매뉴얼",
                version="2.0",
                document_type="maintenance_manual",
                source_filename="manual.md",
                content=(
                    "# 유압 펌프 교체 후 점검\n"
                    "정상 압력에서 10분 동안 압력 안정화 시험을 수행한다."
                ),
            )
            reloaded = DocumentRagService(
                root,
                "equipment-history",
                similarity_cutoff=0.0,
            )
            result = reloaded.search(
                "유압 펌프 교체 후 압력 시험 절차",
                roles=("Analyst",),
            )

        self.assertFalse(indexed["duplicate"])
        self.assertGreaterEqual(indexed["chunk_count"], 1)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matches"][0]["document_id"], "press-manual")
        self.assertEqual(result["matches"][0]["page_number"], 1)
        self.assertEqual(result["citations"][0]["citation_id"], "press-manual@2.0:p1")

    def test_duplicate_upload_does_not_create_duplicate_chunks(self):
        with TemporaryDirectory() as directory:
            service = DocumentRagService(Path(directory), "cip-dmd")
            arguments = {
                "document_id": "quality-sop",
                "title": "품질검사 SOP",
                "version": "1.0",
                "document_type": "sop",
                "source_filename": "quality.md",
                "content": "압력검사 실패 시 상류 공정과 구성품을 확인한다.",
            }
            first = service.ingest(**arguments)
            second = service.ingest(**arguments)
            documents = service.list_documents()

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(documents), 1)

    def test_new_version_supersedes_old_and_current_filter_is_enforced(self):
        with TemporaryDirectory() as directory:
            service = DocumentRagService(
                Path(directory),
                "equipment-history",
                similarity_cutoff=0.0,
            )
            common = {
                "document_id": "press-manual",
                "title": "Press Manual",
                "document_type": "maintenance_manual",
                "source_filename": "manual.md",
            }
            service.ingest(
                **common,
                version="1.0",
                content="교체 후 저압에서 3분 동안 시험한다.",
            )
            service.ingest(
                **common,
                version="2.0",
                content="교체 후 정상 압력에서 10분 동안 안정화 시험한다.",
            )
            current = service.search(
                "교체 후 시험",
                current_only=True,
                top_k=10,
            )
            all_versions = service.search(
                "교체 후 시험",
                current_only=False,
                top_k=10,
            )
            documents = service.list_documents()

        self.assertEqual({item["version"] for item in current["matches"]}, {"2.0"})
        self.assertEqual(
            {item["version"] for item in all_versions["matches"]},
            {"1.0", "2.0"},
        )
        current_flags = {item["version"]: item["is_current"] for item in documents}
        self.assertEqual(current_flags, {"1.0": False, "2.0": True})

    def test_document_roles_are_filtered_without_metadata_leakage(self):
        with TemporaryDirectory() as directory:
            service = DocumentRagService(
                Path(directory),
                "equipment-history",
                similarity_cutoff=0.0,
            )
            service.ingest(
                document_id="restricted-sop",
                title="Restricted SOP",
                version="1.0",
                document_type="sop",
                source_filename="restricted.md",
                content="고압 시험은 승인된 기술자만 수행한다.",
                allowed_roles=("Domain Expert", "Admin"),
            )
            viewer = service.search("고압 시험 절차", roles=("Viewer",))
            expert = service.search("고압 시험 절차", roles=("Domain Expert",))
            viewer_documents = service.list_documents(roles=("Viewer",))
            expert_documents = service.list_documents(
                roles=("Domain Expert",)
            )
            viewer_readiness = service.readiness(roles=("Viewer",))
            admin_readiness = service.readiness(
                roles=("Admin",),
                include_restricted=True,
            )

        self.assertEqual(viewer["status"], "empty")
        self.assertEqual(viewer["matches"], [])
        self.assertEqual(viewer["citations"], [])
        self.assertNotIn("Restricted SOP", viewer["answer"])
        self.assertEqual(expert["status"], "success")
        self.assertEqual(expert["matches"][0]["document_id"], "restricted-sop")
        self.assertEqual(viewer_documents, [])
        self.assertEqual(expert_documents[0]["document_id"], "restricted-sop")
        self.assertEqual(viewer_readiness["document_count"], 0)
        self.assertEqual(admin_readiness["document_count"], 1)

    def test_no_match_never_invents_a_citation(self):
        with TemporaryDirectory() as directory:
            service = DocumentRagService(
                Path(directory),
                "cip-dmd",
                similarity_cutoff=0.99,
            )
            service.ingest(
                document_id="quality-sop",
                title="Quality SOP",
                version="1.0",
                document_type="sop",
                source_filename="quality.txt",
                content="압력검사 실패 시 구성품을 확인한다.",
            )
            result = service.search("우주선 연료 규정")

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["citations"], [])
        self.assertNotIn("@", result["answer"])

    def test_project_indexes_are_physically_isolated(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            equipment = DocumentRagService(root, "equipment-history", similarity_cutoff=0.0)
            manufacturing = DocumentRagService(root, "cip-dmd", similarity_cutoff=0.0)
            equipment.ingest(
                document_id="maintenance",
                title="Maintenance",
                version="1",
                document_type="manual",
                source_filename="maintenance.txt",
                content="유압 펌프 정비 절차",
            )
            manufacturing.ingest(
                document_id="quality",
                title="Quality",
                version="1",
                document_type="sop",
                source_filename="quality.txt",
                content="압력검사 품질 절차",
            )
            equipment_result = equipment.search("유압 펌프", top_k=10)
            manufacturing_result = manufacturing.search("유압 펌프", top_k=10)

        self.assertEqual(
            {item["document_id"] for item in equipment_result["matches"]},
            {"maintenance"},
        )
        self.assertNotIn(
            "maintenance",
            {item["document_id"] for item in manufacturing_result["matches"]},
        )
        self.assertNotEqual(equipment.index_dir, manufacturing.index_dir)

    def test_scanned_or_blank_pdf_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "blank.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            with pdf_path.open("wb") as stream:
                writer.write(stream)
            service = DocumentRagService(root, "equipment-history")

            with self.assertRaisesRegex(ValueError, "텍스트 레이어"):
                service.ingest(
                    document_id="blank",
                    title="Blank",
                    version="1",
                    document_type="manual",
                    source_filename="blank.pdf",
                    content_base64=__import__("base64").b64encode(
                        pdf_path.read_bytes()
                    ).decode("ascii"),
                )

        self.assertEqual(service.list_documents(), [])


if __name__ == "__main__":
    unittest.main()
