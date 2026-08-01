# 12단계 결과 해석·근거 데이터 검증

## 판정

**PASS**

Neo4j 실행 결과를 템플릿 답변, 결과표, 생성 Cypher, 검증 이력,
부분 그래프로 변환하는 서비스 계층을 구현했다.

## 검증 결과

| 항목 | 결과 |
|---|---:|
| 전체 단위 테스트 | 21/21 PASS |
| Gold Cypher 실제 실행 | 15/15 PASS |
| Gold UI 출력 계약 | 15/15 PASS |
| 상세 genealogy 부분 그래프 | PASS |
| 집계 결과 관계 비생성 | PASS |
| 빈 결과 답변·근거 0건 | PASS |
| 차단 결과 근거 0건 | PASS |
| 그래프 관계 endpoint 무결성 | 15/15 PASS |
| 노드·관계·행 상한 | PASS |

## 실제 사례

Q1 압력 불합격 상류 추적:

- 결과 38행
- 부분 그래프는 앞 10행을 사용
- 실제 반환된 cylinder, component, run, equipment, anomaly,
  measurement ID로 노드·관계를 구성

Q5 존재하지 않는 완제품:

- 상태 `empty`
- 결과 0행
- 근거 노드 0개, 관계 0개
- 응답: “조건에 해당하는 데이터를 찾지 못했습니다.”

## 구현 파일

- `backend/app/services/result_formatter.py`
- `backend/app/services/query_service.py`
- `tests/test_result_formatter.py`
- `docs/service-contract.md`

## 남은 범위

- Streamlit에서 `rows`, `evidence`, `validation`을 실제 컴포넌트로 표시
- 질문별 자연어 서술을 풍부하게 만드는 작업은 선택 사항이며, 추가하더라도
  결과 데이터만 입력으로 사용하고 별도 사실을 생성하지 않아야 한다.
