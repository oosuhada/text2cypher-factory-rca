"""Safe project-scoped persistence for uploaded datasets and profiles."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

from .profiler import profile_tabular


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_FILES = 10
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._ -]{1,160}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatasetWorkspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _project_root(self, project_id: str) -> Path:
        path = (self.root / project_id).resolve()
        if self.root not in path.parents:
            raise ValueError("프로젝트 업로드 경로가 허용 범위를 벗어났습니다.")
        return path

    def profile_upload(
        self, project_id: str, files: list[dict[str, str]]
    ) -> dict[str, Any]:
        if not files or len(files) > MAX_FILES:
            raise ValueError(f"파일은 1~{MAX_FILES}개 업로드해야 합니다.")
        upload_id = str(uuid4())
        upload_root = self._project_root(project_id) / upload_id
        source_root = upload_root / "source"
        source_root.mkdir(parents=True, exist_ok=False)
        try:
            profiles = []
            total_bytes = 0
            seen_names: set[str] = set()
            for item in files:
                filename = Path(item["filename"]).name
                if (
                    filename != item["filename"]
                    or not SAFE_FILENAME.fullmatch(filename)
                ):
                    raise ValueError(
                        f"안전하지 않은 파일명입니다: {item['filename']}"
                    )
                if filename in seen_names:
                    raise ValueError(f"중복 파일명입니다: {filename}")
                seen_names.add(filename)
                try:
                    payload = base64.b64decode(
                        item["content_base64"], validate=True
                    )
                except Exception as error:
                    raise ValueError(
                        f"{filename}의 base64 데이터가 유효하지 않습니다."
                    ) from error
                if not payload or len(payload) > MAX_FILE_BYTES:
                    raise ValueError(
                        f"{filename}은 비었거나 10MB 제한을 초과했습니다."
                    )
                total_bytes += len(payload)
                target = source_root / filename
                target.write_bytes(payload)
                profile = profile_tabular(filename, payload)
                profile["sha256"] = hashlib.sha256(payload).hexdigest()
                profile["bytes"] = len(payload)
                profiles.append(profile)
            record = {
                "upload_id": upload_id,
                "project_id": project_id,
                "created_at": _now(),
                "status": "profiled",
                "total_bytes": total_bytes,
                "files": profiles,
            }
            (upload_root / "profile.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return record
        except Exception:
            shutil.rmtree(upload_root, ignore_errors=True)
            raise

    def get(self, project_id: str, upload_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f-]{36}", upload_id):
            raise ValueError("유효하지 않은 upload_id입니다.")
        path = self._project_root(project_id) / upload_id / "profile.json"
        if not path.exists():
            raise KeyError(f"업로드를 찾을 수 없습니다: {upload_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, project_id: str) -> list[dict[str, Any]]:
        root = self._project_root(project_id)
        if not root.exists():
            return []
        records = []
        for path in root.glob("*/profile.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(records, key=lambda row: row["created_at"], reverse=True)
