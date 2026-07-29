# Architecture Documentation

이 디렉터리는 바이브 코딩으로 시작한 MVP를 팀이 공동 소유할 수 있는 엔지니어링 시스템으로 전환하기 위한 아키텍처 기준선이다.

## 문서 구성

| 문서 | 목적 |
|---|---|
| [바이브 코딩 MVP에서 팀 엔지니어링으로](./vibe-coding-to-team-engineering.md) | 최근 전문가 글·연구·기업 사례를 근거로 전환 원칙과 30일 실행안을 설명한다. |
| [현재 시스템 아키텍처](./current-state.md) | 현재 저장소의 C4형 구조, 배포 구성, 질의·데이터 흐름, 저장소, 모듈 책임과 기술 부채를 기록한다. |
| [ADR 목록](./adr/README.md) | 구조적으로 중요한 결정을 짧고 추적 가능한 기록으로 유지한다. |

## 기준선

- 기준 브랜치: `main`
- 기준 커밋: `e582bf3` (`feat: add LlamaIndex document RAG`)
- 기준 태그: `p3-stage3-4-v1`
- 문서화 기준일: 2026-07-29
- 제품 자동 Gate: PASS
- 실제 사용자 무설명 수동 검토: PENDING

## 유지 규칙

1. 구조·의존성·배포 단위·데이터 저장 방식·보안 경계가 바뀌면 관련 ADR을 먼저 추가하거나 갱신한다.
2. 컨테이너나 주요 컴포넌트가 바뀌면 `current-state.md`의 Mermaid 다이어그램도 같은 PR에서 갱신한다.
3. 아키텍처 문서는 구현을 희망사항처럼 표현하지 않는다. 현재 구현과 목표 구조를 명확히 구분한다.
4. 새 서비스 분리는 팀 규모나 유행이 아니라 독립 배포, 장애 격리, 확장성, 보안 경계 같은 측정 가능한 필요로 결정한다.
5. 모든 아키텍처 변경은 기존 `scripts/release_check.sh`와 해당 영역의 Gate를 통과해야 한다.

## 문서 책임

기본 소유권은 [`docs/module-ownership.md`](../module-ownership.md)를 따른다.

- 전체 구조와 API 경계: Platform Owner
- Agent·Tool·RAG·보안 경계: Agent·Security Owner
- 데이터·ETL·그래프 적재: Data·ETL Owner + Graph Schema Owner
- React·Streamlit Surface: UI·Evidence Owner
- 배포·CI·Gate: Release Manager

아키텍처 변경 PR은 주 소유자와 영향을 받는 인접 영역 소유자의 교차 검토를 원칙으로 한다.
