# 9단계 — 두 번째 도메인 재적용

설비 이력 도메인을 별도 하드코딩 ETL 없이 동일한 업로드 → 프로파일 → 매핑 검토 → schema 생성 → 프로젝트 격리 적재 경로에 통과시켰다.

- 예제: 장비 4대, 정비 이벤트 12건, 기술자 4명
- 그래프: `Equipment`, `MaintenanceEvent`, `Technician`
- 관계: `HAS_MAINTENANCE`, `PERFORMED`
- 프로젝트별 Gold 자연어 질문/Cypher 7개
- `scripts/bootstrap_equipment_history.py`로 워크스페이스를 재현한다.

이는 CiP-DMD 전용 화면 복제가 아니라 동일 플랫폼 파이프라인을 설비 이력 그래프에 재사용할 수 있다는 검증이다.

프로젝트 상태는 업로드와 매핑 승인만 완료했을 때 `mapping_ready`이며,
Neo4j 적재·무결성 확인 후에만 `ready`로 승격한다. React 헤더의 프로젝트
선택기는 브라우저 사용자별 선택 상태를 유지하고, 적재되지 않은 프로젝트는
질의를 보내지 않고 Data 또는 Schema 단계로 안내한다.

로컬 Homebrew Neo4j에서는 다음처럼 적재 기능을 명시적으로 켠 FastAPI를
실행한다.

```bash
P3_ENABLE_UI_LOAD=1 P3_NEO4J_MODE_CONTROL=homebrew ./scripts/run_api.sh
```

Schema Studio는 승인된 매핑을 다시 불러와 표시하며, 프로젝트 ID 확인 후
loader 전환 → 프로젝트 범위 적재 → 노드·관계 무결성 확인 → reader 복귀를
한 요청 안에서 수행한다.

## 실제 적재·질의 검증

2026-07-28 로컬 Homebrew Neo4j에서 UI와 동일한 API 경로로 검증했다.

- 노드 20개: `Equipment` 4, `MaintenanceEvent` 12, `Technician` 4
- 관계 24개: `HAS_MAINTENANCE` 12, `PERFORMED` 12
- 타입: `cost_usd` INTEGER, `downtime_hours` FLOAT, `resolved` BOOLEAN
- 적재 결과: `project_scope_applied=true`, `reader_mode_restored=true`
- Gemini 질의: 장비 이력 4행, 1,000달러 이상 정비 5행, 교체·기술자 2행
- React Evidence: 장비 이력 질문 기준 노드 5개·관계 4개와 생성 Cypher 표시

검증 중 Homebrew 서비스가 완전히 종료되기 전에 다시 시작되면
`Neo4j is already running`으로 전환이 실패하는 문제를 발견했다.
`set_homebrew_mode.sh`는 실제 종료를 확인한 뒤 시작하도록 수정했고,
로컬 단일 서버 적재 연결은 라우팅 검색이 없는 `bolt://` 직접 연결을 쓴다.
