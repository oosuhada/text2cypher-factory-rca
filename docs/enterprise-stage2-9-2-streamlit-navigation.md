# 엔터프라이즈 2.9-2 — Streamlit 자동 페이지 충돌 제거

상태: **구현·검증 완료 (2026-07-28)**

## 목적

Streamlit의 예약된 `pages/` 자동 멀티페이지 동작과 프로젝트의 커스텀 작업공간 메뉴가 동시에 노출되던 문제를 제거한다. 사용자가 보는 내비게이션은 하나만 유지하고, 이전 자동 페이지 URL도 흰 빈 화면 대신 명확한 이전 경로 안내를 제공한다.

## 확인된 원인

- `frontend/pages/`가 Streamlit의 자동 멀티페이지 디렉터리로 인식됐다.
- 내부 렌더 모듈 파일명이 `stSidebarNavItems`에 자동 노출됐다.
- 각 모듈은 독립 페이지가 아니라 렌더 함수 모음이어서 직접 실행 시 본문이 비었다.
- 자동 메뉴와 `render_sidebar_navigation()` 커스텀 메뉴가 동시에 존재했다.
- `client.showSidebarNavigation=false`만 적용하면 자동 메뉴는 사라지지만 이전 `/projects`, `/audit` URL이 빈 Streamlit 셸로 남았다.

## 구현

### 숨겨진 공식 라우터

`frontend/streamlit_router.py`에서 `st.navigation(position="hidden")`을 사용한다.

- 기본 페이지는 `render_internal_console` callable이다.
- 이전 자동 URL 10개는 숨겨진 호환 페이지로 등록한다.
- Streamlit의 공식 라우터는 유지하지만 프레임워크 메뉴는 렌더링하지 않는다.
- 사용자가 보는 메뉴는 기존 `Navigation` 라디오 하나뿐이다.

### 내부 콘솔 실행 경계

- `frontend/internal_console.py`: 내부 콘솔 실행 흐름
- `frontend/workspaces/`: 공식 작업공간 import 경계
- `frontend/streamlit_app.py`: 숨김 navigation 생성과 `navigation.run()`만 담당

진입점과 실행 경계는 `frontend.pages.*`를 직접 import하지 않는다.

### 자동 메뉴 방어 설정

`.streamlit/config.toml`:

```toml
[client]
showSidebarNavigation = false
```

### 이전 URL 호환

다음 이전 경로를 숨겨진 호환 페이지로 등록했다.

- `/audit`
- `/dashboard`
- `/data_sources`
- `/evaluations`
- `/evidence`
- `/graph_explorer_page`
- `/home`
- `/projects`
- `/query_studio`
- `/schema_studio`

각 URL은 빈 화면 대신 다음을 표시한다.

- 주소 변경 안내
- 정식 `/?workspace=...` 링크
- 기존 `project_id` 보존

## 검증 결과

### 자동화

- 전체 Python 테스트: **231/231 PASS**
- Streamlit 구조·호환 경로 Gate: PASS
- UI visual quality Gate: PASS
- Cross-surface architecture Gate: PASS

### 실브라우저

- `[data-testid="stSidebarNavItems"]`: **0개**
- 작업공간 `Navigation` radiogroup: **1개**
- 언어 선택은 별도 radiogroup으로 구분
- 내부 콘솔 본문: 비어 있지 않음
- 이전 URL 10개:
  - 본문 길이 146~156자
  - 정식 작업공간 링크 존재
  - 자동 메뉴 0개
  - Traceback·Exception 0건
  - `project_id=equipment-history` 보존

## 경계

다음 항목은 2.9-3 범위다.

- provider·model 선택 노출
- OpenAI 키·Gemini fallback 설명
- 역할 미리보기
- Gold 회귀모드
- Stage·foundation 배지

2.9-2는 내비게이션 충돌과 흰 빈 화면 제거에 한정한다.
