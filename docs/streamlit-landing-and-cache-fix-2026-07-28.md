# Streamlit 랜딩·캐시 호환성 수정 — 2026-07-28

## 확인된 문제

### `ServiceBundle.feedback` AttributeError

실행 중이던 Streamlit 프로세스는 전문가 검증 기능이 추가되기 전부터
살아 있었다. 화면 코드는 hot reload됐지만 `st.cache_resource`에는 이전
`ServiceBundle` 인스턴스가 남아 있어 새 `feedback` 속성을 찾지 못했다.

수정:

- 서비스 번들 캐시 버전을 명시해 구조가 바뀌면 새 인스턴스를 생성
- 구버전 객체가 남아도 `getattr`로 안전하게 기능을 비활성화
- 기존 8501 프로세스를 종료하고 최신 코드로 완전 재시작

## 랜딩 페이지가 보이지 않았던 이유

React 랜딩은 별도 Next.js 제품 UI의 `/`와 3000번 포트에 구현되어
있었다. Streamlit 8501에는 Hero와 4개 기능 카드만 이식했고 모든 업무
화면을 하나의 탭 묶음으로 노출했다. 따라서 서버 반영 문제가 아니라
“핵심 UX만 이전” 범위를 랜딩과 정보 구조까지 포함하지 않은 구현 갭이었다.

## 수정된 Streamlit 구조

- 기본 진입 화면을 `Home` 랜딩으로 변경
- React 랜딩의 핵심 계층을 Streamlit 네이티브 화면으로 이전
  - 가치 제안 Hero
  - 실제 RCA 질문·관계·Cypher 미리보기
  - 핵심 검증 지표
  - 기능과 Agent workflow
  - Query Studio·Graph Explorer CTA
- 사이드바 Navigation으로 Home, Query, Evidence, Graph, Operations,
  Data & Health를 분리
- Home은 Neo4j·LLM 연결이 실패해도 제품 설명을 표시
- CTA가 세션 라우팅으로 실제 업무 화면을 연다.

## 검증

- 브라우저에서 `http://localhost:8501` 랜딩 렌더링 확인
- 랜딩 CTA → Query Studio 전환 확인
- Operations의 전문가 검증 영역 렌더링과 AttributeError 제거 확인
- Streamlit 화면 전환·Gold chat 자동 테스트 통과

