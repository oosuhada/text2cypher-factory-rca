# ADR-0004: 측정 가능한 trigger가 생기기 전에는 서비스 분리를 연기한다

- Status: Accepted
- Date: 2026-07-29
- Owners: Platform Owner, Release Manager

## Context

MVP가 커지면 마이크로서비스 전환을 곧바로 아키텍처 고도화로 간주하기 쉽다. 하지만 현재 시스템은 작은 팀이 한 저장소에서 개발하고, 프로젝트 context·권한·audit·평가 계약을 여러 capability가 공유한다.

지금 서비스를 분리하면 다음 운영 요소가 즉시 필요하다.

- 서비스 간 인증과 authorization context 전달
- API·event contract versioning
- retry, idempotency와 distributed failure 처리
- 중앙 logging, metrics, tracing과 alert
- 독립 배포와 rollback
- queue 또는 orchestration
- 데이터 ownership과 migration

현재 확인된 주요 문제는 네트워크 경계 부족보다 `api/main.py`, `services/bootstrap.py`, Agent와 RAG 내부 책임의 집중이다. 이 문제는 먼저 동일 프로세스 안의 모듈 분리로 해결할 수 있다.

## Decision

현재 FastAPI 모듈러 모놀리스를 유지하고, 다음 순서로 진화한다.

1. API route를 도메인별 `APIRouter`로 분리한다.
2. project bundle composition을 factory·provider·adapter로 분리한다.
3. 인증·인가, 관측성, 백업·복구와 운영 기준을 먼저 확립한다.
4. 장시간 ETL·문서 색인이 병목이 되면 queue 기반 worker를 우선 분리한다.
5. 아래 trigger가 실제 지표나 운영 요구로 확인된 capability만 별도 서비스로 분리한다.

서비스 분리 trigger:

- 독립 배포 빈도와 release cadence가 다른 영역과 지속적으로 충돌한다.
- 한 capability의 장애가 전체 API 안정성을 반복적으로 훼손한다.
- 처리량·메모리·GPU·storage scaling 요구가 현저히 다르다.
- 별도 보안·규제·데이터 residency 경계가 필요하다.
- 장시간 작업의 queue, cancel, retry, resume와 수평 확장이 필요하다.
- 독립 운영 책임을 질 팀이 존재한다.

## Consequences

### Positive

- 현재 팀 규모에 맞는 낮은 운영 복잡도를 유지한다.
- 프로젝트 context와 audit 계약을 한 프로세스에서 일관되게 적용한다.
- 내부 모듈화로 실제 결합도를 먼저 드러낸 뒤 안전하게 분리할 수 있다.
- 서비스 분리의 비용과 효과를 지표로 판단할 수 있다.

### Negative / Trade-offs

- 일부 capability를 독립 확장하거나 배포하기 어렵다.
- composition root와 API 프로세스가 당분간 공통 장애 영역이다.
- 분리 trigger와 지표를 관찰하지 않으면 모놀리스가 무계획하게 커질 수 있다.

## Alternatives considered

### RAG, Agent, ETL, Audit를 즉시 별도 서비스로 분리

현재 capability가 프로젝트·권한·audit context를 강하게 공유하고 있어 계약과 운영 복잡성이 기능 이익보다 크다.

### 영구적인 단일 모놀리스 선언

향후 데이터 규모, GPU, 비동기 처리와 보안 요구가 달라질 수 있으므로 영구 결정을 하지 않는다. 이 ADR은 조건부 연기 결정이다.

### 서버리스 함수 중심으로 전환

LangGraph checkpoint, Neo4j connection, persisted RAG와 장시간 작업의 lifecycle을 고려할 때 현재 구조를 단순하게 만들지 않는다.

## Validation

분기별 아키텍처 리뷰에서 다음을 확인한다.

- capability별 배포 빈도와 실패 영향
- API latency, error rate, CPU·memory와 색인 시간
- 장시간 작업과 재시도·취소 요구
- 팀 ownership과 on-call 가능 여부
- 보안·규제 경계 변화

trigger가 충족되면 새 ADR에서 대상 capability, contract, data ownership, migration과 rollback을 정의한다.
