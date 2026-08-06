# P3 엔터프라이즈 플랫폼 단계별 작업계획서

## 1. 계획 원칙

작업을 네 개의 순차 Gate로 구분한다.

1. **1단계: P3 필수 기능을 백엔드·평가 기준까지 완성**
2. **2단계: 다중 프로젝트 업무 기능과 UI 기준선 구축**
3. **2.9단계: 하나의 완성된 P3 사용자 서비스로 제품화**
4. **3단계: P4의 Agentic AI 기능을 P3에 통합**

현재 준비도:

| 범위 | 판정 |
|---|---|
| P3 백엔드·데이터·평가 | `READY` |
| P3 최종 사용자 서비스 | `NOT READY — PRODUCTIZATION GATE REOPENED` |
| 3단계 Agentic AI 기본 여정 병합 | `HOLD` |

각 세부 단계는 다음 Gate를 통과한 뒤 다음 단계로 이동한다.

- 코드·문서 작성
- 단위·통합 테스트
- 실제 Neo4j 검증
- UI가 포함된 단계는 브라우저 E2E 검증
- 보이는 모든 내비게이션·링크·핵심 행동의 실제 클릭 검증
- HTTP 200·예외 0건뿐 아니라 의미 있는 본문과 다음 행동 검증
- 보안·권한·프로젝트 격리 회귀 테스트
- 결과 문서화

현재 구현된 기능은 다시 만드는 대신 계약·테스트로 검증하고,
부족한 부분만 보강한다. 다만 사용자에게 노출할 이유가 없는 개발·평가 기능은
보존을 우선하지 않고 내부 콘솔로 이동하거나 배포 프로필에서 제거한다.

3단계는 2.9 전체 Gate가 통과된 뒤 시작한다. 2.9 진행 중에는 LangGraph Router,
문서 RAG, 권고, HITL, 알림 같은 새 기능을 기본 사용자 여정에 추가하지 않는다.

---

## 1단계 — P3 필수 기능 백엔드 반영 버전

### 1-1. 요구사항 Baseline과 Gap Matrix 고정

상태: **완료**

목표:

- 발표자료 6~7페이지 요구사항과 현재 코드·문서·테스트를 일대일 대응한다.

작업:

- FR-1.1~FR-6.5, NFR-1~NFR-5별 구현 파일·테스트·문서를 연결한다.
- `완료 / 부분 완료 / 미구현 / 검증 필요`로 상태를 분류한다.
- `platform-stage*`, `refactor-stage*` 문서를 README의 확장 트랙에 연결한다.
- 결과 정확도 목표와 현재 실측값 차이를 명시한다.

검증:

- 모든 요구사항에 최소 하나의 증거 또는 미구현 사유가 존재한다.
- 구현 상태와 목표 명세가 섞이지 않는다.

산출물:

- 요구사항 추적표
- README 확장 트랙

### 1-2. 데이터 프로파일·스키마 계약 일반화

상태: **완료**

목표:

- CiP-DMD 고정 코드를 프로젝트별 설정으로 분리한다.

작업:

- 데이터셋 프로파일 공통 모델 정의
- 노드·관계·속성·카디널리티·식별자 Schema DSL 정의
- schema version과 source version 연결
- 질의 관점 schema validation API
- 관계 방향·필수 속성·식별자 중복 검사

검증:

- CiP-DMD와 설비 정비 이력 두 도메인이 같은 Schema DSL로 표현된다.
- 대표 질문 3개가 각 스키마에서 수동 Cypher로 실행된다.

산출물:

- schema contract
- 두 도메인 schema fixture

### 1-3. 범용 ETL Adapter와 Dry-run

상태: **완료**

목표:

- 업로드 파일을 승인된 매핑에 따라 노드·관계 레코드로 변환한다.

작업:

- CSV·JSON·XLSX·ZIP source adapter
- 정제 규칙: 결측, 타입, 중복, 식별자
- 노드·관계 transform contract
- 매핑 preview
- dry-run과 오류·격리 레코드
- 원본 hash와 lineage 기록

검증:

- 두 도메인에서 동일 ETL entrypoint를 사용한다.
- 잘못된 타입·고아 참조·중복 데이터 fixture가 올바르게 격리된다.

산출물:

- ETL adapter
- dry-run report

### 1-4. Neo4j 적재·무결성·멱등성 강화

상태: **완료**

목표:

- 승인된 데이터만 프로젝트 범위에 안전하게 적재한다.

작업:

- batch/bulk load
- constraint·index 자동 적용
- 원본·변환·적재 count reconciliation
- 고아 노드·끊어진 관계 검사
- 재실행 멱등성
- 실패 시 rollback 또는 실패 상태 유지
- loader/reader 권한 분리

검증:

- 빈 DB 적재와 재적재가 모두 통과한다.
- 재적재 후 불필요한 증가 0건
- 프로젝트 A 질의로 프로젝트 B 데이터가 반환되지 않는다.

산출물:

- load report
- integrity report
- idempotency test

### 1-5. Gold·Blind 평가 프레임워크 일반화

상태: **완료**

목표:

- 프로젝트별 질문·정답·평가 결과를 버전 관리한다.

작업:

