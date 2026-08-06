# Streamlit 리팩토링 1단계 · 공통 기반 분리

## 목적

페이지 UI를 분리하기 전에 세션, 프로젝트 컨텍스트, 대화, 네비게이션,
사이드바와 공통 상태 표시의 소유권을 고정한다. 화면 동작은 유지하고
`streamlit_app.py`에서 공통 상태 전이와 운영 chrome을 제거했다.

## 모듈 경계

| 모듈 | 책임 |
|---|---|
| `frontend/session_state.py` | 세션 기본값, 대화 저장·복원, 프로젝트별 상태 격리 |
| `frontend/navigation.py` | URL·pending page 해석, sidebar radio 상태, 공통 페이지 헤더 |
| `frontend/sidebar.py` | 프로젝트 → 작업공간 → 대화 → 실행 설정 → 역할 → 언어 → 안전 설정 |
| `frontend/common_ui.py` | ready/loading/empty/error 상태, 실패 응답, 서비스 복구 화면 |
| `frontend/streamlit_app.py` | 페이지별 업무 UI와 최종 라우팅 |

## 고정한 상태 계약

- 동일 세션 초기화를 반복해도 대화 메시지가 증가하지 않는다.
- 앱을 다시 열면 프로젝트별 저장 대화가 한 번만 복원된다.
- 프로젝트 전환 전 현재 대화를 저장하고, 복귀 시 해당 프로젝트의
  대화·최근 결과·탐색 상태를 복원한다.
- 새 대화를 시작한 뒤 기존 대화를 재열 수 있다.
- URL workspace와 버튼 기반 pending page를 radio 생성 전에 반영한다.
- 역할에 허용되지 않은 페이지는 Home으로 안전하게 전환한다.

## 회귀검증

- 순수 상태 계약: `tests/test_streamlit_state_contract.py`
- 실제 Streamlit 동선:
  `test_refresh_project_switch_and_conversation_reopen_are_stable`
- UI 품질 Gate는 분리된 5개 프론트엔드 모듈을 함께 검사한다.

후속 작업에서 Graph Explorer, Pipeline, Dashboard, Query Studio 등
페이지별 `render_*` 함수를 `frontend/pages/`로 이동했다. 결과는
`refactor-stage-page-modules.md`에 기록한다.
