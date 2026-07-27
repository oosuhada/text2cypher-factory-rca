"""Registry that resolves ETL behavior by project."""

from __future__ import annotations

from .base import EtlAdapter


class EtlAdapterRegistry:
    def __init__(self, adapters: list[EtlAdapter] | None = None):
        self._adapters: dict[str, EtlAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: EtlAdapter) -> None:
        if adapter.project_id in self._adapters:
            raise ValueError(
                f"ETL adapter가 이미 등록되어 있습니다: {adapter.project_id}"
            )
        self._adapters[adapter.project_id] = adapter

    def require(self, project_id: str) -> EtlAdapter:
        try:
            return self._adapters[project_id]
        except KeyError as error:
            raise KeyError(
                f"ETL adapter가 없는 프로젝트입니다: {project_id}"
            ) from error

    def projects(self) -> list[str]:
        return sorted(self._adapters)


def default_adapter_registry() -> EtlAdapterRegistry:
    from .cip_dmd import CipDmdAdapter

    return EtlAdapterRegistry([CipDmdAdapter()])

