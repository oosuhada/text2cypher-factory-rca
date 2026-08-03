# 플랫폼 4단계 — 공통 ETL Adapter

기존 CiP-DMD ETL을 `EtlAdapter`와 `EtlPipeline` 뒤로 이동했다.

## 계약

- `required_paths`
- `prepare` — Extract, Transform, Validate
- `load` — 배치 적재
- `graph_counts` — 적재 무결성

CLI와 승인형 Data Intake가 모두 같은 `CipDmdAdapter`를 사용한다.
두 번째 도메인은 새 Adapter를 등록하는 방식으로 추가할 수 있다.
