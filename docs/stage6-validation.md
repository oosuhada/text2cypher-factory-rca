# 6단계 그래프 무결성·수동 Cypher 검증

검증일: 2026-07-27

## 결론

Gold 업무 질문 15개의 수동 Cypher가 실제 Neo4j에서 모두 실행됐고,
현재 결과가 승인된 결과 스냅샷과 **15/15 일치**했다. 쿼리가 오류 없이
실행되는지만 보는 것이 아니라 반환 행의 실제 내용까지 비교한다.

## 결과 기준선

각 질문의 정규화된 결과는 `evaluation/gold_results/Q1.json`부터
`Q15.json`까지 저장한다.

| 질문 | 결과 행 | 검증 |
|---|---:|---|
| Q1 | 38 | PASS |
| Q2 | 4 | PASS |
| Q3 | 2 | PASS |
| Q4 | 37 | PASS |
| Q5 | 0 | PASS — 존재하지 않는 엔티티 |
| Q6 | 3 | PASS |
| Q7 | 4 | PASS |
| Q8 | 9 | PASS |
| Q9 | 2 | PASS |
| Q10 | 3 | PASS |
| Q11 | 2 | PASS |
| Q12 | 2 | PASS |
| Q13 | 4 | PASS |
| Q14 | 3 | PASS |
| Q15 | 1 | PASS |

## 비교 방식

- Cypher 문자열의 완전 일치는 요구하지 않는다.
- 최상위 결과 행과 중첩 목록 순서를 정규화한다.
- 키 순서와 반환 순서가 달라도 내용이 같으면 동일 결과로 판정한다.
- 행 수, 정규화된 전체 결과, SHA-256 fingerprint를 함께 비교한다.
- 누락되거나 새로 생긴 행은 최대 5개까지 차이 정보로 출력한다.

현재 DB를 승인된 기준선과 비교:

```bash
.venv/bin/python scripts/validate_gold_results.py
```

데이터 또는 Gold Cypher를 의도적으로 변경한 뒤 기준선을 다시 승인할
때만 다음 명령을 사용한다.

```bash
.venv/bin/python scripts/validate_gold_results.py --update
```

`--update`는 기존 기준선을 덮어쓰므로 실패 원인을 검토하지 않은 채
사용하면 안 된다.

## 그래프 무결성

`tests/test_graph_integrity.py`가 실제 Neo4j에서 다음을 검증한다.

- 노드·관계 유형별 건수가 ETL 검증값과 일치
- 고유키 제약조건 6개 존재
- 모든 ProcessRun에 Part·Process·Equipment·AnomalyClass 경로가 각각 1개
- 모든 QualityMeasurement에 Part와 Process 경로가 각각 1개
- 완제품 802개 중 완전 Genealogy 767개, 불완전 35개

불완전 35개는 ETL 오류로 숨기지 않고 원본의 누락 참조로 격리한
알려진 데이터 한계다.

## 전체 회귀 테스트

```bash
.venv/bin/python -m unittest discover -s tests -v
```

결과: **38/38 PASS**

여기에는 ETL, Gold 결과 비교, 실제 그래프 무결성, Text-to-Cypher,
결과 근거 구성, Streamlit 통합과 대시보드 테스트가 포함된다.
