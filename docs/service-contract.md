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
    }
  },
  "validation": {
    "attempts": 1,
    "errors": [],
    "trace": [],
    "elapsed_ms": 90
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
