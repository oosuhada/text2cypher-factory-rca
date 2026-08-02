"""Safe, approval-gated CiP-DMD upload and Neo4j reload workflow."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import time
from typing import Any, Callable, Iterator
from uuid import uuid4
import zipfile

from neo4j import GraphDatabase

from backend.app.etl.cli import (
    password_from_keychain,
    write_quarantine,
    write_report,
)
from backend.app.etl.extract import (
    QUALITY_CSV_SPECS,
    SOURCE_SPECS,
    audit_quality_csvs,
    extract_records,
)
from backend.app.etl.load import graph_counts, load_payload
from backend.app.etl.transform import transform_records
from backend.app.etl.validate import EXPECTED_COUNTS, validate_payload


MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 100
APPROVAL_TTL_SECONDS = 30 * 60
REQUIRED_SOURCE_PATHS = tuple(
    dict.fromkeys(
        [
            *(spec[0] for spec in SOURCE_SPECS),
            *QUALITY_CSV_SPECS.keys(),
        ]
    )
)

ModeSwitcher = Callable[[str], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _safe_member_name(name: str) -> str:
    if "\\" in name:
        raise ValueError("ZIP 멤버 경로에는 역슬래시를 사용할 수 없습니다.")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"안전하지 않은 ZIP 경로입니다: {name}")
    return path.as_posix().lstrip("./")


def _resolve_required_members(
    archive: zipfile.ZipFile,
) -> dict[str, zipfile.ZipInfo]:
    infos = [info for info in archive.infolist() if not info.is_dir()]
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(
            f"ZIP 파일 수가 제한({MAX_ARCHIVE_MEMBERS})을 초과했습니다."
        )
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("압축 해제 크기가 100MB 제한을 초과했습니다.")
    safe_names = {info: _safe_member_name(info.filename) for info in infos}
    resolved: dict[str, zipfile.ZipInfo] = {}
    for required in REQUIRED_SOURCE_PATHS:
        candidates = [
            info
            for info, safe_name in safe_names.items()
            if safe_name == required or safe_name.endswith(f"/{required}")
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"필수 파일 매핑 실패: {required} "
                f"(발견 {len(candidates)}개)"
            )
        resolved[required] = candidates[0]
    return resolved


class DataIntakeService:
    """Stage, validate and explicitly reload the fixed CiP-DMD bundle."""

    def __init__(
        self,
        project_root: Path,
        *,
        processed_root: Path | None = None,
        intake_root: Path | None = None,
        mode_switcher: ModeSwitcher | None = None,
    ):
        self.project_root = project_root.resolve()
        self.processed_root = (
            processed_root or self.project_root / "data" / "processed"
        ).resolve()
        self.intake_root = (
            intake_root or self.processed_root / "intake_runs"
        ).resolve()
        self.mode_switcher = mode_switcher or self._switch_homebrew_mode
        self.schema_path = self.project_root / "infra" / "schema.cypher"

    def _run_root(self, run_id: str) -> Path:
        if not run_id or any(character not in "0123456789abcdef-" for character in run_id):
            raise ValueError("유효하지 않은 intake run ID입니다.")
        run_root = (self.intake_root / run_id).resolve()
        if self.intake_root not in run_root.parents:
            raise ValueError("intake run 경로가 허용 범위를 벗어났습니다.")
        return run_root

    def _record_path(self, run_id: str) -> Path:
        return self._run_root(run_id) / "run.json"

    def _read_record(self, run_id: str) -> dict[str, Any]:
        path = self._record_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"intake run을 찾을 수 없습니다: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_record(self, record: dict[str, Any]) -> None:
        _atomic_write_json(self._record_path(record["run_id"]), record)

    def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        if not self.intake_root.exists():
            return []
        records = []
        for path in self.intake_root.glob("*/run.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(
            records,
            key=lambda item: item.get("updated_at", ""),
            reverse=True,
        )[:limit]

    def recent_audit_events(self, limit: int = 20) -> list[dict[str, Any]]:
        audit_path = self.processed_root / "intake_audit.jsonl"
        if limit < 1 or not audit_path.exists():
            return []
        events = []
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events[-limit:][::-1]

    def _append_audit(
        self,
        *,
        run_id: str,
        event: str,
        status: str,
        detail: str = "",
    ) -> None:
        audit_path = self.processed_root / "intake_audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": _utc_now().isoformat(),
            "run_id": run_id,
            "event": event,
            "status": status,
            "detail": detail,
        }
        with audit_path.open("a", encoding="utf-8") as target:
            target.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def build_reference_archive(self) -> bytes:
        """Build a deterministic demo bundle from the checked-in public data."""

        canonical_root = self.project_root / "data" / "raw" / "cip_dmd"
        target = io.BytesIO()
        with zipfile.ZipFile(
            target,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for relative_path in REQUIRED_SOURCE_PATHS:
                source = canonical_root / relative_path
                if not source.exists():
                    raise FileNotFoundError(
                        f"검증 기준 파일이 없습니다: {relative_path}"
                    )
                info = zipfile.ZipInfo(
                    filename=f"CiP-DMD/{relative_path}",
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, source.read_bytes())
        return target.getvalue()

    def stage_archive(
        self,
        filename: str,
        archive_payload: bytes,
    ) -> dict[str, Any]:
        if Path(filename).suffix.lower() != ".zip":
            raise ValueError("CiP-DMD 번들은 ZIP 형식이어야 합니다.")
        if not archive_payload:
            raise ValueError("업로드된 ZIP 파일이 비어 있습니다.")
        if len(archive_payload) > MAX_ARCHIVE_BYTES:
            raise ValueError("ZIP 파일이 25MB 제한을 초과했습니다.")

        run_id = str(uuid4())
        run_root = self._run_root(run_id)
        raw_root = run_root / "raw"
        run_root.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(io.BytesIO(archive_payload)) as archive:
                if archive.testzip() is not None:
                    raise ValueError("ZIP CRC 검증에 실패했습니다.")
                resolved = _resolve_required_members(archive)
                source_files = []
                canonical_root = (
                    self.project_root / "data" / "raw" / "cip_dmd"
                )
                for relative_path, info in resolved.items():
                    payload = archive.read(info)
                    target = raw_root / relative_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                    canonical_path = canonical_root / relative_path
                    uploaded_hash = _sha256_bytes(payload)
                    canonical_hash = (
                        _sha256_file(canonical_path)
                        if canonical_path.exists()
                        else None
                    )
                    source_files.append(
                        {
                            "path": relative_path,
                            "size_bytes": len(payload),
                            "sha256": uploaded_hash,
                            "canonical_sha256": canonical_hash,
                            "canonical_match": (
                                canonical_hash is not None
                                and uploaded_hash == canonical_hash
                            ),
                        }
                    )
            record = {
                "run_id": run_id,
                "dataset": "CiP-DMD",
                "original_filename": Path(filename).name,
                "archive_sha256": _sha256_bytes(archive_payload),
                "created_at": _utc_now().isoformat(),
                "updated_at": _utc_now().isoformat(),
                "status": "staged",
                "source_files": source_files,
                "canonical_bundle_match": all(
                    item["canonical_match"] for item in source_files
                ),
            }
            self._write_record(record)
            self._append_audit(
                run_id=run_id,
                event="stage",
                status="PASS",
                detail=f"{len(source_files)} required files",
            )
            return record
        except Exception as error:
            shutil.rmtree(run_root, ignore_errors=True)
            self._append_audit(
                run_id=run_id,
                event="stage",
                status="FAIL",
                detail=str(error),
            )
            raise

    def _assert_staged_files_unchanged(
        self,
        record: dict[str, Any],
    ) -> None:
        raw_root = self._run_root(record["run_id"]) / "raw"
        for source in record["source_files"]:
            path = raw_root / source["path"]
            if not path.exists() or _sha256_file(path) != source["sha256"]:
                raise RuntimeError(
                    f"staging 이후 파일이 변경되었습니다: {source['path']}"
                )

    def dry_run(self, run_id: str) -> dict[str, Any]:
        record = self._read_record(run_id)
        if record["status"] not in {"staged", "dry_run_pass"}:
            raise RuntimeError(
                f"현재 상태에서는 dry-run할 수 없습니다: {record['status']}"
            )
        self._assert_staged_files_unchanged(record)
        if not record["canonical_bundle_match"]:
            raise RuntimeError(
                "업로드 번들이 검증 기준 CiP-DMD 원본과 일치하지 않습니다. "
                "이 단계에서는 변경된 데이터의 자동 적재를 허용하지 않습니다."
            )

        raw_root = self._run_root(run_id) / "raw"
        try:
            extracted = extract_records(raw_root)
            quality_csv_audit = audit_quality_csvs(raw_root)
            payload = transform_records(extracted)
            validation = validate_payload(payload)
            approval_token = secrets.token_urlsafe(24)
            expires_at = _utc_now().timestamp() + APPROVAL_TTL_SECONDS
            record.update(
                {
                    "updated_at": _utc_now().isoformat(),
                    "status": "dry_run_pass",
                    "validation": validation,
                    "payload": payload.summary(),
                    "quality_csv_audit": quality_csv_audit,
                    "approval_token_sha256": _sha256_bytes(
                        approval_token.encode("utf-8")
                    ),
                    "approval_expires_at": datetime.fromtimestamp(
                        expires_at, timezone.utc
                    ).isoformat(),
                }
            )
            self._write_record(record)
            self._append_audit(
                run_id=run_id,
                event="dry_run",
                status="PASS",
                detail=f"{len(validation['counts'])} graph counters",
            )
            return {**record, "approval_token": approval_token}
        except Exception as error:
            record.update(
                {
                    "updated_at": _utc_now().isoformat(),
                    "status": "dry_run_failed",
                    "error": str(error),
                }
            )
            self._write_record(record)
            self._append_audit(
                run_id=run_id,
                event="dry_run",
                status="FAIL",
                detail=str(error),
            )
            raise

    def _neo4j_settings(self) -> tuple[str, str, str, str]:
        uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        database = os.getenv("NEO4J_DATABASE", "neo4j")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = (
            os.getenv("NEO4J_PASSWORD")
            or password_from_keychain(username)
        )
        if not password:
            raise RuntimeError("Neo4j 인증정보를 찾을 수 없습니다.")
        return uri, database, username, password

    def _wait_for_driver(self):
        uri, database, username, password = self._neo4j_settings()
        last_error: Exception | None = None
        for _ in range(30):
            driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
            )
            try:
                driver.verify_connectivity()
                return driver, database
            except Exception as error:
                last_error = error
                driver.close()
                time.sleep(0.5)
        raise RuntimeError(
            f"Neo4j 재시작 후 연결하지 못했습니다: {last_error}"
        )

    def _switch_homebrew_mode(self, mode: str) -> None:
        subprocess.run(
            [str(self.project_root / "infra" / "set_homebrew_mode.sh"), mode],
            cwd=self.project_root,
            check=True,
            capture_output=True,
            text=True,
        )

    @contextmanager
    def _exclusive_load(self, run_id: str) -> Iterator[None]:
        lock_path = self.processed_root / "intake_load.lock"
        descriptor: int | None = None
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(
                descriptor,
                json.dumps(
                    {
                        "run_id": run_id,
                        "pid": os.getpid(),
                        "created_at": _utc_now().isoformat(),
                    }
                ).encode("utf-8"),
            )
            yield
        except FileExistsError as error:
            raise RuntimeError(
                "다른 데이터 적재 작업이 진행 중입니다."
            ) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock_path.unlink(missing_ok=True)

    def load(
        self,
        run_id: str,
        *,
        approval_token: str,
        confirmation: str,
        batch_size: int = 500,
    ) -> dict[str, Any]:
        record = self._read_record(run_id)
        if record["status"] != "dry_run_pass":
            raise RuntimeError("dry-run을 통과한 번들만 적재할 수 있습니다.")
        if confirmation != f"LOAD {run_id}":
            raise RuntimeError("적재 확인 문구가 일치하지 않습니다.")
        if batch_size < 1:
            raise ValueError("batch_size는 1 이상이어야 합니다.")
        expires_at = datetime.fromisoformat(
            record["approval_expires_at"]
        ).timestamp()
        if _utc_now().timestamp() > expires_at:
            raise RuntimeError("적재 승인 토큰이 만료되었습니다.")
        actual_token_hash = _sha256_bytes(
            approval_token.encode("utf-8")
        )
        if not hmac.compare_digest(
            actual_token_hash,
            record.get("approval_token_sha256", ""),
        ):
            raise RuntimeError("적재 승인 토큰이 일치하지 않습니다.")
        self._assert_staged_files_unchanged(record)
        if not record["canonical_bundle_match"]:
            raise RuntimeError("검증 기준 원본과 다른 번들은 적재할 수 없습니다.")

        raw_root = self._run_root(run_id) / "raw"
        extracted = extract_records(raw_root)
        quality_csv_audit = audit_quality_csvs(raw_root)
        payload = transform_records(extracted)
        validation = validate_payload(payload)

        with self._exclusive_load(run_id):
            record["approval_token_sha256"] = None
            record["status"] = "loading"
            record["updated_at"] = _utc_now().isoformat()
            self._write_record(record)
            mode_transition_started = False
            load_error: Exception | None = None
            result: dict[str, Any] | None = None
            try:
                preflight_driver, database = self._wait_for_driver()
                try:
                    before = graph_counts(preflight_driver, database)
                finally:
                    preflight_driver.close()
                if before not in ({name: 0 for name in EXPECTED_COUNTS}, EXPECTED_COUNTS):
                    raise RuntimeError(
                        "현재 Neo4j가 빈 CiP-DMD 그래프 또는 검증된 기준 "
                        "상태가 아니므로 UI 적재를 중단합니다."
                    )

                mode_transition_started = True
                self.mode_switcher("loader")
                driver, database = self._wait_for_driver()
                try:
                    counters = load_payload(
                        driver,
                        database,
                        payload,
                        self.schema_path,
                        batch_size=batch_size,
                    )
                    after = graph_counts(driver, database)
                finally:
                    driver.close()
                if after != validation["counts"]:
                    raise RuntimeError(
                        "적재 후 그래프 건수가 검증된 projection과 다릅니다."
                    )
                result = {
                    "before": before,
                    "after": after,
                    "load_counters": counters,
                    "quality_csv_audit": quality_csv_audit,
                }
            except Exception as error:
                load_error = error
            finally:
                reader_error: Exception | None = None
                if mode_transition_started:
                    try:
                        self.mode_switcher("reader")
                        reader_driver, _ = self._wait_for_driver()
                        reader_driver.close()
                    except Exception as error:
                        reader_error = error
                if reader_error is not None:
                    load_error = RuntimeError(
                        f"reader 모드 복구 실패: {reader_error}"
                    )

            if load_error is not None:
                record.update(
                    {
                        "status": "load_failed",
                        "updated_at": _utc_now().isoformat(),
                        "error": str(load_error),
                    }
                )
                self._write_record(record)
                self._append_audit(
                    run_id=run_id,
                    event="load",
                    status="FAIL",
                    detail=str(load_error),
                )
                raise load_error

            record.update(
                {
                    "status": "load_pass",
                    "updated_at": _utc_now().isoformat(),
                    "finished_at": _utc_now().isoformat(),
                    "database": result,
                    "reader_mode_restored": True,
                }
            )
            self._write_record(record)
            write_quarantine(self.processed_root, payload.quarantined)
            write_report(
                self.processed_root,
                {
                    "dataset": "CiP-DMD",
                    "mode": "approved-ui-load",
                    "status": "PASS",
                    "started_at": record["created_at"],
                    "finished_at": record["finished_at"],
                    "validation": validation,
                    "payload": payload.summary(),
                    "database": result,
                    "idempotency": {
                        "status": (
                            "PASS"
                            if result["before"] == result["after"]
                            else "NOT_APPLICABLE"
                        ),
                        "counts_unchanged": (
                            result["before"] == result["after"]
                        ),
                    },
                    "intake_run_id": run_id,
                },
            )
            self._append_audit(
                run_id=run_id,
                event="load",
                status="PASS",
                detail="reader mode restored",
            )
            return record
