# 엔터프라이즈 3-2 · 자연어 Project Router

## 상태

- 구현: **완료**
- 자동 평가: **PASS**
- 기본 사용자 동선 노출: 프로젝트 미지정 API 요청에만 적용
- 명시적 `project_id`: 항상 Router 우회
- 2.9 수동 사용자 검토: **PENDING 유지**

## 목적

프로젝트를 지정하지 않은 자연어 질문에서 준비 완료된 프로젝트 후보를 검색하고,
신뢰도와 1·2위 점수 차이가 기준을 통과할 때만 프로젝트를 선택한다. 기준을
통과하지 못하면 어떤 프로젝트의 DB도 실행하지 않고 `needs_clarification`을
반환한다.

## 구현 구조

```text
POST /api/v1/query
  ├─ project_id 있음 → explicit_project · Router bypass
  └─ project_id 없음
       → Ready Project Registry 조회
       → Project 설명 + schema summary 구성
       → hashed semantic embedding + domain keyword score
       → confidence / winner margin gate
          ├─ PASS → 선택 프로젝트 readiness 확인 → 기존 Agent 실행
          └─ FAIL → needs_clarification · DB 실행 0회
```

Router 후보 문서는 다음 정보를 결합한다.

- Project Registry의 이름·설명·domain type·dataset
- schema title
- node label과 property
- relationship type
- domain value
- query scenario
- 프로젝트별 한국어·영어 도메인 alias

외부 모델 장애나 비용 때문에 라우팅이 중단되지 않도록 현재 v1은 결정적인
feature-hashing embedding을 사용한다. 점수와 후보 목록은 모두 trace에 남는다.
향후 운영 데이터가 충분해지면 동일 `ProjectRouter` 경계 안에서 학습 embedding
또는 LLM reranker를 추가할 수 있다.

## 안전 계약

- 후보는 `ready` 프로젝트와 유효한 schema manifest로 제한
- 프로젝트 직접 선택 시 자동 전환 금지
- confidence 미달 시 실행 프로젝트 없음
- 1위·2위 margin 미달 시 실행 프로젝트 없음
- 선택 후에도 기존 readiness gate를 다시 통과해야 함
- routing 결과는 LangGraph state, Query 응답, checkpoint, audit에 보존

기본 기준:

```text
P3_PROJECT_ROUTER_CONFIDENCE_THRESHOLD=0.08
P3_PROJECT_ROUTER_MARGIN_THRESHOLD=0.04
P3_PROJECT_ROUTER_TOP_K=3
```

## API 결과

자동 선택 성공:

```json
{
  "project_id": "equipment-history",
  "routing": {
    "status": "routed",
    "selected_project_id": "equipment-history",
    "confidence": 0.65,
    "mode": "automatic",
    "candidates": []
  }
}
```

모호한 질문:

```json
{
  "project_id": null,
  "status": "needs_clarification",
  "provider": "router",
  "routing": {
    "status": "needs_clarification",
    "selected_project_id": null
  }
}
```

## 평가

평가셋:

```text
evaluation/project_router.yml
```

구성:

- CiP-DMD 제조·품질 질문 8건
- Equipment Maintenance 질문 8건
- 프로젝트 단서가 부족한 clarification 질문 4건

자동 Gate:

```bash
.venv/bin/python scripts/project_router_gate.py --json
```

결과:

```text
20 cases
Top-1 accuracy: 100%
Top-k accuracy: 100%
Clarification accuracy: 100%
Failure: 0
```

테스트는 다음을 고정한다.

- 명시 프로젝트 Router bypass
- 두 도메인의 자동 Top-1 선택
- 낮은 신뢰도 clarification
- draft 프로젝트 후보 제외
- 모호한 질문에서 Bundle 실행 0회
- 명시 선택과 질문 도메인이 충돌해도 자동 전환 0회

## 주요 파일

```text
backend/app/agent/project_router.py
evaluation/project_router.yml
scripts/project_router_gate.py
tests/test_project_router.py
backend/app/api/main.py
backend/app/agent/workflow.py
backend/app/services/query_service.py
```

## 남은 경계

- 현재는 두 개의 ready 도메인 기준 평가다.
- 프로젝트 수가 늘어나면 실제 사용자 질문으로 threshold를 재보정해야 한다.
- 학습 embedding·LLM reranker는 선택적 고도화 항목이다.
- Router가 프로젝트를 선택해도 3-3 Tool Registry와 3-4 LlamaIndex는 아직
  구현되지 않았다.
