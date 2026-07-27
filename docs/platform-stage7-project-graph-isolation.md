# 7단계 — 프로젝트별 Neo4j 격리와 적재

승인된 매핑만 Neo4j에 적재하며 모든 노드와 관계에 `project_id`와 `source_upload_id`를 기록한다.

- 노드 `MERGE` 키는 `(project_id, domain identity)` 조합이다.
- 관계의 양 끝 노드도 동일한 `project_id` 안에서만 찾는다.
- 같은 `equipment_id`가 다른 프로젝트에 존재해도 합쳐지지 않는다.
- 적재 후 프로젝트 범위 노드·관계 수를 다시 조회해 무결성 근거를 반환한다.
- 호출자는 경로의 프로젝트 ID를 본문에 다시 입력해야 적재할 수 있다.

API: `POST /api/v1/projects/{project_id}/graph/load`
