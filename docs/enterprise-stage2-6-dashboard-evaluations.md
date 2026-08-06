# 엔터프라이즈 트랙 2-6 — Dashboard·Evaluations

## 구현 결과

Dashboard와 Evaluations를 현재 프로젝트 범위의 단일 운영 관측 화면으로
구현했다.

- NeoDash 패턴의 그래프·Agent·비용 KPI
- 프로젝트 고정 + provider·실행 상태·기간 전역 필터
- 노드·관계·무결성·최근 ETL
- 실행 성공률·의미값/엄격 계약 정확도·Precision/Recall/F1·혼동행렬
- Baseline·Few-shot·Self-correction 비교
- 평균·중앙·P95 지연, token, 비용, 오류 집계
- 도메인 전문가 검증 결과
- 실패 유형과 질문별 평가 결과 drill-down
- 평가 증적 JSON 다운로드
- metrics·audit·Neo4j 원본 lineage와 필터 분모 표시

CiP-DMD 전용 차트가 없는 재사용 프로젝트에서도 화면이 깨지지 않도록
선택 KPI를 빈 상태로 정규화했다. 범용 노드·관계·런타임 지표는 유지하고,
해당 스키마에 정의되지 않은 장비·이상·품질 집계에는 명시적인 안내를
표시한다.

## 집계 계약

FastAPI `GET /api/v1/metrics`가 다음 필터를 받아 서비스 계층에서 한 번
스코프를 확정한다.

- `project_id`
- 반복 가능한 `provider`
- 반복 가능한 `query_status`
- `days`

같은 필터가 성공률·상태·provider·latency·token·cost·error·최근 질의에
동시에 적용된다. Neo4j 구조 수치는 항상 현재 프로젝트의 그래프 범위를
사용한다.

`provenance`에는 graph project, metrics SHA-256, audit 원본 건수와 집계
시각을 기록한다. 화면의 “지표 원본·집계 범위”에서 분자·분모와 최신 ETL을
확인할 수 있다.

## 검증

- audit provider·상태·기간·project 범위 회귀
- 평균·중앙·P95 latency와 오류 집계 회귀
- 기존 metrics API의 무인자 dashboard adapter 하위 호환
- 두 번째 도메인의 선택 KPI 빈 상태
- Streamlit Dashboard·Evaluations 렌더링
- 전체 Python 회귀와 release gate

## 운영 해석

결과 정확도는 Cypher 문자열 일치가 아니라 승인된 결과 의미값을 기준으로
한다. 엄격 계약 정확도는 컬럼명·행·값까지 같은 경우를 별도로 집계한다.
상태 분류는 `success/empty/blocked/failed/needs_clarification` 계약에
대해 혼동행렬과 상태별 Precision/Recall/F1을 제공한다.
