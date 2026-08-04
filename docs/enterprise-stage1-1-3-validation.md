# 엔터프라이즈 트랙 1-1~1-3 구현·검증

## 1. 범위

[`p3-enterprise-platform-implementation-plan.md`](./p3-enterprise-platform-implementation-plan.md)의
다음 작업을 구현했다.

- 1-1 요구사항 Baseline·Gap Matrix
- 1-2 데이터 프로파일·Schema DSL·질의 관점 검증
- 1-3 범용 source adapter·정제·그래프 변환 dry-run·lineage

## 2. 1-1 결과

- `p3-requirements-traceability.md`에 FR/NFR별 구현·테스트·문서 근거를 연결했다.
- `platform-stage1~11`, `refactor-stage1~8` 문서 지도를 추가했다.
- README에서 통합 명세, 구현 계획, 추적표를 함께 찾을 수 있게 했다.

## 3. 1-2 결과

### Schema DSL

- top-level `source_version`
- node `required_properties`, `source`
- relationship `cardinality`, `properties`, `required_properties`, `source_ref`
- `query_scenarios`
- 관계 속성 타입·필수 속성 검증
- 노드 상속 순환 검증

### 질의 관점 검증

`SchemaRegistry.validate_query_scenarios()`가 질문별 필수 노드·관계·속성이
실제 manifest에 존재하는지 검사한다. CiP-DMD와 equipment-history에 각각
3개의 스키마 검증 질문을 추가했다.

### 데이터 프로파일 공통 계약

- `profile_version`
- 결측 셀 수
- 완전 중복 행 수
- 전체 품질 이슈 수

### 실제 Neo4j 수동 질의 검증

로컬 Neo4j의 현재 적재 데이터에 대해 두 도메인의 수동 Gold Cypher를
각 3개씩 실행했다.

| 도메인 | 질문 | 실행 결과 |
|---|---|---:|
| CiP-DMD | Q1 | PASS · 38행 |
| CiP-DMD | Q2 | PASS · 4행 |
| CiP-DMD | Q3 | PASS · 2행 |
| Equipment history | EH1 | PASS · 4행 |
| Equipment history | EH2 | PASS · 4행 |
| Equipment history | EH3 | PASS · 1행 |

따라서 1-2의 Gate는 정적 Schema DSL 검증뿐 아니라 실제 Neo4j READ
질의 실행까지 통과했다.

## 4. 1-3 결과

### Source adapter

| 입력 | 정규화 |
|---|---|
| CSV | UTF-8 CSV 유지 |
| JSON | 객체 배열 또는 `rows/data` 배열 유지 |
| XLSX | sheet별 CSV 생성 |
| ZIP | 내부 CSV·JSON·XLSX를 안전하게 추출·정규화 |

보안 경계:

- archive path traversal 차단
- 파일 수·압축 해제 크기·압축률 제한
- nested ZIP 차단
- 정규화 후 중복 파일명 차단
- 실패한 upload workspace rollback

### Lineage

- 원본 파일명·SHA-256·크기
- 정규화 파일명·SHA-256
- XLSX sheet 이름
- ZIP archive와 member 경로

### Mapping dry-run

적재 전에 다음을 격리하고 최대 20개 예시를 반환한다.

- identity 결측
- identity 중복
- 속성 타입 변환 오류
- 관계 key 결측
- 고아 관계
- 중복 관계

노드·관계별 `input_rows`, `projected_rows`, 오류 유형별 count를 제공한다.
관계 속성과 cardinality도 manifest와 실제 적재 Cypher에 반영한다.

## 5. 알려진 경계

- XLSX는 값 중심으로 정규화한다. 서식, 병합 셀, 매크로는 그래프 데이터로
  변환하지 않는다.
- 수식 셀은 workbook에 저장된 cached value가 있을 때만 값으로 읽는다.
- ZIP 내부 폴더는 데이터 도메인이 아니라 출처 lineage로만 보존하며,
  정규화 파일명 충돌은 자동 덮어쓰기 대신 차단한다.
- 1-3은 동기 dry-run이다. 대용량 비동기 Job queue·취소·재개는 2단계
  Pipeline UX와 운영 백엔드에서 다룬다.

## 6. 검증 명령

```bash
.venv/bin/python -m unittest \
  tests.test_schema_registry \
  tests.test_source_adapters \
  tests.test_dataset_workspace \
  tests.test_mapping_workspace \
  tests.test_generic_graph_loader \
  tests.test_second_domain_reuse -v
```

전체 회귀는 다음으로 확인한다.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 7. 최종 회귀 결과

- Python compileall: PASS
- Python 전체 테스트: **132/132 PASS**
- Git diff whitespace 검사: PASS
- React ESLint: PASS
- Next.js production build: PASS
- 생성된 정적 route: `/`, `/data`, `/graph`, `/history`,
  `/operations`, `/query`, `/schema`
