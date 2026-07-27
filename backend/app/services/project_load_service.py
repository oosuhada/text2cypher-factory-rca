"""Controlled graph loading with local reader-mode restoration."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Iterator

from neo4j import GraphDatabase

from backend.app.etl.cli import password_from_keychain
from backend.app.etl.generic_loader import GenericGraphLoader


ModeSwitcher = Callable[[str], None]


class ProjectGraphLoadService:
    def __init__(
        self,
        project_root: Path,
        loader: GenericGraphLoader,
        *,
        mode_switcher: ModeSwitcher | None = None,
        mode_control: str | None = None,
    ):
        self.project_root = project_root.resolve()
        self.loader = loader
        self.mode_switcher = mode_switcher or self._switch_homebrew_mode
        self.mode_control = (
            mode_control
            or os.getenv("P3_NEO4J_MODE_CONTROL")
            or self._default_mode_control()
        ).strip().lower()
        if self.mode_control not in {"homebrew", "none"}:
            raise ValueError(
                "P3_NEO4J_MODE_CONTROL은 homebrew 또는 none이어야 합니다."
            )
        self.lock_path = (
            self.project_root
            / "data"
            / "processed"
            / "project_graph_load.lock"
        )

    def _default_mode_control(self) -> str:
        uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        script = self.project_root / "infra" / "set_homebrew_mode.sh"
        return (
            "homebrew"
            if script.exists()
            and ("localhost" in uri or "127.0.0.1" in uri)
            else "none"
        )

    def _neo4j_settings(self) -> tuple[str, str, str, str]:
        uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        if self.mode_control == "homebrew" and uri.startswith("neo4j://"):
            # Homebrew runs one local server. During a restart the routing
            # table can lag behind Bolt readiness, so the controlled loader
            # must use a direct connection rather than cluster discovery.
            uri = f"bolt://{uri.removeprefix('neo4j://')}"
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
        uri, _database, username, password = self._neo4j_settings()
        last_error: Exception | None = None
        timeout_seconds = float(
            os.getenv("P3_NEO4J_RESTART_TIMEOUT_SECONDS", "90")
        )
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
            )
            try:
                driver.verify_connectivity()
                return driver
            except Exception as error:
                last_error = error
                driver.close()
                time.sleep(0.5)
        raise RuntimeError(
            "Neo4j 모드 전환 후 "
            f"{timeout_seconds:.0f}초 안에 연결하지 못했습니다: {last_error}"
        )

    def _switch_homebrew_mode(self, mode: str) -> None:
        subprocess.run(
            [
                str(
                    self.project_root
                    / "infra"
                    / "set_homebrew_mode.sh"
                ),
                mode,
            ],
            cwd=self.project_root,
            check=True,
            capture_output=True,
            text=True,
        )

    @contextmanager
    def _exclusive_load(
        self, project_id: str, upload_id: str
    ) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(
                descriptor,
                json.dumps(
                    {
                        "project_id": project_id,
                        "upload_id": upload_id,
                        "pid": os.getpid(),
                    }
                ).encode("utf-8"),
            )
            yield
        except FileExistsError as error:
            raise RuntimeError(
                "다른 프로젝트 그래프 적재가 진행 중입니다."
            ) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
                self.lock_path.unlink(missing_ok=True)

    def load(
        self, project_id: str, upload_id: str
    ) -> dict[str, Any]:
        with self._exclusive_load(project_id, upload_id):
            transition = self.mode_control == "homebrew"
            load_error: Exception | None = None
            result: dict[str, Any] | None = None
            try:
                if transition:
                    self.mode_switcher("loader")
                driver = self._wait_for_driver()
                try:
                    result = self.loader.load(
                        driver, project_id, upload_id
                    )
                finally:
                    driver.close()
                integrity = result["integrity"]
                if integrity["scoped_node_count"] < 1:
                    raise RuntimeError(
                        "적재 후 프로젝트 노드가 0개이므로 완료 처리할 수 없습니다."
                    )
            except Exception as error:
                load_error = error
            finally:
                restore_error: Exception | None = None
                if transition:
                    try:
                        self.mode_switcher("reader")
                        reader_driver = self._wait_for_driver()
                        reader_driver.close()
                    except Exception as error:
                        restore_error = error
                if restore_error is not None:
                    load_error = RuntimeError(
                        f"reader 모드 복구 실패: {restore_error}"
                    )

            if load_error is not None:
                raise load_error
            assert result is not None
            return {
                **result,
                "mode_control": self.mode_control,
                "reader_mode_restored": transition,
            }
