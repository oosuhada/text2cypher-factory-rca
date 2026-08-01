# Blind 평가 실패 유형

| 실패 유형 | 판정 기준 | 우선 확인할 부분 |
|---|---|---|
| `generation_error` | 모델 호출 자체가 실패 | API 키·모델명·네트워크 |
| `empty_query` | 모델이 Cypher를 반환하지 않음 | 출력 형식 지시·응답 파싱 |
| `unsafe_query` | 읽기 전용 위반 쿼리 생성 | Guardrail·프롬프트 |
| `syntax_or_schema_error` | EXPLAIN 문법·스키마 검사 실패 | 라벨·관계·속성·Cypher 문법 |
| `semantic_validation_error` | 장비 ID/표시명 혼동 또는 질문 필수 필드 누락 | 도메인 값·질문-RETURN 정렬 |
| `execution_error` | 검증 후 실제 조회에서 오류 | timeout·DB 연결·데이터형 |
| `wrong_status` | success/empty/blocked/clarification 오판 | 의도 분류·빈 결과 정책 |
| `wrong_value_or_rowset` | 기대값 누락·값 오류·행 수/집합 불일치 | JOIN 경로·필터·집계·중복 |
| `missing_evidence` | 성공 답변에 Cypher·결과가 없음 | 결과 포맷·UI 계약 |

## 결과 차이 진단

실패 여부와 별개로 `difference_type`을 함께 기록한다.

| 차이 유형 | 의미 |
|---|---|
| `exact` | 컬럼 이름·행·값이 승인 결과와 완전히 동일 |
| `column_alias_or_extra_field` | 기대값은 모두 맞지만 별칭이 다르거나 근거 필드가 추가됨 |
| `wrong_value_or_rowset` | 실제 값·필드 누락·행 수 또는 행 집합이 다름 |

`result_accuracy`는 별칭을 무시하고 기대값이 모두 포함됐는지를 평가한다.
`strict_result_accuracy`는 기존처럼 컬럼 이름까지 동일한지를 평가한다.

실패 건수는 평가 결과 JSON의 각 variant `metrics.failure_counts`와 질문별
`failure_type`에 기록한다. 결과가 나쁘다는 이유로 정답 스냅샷을 갱신하지
않는다.
