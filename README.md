# P3 제조 지식그래프 RCA · Text-to-Cypher MVP

CiP-DMD의 완제품·구성품·공정·품질 관계를 Neo4j로 구조화하고, 자연어 질문을 읽기 전용 Cypher로 변환해 RCA 후보와 근거 경로를 보여주는 MVP다.

구현 순서와 완료 조건은 [MVP_단계별_구현_계획.md](./MVP_단계별_구현_계획.md)를 따른다.
PPT 대조 후 수정 근거는 [방향 수정 기록](./docs/direction-correction-2026-07-27.md)에 정리했다.

## 최종 목표 명세와 확장 트랙

- [P3 엔터프라이즈 플랫폼 통합 기능명세](./docs/p3-enterprise-platform-functional-spec.md)
- [P3 엔터프라이즈 플랫폼 단계별 작업계획서](./docs/p3-enterprise-platform-implementation-plan.md)
- [P3 요구사항 Baseline·Gap Matrix](./docs/p3-requirements-traceability.md)
- [엔터프라이즈 트랙 1-1~1-3 구현·검증](./docs/enterprise-stage1-1-3-validation.md)
- [엔터프라이즈 트랙 1-4~1-5 구현·검증](./docs/enterprise-stage1-4-5-validation.md)
- [엔터프라이즈 트랙 1-6 구현·검증](./docs/enterprise-stage1-6-validation.md)
- [엔터프라이즈 트랙 1-7 구현·검증](./docs/enterprise-stage1-7-validation.md)
- [엔터프라이즈 트랙 1-8 Release Gate·문서화](./docs/enterprise-stage1-8-validation.md)
- [엔터프라이즈 트랙 2-1 정보구조·디자인 시스템](./docs/enterprise-stage2-1-information-architecture.md)
- [엔터프라이즈 트랙 2-2 Home·Projects Workspace](./docs/enterprise-stage2-2-home-projects.md)
- [엔터프라이즈 트랙 2-3 Data Sources·Pipeline UX](./docs/enterprise-stage2-3-data-pipeline.md)
- [엔터프라이즈 트랙 2-4 Query Studio](./docs/enterprise-stage2-4-query-studio.md)
- [엔터프라이즈 트랙 2-5 Interactive Graph Explorer](./docs/enterprise-stage2-5-interactive-graph-explorer.md)
- [엔터프라이즈 트랙 2-6 Dashboard·Evaluations](./docs/enterprise-stage2-6-dashboard-evaluations.md)
- [엔터프라이즈 트랙 2-7 History·Audit·운영 상태](./docs/enterprise-stage2-7-history-audit-operations.md)
- [엔터프라이즈 트랙 2-8 UI 품질 Gate](./docs/enterprise-stage2-8-ui-quality-gate.md)
- [엔터프라이즈 2단계 기능 기준선 검증·릴리스 기록](./docs/enterprise-stage2-release.md)
- [2.9 제품화 단계 기능명세·작업계획](./docs/p3-enterprise-platform-implementation-plan.md#29단계--p3-사용자-서비스-제품화완성)
- [2.9-1 단일 제품 UI·Surface 경계 검증](./docs/enterprise-stage2-9-1-surface-boundary.md)
- [UX 내비게이션 재검증·수정](./docs/ux-navigation-correction-2026-07-28.md)
- [Streamlit 리팩토링 1단계 · 공통 기반 분리](./docs/refactor-stage-common-foundation.md)
- [Streamlit 리팩토링 2단계 · 페이지 모듈 분리](./docs/refactor-stage-page-modules.md)
- [리팩토링 3단계 · React 구조·UX](./docs/refactor-stage3-react-structure-ux.md)
- [리팩토링 4단계 · 화면별 품질 개선](./docs/refactor-stage4-screen-quality.md)
- [리팩토링 5단계 · 최종 Release Gate](./docs/refactor-stage5-final-release-gate.md)
- [최종 리팩토링 감사 · 3단계 준비도](./docs/refactor-final-audit-and-phase3-readiness.md)
- 플랫폼 공통 API·Registry·스키마·ETL·다중 도메인:
  [`platform-stage1~11`](./docs/platform-stage1-shared-api.md)
- 제품 리팩터링·Data Intake·Graph Explorer·HITL·배포:
  [`refactor-stage1~8`](./docs/refactor-stage1-2-validation.md)

통합 기능명세는 발표자료의 P3 필수 범위, 다중 프로젝트 사내 플랫폼 UI,
P4에서 차용할 LangGraph Router·Tool Registry·RAG·권고·HITL·알림·감사로그를
구분해 정의한다. 단계별 작업계획서는 이를 `1-x / 2-x / 3-x` 릴리스로 나눈다.

## 프로젝트형 플랫폼 확장

새 프로젝트를 만들고 CSV/JSON을 업로드한 뒤 컬럼 프로파일 → 그래프
매핑 검토 → schema 승인 → 프로젝트 격리 적재 → schema 기반
Text-to-Cypher 질의까지 같은 파이프라인으로 실행할 수 있다. 설비 정비
이력 예제가 두 번째 도메인 재적용 기준으로 포함되어 있다.

- 최종 사용자 제품 UI · React: `http://localhost:3000`
- 내부 운영 콘솔 · Streamlit: `http://localhost:8501`
- API 개발 문서 · FastAPI/OpenAPI: `http://localhost:8000/docs`
- DB 개발 도구 · Neo4j Browser: `http://localhost:7474`

## 현재 진행 상태

| 단계 | 상태 | 산출물 |
|---|---|---|
| 1단계 — MVP 질문과 성공 조건 고정 | **재검증 완료** | `docs/mvp-scope.md`, `docs/scope-validation.md`, `evaluation/gold_questions.yml` |
| 2단계 — 원본 데이터와 연결 키 점검 | **완료** | `docs/data-dictionary.md`, `docs/data-profile.md`, `docs/data-gap.md`, `data/processed/cip_dmd_profile.json` |
| 3단계 — 최소 그래프 스키마 설계 | **v1.1 수정 완료** | 장비·이상 분류·QualityFailure 포함 |
| 4단계 — Neo4j 실행 환경과 권한 | **완료** | 실제 Neo4j 스키마 적용·read-only 차단 검증 |
| 5단계 — 재실행 가능한 ETL | **v1.1 재검증 완료** | 실제 데이터 적재·재적재 멱등성 PASS |
| 6단계 — 그래프 무결성과 수동 Cypher | **완료** | Gold 결과 스냅샷 15/15 일치, 무결성·전체 테스트 38/38 PASS |
| 8~11단계 — Text-to-Cypher Agent | **구현 완료** | 생성·차단·EXPLAIN·교정·재검증·실행 PASS |
| 12단계 — 결과 해석·근거 구성 | **완료** | 답변·표·Cypher·부분 그래프 출력 계약 15/15 PASS |
| 13단계 — Streamlit UI | **제품형 UX 보강 완료** | 인라인 근거·세션 대화 기록·Graph Explorer·데이터 사전검증 |
| 14단계 — 실제 Agent·UI 연결 | **완료** | OpenAI 키가 없으면 Vertex Gemini 자동 연결, 실제 자유 질문 PASS |
| 15단계 — 대시보드·그래프 시각화 | **완료** | 무결성·런타임·토큰·비용 지표와 Evidence 필터 구현 |
| 16단계 — Blind 평가·회귀 테스트 | **완료** | Gemini 26문항 의미값 정확도 50.0%→50.0%→61.5%, 엄격 계약 정확도 38.5%, 자기수정 스트레스 8건 |
| 17단계 — 데모 고정·실행 패키징 | **완료** | 원커맨드 프리플라이트·Gold 고정 시나리오 4/4·장애 시 안전 폴백·인라인 Evidence |
| 제품 리팩터링 5단계 — Data Intake | **구현 완료** | ZIP staging·dry-run·승인 적재·reader 복귀·감사로그 |
| 제품 리팩터링 6단계 — 검색형 Graph Explorer | **구현 완료** | 부분 문자열 노드 검색·선택·1~3-hop 읽기 전용 탐색 |
| 제품 리팩터링 7단계 — 전문가 검증(HITL) | **구현 완료** | 3단계 판정·의견·질의 지문·append-only 감사기록 |
| 제품 리팩터링 8단계 — 배포·E2E | **구현 완료** | 5-service Compose·health gate·보안 헤더·black-box smoke |
| 엔터프라이즈 1-7 — Project Registry·Readiness | **구현 완료** | 정식 상태 머신·파일/외부 Neo4j 연결·schema/prompt/Gold/evaluation lineage·준비 전 질의 차단 |
| 엔터프라이즈 1-8 — 백엔드 Release Gate | **구현 완료** | 구조화 오류 계약·tracked secret 0건·P3 추적률 100%·fresh Compose E2E·lineage/runbook |
| 엔터프라이즈 2-1 — 정보구조·디자인 시스템 | **구현 완료** | 11개 workspace·5개 역할 최소권한 메뉴·4개 화면 상태·공통 토큰·Streamlit/React 경계 |
| 엔터프라이즈 2-2 — Home·Projects Workspace | **구현 완료** | Registry 기반 최근 프로젝트·검색·즐겨찾기·readiness·생성 Wizard·프로젝트별 UI 컨텍스트 격리 |
| 엔터프라이즈 2-3 — Data Sources·Pipeline UX | **구현 완료** | 멀티포맷 업로드·Neo4j 연결 검증·프로파일·mapping dry-run/승인·영속 Job·무결성/readiness |
| 엔터프라이즈 2-4 — Query Studio | **구현 완료** | version context·질의 progress·답변/표/Cypher/경로/trace 인라인·영속 대화·검색/재실행 |
| 엔터프라이즈 2-5 — Interactive Graph Explorer | **구현 완료** | NVL 양방향 선택·검색·1~3 hop 누적 확장·필터·경로 강조·상세 패널·프로젝트 격리·1천/1만 노드 경계 |
| 엔터프라이즈 2-6 — Dashboard·Evaluations | **구현 완료** | 프로젝트 공통 필터·그래프/ETL/Agent KPI·모델/프롬프트 비교·F1/혼동행렬·latency/token/cost/error·평가 증적 |
| 엔터프라이즈 2-7 — History·Audit·운영 상태 | **구현 완료** | 프로젝트 대화 검색/재열기/재실행·질의/ETL/평가 Timeline·run_id 증적·CSV/JSON 다운로드·서비스 진단·민감정보 차단 |
| 엔터프라이즈 2-8 — UI 기능 기준선 | **기능 기준선 완료·제품화 Gate 재개방** | 반응형·접근성·역할별 메뉴/행동·상태/복구·두 도메인 기능 계약 |
| 제품화 2.9-1 — 단일 제품 UI·Surface 경계 | **구현·검증 완료** | React 제품 진입점·Streamlit Internal Console·운영 경로 리디렉션·프로젝트 컨텍스트 전달 |

## 확정 데이터

- 데이터셋: CiP-DMD
- MVP 입력: 메타데이터 JSON, 품질 CSV, 생산 로그 XLSX
- 1차 MVP 제외: 대용량 HDF5 센서 원본
- 유효 완제품: 802개
- 구성품까지 완전히 연결된 완제품: 767개(95.6%)
- 검증 가능한 사례: 압력 불합격 19건, 표면거칠기 불합격 190건, 밀링 anomaly class 2 39건

## 목표 구조

```text
Cylinder ──ASSEMBLED_FROM──> CylinderBottom ──UNDERWENT──> ProcessRun
   │                              │                        ├──RUN_ON──> Equipment
   │                              │                        └──CLASSIFIED_AS──> AnomalyClass
   │                              └──HAS_QUALITY_RESULT───────┘
   ├──ASSEMBLED_FROM──> PistonRod ──UNDERWENT──> Turning
   └──HAS_QUALITY_RESULT──> Assembly QC
```

## MVP에서 반드시 남길 것

- 재실행 가능하고 중복 적재를 막는 ETL
- 사람이 검증한 Gold 질문·수동 Cypher
- 장비 모델·이상 유형·품질 불합격을 명시한 검증 가능한 경로
- 자연어 → Cypher 생성·검증·수정·실행
- 쓰기 쿼리 차단과 Neo4j 읽기 전용 계정
- 답변·Cypher·결과표·관계 경로를 함께 표시하는 UI
- 실행 성공률·결과 정확도·읽기 전용 준수율 평가

실행 방법은 [Text-to-Cypher 가이드](./docs/text2cypher-guide.md),
검증 근거는 [8~11단계 검증 결과](./docs/stage8-11-validation.md)를 참고한다.
UI 출력 구조는 [질의 서비스 계약](./docs/service-contract.md),
12단계 검증은 [결과 해석·근거 검증](./docs/stage12-validation.md)에 정리했다.
Streamlit 실행은 [UI 실행 가이드](./docs/streamlit-guide.md),
검증 근거는 [13단계 검증](./docs/stage13-validation.md)을 참고한다.
대시보드·그래프 고도화 결과는 [15단계 검증](./docs/stage15-validation.md)에
정리했다.
Gold 결과와 그래프 무결성 검증은
[6단계 검증](./docs/stage6-validation.md)에 정리했다.
실제 Agent·UI 상태별 검증은
[14단계 검증](./docs/stage14-validation.md)에 정리했다.
Blind 실제 평가와 남은 생성 품질 한계는
[16단계 검증](./docs/stage16-validation.md)에 정리했다.
발표 실행 패키지와 장애 대응은
[17단계 검증](./docs/stage17-demo-packaging.md)에 정리했다.
발표에서 함께 밝혀야 할 데이터·모델 한계는
[발표용 제한사항](./docs/presentation-limitations.md)에 요약했다.

## 제품 리팩터링 1차 — FastAPI

검증된 Streamlit MVP는 발표·운영 콘솔로 유지하고, 외부 제품 UI가 같은
Text-to-Cypher 엔진을 사용할 수 있도록 FastAPI 경계를 추가했다.

```bash
./scripts/run_api.sh
```

- OpenAPI 문서: `http://127.0.0.1:8000/docs`
- 준비 상태: `http://127.0.0.1:8000/api/v1/health`
- 자연어 질의: `POST http://127.0.0.1:8000/api/v1/query`
- 전문가 판정: `POST http://127.0.0.1:8000/api/v1/feedback`
- 전문가 판정 요약: `GET http://127.0.0.1:8000/api/v1/feedback/summary`
- 그래프 스키마: `GET http://127.0.0.1:8000/api/v1/graph/schema`
- 노드 검색: `GET http://127.0.0.1:8000/api/v1/graph/search`
- 부분 그래프: `GET http://127.0.0.1:8000/api/v1/graph/subgraph`

구조 변경과 완료 조건은
[제품 리팩터링 1~2단계 검증](./docs/refactor-stage1-2-validation.md)에
정리했다.

## 공식 제품 UI — React / Next.js

React는 최종 사용자와 발표 평가자의 단일 제품 진입점이다. 프로젝트 선택,
RCA 질문, 답변·결과표·관계 근거, History와 전문가 검토 흐름을 React에서
완결한다.

```bash
./scripts/run_product.sh
```

- 제품 홈: `http://127.0.0.1:3000`
- Projects: `http://127.0.0.1:3000/projects`
- Query Studio: `http://127.0.0.1:3000/query`
- Evidence / Graph: `http://127.0.0.1:3000/graph`
- History: `http://127.0.0.1:3000/history`

Data·Schema·Operations는 최종 사용자 기본 내비게이션에서 제외한다.
데이터 온보딩, 적재, 평가, 감사와 모델 진단은 Streamlit Internal Console이
소유한다. React는 필요한 운영 상태를 읽기 전용으로 요약하거나 내부 콘솔로
연결하며 같은 기능을 별도 UX로 중복 구현하지 않는다.

Query Studio는 한 화면에서 자연어 답변, 결과표, 인터랙티브 근거 그래프,
생성 Cypher와 검증 이력을 확인한다. 최근 대화는 프로젝트별로 저장한다.
CiP-DMD와 별개인 설비 정비 이력 예제가 같은 질의 계약의 재사용 기준이다.

구현 범위와 기존 검증 결과는
[제품 리팩터링 3~4단계 검증](./docs/refactor-stage3-4-validation.md)에
정리했다.

## 내부 운영 콘솔 — Streamlit

```bash
./scripts/run_streamlit.sh
```

Streamlit은 개발자, Data Steward, 평가 담당자와 Admin을 위한 내부 콘솔이다.
최종 사용자용 제품 랜딩이나 발표 RCA 여정을 별도로 소유하지 않는다.

- 프로젝트 Registry와 readiness 진단
- 파일·Neo4j 데이터 소스와 업로드 프로파일
- 그래프 매핑, dry-run, 적재와 무결성 확인
- Gold·Blind 평가와 실패 유형 분석
- 질의·ETL·평가 감사로그와 운영 진단
- 개발 환경의 모델·provider·권한 시뮬레이션

제품 질의·Evidence·History는 React에서 수행한다. Streamlit의 기존 Query와
Graph 화면은 내부 진단 기능으로만 취급하며, 배포 프로필별 격리는 2.9-3에서
완결한다.

기존 구현 경계와 검증 결과는
[Streamlit 제품형 UX 이전](./docs/streamlit-product-ux-migration.md)에
기록되어 있으며, 2.9 제품화 단계가 현재 역할 경계를 다시 정의한다.

제품 리팩터링 5단계 Data Intake의 안전 경계는
[Data Intake 검증](./docs/refactor-stage5-data-intake.md)에 정리했다.
검색형 Graph Explorer의 계약과 안전 경계는
[6단계 Graph Discovery](./docs/refactor-stage6-graph-discovery.md)에 정리했다.
도메인 전문가 검증과 감사기록의 신뢰 경계는
[7단계 HITL 검증](./docs/refactor-stage7-expert-verification.md)에
정리했다.

## 제품형 전체 스택 실행

Docker Desktop 또는 Docker Engine이 있는 환경에서는 Neo4j부터 두 UI까지
한 번에 재현할 수 있다.

```bash
cp .env.example .env
# .env의 NEO4J_PASSWORD를 실제 비밀값으로 변경
./scripts/run_product_stack.sh
```

- React 최종 사용자 제품 UI: `http://127.0.0.1:3000`
- Streamlit 내부 운영 콘솔: `http://127.0.0.1:8501`
- FastAPI 개발 문서: `http://127.0.0.1:8000/docs`
- Neo4j DB 개발 도구: `http://127.0.0.1:7474`

전체 회귀·빌드·패키지 계약은 `./scripts/release_check.sh`로 확인한다.
컨테이너 구성과 E2E 범위, Neo4j Community 권한 한계는
[8단계 배포·E2E 검증](./docs/refactor-stage8-deployment-e2e.md)에
정리했다.

## MVP 이후로 미룰 것

- HDF5 센서 시계열 전체 적재
- VectorDB 기반 예제 검색
- 범용 GraphRAG와 다중 Agent
- 인증된 다단계 승인, 외부 알림, PostgreSQL·pgvector·n8n 통합
- 사용자 계정·서버 동기화 대화 기록
- 대용량 데이터셋의 비동기 ETL 작업 큐와 재개·취소

## 발표용 실행

발표 사용자 여정은 React 하나로 진행한다. Neo4j가 준비된 상태에서 별도
터미널 두 개로 API와 제품 UI를 실행한다.

```bash
# Terminal 1
./scripts/run_api.sh

# Terminal 2
./scripts/run_product.sh
```

발표 시작 주소는 `http://localhost:3000`이다. 기본 동선은
`Home → Projects → Query Studio → Evidence / Graph → History`이며,
Streamlit은 데이터·평가·운영 증적을 추가로 설명할 때만 연다.
