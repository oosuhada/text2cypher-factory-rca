# 5단계 — 데이터 업로드와 프로파일링

프로젝트마다 CSV/JSON 원본을 격리 저장하고, 그래프 적재 전에 컬럼 타입·결측률·고유값·식별자 후보를 확인한다.

- 업로드 원본은 `data/processed/project_uploads/{project_id}/{upload_id}/source`에 저장한다.
- 파일명, 형식, 개수, 크기와 경로 이탈을 검증한다.
- 프로파일은 SHA-256과 함께 `profile.json`에 남아 후속 매핑의 재현 가능한 입력이 된다.
- 이 단계는 데이터를 Neo4j에 쓰지 않는다. 사용자가 매핑을 검토·승인한 뒤 적재한다.

API:

- `POST /api/v1/projects/{project_id}/uploads/profile`
- `GET /api/v1/projects/{project_id}/uploads`
- `GET /api/v1/projects/{project_id}/uploads/{upload_id}`
