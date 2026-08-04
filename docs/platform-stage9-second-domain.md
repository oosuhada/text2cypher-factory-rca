# 9단계 — 두 번째 도메인 재적용

설비 이력 도메인을 별도 하드코딩 ETL 없이 동일한 업로드 → 프로파일 → 매핑 검토 → schema 생성 → 프로젝트 격리 적재 경로에 통과시켰다.

- 예제: 장비 4대, 정비 이벤트 12건, 기술자 4명
- 그래프: `Equipment`, `MaintenanceEvent`, `Technician`
- 관계: `HAS_MAINTENANCE`, `PERFORMED`
- 프로젝트별 Gold 자연어 질문/Cypher 5개
- `scripts/bootstrap_equipment_history.py`로 워크스페이스를 재현한다.

이는 CiP-DMD 전용 화면 복제가 아니라 동일 플랫폼 파이프라인을 설비 이력 그래프에 재사용할 수 있다는 검증이다.
