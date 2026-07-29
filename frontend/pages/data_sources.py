"""Dataset upload, profiling, intake and pipeline-status workspaces."""

from __future__ import annotations

import base64
import os
from typing import Any

import pandas as pd
import streamlit as st

from backend.app.ingestion import DatasetWorkspace
from backend.app.jobs import PipelineJobStore
from backend.app.projects import ProjectRegistry
from backend.app.services.diagnostics import collect_demo_diagnostics
from frontend.api_client import FactoryGraphApiClient
from frontend.app_services import ServiceBundle
from frontend.common_ui import render_view_state
from frontend.data_preflight import inspect_uploaded_source
from frontend.design_system import ViewState
from frontend.navigation import navigate_to_page
from frontend.onboarding import (
    format_elapsed,
    job_elapsed_seconds,
    job_status_presentation,
    onboarding_progress,
    profile_quality_warnings,
)
from frontend.runtime import (
    PROJECT_ROOT,
    clear_service_cache,
    get_data_intake_service,
    get_reference_intake_archive,
)

def render_data_intake_workflow() -> None:
    intake = get_data_intake_service()
    st.markdown("#### CiP-DMD Data Intake")
    st.caption(
        "검증 기준과 동일한 CiP-DMD ZIP 번들만 staging할 수 있습니다. "
        "일부 파일이나 변경된 데이터는 실제 그래프에 적재되지 않습니다."
    )
    stage_column, policy_column = st.columns([1.45, 1])
    with stage_column:
        uploaded_bundle = st.file_uploader(
            "CiP-DMD 전체 폴더 구조가 포함된 ZIP (25MB 이하)",
            type=("zip",),
            accept_multiple_files=False,
            key="cip-dmd-intake-zip",
            help=(
                "cylinder, cylinder_bottom, piston_rod 하위의 메타데이터와 "
                "품질 CSV 8개를 원래 상대경로로 포함해야 합니다."
            ),
        )
        st.download_button(
            "검증용 CiP-DMD 번들 다운로드",
            data=get_reference_intake_archive(),
            file_name="cip_dmd_reference_bundle.zip",
            mime="application/zip",
            width="stretch",
            help="현재 프로젝트에 포함된 공개 데이터로 만든 데모 번들입니다.",
        )
        if st.button(
            "1 · 번들 staging",
            type="secondary",
            width="stretch",
            disabled=uploaded_bundle is None,
            key="stage-intake-bundle",
        ):
            try:
                with st.spinner("ZIP 경로·크기·필수 파일·해시를 검사합니다."):
                    record = intake.stage_archive(
                        uploaded_bundle.name,
                        uploaded_bundle.getvalue(),
                    )
                st.session_state["intake_record"] = record
                st.session_state["intake_approval_token"] = None
            except Exception as error:
                st.error(f"번들 staging 실패: {error}")
    with policy_column:
        st.markdown(
            """
            <div class="p3-section-note">
              <b>안전 정책</b><br>
              ZIP 경로 탈출 차단 · 압축 해제 크기 제한 · 필수 파일 8개
              고정 매핑 · 기준 원본 SHA-256 일치 · dry-run PASS ·
              30분 승인 토큰 · 단일 적재 잠금 · reader 모드 자동 복귀
            </div>
            """,
            unsafe_allow_html=True,
        )

    record = st.session_state.get("intake_record")
    if record:
        status_columns = st.columns(4)
        status_columns[0].metric("Run 상태", record["status"])
        status_columns[1].metric(
            "필수 파일", len(record.get("source_files", []))
        )
        status_columns[2].metric(
            "원본 일치",
            "PASS" if record.get("canonical_bundle_match") else "REVIEW",
        )
        status_columns[3].metric(
            "Run ID", record["run_id"].split("-")[0]
        )
        with st.expander("파일 매핑·해시 상세"):
            st.dataframe(
                pd.DataFrame(record.get("source_files", [])),
                width="stretch",
                hide_index=True,
                column_config={
                    "sha256": st.column_config.TextColumn(width="medium"),
                    "canonical_sha256": st.column_config.TextColumn(
                        width="medium"
                    ),
                },
            )

        if record["status"] == "staged":
            if not record.get("canonical_bundle_match"):
                st.warning(
                    "필수 구조는 확인했지만 검증 기준 원본과 다른 파일이 "
                    "있어 자동 적재를 중단했습니다."
                )
            if st.button(
                "2 · ETL dry-run",
                type="primary",
                width="stretch",
                disabled=not record.get("canonical_bundle_match"),
                key=f"dry-run-{record['run_id']}",
            ):
                try:
                    with st.spinner(
                        "Extract → Transform → Validate를 실행합니다."
                    ):
                        dry_run = intake.dry_run(record["run_id"])
                    st.session_state["intake_record"] = {
                        key: value
                        for key, value in dry_run.items()
                        if key != "approval_token"
                    }
                    st.session_state["intake_approval_token"] = dry_run[
                        "approval_token"
                    ]
                    st.rerun()
                except Exception as error:
                    st.error(f"ETL dry-run 실패: {error}")

        if record["status"] == "dry_run_pass":
            validation = record["validation"]
            st.success(
                "ETL dry-run PASS · 실제 Neo4j에는 아직 아무것도 "
                "기록하지 않았습니다."
            )
            count_rows = [
                {"entity_or_relation": name, "projected_count": count}
                for name, count in validation["counts"].items()
            ]
            st.dataframe(
                pd.DataFrame(count_rows),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                f"격리 예정 레코드 "
                f"{validation['quarantined_count']}건 · "
                f"승인 만료 {record['approval_expires_at']}"
            )

            confirmation_text = f"LOAD {record['run_id']}"
            st.markdown("##### 실제 적재 승인")
            st.code(confirmation_text)
            acknowledged = st.checkbox(
                "현재 그래프가 일시적으로 재시작되며, 적재 후 reader "
                "모드로 복귀하는 것에 동의합니다.",
                key=f"approve-intake-{record['run_id']}",
            )
            confirmation = st.text_input(
                "위 확인 문구를 정확히 입력",
                key=f"confirm-intake-{record['run_id']}",
            )
            ui_load_enabled = os.getenv("P3_ENABLE_UI_LOAD") == "1"
            approval_token = st.session_state.get(
                "intake_approval_token"
            )
            if not ui_load_enabled:
                st.info(
                    "실제 적재는 기본 비활성화 상태입니다. 관리자가 "
                    "`P3_ENABLE_UI_LOAD=1`로 앱을 시작한 경우에만 "
                    "승인 버튼이 활성화됩니다."
                )
            if approval_token is None:
                st.warning(
                    "승인 토큰이 현재 세션에 없습니다. dry-run을 다시 "
                    "실행해 새 토큰을 발급하세요."
                )
            can_load = (
                ui_load_enabled
                and approval_token is not None
                and acknowledged
                and confirmation == confirmation_text
            )
            if st.button(
                "3 · 승인 후 Neo4j 적재",
                type="primary",
                width="stretch",
                disabled=not can_load,
                key=f"load-intake-{record['run_id']}",
            ):
                try:
                    with st.spinner(
                        "loader 전환 → 적재 → 건수 검증 → reader 복귀"
                    ):
                        loaded = intake.load(
                            record["run_id"],
                            approval_token=approval_token,
                            confirmation=confirmation,
                        )
                    st.session_state["intake_record"] = loaded
                    st.session_state["intake_approval_token"] = None
                    clear_service_cache()
                    st.success(
                        "적재와 reader 모드 복귀를 완료했습니다. 다음 "
                        "화면 갱신부터 새 연결을 사용합니다."
                    )
                except Exception as error:
                    st.error(f"승인 적재 실패: {error}")

        if record["status"] == "load_pass":
            st.success("적재 완료 · Neo4j reader 모드 복귀 확인")
        elif record["status"] in {"dry_run_failed", "load_failed"}:
            st.error(record.get("error", "Data Intake 작업이 실패했습니다."))

    with st.expander("최근 Data Intake 실행·감사로그"):
        recent_runs = intake.list_runs(limit=10)
        if recent_runs:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "run_id": item["run_id"],
                            "status": item["status"],
                            "filename": item.get("original_filename"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                        }
                        for item in recent_runs
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        events = intake.recent_audit_events(limit=20)
        if events:
            st.dataframe(
                pd.DataFrame(events),
                width="stretch",
                hide_index=True,
            )
        if not recent_runs and not events:
            st.info("아직 Data Intake 실행 기록이 없습니다.")

    with st.expander("개별 파일 빠른 사전검증"):
        uploaded_files = st.file_uploader(
            "메타데이터 JSON 또는 품질 CSV (10MB 이하)",
            type=("json", "csv"),
            accept_multiple_files=True,
            key="candidate-source-files",
            help=(
                "이 검사는 파일 구조와 공통 ID 후보만 확인하며 실제 "
                "적재 승인으로 사용되지 않습니다."
            ),
        )
        if uploaded_files:
            inspections = [
                inspect_uploaded_source(file.name, file.getvalue())
                for file in uploaded_files
            ]
            st.dataframe(
                pd.DataFrame(inspections),
                width="stretch",
                hide_index=True,
            )

