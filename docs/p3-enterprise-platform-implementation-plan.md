# P3 엔터프라이즈 플랫폼 단계별 작업계획서

## 1. 계획 원칙

작업을 세 개의 큰 릴리스로 구분한다.

1. **1단계: P3 필수 기능을 백엔드·평가 기준까지 완성**
2. **2단계: 레퍼런스를 활용해 사내 플랫폼 수준의 Streamlit UI로 발전**
3. **3단계: P4의 Agentic AI 기능을 P3에 통합**

각 세부 단계는 다음 Gate를 통과한 뒤 다음 단계로 이동한다.

- 코드·문서 작성
- 단위·통합 테스트
- 실제 Neo4j 검증
- UI가 포함된 단계는 브라우저 E2E 검증
- 보안·권한·프로젝트 격리 회귀 테스트
- 결과 문서화

현재 구현된 기능은 다시 만드는 대신 계약·테스트로 검증하고,
부족한 부분만 보강한다.

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

## 2단계 — 레퍼런스 기반 엔터프라이즈 Streamlit UI

### 2-1. 정보구조·디자인 시스템

목표:

- Streamlit을 단순 데모가 아닌 다중 프로젝트 사내 플랫폼으로 재구성한다.

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

- 프로젝트 생성→적재→평가→질의→근거 탐색을 UI에서 완결한다.

---

## 3단계 — 프로젝트 4 차용 Agentic AI 버전

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
3-1 → 3-2 → 3-3 → 3-4 → 3-5 → 3-6 → 3-7 → 3-8 → 3-9
                                                       ├→ 3-10
                                                       └→ 3-11
```

## 5. 범위 관리 원칙

- 1단계는 프로젝트 3 채점 기준이므로 최우선이다.
- 2단계는 기능을 숨기지 않고 실제 업무 흐름으로 보여주는 제품화 단계다.
- 3단계는 P3를 훼손하지 않는 별도 확장 트랙이다.
- 이상감지, Text2SQL, 다채널 알림은 데이터·일정에 따라 선택한다.
- 라우터가 틀렸을 때 자동 실행하는 것보다 확인 질문으로 멈추는 것을 우선한다.
- 새로운 도메인마다 Gold 질의셋을 자동 생성했다고 주장하지 않는다.
  LLM 초안 생성은 가능하지만 도메인 전문가 검증을 완료 조건으로 둔다.
