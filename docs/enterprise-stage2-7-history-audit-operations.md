# 엔터프라이즈 트랙 2-7 — History·Audit·운영 상태

## 구현 결과

프로젝트별 대화와 데이터 작업을 재현할 수 있는 Audit Logs 운영 화면을
구현했다.

- 프로젝트 대화 제목·본문 검색
- 저장된 대화 재열기와 마지막 질문 재실행
- 질의·ETL·평가 이벤트 통합 Timeline
- 이벤트 유형과 검색어 필터
- `run_id` 기반 Run detail
- 질문·실행 Cypher·provider·model·schema/prompt version·결과 건수·비용
- Timeline CSV와 개별 run JSON 감사 증적 다운로드
- Neo4j·ETL·생성 모델·평가 파일 서비스 진단

새 질의는 UUID `run_id`를 발급한다. 기존 query audit에는 timestamp,
question, project ID의 SHA-256으로 만든 안정적인 호환 ID를 부여해 과거
이력도 선택하고 다운로드할 수 있다.

## 통합 이벤트 계약

`GET /api/v1/audit/events`

- 현재 `project_id`를 필수 스코프로 사용
- `event_type=query|etl|evaluation`
- run ID·제목·질문·상태 검색
- 최대 1,000개 bounded result

`GET /api/v1/audit/runs/{run_id}`

- 같은 프로젝트 범위에서 하나의 실행을 재구성
- 질의는 자연어 질문 → Cypher → 검증/실행 지표를 제공
- ETL은 단계·행 수·무결성·멱등성 결과를 제공
- 평가는 provider/model/schema/prompt와 조건별 비교 결과를 제공

## 민감정보 정책

Query audit는 반환 필드를 명시적으로 allowlist 한다.

- 허용: 질문, 실행 Cypher, 상태, 버전, latency, token 수, 비용
- 제외: 시스템 프롬프트, Authorization header, API key, DB password,
  connector secret

기존 로그에 미승인 필드가 있어도 감사 API와 UI에는 전달되지 않는다.
검증 테스트는 `authorization`, `api_key`, `system_prompt`가 결과에서
제외되는지 확인한다.

## 검증

- 기존·신규 query run ID 재현
- query/ETL/evaluation 통합 시간순 정렬
- 프로젝트 범위 밖 이벤트 제외
- 검색과 이벤트 유형 필터
- 민감정보 allowlist 회귀
- 저장 대화 검색·재열기·재실행 연결
- Timeline·Run detail·diagnostics 브라우저 렌더링
- 전체 Python·API·release gate·CI
