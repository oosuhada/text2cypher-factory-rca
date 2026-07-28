# P3 질의 서비스 출력 계약

`QueryService.query(question)`은 Streamlit이 바로 사용할 수 있는 다음 구조를 반환한다.

```json
{
  "question": "완제품 300002의 구성품을 보여줘.",
  "answer": "조회 결과 2행입니다. 첫 번째 결과: ...",
  "status": "success",
  "cypher": "MATCH ...",
  "rows": [],
  "row_count": 2,
  "metadata": {
    "project_id": "cip-dmd",
    "schema_version": "1.1",
    "source_version": "CiP-DMD public release",
    "prompt_version": "text2cypher-v1",
    "evaluation_version": "1.0",
    "prompt_template_sha256": "...",
    "prompt_fingerprint": "..."
  },
  "evidence": {
    "nodes": [],
    "relationships": [],
    "node_count": 0,
    "relationship_count": 0,
    "source_row_count": 2,
    "visualized_row_count": 2,
    "truncated": {
      "nodes": false,
      "relationships": false,
      "rows": false
    },
    "provenance": {
      "project_id": "cip-dmd",
      "schema_version": "1.1",
      "prompt_version": "text2cypher-v1",
      "verified_statement_sha256": "..."
    }
  },
  "validation": {
    "attempts": 1,
    "errors": [],
    "trace": [],
    "elapsed_ms": 90,
    "verified_statement_sha256": "...",
    "execution_verified": true
  },
  "usage": {
    "call_count": 1,
    "input_tokens": 1640,
    "output_tokens": 40,
    "model_elapsed_ms": 1188,
    "estimated_cost_usd": 0.00027
  },
  "caveat": "연결 관계와 집계를 기반으로 한 검토 후보..."
}
```

## 상태

| 상태 | 의미 | UI 처리 |
|---|---|---|
| `success` | 결과 1행 이상 | 답변·표·근거 표시 |
| `empty` | 정상 실행 결과 0행 | 데이터 없음 안내 |
| `blocked` | 쓰기 의도 또는 쓰기 쿼리 | 차단 안내, 실행 결과 숨김 |
| `failed` | 재시도 후에도 검증 실패 | 답변 보류와 오류 표시 |
| `needs_clarification` | 질문 조건 부족 | 추가 조건 요청 |
| `unsupported` | Gold에 등록되지 않은 질문 | Auto/Gemini 모드 전환 안내 |

## 실행 안전 계약

- 생성·교정된 쿼리는 READ 전용 검사, 도메인 값 검사, 프로젝트 범위 검사,
  Neo4j `EXPLAIN` 검증을 순서대로 통과해야 한다.
- 검증을 통과한 정확한 문자열의 SHA-256을 상태에 기록하며, 실행 직전
  현재 쿼리 해시와 일치하지 않으면 `VERIFICATION_REQUIRED`로 중단한다.
- 모델 호출·검증·실행 오류와 전체 처리 제한시간 초과는 예외를 외부로
  노출하지 않고 `failed` 상태와 검증 이력으로 반환한다.
- `metadata`와 `evidence.provenance`는 어떤 프로젝트·스키마·프롬프트로
  결과를 만들었는지 재현할 수 있게 한다.

## 근거 그래프 규칙

- Neo4j 결과에 반환된 ID만 노드로 만든다.
- 실제 스키마 관계인 `ASSEMBLED_FROM`, `UNDERWENT`, `INSTANCE_OF`,
  `RUN_ON`, `CLASSIFIED_AS`, `HAS_MEASUREMENT`, `FOR_PROCESS`만 만든다.
- 집계 행에서 관계 경로가 반환되지 않으면 관계를 추측하지 않는다.
- 시각화는 앞 10개 결과 행, 최대 노드 120개·관계 200개로 제한한다.
- 집계 결과의 ID 목록은 그룹별 최대 5개만 근거 샘플 노드로 표시한다.
- `truncated`와 `visualized_row_count`로 일부만 표시됐음을 UI에 알린다.

## 답변 생성 규칙

- 템플릿 기반이며 별도 LLM을 호출하지 않는다.
- 결과 행 수와 첫 번째 행의 실제 scalar 값만 사용한다.
- 빈 결과에서는 엔티티·원인·유사 ID를 생성하지 않는다.
- RCA 결과에는 인과관계를 확정하지 않는다는 주의 문구를 함께 제공한다.

## HTTP 경계

이 문서는 성공한 질의의 도메인 출력 계약을 정의한다. FastAPI의 상태코드,
구조화된 오류 envelope, request ID와 lifecycle 충돌 처리는
[백엔드 API·오류 계약](./api-contract.md)을 따른다.