- 프로젝트별 Gold 15~20문항
- 결과 snapshot과 evaluation policy
- Blind 질문 분리
- 값 기준·엄격 계약 기준 비교
- 상태 분류 Precision·Recall·F1·혼동행렬
- 실패 유형 taxonomy
- 모델·프롬프트·schema version 기록

검증:

- 같은 평가 실행을 재현할 수 있다.
- alias 차이와 실제 값 오류를 구분한다.
- 질문 상태 분류 혼동행렬이 생성된다.

산출물:

- evaluation runner
- metrics JSON/Markdown
- failure taxonomy

### 1-6. Text-to-Cypher 안전 파이프라인 완결

상태: **완료**

목표:

- 프로젝트별 schema context로 생성·검증·교정·실행한다.

작업:

- schema context·few-shot 동적 주입
- READ 전용·다중 statement 차단
- `EXPLAIN` 문법·schema 검증
- domain value validation
- 자기수정 횟수·timeout 제한
- 빈 결과·차단·실패·확인 필요 상태 계약
- 결과 formatter와 evidence contract

검증:

- Gold 100% 실행
- Blind 실행 성공률·결과 정확도 측정
- 쓰기 차단 100%
- 미검증 쿼리 실행 0건

산출물:

- Agent workflow
- query service contract
- 회귀 테스트

### 1-7. Project Registry·데이터 연결·Readiness

목표:

- 새 프로젝트가 질의 가능한 상태가 되는 전체 백엔드 lifecycle을 구현한다.

작업:

- 프로젝트 CRUD·activate/archive
- 파일 업로드와 외부 Neo4j connector
- Neo4j schema introspection
- 상태 머신:
  `draft → profiling → mapping_review → loading → validating →
  evaluation_required → ready`
- schema·prompt·Gold·평가 버전 연결
- readiness API
- 프로젝트별 서비스 bundle

검증:

- 새 파일 프로젝트와 기존 Neo4j 프로젝트를 각각 등록한다.
- 준비되지 않은 프로젝트의 자유 질의를 차단한다.
- 프로젝트 전환 시 schema context와 평가 기준이 함께 바뀐다.

산출물:

- Registry API
- connector API
- readiness report

### 1-8. 백엔드 Release Gate와 문서화

목표:

- 1단계 전체를 재현 가능한 릴리스로 고정한다.

작업:

- 전체 단위·통합·보안 회귀
- Docker Compose 또는 원커맨드 실행
- API schema와 error contract 정리
- Trouble Shooting과 제한사항
- 데이터·스키마·ETL·평가 lineage 문서

검증:

- fresh environment E2E 통과
- CI 통과
- 비밀정보 노출 0건
- P3 필수 요구사항 추적표 100%

릴리스 Gate:

- 이 단계가 통과하기 전 P4 확장 기능을 핵심 경로에 병합하지 않는다.

---

## 2단계 — 다중 프로젝트 엔터프라이즈 UI 기능 기준선

이 단계의 Streamlit 중심 구현은 기능·구조 기준선으로 보존한다.
최종 사용자 제품 Surface 결정과 배포 품질 판정은 2.9단계가 대체한다.

### 2-1. 정보구조·디자인 시스템

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-1-information-architecture.md`](./enterprise-stage2-1-information-architecture.md)

목표:

- Streamlit 중심의 다중 프로젝트 사내 업무 프로토타입과 공통 UI 계약을 구축한다.
- 이 단계의 결과를 최종 사용자 제품으로 자동 간주하지 않고 2.9에서 Surface를 재결정한다.

작업:

- Home, Projects, Data Sources, Pipeline, Query Studio, Graph Explorer,
  Dashboard, Evaluations, Approval Queue, Audit Logs, Admin 구조 정의
- 공통 색상·타이포·spacing·status·card·table·empty/error/loading 상태 정의
- 역할별 메뉴와 접근 권한 정의
- React 제품 UI와 Streamlit 기능 중복·경계를 명확히 한다.

참고:

- `CodeGraph`: 프로젝트·분석 진행 UX
- `NeoDash`: 대시보드 정보구조

검증:

- 핵심 사용자 여정 wireflow 검토
- 모든 기능에 정상·로딩·빈 상태·오류 화면 존재

### 2-2. Home·Projects Workspace

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-2-home-projects.md`](./enterprise-stage2-2-home-projects.md)

목표:

- 사용자가 현재 프로젝트와 시스템 상태를 즉시 이해하고 전환한다.

작업:

- 제품 랜딩과 핵심 가치
- 최근 프로젝트·즐겨찾기·상태
- 프로젝트 생성 Wizard
- 명시적 프로젝트 전환
- 프로젝트별 대화·필터·평가 컨텍스트 복원
- `ready`가 아닌 프로젝트 상태와 다음 행동 표시

검증:

- 프로젝트 전환 후 이전 프로젝트 데이터가 남지 않는다.
- 새 프로젝트 생성 후 Data Sources로 자연스럽게 이동한다.

