# 11단계 — React와 Streamlit의 공통 플랫폼 API

React는 Streamlit을 iframe으로 감싸지 않고 동일 FastAPI를 사용하는 고객용 UI로 유지한다. 두 UI는 같은 프로젝트·업로드·스키마·질의·적재 계약을 공유한다.

React에 추가된 기능:

- 전역 프로젝트 선택기와 API 기반 활성 프로젝트 전환
- 프로젝트별 브라우저 대화 기록
- 프로젝트 생성, CSV/JSON 업로드, 컬럼 프로파일 UI
- Schema Studio 매핑 미리보기·승인·적재
- 프로젝트 schema 기반 Graph Explorer
- 프로젝트 ID를 포함한 Text-to-Cypher 요청

운영 역할:

- React: 상용 서비스에 가까운 고객 경험
- Streamlit: PPT 요구사항을 충족하는 분석·운영·발표 UI
- FastAPI: 두 UI가 공유하는 단일 비즈니스 경계
- Neo4j: `project_id`로 격리된 그래프 저장소

검증 기준은 Python 전체 테스트, ESLint, Next.js production build, Streamlit compile/AppTest다.
