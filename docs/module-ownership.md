# P3 백엔드 모듈 소유권

실제 담당자 이름은 팀 킥오프에서 각 역할 옆에 기록한다. 코드 리뷰는
주 소유자 1명과 교차 검토자 1명을 원칙으로 한다.

| 소유 역할 | 모듈 | 책임 | Release 승인 근거 |
|---|---|---|---|
| Data·ETL Owner | `ingestion/`, `mapping/`, `etl/` | 원본 profile, 정제, mapping, load, 무결성 | reconciliation·멱등성 테스트 |
| Graph Schema Owner | `schema_registry.py`, `schemas/` | 라벨·관계·identity·질의 시나리오 | schema DSL·Gold 경로 검증 |
| Agent·Security Owner | `agent/`, `security/` | Prompt, Text-to-Cypher, EXPLAIN, 자기수정, READ 차단 | Agent·보안 회귀 |
| Evaluation Owner | `evaluation/` | Gold·Blind 분리, snapshot, metrics, 실패 분류 | version fingerprint·평가 리포트 |
| Platform Owner | `projects/`, `api/`, `services/` | lifecycle, connector, readiness, API 오류 계약 | OpenAPI·readiness·E2E |
| UI·Evidence Owner | `frontend/`, `web/` | 질문·Cypher·결과·근거·운영 상태 | Streamlit·Next.js UI 회귀 |
| Release Manager | `infra/`, `scripts/`, `.github/` | Compose, secret gate, CI, 문서 추적 | release gate 전 항목 PASS |

## 변경 승인 규칙

- Schema 변경: Graph Schema + Evaluation Owner 승인
- ETL 변경: Data·ETL + Graph Schema Owner 승인
- Prompt·Agent 변경: Agent·Security + Evaluation Owner 승인
- API lifecycle 변경: Platform + UI·Evidence Owner 승인
- 배포·secret 변경: Release Manager + 해당 모듈 Owner 승인

P4 확장 기능은 1단계 Release Gate를 통과한 백엔드 핵심 경로와 별도
feature flag·모듈로 개발한다.