### 2-3. Data Sources·Pipeline UX

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-3-data-pipeline.md`](./enterprise-stage2-3-data-pipeline.md)

목표:

- 데이터 등록부터 적재·검증까지 진행 과정을 시각적으로 제공한다.

작업:

- drag-and-drop 업로드
- Neo4j 연결 테스트
- 데이터 프로파일·샘플·품질 경고
- 노드·관계 매핑 검토·승인
- ETL dry-run
- 단계별 progress·처리량·경과시간·로그
- 취소·재시도·실패 재개
- 무결성 결과와 readiness

참고:

- `genai-stack`: Loader와 적재 통계
- `graphrag-contract-review`: ingestion→graph→query 흐름

검증:

- 작은 fixture와 실패 fixture를 브라우저에서 업로드한다.
- 새로고침 후 Job 상태가 유지된다.
- 승인 없이는 실제 적재 버튼이 활성화되지 않는다.

### 2-4. Query Studio

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-4-query-studio.md`](./enterprise-stage2-4-query-studio.md)

목표:

- 질문과 모든 근거를 하나의 연속된 화면에서 확인한다.

작업:

- 프로젝트·데이터·schema version 표시
- 자연어 질문과 streaming 상태
- 자연어 답변
- 결과표·다운로드
- 생성·수정 Cypher
- 관계 경로
- validation·self-correction trace
- 피드백·대화 저장·재실행

참고:

- `ps-genai-agents`: 답변 직하 Cypher·raw result·subtask

검증:

- `success`, `empty`, `blocked`, `failed`, `needs_clarification` UI 회귀
- 질문→답변→근거 확인이 탭 이동 없이 가능

### 2-5. Interactive Graph Explorer

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-5-interactive-graph-explorer.md`](./enterprise-stage2-5-interactive-graph-explorer.md)

목표:

- Graphviz 정적 그림을 업무용 탐색 화면으로 교체한다.

작업:

- 1차 후보: `neo4j-viz`의 공식 NVL Streamlit widget
- 대안·비교: `yfiles-graphs-for-streamlit`
- pan, zoom, drag, select, search
- neighborhood 1~3 hop expand
- layout switch
- 노드·관계 상세 패널
- path highlight와 filter
- 대규모 결과 제한·sampling·truncation 고지

검증:

- 노드 선택 결과가 Python 상태와 양방향 동기화된다.
- 프로젝트 범위 밖 노드를 탐색할 수 없다.
- 1천·1만 노드 성능 경계를 기록한다.

### 2-6. Dashboard·Evaluations

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-6-dashboard-evaluations.md`](./enterprise-stage2-6-dashboard-evaluations.md)

목표:

- 데이터·그래프·Agent 품질·운영 상태를 함께 보여준다.

작업:

- NeoDash 패턴의 KPI 카드·전역 필터·차트·테이블
- 노드·관계·무결성·최근 ETL
- 실행 성공률·결과 정확도·F1·혼동행렬
- provider·prompt·self-correction 비교
- latency·token·cost·error
- 도메인 전문가 피드백

검증:

- 대시보드 수치와 원본 metrics·audit 집계가 일치한다.
- 프로젝트 필터 변경 시 모든 위젯이 같은 범위를 사용한다.

