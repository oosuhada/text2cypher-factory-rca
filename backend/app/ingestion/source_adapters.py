"""Normalize CSV, JSON, XLSX and ZIP uploads into tabular files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
from pathlib import Path, PurePosixPath
import re
from typing import Any, Protocol
import xml.etree.ElementTree as ET
import zipfile


SUPPORTED_UPLOAD_SUFFIXES = {".csv", ".json", ".xlsx", ".zip"}
MAX_ARCHIVE_ENTRIES = 50
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
SAFE_MEMBER = re.compile(r"^[\w .()/\[\]-]{1,240}$", re.UNICODE)


@dataclass(frozen=True)
class NormalizedSource:
    filename: str
    payload: bytes
    lineage: dict[str, Any]


class SourceAdapter(Protocol):
    suffixes: frozenset[str]

    def normalize(
        self,
        filename: str,
        payload: bytes,
        registry: "SourceAdapterRegistry",
    ) -> list[NormalizedSource]: ...


class PassthroughTabularAdapter:
    suffixes = frozenset({".csv", ".json"})

    def normalize(
        self,
        filename: str,
        payload: bytes,
        registry: "SourceAdapterRegistry",
    ) -> list[NormalizedSource]:
        del registry
        return [
            NormalizedSource(
                filename=filename,
                payload=payload,
                lineage={
                    "source_format": Path(filename).suffix.lower().lstrip("."),
                    "original_filename": filename,
                    "normalized_filename": filename,
                },
            )
        ]


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    value = 0
    for character in letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _cell_text(
    cell: ET.Element, shared_strings: list[str], namespace: str
) -> Any:
    cell_type = cell.attrib.get("t")
    value = cell.find(f"{namespace}v")
    if cell_type == "inlineStr":
        return "".join(
            node.text or ""
            for node in cell.findall(f".//{namespace}t")
        )
    if value is None:
        return ""
    raw = value.text or ""
    if cell_type == "s":
        return shared_strings[int(raw)]
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e"}:
        return raw
    try:
        numeric = float(raw)
        return int(numeric) if numeric.is_integer() else numeric
    except ValueError:
        return raw


def _safe_sheet_slug(name: str, index: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug[:80] or f"sheet_{index}"


def _rows_to_csv(rows: list[list[Any]]) -> bytes:
    if not rows:
        raise ValueError("XLSX sheet에 행이 없습니다.")
    width = max(len(row) for row in rows)
    header = []
    seen: dict[str, int] = {}
    for index in range(width):
        raw = rows[0][index] if index < len(rows[0]) else ""
        name = str(raw).strip() or f"column_{index + 1}"
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}_{seen[name]}"
        header.append(name)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(header)
    for row in rows[1:]:
        writer.writerow(
            [row[index] if index < len(row) else "" for index in range(width)]
        )
    return output.getvalue().encode("utf-8")


class XlsxSourceAdapter:
    suffixes = frozenset({".xlsx"})

    def normalize(
        self,
        filename: str,
        payload: bytes,
        registry: "SourceAdapterRegistry",
    ) -> list[NormalizedSource]:
        del registry
        try:
            workbook = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as error:
            raise ValueError(f"유효하지 않은 XLSX 파일입니다: {filename}") from error
        with workbook:
            names = set(workbook.namelist())
            required = {
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
            }
            if not required <= names:
                raise ValueError(f"XLSX workbook 구조가 없습니다: {filename}")
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                shared_strings = [
                    "".join(node.text or "" for node in item.findall(f".//{namespace}t"))
                    for item in root.findall(f"{namespace}si")
                ]
            relationship_root = ET.fromstring(
                workbook.read("xl/_rels/workbook.xml.rels")
            )
            relationship_namespace = (
                "{http://schemas.openxmlformats.org/package/2006/relationships}"
            )
            targets = {
                row.attrib["Id"]: row.attrib["Target"]
                for row in relationship_root.findall(
                    f"{relationship_namespace}Relationship"
                )
            }
            workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
            sheet_namespace = (
                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            )
            office_rel_namespace = (
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
            )
            normalized: list[NormalizedSource] = []
            stem = Path(filename).stem
            for index, sheet in enumerate(
                workbook_root.findall(f".//{sheet_namespace}sheet"),
                start=1,
            ):
                sheet_name = sheet.attrib.get("name", f"sheet_{index}")
                relationship_id = sheet.attrib[
                    f"{office_rel_namespace}id"
                ]
                target = targets[relationship_id].lstrip("/")
                if not target.startswith("xl/"):
                    target = f"xl/{target}"
                sheet_root = ET.fromstring(workbook.read(target))
                rows: list[list[Any]] = []
                for row in sheet_root.findall(
                    f".//{sheet_namespace}sheetData/{sheet_namespace}row"
                ):
                    values: list[Any] = []
                    for cell in row.findall(f"{sheet_namespace}c"):
                        column = _column_index(cell.attrib.get("r", "A1"))
                        while len(values) <= column:
                            values.append("")
                        values[column] = _cell_text(
                            cell, shared_strings, sheet_namespace
                        )
                    rows.append(values)
                if not rows:
                    continue
                normalized_filename = (
                    f"{stem}__{_safe_sheet_slug(sheet_name, index)}.csv"
                )
                normalized.append(
                    NormalizedSource(
                        filename=normalized_filename,
                        payload=_rows_to_csv(rows),
                        lineage={
                            "source_format": "xlsx",
                            "original_filename": filename,
                            "sheet_name": sheet_name,
                            "normalized_filename": normalized_filename,
                        },
                    )
                )
            if not normalized:
                raise ValueError(f"XLSX에 처리 가능한 sheet가 없습니다: {filename}")
            return normalized


class ZipSourceAdapter:
    suffixes = frozenset({".zip"})

    def normalize(
        self,
        filename: str,
        payload: bytes,
        registry: "SourceAdapterRegistry",
    ) -> list[NormalizedSource]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload))
        except zipfile.BadZipFile as error:
            raise ValueError(f"유효하지 않은 ZIP 파일입니다: {filename}") from error
        with archive:
            files = [entry for entry in archive.infolist() if not entry.is_dir()]
            if not files or len(files) > MAX_ARCHIVE_ENTRIES:
                raise ValueError(
                    f"ZIP 파일은 1~{MAX_ARCHIVE_ENTRIES}개 파일이어야 합니다."
                )
            expanded_bytes = sum(entry.file_size for entry in files)
            if expanded_bytes > MAX_EXPANDED_BYTES:
                raise ValueError("ZIP 압축 해제 크기 제한을 초과했습니다.")
            normalized: list[NormalizedSource] = []
            seen_names: set[str] = set()
            for entry in files:
                member = PurePosixPath(entry.filename)
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or not SAFE_MEMBER.fullmatch(entry.filename)
                ):
                    raise ValueError(
                        f"ZIP 내부 경로가 안전하지 않습니다: {entry.filename}"
                    )
                if (
                    entry.compress_size > 0
                    and entry.file_size / entry.compress_size
                    > MAX_COMPRESSION_RATIO
                ):
                    raise ValueError(
                        f"ZIP 압축률 제한을 초과했습니다: {entry.filename}"
                    )
                member_name = member.name
                suffix = Path(member_name).suffix.lower()
                if suffix not in {".csv", ".json", ".xlsx"}:
                    continue
                children = registry.normalize(
                    member_name,
                    archive.read(entry),
                    allow_archive=False,
                )
                for child in children:
                    normalized_key = child.filename.casefold()
                    if normalized_key in seen_names:
                        raise ValueError(
                            "ZIP 정규화 후 중복 파일명이 발생했습니다: "
                            f"{child.filename}"
                        )
                    seen_names.add(normalized_key)
                    normalized.append(
                        NormalizedSource(
                            filename=child.filename,
                            payload=child.payload,
                            lineage={
                                **child.lineage,
                                "archive_filename": filename,
                                "archive_member": entry.filename,
                            },
                        )
                    )
            if not normalized:
                raise ValueError(
                    "ZIP에 지원되는 CSV, JSON 또는 XLSX 파일이 없습니다."
                )
            return normalized


class SourceAdapterRegistry:
    def __init__(self, adapters: list[SourceAdapter] | None = None):
        self._adapters: dict[str, SourceAdapter] = {}
        for adapter in adapters or []:
            for suffix in adapter.suffixes:
                if suffix in self._adapters:
                    raise ValueError(
                        f"중복 source adapter suffix입니다: {suffix}"
                    )
                self._adapters[suffix] = adapter

    def normalize(
        self,
        filename: str,
        payload: bytes,
        *,
        allow_archive: bool = True,
    ) -> list[NormalizedSource]:
        suffix = Path(filename).suffix.lower()
        adapter = self._adapters.get(suffix)
        if adapter is None or (suffix == ".zip" and not allow_archive):
            raise ValueError(
                "CSV와 JSON을 포함해 XLSX와 ZIP 파일만 지원합니다."
            )
        return adapter.normalize(filename, payload, self)


def default_source_adapter_registry() -> SourceAdapterRegistry:
    return SourceAdapterRegistry(
        [
            PassthroughTabularAdapter(),
            XlsxSourceAdapter(),
            ZipSourceAdapter(),
        ]
    )
