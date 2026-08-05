# 엔터프라이즈 트랙 1-7 구현·검증

## 결론

새 프로젝트가 생성된 순간부터 자유 질의가 허용되는 순간까지를 하나의
검증 가능한 lifecycle로 고정했다. 파일 적재 성공이나 Neo4j 연결 성공만으로
`ready`가 되지 않으며, 현재 데이터·스키마와 연결된 Prompt·Gold·Blind 평가가
모두 확인된 뒤에만 readiness gate가 승격을 허용한다.

## 구현 범위

### 1. Project Registry와 상태 머신

정식 상태는 다음과 같다.

```text
draft → profiling → mapping_review → loading → validating
      → evaluation_required → ready
```

실패와 운영 종료를 위해 `failed`, `archived`를 별도로 둔다.

- 새 프로젝트는 반드시 `draft`로 생성한다.
- 허용되지 않은 상태 건너뛰기를 Registry가 거부한다.
- `PATCH` API로는 `ready`를 직접 지정할 수 없다.
- 모든 상태 전이는 사유와 시각을 SQLite에 기록한다.
- archive는 활성 workspace를 다른 프로젝트로 전환한 뒤 수행한다.

### 2. 프로젝트별 lineage와 버전 증거

`project_artifacts`에 다음 증거를 프로젝트별로 저장한다.

- source
- connector 또는 mapping
- schema
- load·integrity
- read_only
- prompt
- gold
- evaluation

각 증거는 version, status, fingerprint, metadata, updated_at을 가진다.
최종 승격 때 Project metadata에도 source/schema/prompt/gold/evaluation
버전을 연결한다.

### 3. 파일 프로젝트 lifecycle

```text
파일 profile
→ source_version 고정
→ mapping review·승인
→ project_id 격리 ETL
→ 적재 무결성 검증
→ evaluation_required
→ Prompt·Gold·Blind 평가 확인
→ ready
```

적재 완료 직후의 상태를 과거의 `ready`에서 `evaluation_required`로
변경했다. 새 파일이 올라오면 기존 결과를 그대로 신뢰하지 않고
`profiling`부터 다시 시작한다.

### 4. 외부 Neo4j connector

기존 Neo4j를 데이터 원천으로 쓰는 API를 추가했다.

- `POST /api/v1/projects/{id}/connectors/neo4j/validate`
- `POST /api/v1/projects/{id}/connectors/neo4j/{connector_id}/approve`

검증 단계에서 READ 세션으로 다음을 introspection한다.

- 노드 라벨·속성·추론 타입
- 관계 타입·시작/도착 라벨
- 노드·관계 건수
- identity 후보

비밀번호 값은 파일이나 SQLite에 저장하지 않는다. connector에는
`password_env` 이름만 저장하며, URI 안의 username/password도 거부한다.
승인된 외부 DB는 `isolation_mode: database`, 공유 적재 그래프는
`isolation_mode: property`로 구분한다.

### 5. Readiness API

- `GET /api/v1/projects/{id}/readiness`
- `POST /api/v1/projects/{id}/readiness/promote`

Readiness 조회는 LLM Agent bundle을 먼저 생성하지 않는다. 다음 gate를
독립적으로 검사한다.

1. source 연결과 source_version
2. schema_version과 source_version 일치
3. mapping 승인 또는 connector 승인
4. 적재/연결 무결성
5. Gold·Blind 계약
6. Prompt와 schema/evaluation 연결
7. 현재 lineage의 Blind 평가 완료
8. READ 전용 계약
9. 실제 그래프 runtime에 노드 존재

응답은 `checks`, `versions`, `artifacts`, `transitions`,
`eligible_for_ready`, `can_query`, `next_action`을 함께 반환한다.

### 6. 프로젝트별 ServiceBundle

질의 준비가 끝난 프로젝트만 Agent bundle을 생성한다.

- 파일 기반 공유 그래프: 공통 Neo4j 연결 + `project_id` 속성 격리
- 외부 Neo4j: connector별 URI/database/reader 계정
- 프로젝트별 schema context, Prompt, Gold, 평가 계약
- 프로젝트 전환 시 bundle cache도 프로젝트 단위로 분리·폐기

## 검증 결과

2026-07-28 기준:

- Python 회귀: **155/155 PASS**
- 신규 Registry·connector·readiness 테스트: **6건 PASS**
- Next.js ESLint: **PASS**
- Next.js production build·TypeScript: **PASS**
- shell syntax: **PASS**
- container contract: **PASS**  
  로컬 Docker CLI가 없어 Compose 실제 파싱은 CI gate로 이관했다.

검증된 핵심 시나리오:

- draft에서 ready 직접 생성·전이 차단
- 준비 전 자유 질의 HTTP 409 차단
- 파일 ETL 성공 후 `evaluation_required` 유지
- version mismatch 시 승격 차단
- Prompt·Gold·평가 version 일치 시 ready 승격
- 외부 Neo4j 비밀정보 비저장
- 외부 Neo4j introspection→승인→evaluation_required
- 프로젝트별 graph 연결과 ServiceBundle 분리

## 남은 경계

- 임의 도메인의 Prompt·Gold 질문과 정답 snapshot을 자동 생성해 곧바로
  신뢰하는 기능은 의도적으로 넣지 않았다. 도메인 전문가 승인과 실제
  평가가 readiness의 필수 입력이다.
- 외부 Neo4j introspection은 일반 속성 그래프를 대상으로 한다. 같은 관계
  타입이 서로 다른 source 라벨에서 완전히 다른 의미로 사용되는 복합
  모델은 수동 schema review가 필요하다.
- 공유 DB의 `project_id` 속성 격리는 프로토타입 경계다. 상용 멀티테넌시는
  DB/인스턴스 분리와 DB 권한 정책을 우선한다.
