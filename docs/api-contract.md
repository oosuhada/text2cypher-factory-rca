# FactoryGraph 백엔드 API·오류 계약

## 1. 경계와 버전

- Base path: `/api/v1`
- OpenAPI: `/docs`, `/openapi.json`
- 입력·출력: UTF-8 JSON
- 현재 호환 버전: `backend-v1`
- 자연어 질의와 그래프 탐색은 READ 전용이다.
- 적재 API는 `P3_ENABLE_UI_LOAD=1`과 명시적 프로젝트 확인 문자열이 모두
  있어야 실행된다.

## 2. 핵심 리소스

| 영역 | Method·Path | 정상 응답 | 대표 오류 |
|---|---|---:|---:|
| Liveness | `GET /health/live` | 200 | 500 |
| 프로젝트 | `GET·POST /projects` | 200·201 | 422 |
| 활성 workspace | `POST /projects/{id}/activate` | 200 | 404·422 |
| Readiness | `GET /projects/{id}/readiness` | 200 | 404·500 |
| Ready 승격 | `POST /projects/{id}/readiness/promote` | 200 | 404·409 |
| 파일 profile | `POST /projects/{id}/uploads/profile` | 201 | 404·422 |
| Mapping 승인 | `POST /projects/{id}/mappings/approve` | 200 | 404·422 |
| 그래프 적재 | `POST /projects/{id}/graph/load` | 200 | 403·422·502 |
| Neo4j 검증 | `POST /projects/{id}/connectors/neo4j/validate` | 201 | 404·422·502 |
| Neo4j 승인 | `POST /projects/{id}/connectors/neo4j/{connector}/approve` | 200 | 404·422 |
| 자연어 질의 | `POST /query` | 200 | 404·409·422·502 |
| 스키마 | `GET /graph/schema` | 200 | 404·422 |
| 그래프 검색 | `GET /graph/search` | 200 | 404·422·502 |

전체 요청·응답 schema의 단일 기준은 실행 중 생성되는 OpenAPI 문서다.
`scripts/release_gate.py`가 필수 endpoint와 error schema가 OpenAPI에서
사라지지 않았는지 릴리스마다 검사한다.

## 3. 오류 envelope

모든 애플리케이션 HTTP 오류는 기존 `detail`과 구조화된 `error`를 함께
반환한다.

```json
{
  "detail": "선택한 프로젝트가 readiness gate를 통과하지 못했습니다.",
  "error": {
    "code": "STATE_CONFLICT",
    "category": "state",
    "message": "선택한 프로젝트가 readiness gate를 통과하지 못했습니다.",
    "retryable": false,
    "request_id": "c78fdc5d-2ec0-4868-b8ce-7e36e722f58a"
  }
}
```

모든 응답에는 `X-Request-ID`가 들어간다. 사용자 화면은 `message`를
보여주고, 운영 로그·문의에는 `request_id`를 남긴다.

| HTTP | code | category | retryable | 클라이언트 처리 |
|---:|---|---|---|---|
| 400 | `BAD_REQUEST` | request | false | 입력 수정 |
| 403 | `FORBIDDEN` | authorization | false | 권한·서버 설정 확인 |
| 404 | `NOT_FOUND` | request | false | ID·경로 확인 |
| 409 | `STATE_CONFLICT` | state | false | readiness의 `next_action` 수행 |
| 422 | `VALIDATION_ERROR` | request | false | 필드별 검증 오류 표시 |
| 500 | `INTERNAL_ERROR` | internal | true | request ID 기록 후 재시도 |
| 502 | `UPSTREAM_ERROR` | dependency | true | Neo4j·LLM 상태 확인 |
| 503 | `DEPENDENCY_UNAVAILABLE` | dependency | true | 의존 서비스 복구 후 재시도 |

## 4. 프로젝트 lifecycle 계약

```text
draft → profiling → mapping_review → loading → validating
      → evaluation_required → ready
```

- `failed`, `archived`는 예외·종료 상태다.
- 일반 PATCH로 `ready`를 지정할 수 없다.
- `readiness/promote`만 `evaluation_required → ready`를 수행한다.
- 프로젝트 선택과 질의 가능 여부는 다르다. 준비 전 workspace도 선택할
  수 있지만 `/query`는 HTTP 409로 차단된다.

## 5. 호환성과 변경 규칙

- 필드 추가는 하위 호환 변경이다.
- 기존 필드 제거·타입 변경·상태 의미 변경은 `/api/v2` 또는 명시적
  migration이 필요하다.
- `schema_version`, `source_version`, `prompt_version`,
  `evaluation_version`이 바뀌면 readiness를 다시 통과해야 한다.
- 동일 요청 재시도는 조회에는 안전하다. 파일 profile은 새 upload ID를
  만들며, 실제 그래프 적재는 MERGE·무결성 gate로 중복을 방지한다.
