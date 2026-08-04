# 10단계 — Streamlit 공식 워크스페이스 UI

PPT가 요구한 Streamlit 프로토타입을 단일 CiP-DMD 데모가 아니라 프로젝트형 워크스페이스로 확장했다.

- 사이드바에서 프로젝트 생성·전환
- 프로젝트별 대화·마지막 근거 상태 분리
- CSV/JSON 업로드와 컬럼 프로파일 확인
- Schema Studio에서 mapping JSON 미리보기·승인
- 운영 플래그와 확인 문구를 거친 Neo4j 적재
- 기존 Query Studio, Evidence Lab, Graph Explorer, Operations 유지
- 질의 서비스가 아직 준비되지 않은 draft 프로젝트도 데이터 온보딩 가능

프로젝트 변경 시 FastAPI의 활성 컨텍스트와 Streamlit 서비스 캐시가 함께 바뀌므로 이전 프로젝트의 schema나 대화가 섞이지 않는다.
