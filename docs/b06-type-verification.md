# B06 `is_normal` 타입·쿼리 검증

검증일: 2026-07-27

## 결론

B06의 0건 결과는 ETL 타입 불일치가 아니다. `AnomalyClass.is_normal`은
모든 클래스에서 Neo4j `BOOLEAN NOT NULL`이고, 두 불리언 필터는 모두
81건을 반환한다.

| 확인 쿼리 | 결과 |
|---|---:|
| `WHERE NOT anomaly.is_normal` | 81 |
| `(:AnomalyClass {is_normal: false})` | 81 |
| 문자열 `{is_normal: 'false'}` | 0 |

문제가 된 Gemini 쿼리는 다음처럼 관계를 연속으로 연결했다.

```cypher
(run:ProcessRun)-[:RUN_ON]->(equipment:Equipment)
  -[:CLASSIFIED_AS]->(anomaly:AnomalyClass)
```

이는 의도한 `ProcessRun→AnomalyClass`가 아니라 존재하지 않는
`Equipment→AnomalyClass` 경로를 조회하므로 0건이 나온다. Neo4j EXPLAIN은
문법 오류가 아니어서 이를 차단하지 못했다.

## 조치

- `Equipment-[:CLASSIFIED_AS]->AnomalyClass` 토폴로지를 의미 검증에서 차단
- 변수명이 있는 `(equipment:Equipment)`와 없는 `(:Equipment)` 모두 검사
- Gemini 자기수정 후 두 관계를 `ProcessRun`에서 각각 분기하도록 교정
- Blind B06 최종 결과 81건 및 엄격 결과 일치 PASS

따라서 ETL 재적재는 수행하지 않았으며, 데이터 수정 대신 쿼리 의미
검증을 보완했다.
