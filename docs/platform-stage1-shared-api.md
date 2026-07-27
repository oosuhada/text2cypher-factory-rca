# 플랫폼 1단계 — 공통 FastAPI 경계

Streamlit과 Next.js가 같은 FastAPI 계약을 사용하도록 읽기·질의 경계를
통합했다.

## 실행 모드

- `P3_STREAMLIT_TRANSPORT=api`: FastAPI 필수
- `P3_STREAMLIT_TRANSPORT=direct`: 로컬 Python 서비스 직접 호출
- `P3_STREAMLIT_TRANSPORT=auto`: API 우선, 미기동 시 direct 폴백

제품 Compose에서는 `api` 모드를 강제한다. Streamlit은 질의, 그래프
탐색, 운영 지표, 전문가 피드백을 HTTP API로 호출한다. ETL 쓰기 경계는
프로젝트·스키마 레지스트리가 도입되는 후속 단계에서 API로 이동한다.

## 검증

- `/api/v1/runtime`으로 실제 provider와 model 확인
- API 오류를 사용자에게 전달 가능한 예외로 변환
- Streamlit 호환 facade에 query, dashboard, graph, feedback 제공
- 제품 Compose에서 API health 이후 Streamlit 시작
