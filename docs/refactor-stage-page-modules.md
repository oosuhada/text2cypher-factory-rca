# Streamlit 리팩토링 2단계 · 페이지 모듈 분리

## 목적

`streamlit_app.py`에 모여 있던 페이지 렌더러를 작업공간별 모듈로
분리한다. Streamlit의 전체 스크립트 재실행 모델은 유지하되, 화면별
변경 범위와 코드 소유권을 명확하게 만든다.

## 변경 결과

- `streamlit_app.py`: 4,213줄에서 119줄로 축소
- 진입점의 최상위 함수: `main()` 하나만 유지
- 페이지 설정과 공통 CSS: `frontend/app_shell.py`로 분리
- 서비스 캐시와 프로젝트 경로: `frontend/runtime.py`로 분리
- 페이지 UI: `frontend/pages/` 아래 10개 모듈로 분리
- 기존 사용자 동선과 세션 상태 계약은 변경하지 않음

## 페이지 소유권

| 모듈 | 담당 작업공간 |
|---|---|
| `pages/home.py` | 랜딩, 프로젝트 현황 |
| `pages/projects.py` | 프로젝트 목록·생성 |
| `pages/query_studio.py` | 자연어 질의, 답변, 인라인 근거, 전문가 검증 |
| `pages/graph_explorer_page.py` | 그래프 탐색·검색·경로 시각화 |
| `pages/dashboard.py` | 그래프·런타임·평가 지표 |
| `pages/evaluations.py` | Gold·Blind·운영 평가 |
| `pages/audit.py` | 질의·ETL·평가 감사로그와 대화 복원 |
| `pages/data_sources.py` | 파일 업로드, Neo4j 연결, 프로파일링 |
| `pages/schema_studio.py` | 매핑, 승인, 격리 적재, 무결성 검증 |
| `pages/evidence.py` | 전체 화면 근거 뷰(호환용) |

## 의존 방향

```text
streamlit_app.py
  ├─ app_shell.py
  ├─ runtime.py
  ├─ session_state.py / sidebar.py / navigation.py / common_ui.py
  └─ pages/*
       ├─ backend services
       └─ frontend domain/presentation modules
```

페이지 모듈은 `streamlit_app.py`를 역으로 import하지 않는다. 따라서
진입점과 페이지 사이에 순환 의존성이 생기지 않는다.

## 고정한 아키텍처 계약

- `streamlit_app.py`에는 `main()` 이외의 함수가 존재하지 않는다.
- 진입점은 150줄 이하를 유지한다.
- 페이지별 모듈의 누락을 자동 테스트로 감지한다.
- 서비스 캐시·데이터 인테이크 리소스는 페이지가 아닌
  `runtime.py`가 소유한다.
- UI 품질 게이트는 진입점뿐 아니라 모든 페이지 모듈을 함께 검사한다.

## 검증

- 구조 계약: `tests/test_streamlit_page_architecture.py`
- 전체 Python 회귀 테스트
- Streamlit AppTest 사용자 동선
- React lint·build·Playwright E2E
- GitHub Actions unit/web/packaged E2E

다음 리팩토링에서는 페이지 내부에서 크기가 큰 Graph Explorer,
Data Sources, Dashboard를 컴포넌트·섹션 단위로 추가 분리할 수 있다.
