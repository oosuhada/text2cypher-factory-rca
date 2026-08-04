import base64
from io import BytesIO
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.ingestion import DatasetWorkspace
from backend.app.ingestion.coercion import coerce_value


def minimal_xlsx() -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Events" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
                Target="worksheets/sheet1.xml"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1">
                  <c r="A1" t="inlineStr"><is><t>equipment_id</t></is></c>
                  <c r="B1" t="inlineStr"><is><t>temperature</t></is></c>
                </row>
                <row r="2">
                  <c r="A2" t="inlineStr"><is><t>EQ-1</t></is></c>
                  <c r="B2"><v>42.5</v></c>
                </row>
                <row r="3">
                  <c r="A3" t="inlineStr"><is><t>EQ-2</t></is></c>
                  <c r="B3"><v>41</v></c>
                </row>
              </sheetData>
            </worksheet>""",
        )
    return output.getvalue()


class SourceAdaptersTest(unittest.TestCase):
    def test_date_and_datetime_overrides_are_validated(self):
        self.assertEqual(
            coerce_value("2026-07-28", "DATE").isoformat(),
            "2026-07-28",
        )
        self.assertEqual(
            coerce_value(
                "2026-07-28T09:30:00+09:00", "DATETIME"
            ).isoformat(),
            "2026-07-28T09:30:00+09:00",
        )
        with self.assertRaises(ValueError):
            coerce_value("not-a-date", "DATE")

    def test_korean_source_filename_is_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            result = workspace.profile_upload(
                "factory-demo",
                [
                    {
                        "filename": "설비 이력.csv",
                        "content_base64": base64.b64encode(
                            "설비ID,상태\nEQ-1,정상\n".encode()
                        ).decode(),
                    }
                ],
            )
            self.assertEqual(result["files"][0]["filename"], "설비 이력.csv")

    def test_xlsx_is_normalized_per_sheet_with_lineage(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            result = workspace.profile_upload(
                "factory-demo",
                [
                    {
                        "filename": "workbook.xlsx",
                        "content_base64": base64.b64encode(
                            minimal_xlsx()
                        ).decode(),
                    }
                ],
            )
            self.assertEqual(result["files"][0]["filename"], "workbook__Events.csv")
            self.assertEqual(result["files"][0]["row_count"], 2)
            self.assertEqual(
                result["files"][0]["lineage"]["sheet_name"], "Events"
            )
            upload_root = Path(temp) / "factory-demo" / result["upload_id"]
            self.assertTrue(
                (upload_root / "original" / "workbook.xlsx").exists()
            )
            self.assertTrue(
                (upload_root / "source" / "workbook__Events.csv").exists()
            )

    def test_zip_expands_supported_members_and_preserves_archive_lineage(self):
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("data/events.csv", "event_id,value\nE-1,10\n")
            archive.writestr(
                "data/assets.json",
                '[{"asset_id":"A-1","name":"Press"}]',
            )
            archive.writestr("README.txt", "ignored")
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            result = workspace.profile_upload(
                "factory-demo",
                [
                    {
                        "filename": "factory.zip",
                        "content_base64": base64.b64encode(
                            archive_bytes.getvalue()
                        ).decode(),
                    }
                ],
            )
            self.assertEqual(
                {row["filename"] for row in result["files"]},
                {"events.csv", "assets.json"},
            )
            self.assertTrue(
                all(
                    row["lineage"]["archive_filename"] == "factory.zip"
                    for row in result["files"]
                )
            )

    def test_zip_path_traversal_is_rejected_and_upload_rolls_back(self):
        archive_bytes = BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr("../events.csv", "id\n1\n")
        with tempfile.TemporaryDirectory() as temp:
            workspace = DatasetWorkspace(Path(temp))
            with self.assertRaisesRegex(ValueError, "안전하지"):
                workspace.profile_upload(
                    "factory-demo",
                    [
                        {
                            "filename": "unsafe.zip",
                            "content_base64": base64.b64encode(
                                archive_bytes.getvalue()
                            ).decode(),
                        }
                    ],
                )
            self.assertEqual(workspace.list("factory-demo"), [])