### 2-7. History·Audit·운영 상태

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-7-history-audit-operations.md`](./enterprise-stage2-7-history-audit-operations.md)

목표:

- 사용자가 과거 질문과 데이터 작업을 재현한다.

작업:

- 프로젝트별 대화 검색·재열기·재실행
- ETL·질의·평가 이벤트 타임라인
- run detail과 Cypher·모델·schema version
- 다운로드 가능한 감사 증적
- 연결·서비스 상태 진단

검증:

- 하나의 run_id로 질문부터 결과까지 재구성한다.
- 민감한 prompt·credential은 감사 화면에 노출하지 않는다.

### 2-8. 엔터프라이즈 UI 품질 Gate

상태: **기술적 기준선 통과, 제품화 Gate 재개방 (2026-07-28)**

재개방 사유:

- 자동 테스트·CI·지정된 작업공간 순회는 통과했지만,
  Streamlit 자동 멀티페이지 내비게이션의 빈 화면을 놓쳤다.
- React와 Streamlit의 제품 역할이 중복되고 개발·평가 기능이 사용자 UI에 노출됐다.
- 따라서 기존 완료 판정은 구조·기능 기준선으로만 유효하며,
  최종 사용자 서비스 완료 판정은 2.9에서 다시 수행한다.

검증 기록:

- [`enterprise-stage2-8-ui-quality-gate.md`](./enterprise-stage2-8-ui-quality-gate.md)

목표:

- 발표 데모가 아닌 사내 운영 프로토타입 품질을 확보한다.

작업:

- 반응형·접근성·한국어/영어
- RBAC에 따른 메뉴·행동 제한
- skeleton·progress·toast·error recovery
- 브라우저 E2E
- 주요 화면 screenshot regression
- Streamlit rerun·session_state·cache 안정성

검증:

- Viewer/Analyst/Expert/Steward/Admin 핵심 여정 통과
- CiP-DMD와 두 번째 도메인 E2E 통과
- 서비스 장애 시 진단·안전 fallback이 보인다.

릴리스 Gate:

- 프로젝트 생성→적재→평가→질의→근거 탐색의 기술적 기준선을 확보한다.
- **기존 기준선 통과 (2026-07-28)**:
  [`enterprise-stage2-release.md`](./enterprise-stage2-release.md)
- **최종 사용자 서비스 릴리스는 미통과**이며 2.9 Gate가 이를 대체한다.

---

## 2.9단계 — P3 사용자 서비스 제품화·완성

상태: **작업 예정 — 3단계 진입 차단 Gate**

### 2.9 추진 배경

현재 구현은 백엔드·데이터·Text-to-Cypher·평가 측면에서는 강한 기준선을
갖췄지만, 사용자 화면은 다음 성격이 혼합되어 있다.

- React 제품 데모
- Streamlit 내부 업무 프로토타입
- provider·model·Gold 평가 개발 콘솔
- 역할·권한 설계 미리보기
- 3단계 예정 기능의 foundation 화면

실제 브라우저 감사에서는 다음 문제가 확인됐다.

- `frontend/pages/`가 Streamlit 자동 멀티페이지 폴더로 인식되어
  `stSidebarNavItems`에 내부 파일명이 노출된다.
- 해당 자동 메뉴를 클릭하면 렌더 함수가 호출되지 않아 본문이 없는 흰 화면이 나타난다.
- 자동 메뉴와 커스텀 작업공간 메뉴가 동시에 존재한다.
- `OpenAI 키가 없으면 Vertex AI Gemini를 자동 사용합니다`,
  `Gold Question 데모`, `역할 미리보기` 같은 개발·평가 문구가 사용자 UI에 노출된다.
- `p3-stage-badge`가 사용자 업무 상태 대신 구현 단계·foundation 상태를 표시한다.
- 긴 프로젝트명과 일부 상태 정보가 제한된 컴포넌트에서 충분히 식별되지 않는다.
- React와 Streamlit이 유사 기능을 서로 다른 메뉴·언어·레이아웃으로 구현한다.
- 기존 Gate는 HTTP 상태·예외·지정된 경로를 중심으로 검증해,
  화면에 실제 표시된 모든 링크와 의미 있는 본문을 확인하지 못했다.

2.9의 목적은 기능을 더 추가하는 것이 아니라, 현재 P3 기능을 하나의 이해 가능한
서비스로 정리하고 사용자 기준으로 완료하는 것이다.

### 2.9 공통 원칙

- React를 최종 사용자용 단일 제품 UI로 사용한다.
- Streamlit은 개발·평가·데이터·운영 담당자의 내부 콘솔로 한정한다.
- FastAPI를 프로젝트·질의·평가·상태의 source of truth로 유지한다.
- Neo4j Browser는 개발·DB 운영자 도구이며 일반 사용자에게 노출하지 않는다.
- 제품 UI에서는 개발 단계, provider fallback, API 키, 회귀평가 모드를 설명하지 않는다.
- 미구현 기능은 foundation 화면으로 일반 사용자 메뉴에 노출하지 않는다.
- 각 하위 단계는 순서대로 진행하며 앞 단계 Gate 실패 시 다음 단계로 넘어가지 않는다.

### 2.9-1. 단일 제품 UI 결정과 Surface 경계 고정

상태: **구현·검증 완료 (2026-07-28)**

검증 기록:

- [`enterprise-stage2-9-1-surface-boundary.md`](./enterprise-stage2-9-1-surface-boundary.md)

목적:

- “어느 화면이 실제 제품인가”를 하나로 결정하고 두 프론트엔드의 책임 중복을 제거한다.

현재 문제:

- React와 Streamlit이 모두 Projects, Query, Graph, 데이터·운영 기능을 제공한다.
- 같은 프로젝트 상태와 결과가 서로 다른 메뉴·문구·레이아웃으로 표현된다.
- 개발자가 어느 UI를 먼저 고쳐야 하는지, 발표에서 무엇을 제품으로 보여줄지 불명확하다.

제품 결정:

| Surface | 최종 책임 |
|---|---|
| React `:3000` | 최종 사용자 제품 UI·발표·포트폴리오 기본 화면 |
| Streamlit `:8501` | 내부 데이터·평가·운영·장애 진단 콘솔 |
| FastAPI `:8000` | 두 클라이언트가 사용하는 공통 업무 계약 |
| Neo4j `:7474` | 개발·DB 운영 진단 도구 |

작업:

- Architecture Decision Record에 Surface 결정과 제외 범위를 기록한다.
- React 제품 메뉴를 `Projects → Query Studio → Evidence/Graph → History → Review`로 고정한다.
- Data Sources·Pipeline·Evaluations·Audit·Admin은 내부 콘솔 책임으로 분류한다.
- 동일 상태명, 프로젝트명, 권한명, 질의 상태 계약을 FastAPI 기준으로 통일한다.
- README·실행 스크립트·발표 문서에서 React를 제품 기본 진입점으로 안내한다.
- Streamlit은 `Internal Console`임을 명시하고 외부 제품 랜딩 역할을 제거한다.
- 중복 구현된 기능은 즉시 삭제하지 않더라도 소유 Surface를 정하고
  다른 Surface에서는 링크·읽기 전용 요약·리디렉션 중 하나로 축소한다.

검증:

- 문서와 실행 안내에서 사용자 제품 진입점이 하나만 존재한다.
- 제품 메뉴와 내부 콘솔 메뉴의 중복 책임이 표로 설명된다.
- React와 Streamlit에서 같은 프로젝트의 ID·readiness·질의 상태가 일치한다.
- 발표 사용자 여정이 React만으로 완결된다.

산출물:

- 제품 Surface ADR
- React·Streamlit 화면 책임표
- 공통 용어·상태 사전
- 제품·내부 콘솔 URL map

완료 Gate:

- 단일 제품 UI 결정이 코드·문서·실행 안내에 모두 반영되어야 2.9-2로 이동한다.

### 2.9-2. Streamlit 자동 페이지 충돌 제거

상태: **다음 진행 단계**

목적:

- Streamlit 내비게이션을 하나로 통일하고 어떤 메뉴를 클릭해도 빈 화면이 나오지 않게 한다.

현재 문제:

- `frontend/pages/`가 Streamlit의 특수 `pages` 폴더로 자동 인식된다.
- `streamlit app`, `audit`, `dashboard`, `projects` 같은 내부 파일명이
  `stSidebarNavItems`에 자동 노출된다.
- 모듈 파일은 렌더 함수만 정의하므로 직접 실행 시 본문이 비어 있다.
- 자동 내비게이션과 `render_sidebar_navigation()`이 동시에 표시된다.

작업:

- 기본안으로 `frontend/pages/`를 `frontend/workspaces/` 또는
  `frontend/views/`로 이동하고 모든 import·테스트·문서를 갱신한다.
- `.streamlit/config.toml`에 `client.showSidebarNavigation = false`를 설정해
  자동 사이드바 내비게이션을 방어적으로 차단한다.
- 장기적으로 `st.navigation`·`st.Page`로 전환할 경우 커스텀 라우터를 제거하고
  하나의 공식 내비게이션만 사용한다. 두 방식을 동시에 유지하지 않는다.
- `/projects`, `/audit` 같은 이전 자동 경로는 내부 콘솔 시작 화면으로
  리디렉션하거나 명시적 404·안내 화면을 제공한다.
- 자동 생성된 프레임워크 파일명과 내부 Python 모듈명이 UI에 나타나지 않게 한다.
- 내비게이션·URL query parameter·session state의 책임을 하나의 모듈로 제한한다.

검증:

- `[data-testid="stSidebarNavItems"]`가 숨겨지거나 의도한 단일 메뉴만 포함한다.
- 사이드바 내비게이션 그룹이 정확히 하나다.
- 화면에 표시된 모든 메뉴를 클릭하고 각 화면의 고유 제목과 본문을 확인한다.
- 클릭 후 본문 0글자, 흰 화면, 프레임워크 파일명 노출이 0건이다.
- 새로고침·딥링크·뒤로가기 후에도 같은 작업공간과 프로젝트가 유지된다.
- Streamlit 버전 변경 시 충돌을 감지하는 구조 회귀 테스트가 존재한다.

산출물:

- 이동된 내부 화면 모듈
- 단일 Streamlit navigation contract
- 모든 표시 메뉴 브라우저 E2E
- 기존 자동 경로 migration 안내

완료 Gate:

- 자동·커스텀 중복 메뉴와 빈 화면이 모두 제거되어야 2.9-3으로 이동한다.

### 2.9-3. 개발·평가 기능 격리

상태: **2.9-2 이후 진행**

목적:

- 최종 사용자 화면에서 개발·회귀평가·환경진단 기능을 제거하고
  필요한 담당자만 내부 콘솔에서 접근하게 한다.

현재 문제:

- 생성 모드에서 `auto`, `gemini`, `gold`, `openai`를 직접 선택한다.
- API 키 존재 여부와 provider fallback 정책이 UI 설명으로 노출된다.
- `역할 미리보기`가 실제 로그인·권한처럼 보인다.
- Gold Question 회귀평가와 추천 질문의 경계가 불분명하다.
- `Stage 3-6 준비`, `foundation`, 실제 모델·transport 정보가 제품 화면에 나타난다.

작업:

- `P3_UI_MODE=production|demo|development` 런타임 프로필을 도입한다.
- production·demo에서는 provider·model 선택, API 키 설명,
  transport·fallback 정보와 역할 시뮬레이션을 렌더링하지 않는다.
- provider·model은 서버 설정 또는 내부 Admin/Diagnostics에서만 관리한다.
- Gold·Blind 실행은 Evaluations 내부 콘솔로 이동한다.
- 제품 화면의 Gold 예시는 `추천 질문`으로 표현하고 회귀 정답셋이라는 설명을 제거한다.
- 역할은 인증 전까지 고정된 demo principal 또는 서버 전달 role을 사용하고,
  role preview는 development에서만 허용한다.
- `p3-stage-badge`와 개발 단계 표시는 제거하고 사용자 업무 상태
  (`질의 가능`, `평가 필요`, `매핑 필요`, `검토 대기`)로 교체한다.
- Approval Queue·Admin처럼 미완성인 화면은 production·demo 메뉴에서 숨긴다.
- 비밀정보·환경변수·내부 모델명이 사용자 응답·HTML·감사 다운로드에
  노출되지 않는지 점검한다.

배포 금지 문구 예시:

```text
OpenAI 키
Gemini를 자동 사용
Gold Question 데모
역할 미리보기
Stage 3-
foundation
실제 연결:
transport
```

검증:

- production·demo 브라우저 DOM에 배포 금지 문구가 0건이다.
- development에서만 내부 설정과 진단을 볼 수 있다.
- 일반 사용자가 provider나 model을 변경할 수 없다.
- 권한 없는 사용자가 전문가 검토·데이터 적재·평가 실행을 수행할 수 없다.
- 추천 질문을 클릭해도 Gold 평가 내부 구조가 노출되지 않는다.
- secret·환경변수·credential 정적·동적 검사 통과

산출물:

- 런타임 프로필 설정
- 제품 UI·내부 콘솔 feature matrix
- 배포 금지 문구 검사
- provider·role·evaluation 내부 설정 화면

완료 Gate:

- production·demo가 개발자 설명 없이 사용자 업무만 표현해야 2.9-4로 이동한다.

### 2.9-4. 핵심 RCA 사용자 여정 완성

상태: **2.9-3 이후 진행**

목적:

- 새로운 기능을 추가하지 않고 현재 P3의 핵심 가치를 하나의 짧고 일관된
  사용자 여정으로 완성한다.

기준 여정:

```text
프로젝트 선택
→ 자연어 RCA 질문
→ 실행·검증 상태
→ 자연어 답변과 결과표
→ 생성 Cypher와 안전 검증
→ 관계 경로·노드 근거
→ 결과 저장 또는 전문가 검토
→ History에서 재열기
```

작업:

- React 제품 홈 또는 Projects에서 현재 프로젝트와 `다음 행동`을 명확히 표시한다.
- 긴 프로젝트명은 전체 이름 확인, tooltip 또는 별도 제목 영역을 제공한다.
- Query Studio의 기본 정보 순서를 `답변 → 결과표 → 근거 경로 → Cypher·검증`으로 고정한다.
- 답변과 Evidence가 같은 조회 결과라는 시각적 연결과 anchor를 제공한다.
- Graph Explorer에서 선택한 경로를 Query 결과로 돌아가 확인할 수 있게 한다.
- 전송 중 중복 제출을 차단하고 완료 후 입력을 초기화한다.
- 추천 질문은 입력창 미리보기 후 사용자가 실행하도록 한다.
- `success`, `empty`, `blocked`, `failed`, `needs_clarification`에
  서로 다른 설명·아이콘·다음 행동을 제공한다.
- 쓰기 요청은 `요청 차단`, 실행되지 않은 이유, 가능한 읽기 전용 대안을 표시한다.
- 전문가 검토는 권한 있는 사용자에게만 편집 가능하게 제공하고,
  일반 사용자에게는 판정 상태만 표시한다.
- History 빈 상태·첫 질문 CTA·재열기·재실행을 완성한다.
- 제품 화면의 언어를 기본 한국어로 통일한다. 영어를 지원할 경우 모든 제품
  문구를 번역 리소스로 이전한 뒤 화면 단위로 완전 전환한다.
- Home·Query·Graph의 정보 밀도를 줄이고 한 화면의 primary action을 하나로 제한한다.

필수 사용자 시나리오:

1. 준비된 프로젝트 선택 후 대표 RCA 질문 성공
2. 존재하지 않는 엔티티 질문의 빈 결과
3. 삭제·수정 의도 질문의 읽기 전용 차단
4. 모호한 질문의 확인 요청
5. 모델·API·Neo4j 장애 시 복구 가능한 오류 안내
6. 프로젝트 전환 후 이전 결과·대화가 섞이지 않음
7. 답변→Evidence→Graph→History 재열기
8. 긴 프로젝트명·긴 질문·다수 결과에서도 핵심 행동 유지

검증:

- 위 시나리오를 실제 브라우저에서 사용자 입력으로 수행한다.
- 각 단계에서 현재 상태와 다음 행동을 사용자가 확인할 수 있다.
- 답변·표·Cypher·경로가 동일한 run_id와 프로젝트를 사용한다.
- 사용자 여정 중 빈 화면, dead end, 중복 CTA, 개발용 설명이 0건이다.
- 390px·768px·1280px·1440px에서 가로 overflow와 조작 불가가 없다.
- 프로젝트 전환·새로고침·뒤로가기 후 컨텍스트 일치

산출물:

- 핵심 RCA UX flow와 화면별 acceptance criteria
- 제품 문구 사전
- 역할별 행동 matrix
- 성공·빈 결과·차단·오류·확인 필요 E2E
- 데스크톱·모바일 시각 기준선

완료 Gate:

- 대표 사용자가 설명 없이 핵심 여정을 끝까지 수행해야 2.9-5로 이동한다.

### 2.9-5. 실제 사용자 기준 Release Gate

상태: **2.9-4 이후 진행**

목적:

- 테스트 개수와 예외 없음이 아니라, 실제 사용 가능한 제품인지 자동·수동으로 판정한다.

작업:

- 기존 `release_check.sh`와 별도로 또는 그 안에 제품 사용자 Gate를 추가한다.
- React 제품 메뉴와 Streamlit 내부 콘솔의 보이는 링크·버튼 목록을 수집한다.
- 모든 표시 내비게이션을 클릭해 고유 heading·본문·상태·CTA 존재를 검증한다.
- 제품 DOM에서 배포 금지 문구와 내부 파일명·프레임워크 페이지명을 검사한다.
- 주요 화면의 desktop·tablet·mobile screenshot regression을 고정한다.
- 키보드 tab 순서, focus-visible, form label, 색상 대비를 검사한다.
- 긴 이름·빈 데이터·대량 결과·오류 fixture로 시각 회귀를 수행한다.
- 프로젝트 전환, 추천 질문, 질문 전송, 입력 초기화, Evidence 이동,
  Graph 경로, History 재열기, 쓰기 차단을 Playwright로 자동화한다.
- production·demo·development 프로필별 메뉴와 기능 노출 차이를 검증한다.
- fresh checkout에서 제품 스택을 실행하고 README의 사용자 절차만으로 재현한다.
- 실제 사용자 1인 이상이 사전 설명 없이 대표 여정을 수행하고
  막힌 지점·오해한 문구·불필요한 요소를 기록한다.

필수 자동 검사:

- 제품 기본 진입점 1개
- Streamlit 내비게이션 그룹 1개
- 표시 링크 클릭 성공률 100%
- 표시 대상의 빈 본문 0건
- production·demo 배포 금지 문구 0건
- 브라우저 console error·Streamlit exception 0건
- 프로젝트 컨텍스트 불일치 0건
- 승인되지 않은 쓰기 실행 0건
- 390·768·1280·1440px 가로 overflow 0건
- 핵심 시나리오 E2E 100%

수동 제품 검토 질문:

- 처음 본 사용자가 이 서비스의 목적을 10초 안에 이해하는가?
- 첫 화면에서 무엇을 눌러야 하는지 명확한가?
- 답변의 근거와 안전 검증을 설명 없이 찾을 수 있는가?
- 개발자만 이해하는 단어·단계·환경 설명이 남아 있지 않은가?
- 실패·차단 상태에서 사용자가 다음에 할 수 있는 행동이 있는가?
- React와 Streamlit이 서로 다른 제품처럼 경쟁하지 않는가?

산출물:

- 제품 Release Gate 스크립트
- 브라우저·접근성·시각 회귀 결과
- 배포 프로필별 DOM 검사 결과
- 사용자 여정 검토 기록
- 2.9 완료 보고서와 제한사항

최종 Gate:

- 모든 필수 자동 검사 통과
- 핵심 사용자 여정 수동 검토 통과
- P3 최종 사용자 서비스 판정 `READY`
- 기존 `refactor-final-audit-and-phase3-readiness.md`의 준비도 판정을
  새 2.9 결과로 대체
- 이 Gate가 통과된 커밋·태그 이후에만 3-1 작업 시작

---

## 3단계 — 프로젝트 4 차용 Agentic AI 버전

진입 상태: **HOLD — 2.9-5 최종 Gate 통과 필요**

### 3-1. LangGraph State와 Checkpoint 재설계

목표:

- 라우팅·Tool·권고·HITL을 수용하는 공통 상태 모델을 만든다.

작업:

- `organization/user/project/run` context
- routing, schema, tool trace, evidence, recommendation, approval state
- PostgreSQL 또는 호환 checkpointer
- 재시작 후 run resume

검증:

- 프로세스 재시작 후 승인 대기 run을 재개한다.
- 상태 schema version migration 테스트

### 3-2. 자연어 프로젝트 Router

목표:

- 프로젝트를 지정하지 않은 질문만 자동 라우팅한다.

작업:

- 프로젝트 설명·schema summary 검색
- LLM/embedding 기반 후보 분류
- confidence threshold
- 낮은 신뢰도 `needs_clarification`
- 특정 프로젝트 선택 시 router bypass
- routing trace와 평가셋

검증:

- 다중 도메인 질문셋 Top-1·Top-k 평가
- 오분류 시 엉뚱한 DB를 실행하지 않는다.
- 수동 선택 모드에서는 자동 전환이 발생하지 않는다.

### 3-3. Tool Registry

목표:

- 기능을 독립 Tool로 등록하고 Agent가 필요한 Tool만 호출한다.

작업:

- 공통 Tool interface
- 입력·출력 schema
- 권한·timeout·retry·error taxonomy
- graph query, RCA, schema lookup, ETL status, evaluation Tool
- Tool별 audit middleware

검증:

- schema validation 실패 입력 차단
- timeout·재시도·권한 실패 테스트
- Tool 호출 trace 재현

### 3-4. 문서 RAG Tool

목표:

- 그래프 사실과 설비·공정·품질 문서 지식을 결합한다.

작업:

- 문서 ingestion·chunk·metadata·version
- `search_docs_tool`
- graph evidence와 document evidence 분리
- source citation
- 문서 접근 권한

검증:

- 문서 근거가 없는 답변에서 출처를 생성하지 않는다.
- 오래된 문서 버전과 현재 버전을 구분한다.

### 3-5. RCA 권고 생성

목표:

- 조회 결과를 근거로 검토 가능한 조치 후보를 제시한다.

작업:

- `recommend_action_tool`
- 근거·위험도·우선순위·담당자·추가 확인사항
- SOP와 그래프 근거 결합
- 인과 확정·자동 제어 금지 문구
- 심각도·불확실성 gate

검증:

- 근거 없는 권고 차단
- 전문가 타당성·과잉 확신 평가

### 3-6. HITL Interrupt와 Approval Queue

목표:

- 고위험 판단과 변경 작업을 승인 대기 후 재개한다.

작업:

- LangGraph Interrupt
- 승인·반려·수정 요청
- 승인자·권한·기한
- 재개·만료·취소
- UI Approval Queue
- schema·load·recommendation·notification 승인 유형

검증:

- 승인 전 side effect 0건
- 동일 승인 중복 처리 방지
- 반려·수정 후 올바른 상태로 재개

### 3-7. 알림 Tool과 Adapter

목표:

- 승인된 심각 이벤트를 외부 채널로 전달한다.

작업:

- `notify_tool`
- webhook 공통 계약
- Slack/Teams/n8n adapter
- idempotency key·rate limit·retry
- 발송 결과와 실패 사유

검증:

- 승인 없는 알림 발송 0건
- 동일 이벤트 중복 발송 방지
- sandbox webhook E2E

### 3-8. 통합 감사로그와 상태 UI

목표:

- 질문→라우팅→Tool→Cypher→권고→승인→알림을 하나의 run으로 추적한다.

작업:

- append-only event schema
- run timeline
- model/prompt/schema/data version
- 결과 hash·latency·token·cost
- 관리자 검색·필터·내보내기
- 보존·마스킹 정책

검증:

- 임의 run을 UI에서 완전 재구성
- 감사 이벤트 누락·순서·중복 검사

### 3-9. 판단 품질 평가

목표:

- Cypher 정확도를 넘어 RCA·권고·라우팅·HITL 품질을 평가한다.

작업:

- router confusion matrix
- Tool selection accuracy
- evidence completeness
- recommendation expert rubric
- approval·수정·반려율
- alert precision·recall
- 모델·prompt 비교 실험

검증:

- 자동 지표와 전문가 평가를 분리한다.
- 표본 수와 신뢰 한계를 함께 표시한다.

### 3-10. 이상감지 Tool(선택)

목표:

- 적합한 시계열 데이터가 있는 프로젝트에서만 능동형 RCA를 제공한다.

작업:

- 통계·ML anomaly detector
- event normalization
- anomaly→graph RCA→document RAG→recommendation 흐름
- drift·threshold 설정

검증:

- 시간 순서가 보존된 train/test 평가
- alert Precision·Recall·F1
- 데이터가 부적합한 프로젝트에서는 Tool 비활성화

### 3-11. 보안·운영·최종 E2E

목표:

- Agentic 기능을 실제 사내 플랫폼 경계에서 검증한다.

작업:

- SSO/OIDC·RBAC
- 프로젝트/DB 레벨 격리
- secret manager
- rate limit·timeout·circuit breaker
- 관측성·backup·restore
- CI/CD와 운영 runbook

최종 E2E 시나리오:

1. 새 도메인 프로젝트 생성
2. 데이터 업로드 또는 Neo4j 연결
3. 매핑 승인과 ETL
4. Gold 평가와 `ready` 전환
5. 프로젝트 미지정 질문 자동 라우팅
6. Graph·문서 Tool 실행
7. RCA와 권고 생성
8. 고위험 권고 Interrupt
9. 승인 후 알림
10. 전체 감사로그 재현

최종 Gate:

- P3 필수 기능 추적률 100%
- 두 도메인 재적용 E2E
- 자동 라우팅과 수동 프로젝트 모드 모두 검증
- 승인 없는 write·알림 0건
- 프로젝트 간 데이터 누출 0건
- CI·보안·브라우저 E2E 통과

---

## 4. 단계 간 의존성

```text
1-1 → 1-2 → 1-3 → 1-4
                 ├→ 1-5 → 1-6
                 └→ 1-7
                       ↓
                     1-8
                       ↓
