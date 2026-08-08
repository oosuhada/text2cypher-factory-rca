# ADR-0001: 아키텍처 결정을 저장소에 기록한다

- Status: Accepted
- Date: 2026-07-29
- Owners: Platform Owner, Release Manager

## Context

이 프로젝트는 바이브 코딩과 단계별 자동화 작업을 통해 짧은 시간에 큰 기능 범위를 구현했다. 코드와 검증 문서는 많지만, 일부 구조적 선택의 이유는 여러 단계 문서와 커밋 기록에 흩어져 있다.

팀원이 늘어나면 다음 문제가 생길 수 있다.

- 현재 구조가 의도된 결정인지 임시 구현인지 구분하기 어렵다.
- 같은 논의를 반복하거나 과거 제약을 잊고 결정을 되돌린다.
- AI coding agent가 기술적으로 가능한 변경을 제안해도 기존 의사결정과 충돌하는지 판단하기 어렵다.
- 다이어그램은 현재 구조를 보여주지만 선택 이유와 trade-off를 설명하지 못한다.

## Decision

아키텍처적으로 중요한 결정을 `docs/architecture/adr/`의 Markdown 파일로 관리한다.

ADR은 다음 항목을 포함한다.

- Status
- Context
- Decision
- Consequences
- Alternatives considered
- Validation

결정이 변경되면 기존 ADR을 과거에 없었던 것처럼 수정하지 않고 새 ADR로 대체한다. 관련 코드와 문서 변경은 같은 PR에서 처리한다.

## Consequences

### Positive

- 팀원이 구조의 의도와 제약을 빠르게 이해할 수 있다.
- AI-assisted 변경에 명시적인 architectural context를 제공할 수 있다.
- 리뷰에서 취향이 아니라 기록된 결정과 품질 속성을 기준으로 토론할 수 있다.
- 변경 이유와 migration history가 Git에 남는다.

### Negative / Trade-offs

- 구조 변경 시 문서 갱신 비용이 추가된다.
- 너무 사소한 결정을 모두 기록하면 문서가 소음이 된다.
- ADR이 코드와 함께 갱신되지 않으면 오히려 잘못된 신뢰를 줄 수 있다.

## Alternatives considered

### 하나의 대형 아키텍처 문서만 유지

현재 구조를 설명하는 데는 유용하지만 결정의 시간 순서와 대체 관계를 추적하기 어렵다.

### 이슈와 채팅 기록만 사용

검색과 보존이 불안정하고 코드 기준선과 함께 versioning되지 않는다.

### 외부 위키 사용

협업에는 편리할 수 있지만 저장소와 분리되어 변경이 어긋날 가능성이 높다. 추후 위키를 사용하더라도 authoritative ADR은 저장소에 둔다.

## Validation

- `docs/architecture/adr/README.md`에 모든 ADR이 색인된다.
- 구조적으로 중요한 PR은 관련 ADR을 링크한다.
- 대체 결정은 새 ADR과 `Superseded` 상태로 추적한다.
- 아키텍처 문서와 ADR 링크를 release documentation Gate에 포함할 수 있다.
