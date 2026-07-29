# 엔터프라이즈 3-1 · LangGraph State와 Checkpoint 재설계

## 1. 상태

- 구현 상태: **IMPLEMENTED · AUTOMATIC VALIDATION PASS**
- 기존 P3 제품 기준선: **보존됨**
- 2.9 실제 사용자 수동 검토: **PENDING 유지**
- 3-2 이후 Agentic AI 기능: **미구현**

3-1 시작 직전 커밋 `e1583f9`는 다음 annotated tag로 원격 저장소에
고정했다.

```text
p3-stage2-9-pre-stage3-v1
```

이 태그는 2.9 자동 Gate를 통과하고 LAN 브라우저 호환성 보강까지 반영된
상태이며, 3단계 변경을 모두 제외한 복원 기준점이다.

복원 확인:

```bash
git switch --detach p3-stage2-9-pre-stage3-v1
```

새 복구 브랜치 생성:

```bash
git switch -c restore-stage2-9 p3-stage2-9-pre-stage3-v1
```

## 2. 진입 결정

기존 계획은 2.9 수동 검토가 끝난 뒤 3단계를 시작하도록 정의했다. 이번
변경은 사용자의 명시적 결정에 따라 다음 안전 경계를 적용해 3-1 foundation만
먼저 구현했다.

- 시작 전 원격 tag로 완전한 복원 지점 고정
- React 제품 동선과 기존 FastAPI 질의 계약 유지
- Router, LlamaIndex RAG, 권고, 실제 HITL 승인 기능은 추가하지 않음
- 공통 상태와 checkpoint 기반만 확장
- 2.9 수동 검토 결과를 `PASS`로 변경하지 않음

## 3. 구현 범위

### 3.1 버전된 공통 Agent 상태

`backend/app/agent/state.py`의 상태 계약을 `state_schema_version=1`로
확장했다.

| 상태 영역 | 현재 값과 다음 단계 용도 |
|---|---|
| `organization` | 조직 ID. 향후 tenant 격리 기준 |
| `user` | 사용자 ID와 역할 |
| `project` | 프로젝트·schema·prompt version |
| `run` | run ID, LangGraph thread ID, 생성·갱신 시각, 실행 상태 |
| `routing` | 현재는 명시적 프로젝트, 3-2 Router가 확장 |
| `schema` | 실행에 사용한 schema와 prompt context |
| `tool_trace` | 현재 graph query Tool trace, 3-3 Tool Registry가 확장 |
| `evidence` | graph/document 근거 분리 구조 |
| `recommendation` | 3-5 권고 결과를 위한 빈 계약 |
| `approval` | 3-6 HITL 승인 상태를 위한 빈 계약 |
| 기존 Cypher state | 질문·statement·검증·교정·records·trace를 그대로 보존 |

기존 코드가 사용하는 `CypherState` 이름은 호환 alias로 유지했다.

### 3.2 상태 migration

`migrate_agent_state()`가 다음 동작을 수행한다.

- `state_schema_version`이 없는 기존 snapshot을 v1으로 승격
- 기존 `metadata.project_id`, schema version, prompt version 보존
- legacy run ID를 입력 상태의 SHA-256 기반으로 결정적으로 생성
- 현재 애플리케이션보다 높은 future schema version은 명시적으로 거부
- recommendation·approval·document evidence 기본 계약 생성

이를 통해 checkpoint schema가 변경되어도 silent data loss 없이 migration
테스트를 추가할 수 있다.

### 3.3 LangGraph graph 경계

기존 흐름:

```text
generate → validate → correct/revalidate → execute
```

변경된 흐름:

```text
guard_question
  → generate
  → validate
  → correct/revalidate
  → execute
  → finalize_run
```

`guard_question`도 graph node가 되어 쓰기 요청·불명확 질문·Gold 미지원 상태가
동일한 state와 checkpoint 계약을 사용한다. `finalize_run`은 terminal status,
tool trace, evidence summary와 run 갱신 시각을 고정한다.

### 3.4 영속 checkpoint

추가 의존성:

```text
langgraph-checkpoint-sqlite==3.1.0
```

기본 runtime 설정:

```text
P3_LANGGRAPH_CHECKPOINT_BACKEND=sqlite
LANGGRAPH_STRICT_MSGPACK=true
```

프로젝트별 기본 저장 위치:

