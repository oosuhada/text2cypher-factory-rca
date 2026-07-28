# P3 백엔드 Trouble Shooting Runbook

## 1. 프로젝트가 선택되지만 질문할 수 없음

증상:

- `/query`가 HTTP 409 `STATE_CONFLICT`
- readiness의 `can_query=false`

확인:

```bash
curl -s http://127.0.0.1:8000/api/v1/projects/PROJECT_ID/readiness
```

해결:

- `next_action=upload`: 파일 profile 또는 Neo4j connector 등록
- `map`: mapping/schema review
- `load`: 승인 적재·무결성 검증
- `evaluate`: 현재 version으로 Gold·Blind 평가
- `activate`: `/readiness/promote` 호출

상태를 PATCH로 `ready`로 바꾸는 것은 지원하지 않는다.

## 2. 외부 Neo4j connector 검증 실패

원인:

- URI 안에 username/password 포함
- `password_env` 환경변수 누락
- TLS scheme 또는 database 이름 오류
- reader 계정에 MATCH 권한 없음
- 노드가 없거나 identity 후보 속성이 없음

해결:

1. URI는 `neo4j+s://host`처럼 인증정보 없이 입력한다.
2. 비밀번호는 서버 환경변수에 넣고 그 이름만 API에 전달한다.
3. Neo4j Browser가 아니라 동일 reader 계정으로 `RETURN 1`과
   `MATCH (n) RETURN count(n)`을 확인한다.
4. introspection 결과를 승인하기 전에 라벨·관계 방향·identity를 검토한다.

## 3. 적재 후 `evaluation_required`에 머묾

정상 동작이다. 적재 성공은 데이터베이스에 들어갔다는 뜻이지 LLM 질의
품질이 검증됐다는 뜻이 아니다.

해결:

1. 새 schema/source version용 Gold 15~20개와 snapshot을 준비한다.
2. prompt manifest의 version 연결을 갱신한다.
3. Blind 평가를 실행해 metrics를 만든다.
4. readiness가 `eligible_for_ready=true`인지 확인한다.
5. promote endpoint로 승격한다.

## 4. `schema/source/prompt/evaluation version mismatch`

원인:

- 새 파일 업로드 후 과거 schema·metrics 사용
- schema만 수정하고 evaluation snapshot을 갱신하지 않음
- prompt manifest가 이전 evaluation version을 참조

해결:

- [backend-lineage.md](./backend-lineage.md)의 순서대로 downstream
  artifact를 재생성한다.
- mismatch를 무시하거나 metadata만 직접 수정하지 않는다.

## 5. LLM이 만든 Cypher가 실행되지 않음

`validation.trace`와 error code를 확인한다.

- 쓰기 절 발견: 의도적으로 차단된 상태
- EXPLAIN 실패: 오류 메시지를 넣어 최대 횟수 내 자기수정
- domain value 오류: 저장값·표시명 혼동 확인
- project scope 오류: 공유 DB는 `project_id` 조건 필요
- `VERIFICATION_REQUIRED`: 검증 후 쿼리 문자열이 바뀐 보안 차단

실행되지 않은 Cypher를 수동으로 WRITE 계정에서 재실행하지 않는다.

## 6. Compose fresh gate 실패

```bash
P3_RELEASE_ENV_FILE=.env ./scripts/fresh_release_gate.sh
```

스크립트는 실패 시 서비스 로그 200줄을 출력하고 volume까지 정리한다.

- Neo4j health timeout: Docker 메모리와 7474/7687 포트 확인
- initialize 실패: 원본 데이터 존재와 ETL reconciliation 확인
- API health 실패: `NEO4J_PASSWORD`, provider 설정 확인
- Web 실패: 3000 포트와 API base URL 확인

## 7. 오류를 보고할 때 남길 정보

- `X-Request-ID`
- project ID와 lifecycle status
- readiness의 실패 check 이름
- source/schema/prompt/evaluation version
- 오류 시각과 재현 질문
- 비밀번호·API key·원본 고객 데이터는 첨부하지 않는다.
