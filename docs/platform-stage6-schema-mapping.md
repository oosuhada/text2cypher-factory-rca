# 6단계 — 그래프 매핑과 스키마 검토

업로드 프로파일의 원본 컬럼을 노드·관계·속성으로 명시적으로 매핑한다.

1. Preview는 원본 파일과 컬럼 존재 여부, 식별자, 라벨·관계 이름을 검증한다.
2. 예상 노드·관계 입력 행 수와 생성될 schema manifest를 반환한다.
3. Approve를 눌러야 매핑과 versioned schema가 저장되고 프로젝트가 `ready`가 된다.

이 승인 경계 때문에 임의 CSV를 업로드했다고 즉시 운영 그래프가 변경되지 않는다.

API:

- `POST /api/v1/projects/{project_id}/mappings/preview`
- `POST /api/v1/projects/{project_id}/mappings/approve`
- `GET /api/v1/projects/{project_id}/mappings/approved`
