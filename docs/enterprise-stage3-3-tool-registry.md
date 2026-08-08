# 엔터프라이즈 3-3 · Tool Registry

## 상태

- 구현: **완료**
- 전용 Tool Gate: **PASS**
- 기존 질의 경로의 `graph_query_tool` 전환: **완료**
- 2.9 수동 사용자 검토: **PENDING 유지**
- 3-4 LlamaIndex 문서 RAG: **미구현**

## 목적

Agent가 서비스 구현을 직접 호출하지 않고 공통 Tool 계약을 통해 기능을
실행하도록 한다. 모든 Tool은 같은 입력·출력 검증, 권한, timeout, retry,
오류 분류와 감사 trace를 사용한다.

```text
Project Router
   → Tool Registry
       ├─ graph_query_tool
       ├─ rca_query_tool
       ├─ schema_lookup_tool
       ├─ search_docs_tool
       ├─ etl_status_tool
       └─ evaluation_tool
```

## 공통 계약

`ToolSpec`은 다음 필드를 고정한다.

```text
name
description
input_model
output_model
handler
allowed_roles
timeout_seconds
max_retries
retry_backoff_seconds
```

입력과 출력은 Pydantic model로 검증한다. 입력 schema가 맞지 않으면 handler를
호출하지 않으며, 출력 schema가 맞지 않으면 성공 결과로 반환하지 않는다.

`ToolContext`는 다음 실행 문맥을 모든 Tool에 전달한다.

```text
organization_id
user_id
project_id
run_id
roles
routing
```

## 등록 Tool

| Tool | 역할 | 권한 |
|---|---|---|
| `graph_query_tool` | 기존 read-only Text-to-Cypher 생성·검증·실행 | 모든 Query 사용자 |
| `rca_query_tool` | 현재 evidence-first RCA 질의 경로 | 모든 Query 사용자 |
| `schema_lookup_tool` | 프로젝트 schema·노드·관계·질의 시나리오 조회 | 모든 사용자 |
| `search_docs_tool` | LlamaIndex 프로젝트 문서 검색과 citation | 문서 metadata 권한에 따라 필터 |
| `etl_status_tool` | 프로젝트 lifecycle·source·artifact 상태 조회 | Data Steward, Admin |
| `evaluation_tool` | 최신 평가 metric과 failure 조회 | Analyst, Domain Expert, Data Steward, Admin |

현재 `POST /api/v1/query`의 실제 그래프 질의는 `graph_query_tool`을 통해 실행된다.
primary provider 실패 시 Gold fallback도 같은 Tool invocation과 run ID 안에서
처리한다.

## 오류 분류

| 코드 | category | retryable |
|---|---|---:|
| `TOOL_INPUT_INVALID` | validation | false |
| `TOOL_OUTPUT_INVALID` | contract | false |
| `TOOL_PERMISSION_DENIED` | authorization | false |
| `TOOL_TIMEOUT` | timeout | true |
| `TOOL_NOT_FOUND` | configuration | false |
| `TOOL_DUPLICATE` | configuration | false |
| `TOOL_EXECUTION_FAILED` | execution | true |

Registry는 retryable 오류에 한해서만 `max_retries` 범위 내에서 재시도한다.
입력·출력·권한 오류는 재시도하지 않는다. 현재 내장 Tool의 기본 retry는 0이며,
외부 notification이나 문서 검색 Tool을 추가할 때 Tool별로 명시한다.

## Timeout

각 Tool은 별도 worker에서 실행되고 Tool별 timeout을 적용한다.

- graph/RCA query: Agent timeout + 5초
- schema lookup: 5초
- ETL status: 5초
- evaluation: 5초

Tool timeout은 기존 모델·Neo4j timeout을 대체하지 않는다. 내부 dependency
단위 timeout과 바깥 Tool 전체 timeout을 함께 적용한다.

## 감사 trace

모든 invocation은 다음 필드를 가진다.

```text
invocation_id
tool
status
attempts
elapsed_ms
organization_id
user_id
project_id
run_id
roles
input_sha256
error
```

원문 입력은 Tool audit에 저장하지 않고 SHA-256만 저장한다. 프로젝트별 경로:

```text
data/processed/query_audit.jsonl                # cip-dmd query audit
data/processed/tool_audit.jsonl                 # cip-dmd tool audit
data/processed/projects/<project>/tool_audit.jsonl
```

`graph_query_tool` trace는 기존 LangGraph `validation.tool_trace` 앞에 추가되므로
Router → Registry → 내부 Agent node의 실행 순서를 같은 응답과 checkpoint에서
재현할 수 있다.

## API

등록 Tool과 JSON schema 조회:

```text
GET /api/v1/tools?project_id=<project_id>
```

Tool 직접 실행:

```text
POST /api/v1/tools/{tool_name}/invoke
```

예시 입력:

```json
{
  "project_id": "cip-dmd",
  "input": {
    "include_properties": true,
    "include_scenarios": false
  }
}
```

호출자의 문맥은 다음 header에서 받는다.

```text
X-Organization-ID
X-User-ID
X-User-Roles
X-Run-ID
```

## 검증

전용 단위 테스트:

```bash
.venv/bin/python -m unittest tests.test_tool_registry -v
```

검증 항목:

- 잘못된 입력에서 handler 호출 0회
- 권한 실패에서 handler 호출 0회
- retryable 실행 실패 후 재시도 성공
- timeout 오류 코드와 retryable 계약
- 잘못된 출력의 재시도 금지
- 원문 입력 없는 append-only audit
- registry JSON schema 노출

전용 Gate:

```bash
.venv/bin/python scripts/tool_registry_gate.py
```

기준선:

```text
evaluation/tool_registry_baseline.json
```

Gate는 등록 Tool 6개, 역할 정책, 입력·출력 schema, graph/schema 실제 invocation,
권한 차단, trace 필드, 오류 taxonomy를 고정한다.

## 남은 경계

- Tool 선택을 LLM이 자유롭게 결정하는 범용 planning Agent는 아직 도입하지 않았다.
- 3-4 `search_docs_tool`은 같은 Registry에 추가됐다.
- 3-5 `recommend_action_tool`, 3-7 notification Tool도 같은 Registry에 추가한다.
- 실제 인증은 아직 header 기반 context이며 SSO/OIDC enforcement는 후속 보안 범위다.
- Python worker timeout은 대기 중인 호출을 취소 처리하지만 dependency가 자체적으로
  종료를 지원하지 않으면 백그라운드 작업이 즉시 중단된다는 보장은 없다. 따라서
  모델·Neo4j·HTTP client의 내부 timeout도 계속 필수다.
