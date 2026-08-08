"""Project-scoped LlamaIndex document ingestion, persistence and retrieval."""

from __future__ import annotations

from base64 import b64decode
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path
import re
import shutil
from threading import RLock
from typing import Any, Iterable
from uuid import uuid4

from llama_index.core import (
    Document,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from pypdf import PdfReader

from .embedding import DeterministicHashEmbedding


RAG_INDEX_VERSION = "llamaindex-rag-v1"
LLAMA_INDEX_VERSION = package_version("llama-index-core")
_SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}
_SAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣._-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _safe_filename(value: str) -> str:
    normalized = _SAFE_NAME.sub("-", Path(value).name).strip("-.")
    return normalized[:120] or "document.txt"


class DocumentRagService:
    """Persist versioned project documents and search them with LlamaIndex."""

    def __init__(
        self,
        project_root: Path,
        project_id: str,
        *,
        chunk_size: int = 320,
        chunk_overlap: int = 48,
        similarity_cutoff: float = 0.04,
    ):
        self.project_root = project_root.resolve()
        self.project_id = project_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.similarity_cutoff = similarity_cutoff
        processed = self.project_root / "data" / "processed"
        self.root = (
            processed / "rag"
            if project_id == "cip-dmd"
            else processed / "projects" / project_id / "rag"
        )
        self.sources_dir = self.root / "sources"
        self.index_dir = self.root / "index"
        self.manifest_path = self.root / "documents.json"
        self.embedding = DeterministicHashEmbedding()
        self._lock = RLock()
        self._index: VectorStoreIndex | None = None

    def _read_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"문서 manifest를 읽지 못했습니다: {self.manifest_path}"
            ) from error
        if not isinstance(payload, list):
            raise RuntimeError("문서 manifest 형식이 올바르지 않습니다.")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _write_manifest(self, documents: list[dict[str, Any]]) -> None:
        _atomic_json(self.manifest_path, documents)

    @staticmethod
    def _decode_content(
        *,
        content: str | None,
        content_base64: str | None,
    ) -> bytes:
        if bool(content) == bool(content_base64):
            raise ValueError("content 또는 content_base64 중 하나만 입력하세요.")
        if content is not None:
            return content.encode("utf-8")
        try:
            return b64decode(content_base64 or "", validate=True)
        except ValueError as error:
            raise ValueError("content_base64가 올바른 Base64가 아닙니다.") from error

    def ingest(
        self,
        *,
        document_id: str,
        title: str,
        version: str,
        document_type: str,
        source_filename: str,
        content: str | None = None,
        content_base64: str | None = None,
        effective_date: str | None = None,
        security_classification: str = "internal",
        allowed_roles: Iterable[str] = (),
        is_current: bool = True,
    ) -> dict[str, Any]:
        suffix = Path(source_filename).suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                "지원 문서 형식은 Markdown, TXT, text-layer PDF입니다."
            )
        raw = self._decode_content(
            content=content,
            content_base64=content_base64,
        )
        if not raw:
            raise ValueError("빈 문서는 등록할 수 없습니다.")
        source_sha256 = hashlib.sha256(raw).hexdigest()
        normalized_roles = sorted({role.strip() for role in allowed_roles if role.strip()})

        with self._lock:
            documents = self._read_manifest()
            for item in documents:
                if (
                    item.get("document_id") == document_id
                    and item.get("version") == version
                    and item.get("source_sha256") == source_sha256
                ):
                    return {**item, "duplicate": True}

            if is_current:
                for item in documents:
                    if item.get("document_id") == document_id:
                        item["is_current"] = False

            stored_name = (
                f"{_safe_filename(document_id)}__{_safe_filename(version)}__"
                f"{_safe_filename(source_filename)}"
            )
            self.sources_dir.mkdir(parents=True, exist_ok=True)
            source_path = self.sources_dir / stored_name
            source_path.write_bytes(raw)
            record = {
                "project_id": self.project_id,
                "document_id": document_id,
                "title": title,
                "version": version,
                "document_type": document_type,
                "effective_date": effective_date,
                "security_classification": security_classification,
                "allowed_roles": normalized_roles,
                "is_current": bool(is_current),
                "source_filename": source_filename,
                "stored_filename": stored_name,
                "source_sha256": source_sha256,
                "indexed_at": _now(),
                "index_version": RAG_INDEX_VERSION,
                "status": "indexed",
            }
            documents.append(record)
            try:
                index_summary = self._rebuild(documents)
                self._write_manifest(documents)
            except Exception:
                source_path.unlink(missing_ok=True)
                raise
            return {
                **record,
                "duplicate": False,
                "chunk_count": index_summary["document_chunks"].get(
                    f"{document_id}:{version}", 0
                ),
            }

    def _read_documents(
        self,
        manifest: list[dict[str, Any]],
    ) -> list[Document]:
        documents: list[Document] = []
        for item in manifest:
            if item.get("status") != "indexed":
                continue
            path = self.sources_dir / str(item["stored_filename"])
            if not path.exists():
                continue
            suffix = path.suffix.lower()
            common = {
                key: item.get(key)
                for key in (
                    "project_id",
                    "document_id",
                    "title",
                    "version",
                    "document_type",
                    "effective_date",
                    "security_classification",
                    "allowed_roles",
                    "is_current",
                    "source_filename",
                    "source_sha256",
                    "index_version",
                )
            }
            if suffix == ".pdf":
                reader = PdfReader(str(path))
                extracted = 0
                for page_number, page in enumerate(reader.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if not text:
                        continue
                    extracted += 1
                    documents.append(
                        Document(
                            text=text,
                            id_=f"{item['document_id']}:{item['version']}:p{page_number}",
                            metadata={
                                **common,
                                "page_number": page_number,
                                "section_title": item["title"],
                            },
                        )
                    )
                if extracted == 0:
                    raise ValueError(
                        f"텍스트 레이어가 없는 PDF입니다: {item['source_filename']}"
                    )
            else:
                text = path.read_text(encoding="utf-8").strip()
                if not text:
                    raise ValueError(f"빈 문서입니다: {item['source_filename']}")
                documents.append(
                    Document(
                        text=text,
                        id_=f"{item['document_id']}:{item['version']}:p1",
                        metadata={
                            **common,
                            "page_number": 1,
                            "section_title": item["title"],
                        },
                    )
                )
        return documents

    def _rebuild(self, manifest: list[dict[str, Any]]) -> dict[str, Any]:
        documents = self._read_documents(manifest)
        temporary = self.root / f".index-{uuid4().hex}"
        document_chunks: dict[str, int] = {}
        try:
            if not documents:
                shutil.rmtree(self.index_dir, ignore_errors=True)
                self._index = None
                return {"chunk_count": 0, "document_chunks": {}}
            pipeline = IngestionPipeline(
                transformations=[
                    SentenceSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                    ),
                    self.embedding,
                ]
            )
            nodes = list(pipeline.run(documents=documents, show_progress=False))
            for node in nodes:
                metadata = node.metadata
                key = f"{metadata.get('document_id')}:{metadata.get('version')}"
                document_chunks[key] = document_chunks.get(key, 0) + 1
            index = VectorStoreIndex(nodes, embed_model=self.embedding)
            index.set_index_id(RAG_INDEX_VERSION)
            temporary.mkdir(parents=True, exist_ok=True)
            index.storage_context.persist(persist_dir=str(temporary))
            shutil.rmtree(self.index_dir, ignore_errors=True)
            os.replace(temporary, self.index_dir)
            self._index = index
            return {
                "chunk_count": len(nodes),
                "document_chunks": document_chunks,
            }
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    def rebuild(self) -> dict[str, Any]:
        with self._lock:
            manifest = self._read_manifest()
            summary = self._rebuild(manifest)
            return {
                "project_id": self.project_id,
                "index_version": RAG_INDEX_VERSION,
                **summary,
            }

    def _load_index(self) -> VectorStoreIndex | None:
        if self._index is not None:
            return self._index
        if not self.index_dir.exists():
            return None
        storage = StorageContext.from_defaults(persist_dir=str(self.index_dir))
        self._index = load_index_from_storage(
            storage,
            index_id=RAG_INDEX_VERSION,
            embed_model=self.embedding,
        )
        return self._index

    @staticmethod
    def _authorized(metadata: dict[str, Any], roles: Iterable[str]) -> bool:
        allowed = {str(role) for role in metadata.get("allowed_roles") or []}
        if not allowed:
            return True
        return not allowed.isdisjoint(set(roles))

    def search(
        self,
        query: str,
        *,
        roles: Iterable[str] = (),
        top_k: int = 5,
        current_only: bool = True,
        document_types: Iterable[str] = (),
    ) -> dict[str, Any]:
        normalized = query.strip()
        if not normalized:
            raise ValueError("문서 검색 질문이 비어 있습니다.")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k는 1~20이어야 합니다.")
        requested_types = {item for item in document_types if item}
        with self._lock:
            index = self._load_index()
            if index is None:
                return self._search_result(normalized, [], top_k)
            retriever = index.as_retriever(similarity_top_k=min(100, top_k * 8))
            matches: list[dict[str, Any]] = []
            seen: set[tuple[str, str, int, str]] = set()
            for result in retriever.retrieve(normalized):
                metadata = dict(result.node.metadata)
                score = float(result.score or 0.0)
                if score < self.similarity_cutoff:
                    continue
                if metadata.get("project_id") != self.project_id:
                    continue
                if current_only and not metadata.get("is_current"):
                    continue
                if requested_types and metadata.get("document_type") not in requested_types:
                    continue
                if not self._authorized(metadata, roles):
                    continue
                text = result.node.get_content().strip()
                key = (
                    str(metadata.get("document_id")),
                    str(metadata.get("version")),
                    int(metadata.get("page_number") or 1),
                    text,
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    {
                        "project_id": self.project_id,
                        "document_id": metadata.get("document_id"),
                        "title": metadata.get("title"),
                        "version": metadata.get("version"),
                        "document_type": metadata.get("document_type"),
                        "effective_date": metadata.get("effective_date"),
                        "is_current": bool(metadata.get("is_current")),
                        "security_classification": metadata.get(
                            "security_classification"
                        ),
                        "source_filename": metadata.get("source_filename"),
                        "page_number": int(metadata.get("page_number") or 1),
                        "section_title": metadata.get("section_title"),
                        "text": text[:1200],
                        "score": round(score, 6),
                        "citation_id": (
                            f"{metadata.get('document_id')}@{metadata.get('version')}"
                            f":p{int(metadata.get('page_number') or 1)}"
                        ),
                    }
                )
                if len(matches) >= top_k:
                    break
            return self._search_result(normalized, matches, top_k)

    def _search_result(
        self,
        query: str,
        matches: list[dict[str, Any]],
        top_k: int,
    ) -> dict[str, Any]:
        answer = (
            "관련 문서 근거를 찾지 못했습니다. 문서가 등록되어 있는지 또는 "
            "질문에 설비·절차·기준 단서를 추가했는지 확인해 주세요."
            if not matches
            else "\n\n".join(
                f"[{item['citation_id']}] {item['text']}" for item in matches[:3]
            )
        )
        return {
            "project_id": self.project_id,
            "query": query,
            "status": "success" if matches else "empty",
            "framework": "LlamaIndex",
            "framework_version": LLAMA_INDEX_VERSION,
            "answer": answer,
            "index_version": RAG_INDEX_VERSION,
            "top_k": top_k,
            "matches": matches,
            "citations": [
                {
                    key: item[key]
                    for key in (
                        "citation_id",
                        "document_id",
                        "title",
                        "version",
                        "page_number",
                        "section_title",
                        "is_current",
                        "source_filename",
                    )
                }
                for item in matches
            ],
        }

    def list_documents(
        self,
        *,
        include_superseded: bool = True,
        roles: Iterable[str] = (),
        include_restricted: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            documents = self._read_manifest()
        if not include_restricted:
            documents = [
                item for item in documents if self._authorized(item, roles)
            ]
        if not include_superseded:
            documents = [item for item in documents if item.get("is_current")]
        return sorted(
            documents,
            key=lambda item: (
                str(item.get("document_id")),
                not bool(item.get("is_current")),
                str(item.get("version")),
            ),
        )

    def readiness(
        self,
        *,
        roles: Iterable[str] = (),
        include_restricted: bool = False,
    ) -> dict[str, Any]:
        documents = self.list_documents(
            roles=roles,
            include_restricted=include_restricted,
        )
        current = [item for item in documents if item.get("is_current")]
        return {
            "project_id": self.project_id,
            "ready": bool(current and self.index_dir.exists()),
            "document_count": len(documents),
            "current_document_count": len(current),
            "index_version": RAG_INDEX_VERSION,
            "index_path": str(self.index_dir),
            "supported_extensions": sorted(_SUPPORTED_SUFFIXES),
            "embedding_model": self.embedding.model_name,
            "framework": "LlamaIndex",
            "framework_version": LLAMA_INDEX_VERSION,
        }
