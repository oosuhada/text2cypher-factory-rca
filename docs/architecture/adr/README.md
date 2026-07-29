# Architecture Decision Records

Architecture Decision Record(ADR)는 시스템 구조, 품질 속성, 의존성, 인터페이스, 데이터 또는 운영 방식에 장기 영향을 주는 결정을 기록한다.

형식은 Michael Nygard의 간결한 ADR 구조를 따른다.

- Status
- Context
- Decision
- Consequences
- Alternatives considered

참고: [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

## 현재 ADR

| ADR | 상태 | 결정 |
|---|---|---|
| [0001](./0001-record-architecture-decisions.md) | Accepted | 아키텍처 결정을 저장소의 Markdown ADR로 관리한다. |
| [0002](./0002-modular-monolith-and-surface-boundaries.md) | Accepted | FastAPI 모듈러 모놀리스와 React/Streamlit Surface 분리를 유지한다. |
| [0003](./0003-graph-and-document-evidence.md) | Accepted | 구조화 graph evidence와 document evidence를 Tool Registry 뒤에서 분리한다. |
| [0004](./0004-defer-service-decomposition.md) | Accepted | 측정 가능한 trigger가 생기기 전에는 마이크로서비스 분리를 연기한다. |

## 운영 규칙

1. 승인된 ADR의 내용을 바꿀 때 기존 파일을 과거에 없었던 것처럼 수정하지 않는다.
2. 결정이 대체되면 새 ADR을 만들고 이전 ADR의 상태를 `Superseded by ADR-xxxx`로 변경한다.
3. 코드가 이미 구현된 결정도 팀이 계속 의존할 중요한 구조라면 ADR로 기준선을 남긴다.
4. PR 설명에서 관련 ADR을 링크한다.
5. 다음 변경은 ADR 후보로 취급한다.
   - 서비스·프로세스·저장소 분리 또는 통합
   - 외부 provider·database·queue·vector store 도입
   - 인증·인가·감사·보존 정책
   - API compatibility와 데이터 migration
   - 장애 격리, 확장성, 비용 또는 보안에 큰 영향을 주는 선택

## 새 ADR 템플릿

```markdown
# ADR-xxxx: 결정 제목

- Status: Proposed
- Date: YYYY-MM-DD
- Owners: 역할 또는 팀

## Context

어떤 문제와 제약 때문에 결정이 필요한가?

## Decision

무엇을 결정하는가?

## Consequences

### Positive

- 장점

### Negative / Trade-offs

- 비용과 위험

## Alternatives considered

- 대안과 선택하지 않은 이유

## Validation

- 결정이 지켜지는지 확인할 테스트, metric 또는 Gate
```
