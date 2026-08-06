# P3 요구사항 Baseline·Gap Matrix

## 1. 목적

이 문서는
[`p3-enterprise-platform-functional-spec.md`](./p3-enterprise-platform-functional-spec.md)의
P3 필수 요구사항을 코드·테스트·검증 문서에 연결한다. 기능 목표와 현재
구현 상태를 분리하고, 구현이 존재하더라도 자동 검증 근거가 부족하면
`부분 완료`로 표시한다.

상태 정의:

- `완료`: 코드, 자동 테스트, 실행·검증 문서가 연결됨
- `부분 완료`: 핵심 코드는 있으나 일반화·검증·문서 중 하나가 부족함
- `미구현`: 실행 가능한 기능이 없음
- `검증 필요`: 구현 주장은 있으나 현재 환경에서 실측 근거 갱신이 필요함

## 2. P3 필수 요구사항 추적표

| ID | 요구사항 | 상태 | 구현·검증 근거 | 남은 작업 |
|---|---|---|---|---|
| FR-1.1 | 엔티티·속성·관계 분석 | 완료 | `docs/data-profile.md`, `docs/data-dictionary.md` | 두 번째 도메인도 동일 형식으로 유지 |
| FR-1.2 | 라벨·관계·속성·식별자·카디널리티 Schema DSL | 완료 | `backend/app/schema_registry.py`, `schemas/*/schema.yml` | 도메인 추가 시 같은 계약 유지 |
| FR-1.3 | 업무 질문 관점 스키마 검증 | 완료 | manifest `query_scenarios`, `SchemaRegistry.validate_query_scenarios()` | 현업 질문 변경 시 회귀 |
| FR-1.4 | 데이터 사전·관계 방향·품질 정책 문서 | 완료 | `docs/data-dictionary.md`, `docs/graph-schema.md`, `docs/data-gap.md` | 도메인별 문서 자동 연결 |
| FR-1.5 | 스키마·source version 연결 | 완료 | `SchemaRegistry`, `schema.yml.version`, `source_version` | 변경 이력 설명은 Git으로 유지 |
| FR-2.1 | 결측·타입·중복·비정상 ID 정제 | 완료 | 범용 mapping dry-run과 격리 사유 | 도메인별 추가 정제 규칙은 adapter로 확장 |
| FR-2.2 | 노드·관계 레코드 변환 | 완료 | `backend/app/etl/transform.py`, `generic_loader.py`, 관계 속성 mapping | 대용량 streaming은 후속 |
| FR-2.3 | Neo4j 배치·벌크 적재 | 완료 | `backend/app/etl/load.py`, transactional `generic_loader.py` | 운영 데이터 크기별 성능 실측은 배포 단계 |
| FR-2.4 | 적재 무결성 검증 | 완료 | 트랜잭션 내부 원본 projection→노드·관계 reconciliation, 교차 프로젝트 관계 검사 | 신규 도메인마다 동일 Gate 적용 |
| FR-2.5 | 멱등성 | 완료 | 실제 Neo4j 두 번째 도메인 2회 적재 시 신규 노드·관계 0건 | 장기 운영 시 stale record 정책 추가 |
| FR-2.6 | 파일 hash·lineage·격리 기록 | 완료 | 원본·정규화 SHA-256, archive/sheet lineage, `backend-lineage.md` | 영속 Job audit는 후속 |
| FR-2.7 | dry-run과 실제 적재 분리 | 완료 | mapping preview의 범용 `dry_run` 보고서와 승인 적재 분리 | UI 시각화는 2단계 |
| FR-3.1 | 대표 질문 15~20개 | 완료 | `evaluation/gold_questions.yml` 15문항 | 새 도메인은 별도 기준셋 필요 |
| FR-3.2 | 정답 Cypher·결과 snapshot | 완료 | `evaluation/gold_results/`, `gold_validation.py` | schema version 연결 보강 |
| FR-3.3 | 예외·안전 질문 | 완료 | Gold·Blind·correction cases | 도메인 라우팅 예외는 3단계 |
| FR-3.4 | Gold 기준선 평가 | 완료 | `evaluation/evaluator.py` | 모델 변경 시 정기 회귀 |
| FR-3.5 | schema·Gold version 연결 | 완료 | `evaluation/projects/*/manifest.yml`, evaluation fingerprint | 변경 시 version과 snapshot 동시 갱신 |
| FR-3.6 | Blind 분리 | 완료 | `blind_questions.yml`, `blind_results/` | 표본 확대 |
| FR-4.1 | 프로젝트 schema context 주입 | 완료 | `bootstrap.py`, `workflow.py`, `SchemaRegistry.context()` | query-scenario context 선택 최적화 |
| FR-4.2 | 자연어→Cypher | 완료 | Gemini/OpenAI/Gold adapter | provider별 회귀 |
| FR-4.3 | READ 전용 | 완료 | `security/read_only.py`, Neo4j reader | DB 수준 project isolation 보강 |
| FR-4.4 | EXPLAIN 검증 | 완료 | `workflow.py`, `graph.py` | 실제 DB 버전별 검증 |
| FR-4.5 | 자기수정 | 완료 | LangGraph correction loop | 실패 유형별 표본 확대 |
| FR-4.6 | 재검증 통과 쿼리만 실행 | 완료 | `workflow.py` | 보안 회귀 유지 |
| FR-4.7 | 상태 계약 | 완료 | `service-contract.md`, `api-contract.md`, OpenAPI release gate | UI 회귀 유지 |
| FR-4.8 | schema·Cypher·검증 근거 반환 | 완료 | `metadata`, evidence provenance, 검증 Cypher SHA-256, query audit | UI 버전 표시는 2단계 |
| FR-4.9 | 프로젝트별 prompt·few-shot·Gold | 완료 | `prompts/*/manifest.yml`, `PromptRegistry`, `EvaluationRegistry`, readiness version linkage | 신규 도메인은 전문가 승인 기준셋 필요 |
| FR-5.1~5.7 | Streamlit 질의·근거·대화 UI | 완료 | `frontend/pages/query_studio.py`, `evidence.py`, `conversation_history.py`, UI·상태 회귀 테스트 | 3단계 Tool·HITL 상태를 같은 화면 계약으로 확장 |
| FR-6.1 | 정확도 평가 리포트 | 완료 | `stage16-validation.md`, `metrics.json` | 최신 릴리스마다 갱신 |
| FR-6.2 | 최종 발표자료 | 완료 | `final-presentation-evidence-pack.md`, 단계별 검증 문서 | 실제 발표 템플릿에 팀명·담당자 반영 |
| FR-6.3 | 산출물 정리 | 완료 | README·docs·evaluation·Git | 최종 릴리스 태그 |
| FR-6.4 | Trouble Shooting | 완료 | `backend-troubleshooting.md`, `stage*-validation.md`, `refactor-stage*.md` | 운영 사례 지속 보강 |
| FR-6.5 | 한계 공개 | 완료 | `presentation-limitations.md`, `data-gap.md` | 신규 기능 한계 추가 |

