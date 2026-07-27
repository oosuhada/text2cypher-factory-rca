# 제품 리팩터링 1차 — 1~2단계 검증

검증일: 2026-07-27

## 목표

1. 검증된 Streamlit MVP를 깨지 않는 기준선을 고정한다.
2. UI가 서비스 조립을 소유하지 않도록 공통 구성을 백엔드로 이동한다.
3. 기존 Text-to-Cypher 엔진을 FastAPI로 노출한다.

## 1단계 — 기준선과 경계

- `backend.app.services.bootstrap`: Neo4j, 생성 모델, QueryService,
  DashboardService, GraphCatalogService를 조립하는 공통 진입점
- `frontend.app_services`: 기존 import를 보존하는 얇은 호환 계층
- Streamlit과 FastAPI가 동일한 QueryService와 Gold fallback을 사용
- 기존 프리플라이트 5/5, 고정 데모 4/4, 회귀 테스트 전부 유지

## 2단계 — FastAPI

| Method | Endpoint | 용도 |
|---|---|---|
| GET | `/api/v1/health/live` | 프로세스 생존 확인 |
| GET | `/api/v1/health` | 데이터·ETL·Neo4j·모델·평가 준비도 |
| POST | `/api/v1/query` | 자연어 질문→답변·Cypher·결과·근거 |
| GET | `/api/v1/metrics` | 그래프·평가·런타임 지표 |
| GET | `/api/v1/graph/schema` | 프론트엔드용 그래프 계약 |
| GET | `/api/v1/graph/subgraph` | 라벨·식별자 기준 제한된 부분 그래프 |

부분 그래프 API는 다음을 강제한다.

- 허용 라벨과 식별 속성 allowlist
- 최대 탐색 깊이 3
- 최대 경로 수 100
- Neo4j READ_ACCESS 세션
- 쿼리 타임아웃

## 실행

```bash
./scripts/run_api.sh
```

- OpenAPI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"완제품 300002의 구성품을 보여줘."}'
```

## 완료 조건

- 기존 Streamlit 통합 테스트 포함 전체 테스트 67/67 PASS
- FastAPI 계약 테스트 PASS
- 실제 Neo4j에서 Gold 질의 API 200과 결과 행 확인
- 스키마·부분 그래프 API가 읽기 전용으로 동작
- 서비스 종료 시 공유 Neo4j 드라이버 정리
