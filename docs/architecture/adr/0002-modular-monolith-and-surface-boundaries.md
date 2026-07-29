# ADR-0002: FastAPI 모듈러 모놀리스와 명시적인 UI Surface 경계를 유지한다

- Status: Accepted
- Date: 2026-07-29
- Owners: Platform Owner, UI·Evidence Owner

## Context

현재 시스템은 React, Streamlit, FastAPI와 Neo4j로 구성된다. React와 Streamlit은 한때 유사 기능을 각각 제공했지만 제품화 2.9 단계에서 다음 책임으로 정리됐다.

- React: 최종 사용자 제품
- Streamlit: 내부 데이터·평가·운영 콘솔
- FastAPI: 공통 업무 계약과 source of truth
- Neo4j Browser: 개발·DB 운영 진단

백엔드는 프로젝트 lifecycle, 데이터 온보딩, Text-to-Cypher, Tool Registry, RAG, 평가와 감사를 하나의 FastAPI 프로세스 안의 모듈로 제공한다. 초기 팀과 현재 배포 규모에서 이를 여러 서비스로 분리하면 네트워크 계약, 인증, 배포, 관측, 데이터 일관성과 운영 부담이 크게 증가한다.

## Decision

백엔드는 당분간 **모듈러 모놀리스**로 유지한다.

- 업무 기능은 `projects`, `ingestion`, `mapping`, `etl`, `agent`, `tools`, `rag`, `services`, `api` 경계로 나눈다.
- FastAPI는 React와 Streamlit이 공유하는 source of truth다.
- React는 제품 사용자 여정을 소유한다.
- Streamlit은 내부 운영 기능을 소유하며 제품 기능을 별도 UX로 다시 구현하지 않는다.
- 중복 운영 경로는 프로젝트 컨텍스트를 유지한 handoff 또는 읽기 전용 요약으로 처리한다.
- 큰 API 파일과 composition root는 동일 프로세스 안에서 router·factory·adapter로 점진적으로 분리한다.

## Consequences

### Positive

- 한 저장소와 한 트랜잭션·서비스 경계 안에서 빠르게 변경할 수 있다.
- 프로젝트 context, 권한, audit와 오류 계약을 한 곳에서 일관되게 적용할 수 있다.
- 작은 팀이 분산 시스템 운영 비용 없이 명확한 모듈 책임을 가질 수 있다.
- React와 Streamlit 사이의 기능 경쟁과 상태 불일치를 줄인다.
- 전체 회귀와 로컬/LAN 데모를 재현하기 쉽다.

### Negative / Trade-offs

- FastAPI 프로세스 장애가 여러 capability에 영향을 준다.
- `api/main.py`와 `services/bootstrap.py` 같은 composition 파일이 커질 수 있다.
- 특정 기능만 독립적으로 배포·확장하기 어렵다.
- 두 UI를 유지하는 한 공통 계약 회귀 테스트가 필요하다.

## Alternatives considered

### 모든 capability를 즉시 마이크로서비스로 분리

현재 팀·트래픽·운영 요구보다 복잡성이 크다. 인증, service discovery, distributed tracing, queue, contract versioning과 배포 자동화가 먼저 필요하다.

### Streamlit 하나로 제품과 운영을 통합

내부 운영에는 빠르지만 최종 사용자 제품 UX, 반응형, 브라우저 제품 여정과 장기 프론트엔드 확장에 제약이 있다.

### React가 백엔드 기능을 직접 구현

비즈니스 규칙과 프로젝트 상태가 클라이언트에 중복되고 Streamlit과 다른 결과를 만들 위험이 있다.

## Validation

- 제품 기본 진입점은 React 하나다.
- 제품 헤더에는 내부 Data·Schema·Operations 기능이 노출되지 않는다.
- React와 Streamlit은 동일 FastAPI 프로젝트·질의 계약을 사용한다.
- Surface 경계는 cross-surface와 product-user release Gate로 검증한다.
- 백엔드 모듈 책임은 `docs/module-ownership.md`와 `current-state.md`에 연결한다.