```text
data/processed/projects/<project_id>/langgraph/checkpoints.sqlite3
```

지원 backend:

| 값 | 용도 |
|---|---|
| `sqlite` | 로컬·LAN 데모·단일 인스턴스 기본값 |
| `memory` | 단위·통합 테스트 |
| `disabled` | checkpoint를 사용할 수 없는 특수 환경 |

SQLite는 WAL, normal synchronous, 30초 busy timeout을 적용한다. checkpoint DB
역직렬화는 strict msgpack을 기본으로 활성화한다.

> SQLite는 현재 단일 인스턴스와 데모에 적합한 호환 checkpointer다. 다중 API
> 인스턴스와 운영 고가용성 전환 시에는 동일 `BaseCheckpointSaver` 경계를
> PostgreSQL saver로 교체해야 한다.

### 3.5 재시작 후 run 재개

각 실행은 다음 식별자를 사용한다.

```text
run_id    = 사용자에게 노출되는 공통 실행 ID
thread_id = <run_id>:<agent namespace>
```

primary provider와 Gold fallback은 같은 `run_id`를 공유하되 서로 다른
`thread_id`를 사용한다. 따라서 primary 실패 기록과 fallback 성공 기록이
checkpoint에서 덮어써지지 않는다.

재개 흐름:

```text
실행 → execute 직전 pause → SQLite checkpoint 저장
프로세스 종료
새 Agent·새 SQLite connection 생성
동일 thread_id 조회 → deadline 갱신 → invoke(None) → execute → finalize
```

실제 HITL `interrupt()`와 Approval Queue는 3-6 범위이며 이번 단계에서는
정적 interrupt로 재시작 복구 능력만 검증했다.

## 4. API 계약

기존 `POST /api/v1/query` 응답에 다음 필드가 additive 방식으로 추가됐다.

```text
run_id
thread_id
state_schema_version
organization
user
project
run
routing
schema
recommendation
approval
validation.tool_trace
```

기존 React·Streamlit이 사용하던 `question`, `answer`, `status`, `cypher`,
`rows`, `evidence`, `validation.trace`는 변경하지 않았다.

추가 endpoint:

```text
GET  /api/v1/agent/runs/{run_id}?project_id=<project_id>
POST /api/v1/agent/runs/{run_id}/resume?project_id=<project_id>
```

요청 header로 향후 인증 계층이 전달할 context를 받을 수 있다.

```text
X-Organization-ID
X-User-ID
X-User-Roles: Analyst,Domain Expert
```

header가 없으면 현재 로컬 제품 계약에 맞춰 `local / anonymous`를 사용한다.

## 5. 주요 파일

```text
backend/app/agent/state.py
backend/app/agent/checkpoints.py
backend/app/agent/workflow.py
backend/app/services/query_service.py
backend/app/services/bootstrap.py
backend/app/services/result_formatter.py
backend/app/api/main.py
backend/app/api/schemas.py
tests/test_agent_checkpointing.py
```

UI는 미래의 `paused` 상태를 안전하게 표시할 수 있도록 타입·상태 문구만
추가했다. 현재 기본 질의에서는 interruption을 설정하지 않으므로 기존 제품
동선에 `paused`가 나타나지 않는다.

## 6. 자동 검증

전용 검증:

```bash
.venv/bin/python -m unittest tests.test_agent_checkpointing -v
```

검증 항목:

- 공통 v1 상태의 모든 section 존재
- legacy v0 → v1 migration
- future schema version 거부
- SQLite checkpoint 생성
- execute 직전 pause
- 첫 Agent와 DB connection 종료
- 두 번째 Agent가 동일 DB에서 run 재개
- 실행 중복 없이 terminal success

전체 Python 회귀:

```text
247 tests PASS
```

## 7. 남은 경계

3-1이 완료됐다고 해서 다음 기능이 구현된 것은 아니다.

- 3-2 자연어 Project Router
- 3-3 Tool Registry
- 3-4 LlamaIndex 문서 RAG
- 3-5 RCA 권고
- 3-6 실제 LangGraph Interrupt·Approval Queue
- PostgreSQL production checkpoint
- 계정 인증과 조직 권한 enforcement

또한 2.9의 실제 사용자 수동 검토는 계속 `PENDING`이다. 3-1 구현 결과는
기존 사용자 서비스의 수동 READY 판정을 대신하지 않는다.
