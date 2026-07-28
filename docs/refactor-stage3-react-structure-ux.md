# 리팩토링 3단계 · React 구조·UX

## 목표

대형 React 컴포넌트가 API 호출, 프로젝트 전환, 대화 상태, 근거 표시와
전문가 검증을 모두 소유하던 구조를 작업 책임별로 분리한다. 사용자
동선과 프로젝트 컨텍스트 계약은 유지한다.

## 변경

### Query Studio

- `query-workspace.tsx`: 780줄 → 114줄 orchestration component
- `use-query-session.ts`: 질문 실행·대화·검증 상태
- `query-sidebar.tsx`: 예시 질문·최근 대화
- `query-conversation-panel.tsx`: 질의 진행·답변·composer
- `query-evidence-panel.tsx`: 결과·그래프·Cypher·검증
- `expert-review.tsx`: 전문가 판정
- `query-config.ts`: 프로젝트별 예시·상태 문구

### Projects

- `project-card.tsx`: Home과 Projects의 공통 프로젝트 카드
- `project-create-form.tsx`: 프로젝트 생성 상태와 입력 폼
- `project-overview.tsx`: 127줄 → 93줄
- `project-workspace.tsx`: 205줄 → 73줄

## 함께 반영한 UX 계약

- 데모 질문은 입력창 미리보기만 수행한다.
- 질문 전송 직후 입력값을 비우고 중복 제출을 차단한다.
- Evidence 기본 탭은 결과표다.
- 답변 카드에서 같은 실행의 Evidence로 바로 이동할 수 있다.
- 전문가 검증은 기본 접힘 상태이며 전문가 전용임을 표시한다.

## 검증

- React architecture contract:
  `tests/test_react_component_architecture.py`
- ESLint, TypeScript production build
- 프로젝트 전환·Query·모바일 Playwright E2E
- 기존 Python 회귀 테스트
