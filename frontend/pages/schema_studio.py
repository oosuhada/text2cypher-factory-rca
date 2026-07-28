"""Schema mapping, approval and isolated-load pipeline workspace."""

from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st

from backend.app.ingestion import DatasetWorkspace
from backend.app.mapping import MappingWorkspace
from backend.app.projects import ProjectRegistry
from backend.app.schema_registry import SchemaRegistry
from frontend.api_client import FactoryGraphApiClient
from frontend.navigation import render_page_header
from frontend.pages.data_sources import (
    get_pipeline_job_store,
    render_onboarding_stage,
    render_pipeline_jobs,
)
from frontend.runtime import PROJECT_ROOT

def render_schema_studio() -> None:
    render_page_header("Pipeline")
    st.caption(
        "프로파일 → 매핑 dry-run → 명시적 승인 → 격리 적재 → "
        "무결성 검증 순서로 진행합니다."
    )
    projects = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    project_rows = projects.list()
    project_ids = [row["project_id"] for row in project_rows]
    active_project = st.session_state.get("active_project_id", "cip-dmd")
    project_id = st.selectbox(
        "프로젝트",
        project_ids,
        index=project_ids.index(active_project)
        if active_project in project_ids
        else 0,
    )
    project = projects.require(project_id)
    render_onboarding_stage(project)
    render_pipeline_jobs(project_id)
    if project["source_type"] == "neo4j":
        st.info(
            "이 프로젝트는 기존 Neo4j 연결형입니다. Data Sources에서 "
            "연결 검증·승인을 완료하면 스키마가 자동 등록됩니다."
        )
        return
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    uploads = datasets.list(project_id)
    if not uploads:
        st.info("먼저 Data Sources에서 데이터셋을 업로드해 프로파일링하세요.")
        return
    upload = uploads[0]
    upload_id = st.selectbox(
        "프로파일", [row["upload_id"] for row in uploads]
    )
    upload = next(row for row in uploads if row["upload_id"] == upload_id)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "file": file["filename"],
                    "rows": file["row_count"],
                    "columns": file["column_count"],
                }
                for file in upload["files"]
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    source = upload["files"][0]
    identity = next(
        (
            column["name"]
            for column in source["columns"]
            if column["identity_candidate"]
        ),
        source["columns"][0]["name"],
    )
    template = {
        "title": f"{project_id} graph",
        "nodes": [
            {
                "label": "Record",
                "source_file": source["filename"],
                "identity": identity,
                "properties": {
                    column["name"]: column["name"]
                    for column in source["columns"]
                },
            }
        ],
        "relationships": [],
    }
    mapping_text = st.text_area(
        "Graph mapping (JSON)",
        value=json.dumps(template, ensure_ascii=False, indent=2),
        height=360,
        help=(
            "노드의 identity와 속성, 관계의 시작·끝 키를 정의합니다. "
            "승인 전 dry-run은 운영 Neo4j를 변경하지 않습니다."
        ),
    )
    schemas = SchemaRegistry(PROJECT_ROOT / "schemas")
    mappings = MappingWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_mappings",
        datasets,
        schemas,
    )
    preview_column, approve_column = st.columns(2)
    try:
        mapping = json.loads(mapping_text)
        if preview_column.button(
            "1 · ETL dry-run",
            width="stretch",
            key=f"mapping-preview-{project_id}-{upload_id}",
        ):
            store = get_pipeline_job_store()
            job = store.create(
                project_id,
                "mapping_dry_run",
                message="매핑 검증과 ETL dry-run 대기",
            )
            try:
                store.start(
                    job["job_id"],
                    "mapping_validation",
                    "컬럼·identity·관계 키를 검증합니다.",
                )
                api = FactoryGraphApiClient()
                try:
                    if api.live():
                        preview = api.preview_mapping(
                            project_id,
                            upload_id=upload_id,
                            schema_version="1.0",
                            mapping=mapping,
                        )
                    else:
                        preview = mappings.preview(
                            project_id,
                            upload_id,
                            mapping,
                            schema_version="1.0",
                        )
                finally:
                    api.close()
                dry_run = preview.get("dry_run", {})
                total_rows = sum(
                    int(value)
                    for value in preview.get(
                        "estimated_node_rows", {}
                    ).values()
                ) + sum(
                    int(value)
                    for value in preview.get(
                        "estimated_relationship_rows", {}
                    ).values()
                )
                store.update(
                    job["job_id"],
                    current_step="dry_run",
                    progress=80,
                    processed_rows=total_rows,
                    total_rows=total_rows,
                    message=(
                        "노드·관계 투영과 격리 레코드 검사를 완료했습니다."
                    ),
                )
                store.succeed(
                    job["job_id"],
                    step="dry_run_complete",
                    message=(
                        f"ETL dry-run {dry_run.get('status', 'PASS')} · "
                        "운영 그래프 변경 없음"
                    ),
                    result={
                        "upload_id": upload_id,
                        "dry_run": dry_run,
                    },
                    processed_rows=total_rows,
                    total_rows=total_rows,
                )
                st.session_state["mapping_preview"] = preview
                st.success(
                    "ETL dry-run을 마쳤습니다. 운영 Neo4j는 변경되지 않았습니다."
                )
            except Exception as error:
                store.fail(
                    job["job_id"], step="mapping_validation", error=str(error)
                )
                st.error(f"매핑 dry-run 실패: {error}")
        preview = st.session_state.get("mapping_preview")
        preview_matches = bool(
            preview
            and preview.get("project_id") == project_id
            and preview.get("upload_id") == upload_id
        )
        if approve_column.button(
            "2 · 검토한 매핑 승인",
            type="primary",
            width="stretch",
            disabled=not preview_matches,
            key=f"mapping-approve-{project_id}-{upload_id}",
        ):
            store = get_pipeline_job_store()
            job = store.create(
                project_id,
                "mapping_approval",
                message="매핑 승인 대기",
            )
            try:
                store.start(
                    job["job_id"],
                    "approval",
                    "검토한 매핑과 스키마 버전을 고정합니다.",
                )
                api = FactoryGraphApiClient()
                try:
                    if api.live():
                        approved = api.approve_mapping(
                            project_id,
                            upload_id=upload_id,
                            schema_version="1.0",
                            mapping=mapping,
                        )
                    else:
                        approved = mappings.approve(
                            project_id,
                            upload_id,
                            mapping,
                            schema_version="1.0",
                        )
                        projects.update(project_id, schema_version="1.0")
                        projects.record_artifact(
                            project_id,
                            "mapping",
                            version="1.0",
                            metadata={"upload_id": upload_id},
                        )
                        projects.record_artifact(
                            project_id,
                            "schema",
                            version="1.0",
                            metadata={"source_version": upload_id},
                        )
                finally:
                    api.close()
                store.succeed(
                    job["job_id"],
                    step="approved",
                    message="매핑·스키마 승인본을 저장했습니다.",
                    result={"upload_id": upload_id, "schema_version": "1.0"},
                )
                st.session_state["mapping_preview"] = approved
                st.success(
                    "매핑과 schema manifest를 승인했습니다. "
                    "아직 운영 그래프에는 적재하지 않았습니다."
                )
            except Exception as error:
                store.fail(job["job_id"], step="approval", error=str(error))
                st.error(f"매핑 승인 실패: {error}")
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        st.error(f"매핑을 검증할 수 없습니다: {error}")
    preview = st.session_state.get("mapping_preview")
    if (
        preview
        and preview.get("project_id") == project_id
        and preview.get("upload_id") == upload_id
    ):
        st.markdown("### Dry-run 결과")
        dry_run = preview.get("dry_run", {})
        dry_metrics = st.columns(4)
        dry_metrics[0].metric("판정", dry_run.get("status", "—"))
        dry_metrics[1].metric(
            "예상 노드",
            f"{sum(preview.get('estimated_node_rows', {}).values()):,}",
        )
        dry_metrics[2].metric(
            "예상 관계",
            f"{sum(preview.get('estimated_relationship_rows', {}).values()):,}",
        )
        dry_metrics[3].metric(
            "격리 후보",
            f"{int(dry_run.get('isolation_count', 0)):,}",
        )
        dry_tabs = st.tabs(["노드", "관계", "격리·Lineage", "Schema"])
        with dry_tabs[0]:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"label": label, **values}
                        for label, values in dry_run.get("nodes", {}).items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with dry_tabs[1]:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"type": relation_type, **values}
                        for relation_type, values in dry_run.get(
                            "relationships", {}
                        ).items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        with dry_tabs[2]:
            if dry_run.get("isolation_examples"):
                st.dataframe(
                    pd.DataFrame(dry_run["isolation_examples"]),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.success("격리해야 할 레코드가 없습니다.")
            st.json(dry_run.get("lineage", {}))
        with dry_tabs[3]:
            st.json(preview["manifest"])
        st.caption(
            f"예상 노드 입력: {preview['estimated_node_rows']} · "
            f"예상 관계 입력: {preview['estimated_relationship_rows']}"
        )
        approved_mapping = None
        try:
            candidate = mappings.get(project_id)
            if candidate.get("upload_id") == upload_id:
                approved_mapping = candidate
        except KeyError:
            pass
        if approved_mapping:
            st.markdown("### Neo4j 적재 승인")
            st.warning(
                "승인된 매핑을 현재 프로젝트 범위로 실제 적재합니다. "
                "다른 프로젝트의 노드·관계는 변경하지 않습니다."
            )
            confirmation = st.text_input(
                f"확인을 위해 `{project_id}` 입력",
                key=f"mapping-load-confirm-{project_id}",
            )
            load_enabled = os.getenv("P3_ENABLE_UI_LOAD") == "1"
            if not load_enabled:
                st.info("관리자가 P3_ENABLE_UI_LOAD=1로 실행해야 활성화됩니다.")
            if st.button(
                "승인된 그래프 적재",
                type="primary",
                disabled=(
                    not load_enabled or confirmation != project_id
                ),
                key=f"mapping-load-{project_id}",
            ):
                store = get_pipeline_job_store()
                total_rows = sum(
                    int(value)
                    for value in preview.get(
                        "estimated_node_rows", {}
                    ).values()
                ) + sum(
                    int(value)
                    for value in preview.get(
                        "estimated_relationship_rows", {}
                    ).values()
                )
                job = store.create(
                    project_id,
                    "graph_load",
                    message="승인된 그래프 적재 대기",
                    total_rows=total_rows,
                )
                api = FactoryGraphApiClient()
                try:
                    store.start(
                        job["job_id"],
                        "load",
                        "프로젝트 격리 범위로 노드·관계를 적재합니다.",
                    )
                    result = api.load_project_graph(project_id, upload_id)
                    store.update(
                        job["job_id"],
                        current_step="integrity",
                        progress=90,
                        processed_rows=total_rows,
                        total_rows=total_rows,
                        message=(
                            "원본·적재 건수, 고아 관계, 프로젝트 범위를 검증합니다."
                        ),
                    )
                    store.succeed(
                        job["job_id"],
                        step="integrity_complete",
                        message="적재와 무결성 gate를 통과했습니다.",
                        result=result,
                        processed_rows=total_rows,
                        total_rows=total_rows,
                    )
                    st.session_state["project_load_result"] = result
                    st.success("프로젝트 격리 적재와 무결성 확인을 완료했습니다.")
                except Exception as error:
                    store.fail(job["job_id"], step="load", error=str(error))
                    st.error(f"그래프 적재 실패: {error}")
                finally:
                    api.close()
    if st.session_state.get("project_load_result"):
        result = st.session_state["project_load_result"]
        st.markdown("### 무결성·Readiness")
        integrity = result.get("integrity", {})
        metrics = st.columns(4)
        metrics[0].metric(
            "프로젝트 범위",
            "PASS" if integrity.get("project_scope_applied") else "FAIL",
        )
        metrics[1].metric(
            "적재 노드", f"{int(integrity.get('scoped_node_count', 0)):,}"
        )
        metrics[2].metric(
            "교차 프로젝트 관계",
            f"{int(integrity.get('cross_project_relationship_count', 0)):,}",
        )
        metrics[3].metric(
            "Reader 복구",
            "PASS" if result.get("reader_mode_restored", True) else "확인 필요",
        )
        api = FactoryGraphApiClient()
        try:
            if api.live():
                readiness = api.project_readiness(project_id)
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"gate": name, **check}
                            for name, check in readiness.get(
                                "checks", {}
                            ).items()
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
                if readiness.get("ready"):
                    st.success("이 프로젝트는 자유 질의 준비가 완료됐습니다.")
                else:
                    st.info(
                        "무결성 검증은 통과했습니다. Gold/Blind 평가와 "
                        "prompt 승인이 완료되면 Query Studio가 열립니다."
                    )
        finally:
            api.close()


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("pipeline")