def render_document_rag_workflow() -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    role = st.session_state.get("preview_role", "Data Steward")
    st.markdown("#### LlamaIndex 문서 RAG")
    st.caption(
        f"`{project_id}` 프로젝트의 매뉴얼·SOP·기준서를 버전별로 색인하고 "
        "Query Studio의 문서 근거로 사용합니다."
    )
    api = FactoryGraphApiClient()
    try:
        readiness = api.document_rag_readiness(project_id, role=role)
        documents = api.project_documents(project_id, role=role)["documents"]
    except Exception as error:
        st.error(f"문서 RAG 상태 조회 실패: {error}")
        api.close()
        return

    metrics = st.columns(4)
    metrics[0].metric("RAG 상태", "READY" if readiness["ready"] else "EMPTY")
    metrics[1].metric("현재 문서", readiness["current_document_count"])
    metrics[2].metric("전체 버전", readiness["document_count"])
    metrics[3].metric("Index", readiness["index_version"])

    if documents:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "document_id": item.get("document_id"),
                        "title": item.get("title"),
                        "version": item.get("version"),
                        "type": item.get("document_type"),
                        "current": item.get("is_current"),
                        "effective_date": item.get("effective_date"),
                        "classification": item.get("security_classification"),
                    }
                    for item in documents
                ]
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("등록된 문서가 없습니다.")

    with st.expander("문서 등록·새 버전 색인"):
        uploaded = st.file_uploader(
            "Markdown, TXT 또는 text-layer PDF",
            type=("md", "markdown", "txt", "pdf"),
            key=f"rag-upload-{project_id}",
        )
        left, right = st.columns(2)
        document_id = left.text_input(
            "Document ID",
            value="press-maintenance-manual" if project_id == "equipment-history" else "quality-sop",
            key=f"rag-document-id-{project_id}",
        )
        version = right.text_input(
            "Version", value="1.0", key=f"rag-version-{project_id}"
        )
        title = left.text_input(
            "Title", value="", key=f"rag-title-{project_id}"
        )
        document_type = right.selectbox(
            "Document type",
            options=("maintenance_manual", "sop", "quality_standard", "work_instruction"),
            key=f"rag-type-{project_id}",
        )
        effective_date = left.text_input(
            "Effective date", placeholder="2026-07-29", key=f"rag-date-{project_id}"
        )
        allowed_roles = right.multiselect(
            "Allowed roles (비우면 전체 조회 가능)",
            options=("Viewer", "Analyst", "Domain Expert", "Data Steward", "Admin"),
            key=f"rag-roles-{project_id}",
        )
        can_manage = role in {"Data Steward", "Admin"}
        if not can_manage:
            st.info("문서 등록·재색인은 Data Steward 또는 Admin 역할에서 가능합니다.")
        if st.button(
            "문서 색인",
            type="primary",
            width="stretch",
            disabled=uploaded is None or not can_manage or not document_id or not version,
            key=f"rag-index-{project_id}",
        ):
            try:
                raw = uploaded.getvalue()
                payload: dict[str, Any] = {
                    "document_id": document_id,
                    "title": title.strip() or uploaded.name,
                    "version": version,
                    "document_type": document_type,
                    "source_filename": uploaded.name,
                    "effective_date": effective_date.strip() or None,
                    "allowed_roles": allowed_roles,
                    "is_current": True,
                }
                if uploaded.name.lower().endswith(".pdf"):
                    payload["content_base64"] = base64.b64encode(raw).decode("ascii")
                else:
                    payload["content"] = raw.decode("utf-8")
                result = api.ingest_project_document(project_id, payload, role=role)
                st.success(
                    f"색인 완료 · {result['document_id']} v{result['version']} · "
                    f"chunk {result.get('chunk_count', 0)}개"
                )
                st.rerun()
            except Exception as error:
                st.error(f"문서 색인 실패: {error}")

        if st.button(
            "전체 문서 재색인",
            disabled=not can_manage,
            key=f"rag-rebuild-{project_id}",
        ):
            try:
                result = api.rebuild_document_index(project_id, role=role)
                st.success(f"재색인 완료 · chunk {result['chunk_count']}개")
                st.rerun()
            except Exception as error:
                st.error(f"재색인 실패: {error}")

    st.markdown("##### Retrieval 테스트")
    query = st.text_input(
        "문서 질문",
        value=(
            "유압 펌프 교체 후 점검 절차"
            if project_id == "equipment-history"
            else "압력검사 실패 대응 절차"
        ),
        key=f"rag-search-{project_id}",
    )
    include_superseded = st.checkbox(
        "폐기 버전도 검색",
        value=False,
        key=f"rag-search-old-{project_id}",
    )
    if st.button("문서 검색", key=f"rag-search-button-{project_id}"):
        try:
            result = api.search_documents(
                project_id,
                query,
                current_only=not include_superseded,
                role=role,
            )
            if result["matches"]:
                for match in result["matches"]:
                    with st.container(border=True):
                        st.markdown(
                            f"**{match['title']}** · `{match['citation_id']}`"
                        )
                        st.caption(
                            f"v{match['version']} · Page {match['page_number']} · "
                            f"score {match['score']:.3f}"
                        )
                        st.write(match["text"])
            else:
                st.info("접근 가능한 문서 근거를 찾지 못했습니다.")
        except Exception as error:
            st.error(f"문서 검색 실패: {error}")
    api.close()


