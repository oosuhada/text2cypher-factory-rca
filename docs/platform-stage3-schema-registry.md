# 플랫폼 3단계 — Schema Manifest와 Registry

노드·관계·속성·식별자·도메인 값·출력 규칙을 프로젝트별 YAML로
분리했다. API와 향후 Agent는 같은 Registry를 통해 스키마 컨텍스트를
조회할 수 있다.

## 핵심 경계

- Manifest 저장 전 라벨, 속성 타입, identity, 관계 방향 검증
- 프로젝트별 `/api/v1/projects/{project_id}/schema`
- Manifest에서 Text-to-Cypher context와 UI contract 동시 생성
- 체크인된 CiP-DMD v1.1 manifest를 회귀검증

Agent의 기존 고정 컨텍스트 교체는 8단계에서 수행한다.