## 3. 비기능 요구사항 추적표

| ID | 요구사항 | 상태 | 근거·남은 작업 |
|---|---|---|---|
| NFR-1 | Neo4j Community/Aura Free 동작 | 완료 | Community 기반 로컬·Docker 구성 |
| NFR-2 | Git/GitHub 버전 관리 | 완료 | `main`, GitHub Actions |
| NFR-3 | 모듈 소유권 | 완료 | `module-ownership.md` 역할·모듈·교차 승인 규칙 |
| NFR-4 | 비밀정보 비커밋 | 완료 | `.env.example`, CI secret 경계 |
| NFR-5 | 재현 가능한 테스트·실행 | 완료 | 9단계 `release_check.sh`, `fresh_release_gate.sh`, Compose, unit/Playwright E2E |

## 4. 확장 트랙 문서 지도

### 공통 플랫폼 1~11

1. [`platform-stage1-shared-api.md`](./platform-stage1-shared-api.md)
2. [`platform-stage2-project-registry.md`](./platform-stage2-project-registry.md)
3. [`platform-stage3-schema-registry.md`](./platform-stage3-schema-registry.md)
4. [`platform-stage4-etl-adapters.md`](./platform-stage4-etl-adapters.md)
5. [`platform-stage5-dataset-profiling.md`](./platform-stage5-dataset-profiling.md)
6. [`platform-stage6-schema-mapping.md`](./platform-stage6-schema-mapping.md)
7. [`platform-stage7-project-graph-isolation.md`](./platform-stage7-project-graph-isolation.md)
8. [`platform-stage8-project-schema-agent.md`](./platform-stage8-project-schema-agent.md)
9. [`platform-stage9-second-domain.md`](./platform-stage9-second-domain.md)
10. [`platform-stage10-streamlit-workspaces.md`](./platform-stage10-streamlit-workspaces.md)
11. [`platform-stage11-react-shared-platform.md`](./platform-stage11-react-shared-platform.md)

### 제품 리팩터링 1~8

1. [`refactor-stage1-2-validation.md`](./refactor-stage1-2-validation.md)
2. [`refactor-stage3-4-validation.md`](./refactor-stage3-4-validation.md)
3. [`refactor-stage5-data-intake.md`](./refactor-stage5-data-intake.md)
4. [`refactor-stage6-graph-discovery.md`](./refactor-stage6-graph-discovery.md)
5. [`refactor-stage7-expert-verification.md`](./refactor-stage7-expert-verification.md)
6. [`refactor-stage8-deployment-e2e.md`](./refactor-stage8-deployment-e2e.md)

`refactor-stage1-2`와 `refactor-stage3-4`는 두 단계를 한 문서로 묶었기
때문에 파일 수는 6개지만 작업 단계는 총 8개다.

### 구조·UX 리팩터링과 최종 감사

1. [`refactor-stage-common-foundation.md`](./refactor-stage-common-foundation.md)
2. [`refactor-stage-page-modules.md`](./refactor-stage-page-modules.md)
3. [`refactor-stage3-react-structure-ux.md`](./refactor-stage3-react-structure-ux.md)
4. [`refactor-stage4-screen-quality.md`](./refactor-stage4-screen-quality.md)
5. [`refactor-stage5-final-release-gate.md`](./refactor-stage5-final-release-gate.md)
6. [`refactor-final-audit-and-phase3-readiness.md`](./refactor-final-audit-and-phase3-readiness.md)

## 5. 1단계 작업 우선순위

1. FR-1.2·1.3·1.5의 Schema DSL과 질의 관점 검증을 일반화한다.
2. FR-2.1·2.6·2.7의 범용 source adapter, lineage, dry-run 격리를 구현한다.
3. 기존 CiP-DMD와 equipment-history 회귀를 동시에 통과시킨다.
4. P4 기능은 1단계 Release Gate 이후 별도 확장으로 유지한다.