2-1 → 2-2 → 2-3 → 2-4 → 2-5 → 2-6 → 2-7 → 2-8
                                                       ↓
2.9-1 → 2.9-2 → 2.9-3 → 2.9-4 → 2.9-5
                                          ↓
3-1 → 3-2 → 3-3 → 3-4 → 3-5 → 3-6 → 3-7 → 3-8 → 3-9
                                                       ├→ 3-10
                                                       └→ 3-11
```

## 5. 범위 관리 원칙

- 1단계는 프로젝트 3 채점 기준이므로 최우선이다.
- 2단계는 다중 프로젝트 업무 기능과 UI 기준선을 구축하는 단계다.
- 2.9단계는 기능 추가보다 삭제·격리·통합·사용자 검증을 우선하는 제품 완성 단계다.
- React는 최종 사용자 제품, Streamlit은 내부 콘솔이라는 경계를 유지한다.
- 3단계는 2.9 최종 Gate 이후 P3를 훼손하지 않는 별도 확장 트랙으로 진행한다.
- 테스트 수·파일 크기·HTTP 200·예외 0건을 제품 완료의 대리 지표로 사용하지 않는다.
- 보이는 모든 메뉴와 링크가 실제 사용자에게 의미 있는 화면으로 연결되어야 한다.
- 이상감지, Text2SQL, 다채널 알림은 데이터·일정에 따라 선택한다.
- 라우터가 틀렸을 때 자동 실행하는 것보다 확인 질문으로 멈추는 것을 우선한다.
- 새로운 도메인마다 Gold 질의셋을 자동 생성했다고 주장하지 않는다.
  LLM 초안 생성은 가능하지만 도메인 전문가 검증을 완료 조건으로 둔다.