def render_data_health_tab(
    services: ServiceBundle | None, snapshot: dict[str, Any] | None
) -> None:
    st.subheader("데이터 적재와 실행 진단")
    st.caption(
        "운영 그래프는 읽기 전용으로 유지합니다. 전체 번들은 staging과 "
        "dry-run을 통과하고 명시적으로 승인된 경우에만 잠시 loader로 "
        "전환됩니다. 현재 질의 provider: "
        f"{services.provider if services is not None else '연결 전'}"
    )
    checks = collect_demo_diagnostics(PROJECT_ROOT)
    check_columns = st.columns(len(checks))
    for column, check in zip(check_columns, checks):
        column.metric(check["check"], check["status"])
        column.caption(check["detail"])

    st.markdown("#### 최근 ETL 실행")
    etl = (snapshot or {}).get("etl")
    if etl:
        etl_columns = st.columns(5)
        etl_columns[0].metric("상태", etl["status"])
        etl_columns[1].metric("모드", etl["mode"])
        etl_columns[2].metric("멱등성", etl["idempotency_status"])
        etl_columns[3].metric("격리 레코드", etl["quarantined_count"])
        etl_columns[4].metric("적재 지표 유형", len(etl["counts"]))
        st.success(f"최근 적재 완료 · {etl['finished_at']}")
        with st.expander("ETL 적재 건수 상세"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {"entity_or_relation": key, "count": value}
                        for key, value in etl["counts"].items()
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            st.caption(f"실행 리포트 · {etl['report_path']}")
    else:
        st.warning("성공한 ETL load 기록을 찾지 못했습니다.")

    st.divider()
    render_generic_dataset_upload()
    st.divider()
    render_document_rag_workflow()
    st.divider()
    render_data_intake_workflow()

def get_pipeline_job_store() -> PipelineJobStore:
    return PipelineJobStore(
        PROJECT_ROOT / "data" / "processed" / "pipeline_jobs.sqlite3"
    )

def render_onboarding_stage(project: dict[str, Any]) -> None:
    progress = onboarding_progress(project["status"])
    st.progress(progress["percent"], text=f"온보딩 {progress['percent']}%")
    columns = st.columns(len(progress["steps"]))
    for column, step in zip(columns, progress["steps"]):
        marker = {
            "complete": "✓",
            "active": "●",
            "pending": "○",
        }[step["state"]]
        column.caption(f"{marker} {step['label']}")

def render_pipeline_jobs(project_id: str) -> None:
    jobs = get_pipeline_job_store().list(project_id, limit=8)
    st.markdown("#### 작업 상태")
    if not jobs:
        render_view_state(
            ViewState.EMPTY,
            page="Pipeline",
            detail="업로드·연결·매핑·적재 작업을 시작하면 여기에 기록됩니다.",
        )
        return
    store = get_pipeline_job_store()
    for job in jobs:
        status = job_status_presentation(job["status"])
        with st.expander(
            f"{status['label']} · {job['kind']} · "
            f"{job['job_id'][:8]} · 시도 {job['attempt']}",
            expanded=job["status"] in {"queued", "running", "failed"},
        ):
            st.progress(
                int(job["progress"]),
                text=f"{job['current_step']} · {job['message']}",
            )
            metrics = st.columns(5)
            metrics[0].metric("상태", status["label"])
            metrics[1].metric("진행률", f"{job['progress']}%")
            metrics[2].metric(
                "처리량",
                (
                    f"{job['processed_rows']:,}/"
                    f"{job['total_rows']:,}"
                    if job["total_rows"]
                    else f"{job['processed_rows']:,}"
                ),
            )
            metrics[3].metric("현재 단계", job["current_step"])
            metrics[4].metric(
                "경과시간",
                format_elapsed(job_elapsed_seconds(job)),
            )
            if job.get("error"):
                st.error(job["error"])
            logs = store.logs(job["job_id"])
            if logs:
                st.dataframe(
                    pd.DataFrame(logs),
                    width="stretch",
                    hide_index=True,
                )
            action_columns = st.columns([1, 1, 4])
            if job["status"] in {"queued", "running"}:
                if action_columns[0].button(
                    "취소",
                    key=f"cancel-job-{job['job_id']}",
                ):
                    try:
                        store.cancel(job["job_id"])
                        st.rerun()
                    except ValueError as error:
                        st.warning(str(error))
            if job["status"] in {"failed", "cancelled"}:
                if action_columns[1].button(
                    "재시도 등록",
                    key=f"retry-job-{job['job_id']}",
                ):
                    store.retry(job["job_id"])
                    st.rerun()
    if st.button("작업 상태 새로고침", key=f"refresh-jobs-{project_id}"):
        st.rerun()

def _profile_uploaded_files(
    project: dict[str, Any],
    files: list[Any],
) -> dict[str, Any]:
    project_id = project["project_id"]
    payload = [
        {
            "filename": file.name,
            "content_base64": base64.b64encode(file.getvalue()).decode(),
        }
        for file in files
    ]
    api = FactoryGraphApiClient()
    try:
        if api.live():
            return api.profile_project_files(project_id, payload)
    finally:
        api.close()

    registry = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    current = registry.require(project_id)
    if current["status"] != "profiling":
        registry.transition(
            project_id, "profiling", reason="ui_profile_started"
        )
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    try:
        result = datasets.profile_upload(project_id, payload)
        registry.update(project_id, source_version=result["upload_id"])
        registry.record_artifact(
            project_id,
            "source",
            version=result["upload_id"],
            fingerprint=result.get("source_sha256"),
            metadata={
                "upload_id": result["upload_id"],
                "file_count": len(result.get("files", [])),
            },
        )
        registry.transition(
            project_id,
            "mapping_review",
            reason="ui_profile_completed",
        )
        return result
    except Exception:
        if registry.require(project_id)["status"] == "profiling":
            registry.transition(
                project_id, "failed", reason="ui_profile_failed"
            )
        raise

def render_generic_dataset_upload() -> None:
    project_id = st.session_state.get("active_project_id", "cip-dmd")
    projects = ProjectRegistry(
        PROJECT_ROOT / "data" / "processed" / "projects.sqlite3"
    )
    project = projects.require(project_id)
    if notice := st.session_state.pop("project_created_notice", None):
        st.success(
            f"`{notice}` 프로젝트를 만들었습니다. 첫 데이터 소스를 등록하세요."
        )
    st.markdown("#### 프로젝트 데이터 온보딩")
    st.caption(
        f"`{project_id}` · {project['source_type']} 소스 · "
        "승인 전에는 운영 Neo4j가 변경되지 않습니다."
    )
    render_onboarding_stage(project)
    if project["source_type"] == "neo4j":
        render_neo4j_source_connection(project)
        render_pipeline_jobs(project_id)
        return

    files = st.file_uploader(
        "파일을 끌어 놓거나 선택하세요 (CSV/JSON/XLSX/ZIP)",
        type=("csv", "json", "xlsx", "zip"),
        accept_multiple_files=True,
        key=f"project-upload-{project_id}",
        help="파일당 10MB, 한 번에 최대 10개. ZIP은 안전 검사 후 펼칩니다.",
    )
    if st.button(
        "업로드·정제·프로파일링",
        disabled=not files,
        width="stretch",
        key=f"profile-upload-{project_id}",
    ):
        store = get_pipeline_job_store()
        job = store.create(
            project_id,
            "profile",
            message=f"{len(files)}개 원본 파일 검증 대기",
        )
        try:
            store.start(
                job["job_id"],
                "extract",
                "파일 해시·확장자·압축 경로를 검증합니다.",
            )
            store.update(
                job["job_id"],
                current_step="profile",
                progress=45,
                message="정규화된 테이블의 타입·결측·ID 후보를 분석합니다.",
            )
            result = _profile_uploaded_files(project, files)
            total_rows = sum(
                int(file.get("row_count", 0)) for file in result["files"]
            )
            store.succeed(
                job["job_id"],
                step="profile_complete",
                message="데이터 프로파일과 lineage 저장을 완료했습니다.",
                result={
                    "upload_id": result["upload_id"],
                    "file_count": len(result["files"]),
                },
                processed_rows=total_rows,
                total_rows=total_rows,
            )
            st.session_state["latest_project_upload"] = result
            st.success(
                f"{len(result['files'])}개 파일 프로파일 완료 · "
                f"upload {result['upload_id'][:8]}"
            )
        except Exception as error:
            store.fail(
                job["job_id"], step="profile", error=str(error)
            )
            st.error(f"프로파일링 실패: {error}")
    datasets = DatasetWorkspace(
        PROJECT_ROOT / "data" / "processed" / "project_uploads"
    )
    uploads = datasets.list(project_id)
    session_upload = (
        st.session_state.get("latest_project_upload") or {}
    )
    latest = (
        session_upload
        if session_upload.get("project_id") == project_id
        else uploads[0]
        if uploads
        else None
    )
    if latest:
        warnings = profile_quality_warnings(latest)
        summary = st.columns(4)
        summary[0].metric("원본 파일", len(latest.get("sources", [])))
        summary[1].metric("정규화 테이블", len(latest["files"]))
        summary[2].metric(
            "전체 행",
            f"{sum(file['row_count'] for file in latest['files']):,}",
        )
        summary[3].metric("품질 경고", len(warnings))
        if warnings:
            st.warning("\n".join(f"- {warning}" for warning in warnings))
        else:
            st.success("ID 후보와 컬럼 품질 기본 검사를 통과했습니다.")
        for file in latest["files"]:
            with st.expander(
                f"{file['filename']} · {file['row_count']}행 "
                f"× {file['column_count']}열"
            ):
                st.dataframe(
                    pd.DataFrame(file["columns"]),
                    width="stretch",
                    hide_index=True,
                )
                source_path = (
                    PROJECT_ROOT
                    / "data"
                    / "processed"
                    / "project_uploads"
                    / project_id
                    / latest["upload_id"]
                    / "source"
                    / file["filename"]
                )
                try:
                    sample_rows = pd.read_csv(source_path, nrows=20)
                    st.caption("샘플 20행")
                    st.dataframe(
                        sample_rows, width="stretch", hide_index=True
                    )
                except Exception:
                    st.caption("샘플은 Pipeline dry-run에서 확인합니다.")
        if st.button(
            "Pipeline에서 매핑 검토 →",
            type="primary",
            key=f"goto-schema-{project_id}",
        ):
            navigate_to_page("Pipeline")
            st.rerun()
    render_pipeline_jobs(project_id)

def render_neo4j_source_connection(project: dict[str, Any]) -> None:
    st.markdown("##### 기존 Neo4j 연결")
    st.info(
        "비밀번호 값은 저장하지 않습니다. 서버 환경변수 이름만 등록하고 "
        "스키마 introspection·샘플 READ 질의를 통과해야 승인할 수 있습니다."
    )
    with st.form(f"neo4j-source-{project['project_id']}"):
        uri = st.text_input("URI", placeholder="neo4j://graph.internal:7687")
        database = st.text_input("Database", value="neo4j")
        username = st.text_input("Username", value="neo4j")
        password_env = st.text_input(
            "비밀번호 환경변수", placeholder="FACTORY_NEO4J_PASSWORD"
        )
        submitted = st.form_submit_button(
            "연결·스키마 검증",
            type="primary",
            width="stretch",
        )
    if submitted:
        store = get_pipeline_job_store()
        job = store.create(
            project["project_id"],
            "neo4j_connect",
            message="Neo4j 연결 검증 대기",
        )
        api = FactoryGraphApiClient()
        try:
            store.start(
                job["job_id"], "connect", "연결과 READ 권한을 확인합니다."
            )
            result = api.validate_neo4j_connector(
                project["project_id"],
                {
                    "uri": uri,
                    "database": database,
                    "username": username,
                    "password_env": password_env,
                },
            )
            store.update(
                job["job_id"],
                current_step="introspection",
                progress=70,
                message="라벨·관계·속성과 샘플 건수를 확인했습니다.",
            )
            store.succeed(
                job["job_id"],
                step="validated",
                message="Neo4j 연결 검증이 완료됐습니다.",
                result=result,
            )
            st.session_state["validated_connector"] = result
        except Exception as error:
            store.fail(job["job_id"], step="connect", error=str(error))
            st.error(str(error))
        finally:
            api.close()
    connector = st.session_state.get("validated_connector")
    if connector and connector.get("project_id") == project["project_id"]:
        st.success(
            f"연결 검증 완료 · 노드 {connector['counts'].get('nodes', 0):,} · "
            f"관계 {connector['counts'].get('relationships', 0):,}"
        )
        if st.button(
            "검증된 연결 승인",
            key=f"approve-connector-{connector['connector_id']}",
            type="primary",
        ):
            api = FactoryGraphApiClient()
            try:
                approved = api.approve_neo4j_connector(
                    project["project_id"], connector["connector_id"]
                )
                st.session_state["validated_connector"] = approved
                st.success("연결 승인과 프로젝트 스키마 등록을 완료했습니다.")
            except Exception as error:
                st.error(str(error))
            finally:
                api.close()


if __name__ == "__main__":
    from frontend.legacy_page_redirect import redirect_legacy_page

    redirect_legacy_page("data_sources")
