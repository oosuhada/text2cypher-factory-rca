# P3 MVP 단계별 구현 계획

## 0. 구현 원칙

이 계획은 기간이 아니라 **완료 조건을 통과하는 순서**로 진행한다. 앞 단계의 산출물이 다음 단계의 입력이 된다.

핵심 경로는 다음과 같다.

```text
제조 데이터
→ Neo4j 지식그래프
→ 사람이 검증한 수동 Cypher
→ 자연어 질문
→ Cypher 생성
→ 안전성·문법 검증
→ 오류 시 수정
→ 읽기 전용 실행
→ RCA 결과와 근거 경로 표시
```

레퍼런스 저장소는 구조를 참고하는 용도다. 저장소 전체를 복사하거나 서로 다른 애플리케이션을 그대로 합치지 않는다.

---

## 1단계. MVP의 질문과 성공 조건 고정

**상태: 완료 — CiP-DMD 원본 기준 재검증 PASS**

### 구현할 내용

CiP-DMD에서 실제로 답할 수 있는 제조 RCA 업무 질문 15개를 정의한다.
Q1~Q5는 스키마 설계용 핵심 기준선, Q6~Q15는 장비·이상 분류·불합격·
genealogy 완전성을 포함한 본 과제 요구사항 충족용 질문으로 사용한다.

예시:

1. 압력검사에 실패한 완제품의 구성품과 상류 공정·QC는 무엇인가?
2. 표면거칠기 불합격 bottom의 milling anomaly 분포는 어떠한가?
3. 완제품 300002의 구성품 genealogy는 무엇인가?
4. milling anomaly class 2가 발생한 bottom이 연결된 완제품의 최종 QC는 어떠한가?
5. 존재하지 않는 완제품을 조회하면 빈 결과를 반환하는가?

각 질문에 다음 항목을 기록한다.

- 자연어 질문
- 업무상 질문 의도
- 기대하는 노드·관계 경로
- 기대 결과 형태: 목록, 집계, 경로
- 정상 결과인지, 빈 결과인지, 차단해야 할 요청인지

### 산출물

- `docs/mvp-scope.md`
- `evaluation/gold_questions.yml` 초안
- MVP 필수 기능과 제외 기능 목록

### 완료 조건

- 팀원 모두가 핵심 5개 질문과 전체 15개 질문의 평가 목적을 설명할 수 있다.
- 질문에 필요한 노드와 관계가 무엇인지 합의됐다.
- “챗봇을 만든다”가 아니라 “어떤 RCA 질문에 답한다”가 명확하다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/example-queries.yml`
  - 질문과 Cypher를 YAML로 관리하는 형식
- 가져오지 않을 내용
  - 레퍼런스의 `NodeA`, `NodeB` 예제 데이터 자체

---

## 2단계. 원본 데이터와 연결 키 점검

**상태: 완료 — CiP-DMD 데이터 게이트 PASS**

### 구현할 내용

CiP-DMD의 메타데이터 JSON, 품질 CSV, 생산 로그 XLSX를 조사한다.

확인할 핵심:

- 완제품·구성품을 식별하는 `part_id`
- `component_ids`의 bottom·rod 참조
- 부품별 `process_data`와 anomaly
- `quality_data`의 feature, value, `qc_pass`
- 각 테이블을 연결할 공통 ID
- 결측치, 중복 행, 시간 형식, 코드값 정의

연결할 수 없는 관계는 추측해서 만들지 않고 `data-gap`으로 기록한다. CiP-DMD에는 LOT, 설비 소모품, 개별 부품과 생산 로그 이벤트의 직접 연결이 없으므로 MVP 범위에서 제외한다.

### 산출물

- `docs/data-dictionary.md`
- `docs/data-gap.md`
- `data/raw/` 원본 파일
- 데이터 프로파일링 결과

### 완료 조건

- 각 테이블의 행 수·중복·결측치를 확인했다.
- 완제품부터 구성품·공정·QC까지 실제 데이터로 연결되는 경로가 있다.
- placeholder와 불완전 genealogy 처리 방침이 정해졌다.
- Gold 질문마다 실제 사례 수와 sample ID가 확인됐다.

### 레퍼런스에서 가져올 내용

- 직접 가져올 코드는 없음
- `graphrag-contract-review/create_graph_from_json.py`
  - 원본 구조를 먼저 확인한 뒤 그래프 적재 구조로 변환하는 사고방식만 참고

---

## 3단계. 최소 그래프 스키마 설계

**상태: 완료 — CiP-DMD projection 검증 PASS**

### 구현할 내용

질문 15개에 답하는 데 필요한 최소 노드와 관계만 설계한다.

초기 스키마 예시:

```text
(:Part {part_type: "cylinder"})-[:ASSEMBLED_FROM]->(:Part {part_type: "cylinder_bottom"})
(:Part {part_type: "cylinder"})-[:ASSEMBLED_FROM]->(:Part {part_type: "piston_rod"})
(:Part)-[:HAS_RUN]->(:ProcessRun)
(:ProcessRun)-[:OF_PROCESS]->(:Process)
(:ProcessRun)-[:RUN_ON]->(:Equipment)
(:ProcessRun)-[:CLASSIFIED_AS]->(:AnomalyClass)
(:Part)-[:HAS_MEASUREMENT]->(:QualityMeasurement)
```

`ProcessRun`에는 원본의 시작·종료 시각을 저장하고 실제 장비 모델과
`AnomalyClass`에 연결한다. `QualityMeasurement`에는 feature·value·`qc_pass`를
저장하며 불합격 측정에는 `QualityFailure` 보조 라벨을 붙인다.

설계할 항목:

- 노드 라벨
- 노드 고유키
- 속성
- 관계 방향
- 관계 속성
- 제약조건과 인덱스
- 그래프에서 저장하지 않을 컬럼

### 산출물

- `docs/graph-schema.md`
- Mermaid 또는 Neo4j Browser용 스키마 그림
- `infra/schema.cypher`

### 완료 조건

- 1단계의 질문 15개를 스키마 위에서 경로로 표현할 수 있다.
- 각 노드에 중복을 방지할 고유키가 있다.
- 관계 방향이 하나로 고정됐다.
- “나중에 쓸 수도 있음”만으로 추가된 노드가 없다.

### 레퍼런스에서 가져올 내용

- `graphrag-contract-review/create_graph_from_json.py`
  - `MERGE`로 노드와 관계를 중복 없이 만드는 패턴
  - 인덱스를 존재 여부 확인 후 생성하는 패턴
- `ps-genai-agents/.../components/text2cypher/schema.py`
  - LLM에 전달할 Neo4j 스키마 표현 방식
- 가져오지 않을 내용
  - 계약서 도메인의 Agreement·Clause 스키마
  - 벡터 인덱스와 임베딩 생성

---

## 4단계. Neo4j 실행 환경과 권한 구성

**상태: 완료 — Community 로컬 프로필 실제 실행 PASS**

### 구현할 내용

- Docker Compose 또는 Neo4j Desktop 중 팀 공통 실행 방식을 하나로 고정
- 환경변수로 접속 정보 관리
- ETL용 쓰기 계정과 애플리케이션용 읽기 전용 계정 분리
- 상태 확인용 health check 작성

권장 계정:

- `graph_loader`: ETL에서만 사용
- `graph_reader`: Text-to-Cypher 실행에서 사용

검증기만으로 안전을 보장하지 않는다. LLM이 쓰기 쿼리를 생성해도 애플리케이션 계정에는 쓰기 권한이 없어야 한다.

Community Edition은 역할을 지원하지 않으므로 로컬에서는 ETL 시 `loader`
모드, Agent 실행 시 데이터베이스 전체를 쓰기 차단하는 `reader` 모드로
전환한다. Enterprise/RBAC 환경에서만 위 두 계정에 `architect`와 `reader`
역할을 각각 부여한다.

### 산출물

- `infra/docker-compose.yml`
- `.env.example`
- `infra/schema.cypher`
- Neo4j health check

### 완료 조건

- 팀원의 다른 컴퓨터에서도 같은 명령으로 Neo4j가 실행된다.
- Community `reader` 모드 또는 Enterprise `graph_reader`로 `MATCH`가 성공한다.
- 동일 보안 프로필에서 `CREATE`, `DELETE`, `SET`이 실패한다.

### 레퍼런스에서 가져올 내용

- `graphrag-contract-review/create_graph_from_json.py`
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 환경변수 패턴
- 가져오지 않을 내용
  - 코드에 기본 비밀번호나 실제 API 키를 넣는 방식

---

## 5단계. 재실행 가능한 ETL 구현

**상태: 완료 — 실제 적재 및 재적재 멱등성 PASS**

### 구현할 내용

중첩 JSON은 Python 표준 `json`, 품질 CSV 교차검증은 `csv`로 읽고 다음
과정을 분리한다. pandas는 표 형태 분석이 필요해지는 확장 단계에서
추가한다.

1. `extract`: 파일 로드
2. `transform`: 컬럼 정리, 타입 변환, ID 표준화
3. `validate`: 필수 키·중복·결측 검증
4. `load`: Neo4j 노드와 관계 적재

ETL을 여러 번 실행해도 동일 노드가 계속 늘어나지 않도록 `MERGE`를 사용한다. 대용량이면 행마다 쿼리하지 않고 batch 또는 `UNWIND`로 적재한다.

### 산출물

- `backend/app/etl/`
- `data/processed/`
- ETL 실행 로그
- 적재 전후 건수 비교표

### 완료 조건

- 빈 DB에서 한 번의 명령으로 전체 그래프가 생성된다.
- 두 번 실행해도 노드와 관계 수가 불필요하게 증가하지 않는다.
- 원본 행 수와 그래프 적재 건수의 차이를 설명할 수 있다.
- 필수 ID가 없는 행은 조용히 누락되지 않고 로그에 남는다.

### 레퍼런스에서 가져올 내용

- `graphrag-contract-review/create_graph_from_json.py`
  - `MERGE` 기반 노드·관계 생성
  - 데이터와 Cypher 파라미터를 분리하는 방식
  - 인덱스 생성 흐름
- 수정할 내용
  - 원본 JSON을 CiP-DMD의 중첩 구조에 맞게 정규화
  - 품질 CSV는 세미콜론 구분자로 교차검증
  - 단건 실행을 batch `UNWIND` 방식으로 변경
- 가져오지 않을 내용
  - 계약 문서 임베딩과 full-text/vector index

---

## 6단계. 그래프 무결성과 수동 Cypher 검증

**상태: 완료 — Gold 15개 결과 스냅샷과 현재 Neo4j 결과가 15/15
일치하고, 고유키·관계 완전성·Genealogy gap을 자동 검증한다. 전체 회귀
테스트 38/38 PASS.**

### 구현할 내용

1단계 질문마다 사람이 직접 Cypher를 작성한다. 이것이 LLM의 few-shot 예제이자 정답 기준선이 된다.

함께 점검할 것:

- 고아 노드 수
- 중복 고유키
- 관계 누락
- 예상 경로 길이
- 각 노드·관계 수
- 의도적으로 삽입한 RCA 원인을 다시 찾을 수 있는지

### 산출물

- `evaluation/gold_questions.yml`
- `evaluation/gold_results/`
- `tests/test_graph_integrity.py`
- 수동 Cypher 실행 결과

### 완료 조건

- 최소 15개 질문이 수동 Cypher로 정확히 실행된다.
- 정상·빈 결과·다중 hop 질문이 모두 포함된다.
- 그래프만으로 RCA 후보를 찾을 수 있다.
- 이 단계가 실패하면 LLM 구현으로 넘어가지 않는다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/example-queries.yml`
  - `question`과 `cql` 쌍의 저장 형식
- 가져오지 않을 내용
  - 생성형 모델을 이용한 자동 정답 제작

---

## 7단계. 질의 서비스 계약 고정

### 구현할 내용

Text-to-Cypher 서비스의 Python 입출력 계약을 먼저 고정한다. Streamlit이
동일 프로세스에서 서비스를 직접 호출하는 구성을 공식 MVP로 사용한다.
팀 분업이나 외부 연동이 필요할 때만 얇은 FastAPI 어댑터를 선택적으로 붙인다.

최소 서비스 함수:

```text
health() -> HealthResult
query(question: str) -> QueryResult
dashboard() -> DashboardResult
```

`POST /api/query` 응답 예시:

```json
{
  "question": "완제품 300002의 구성품과 품질검사 결과를 보여줘.",
  "answer": "Cylinder bottom 103504와 piston rod 200102가 연결되어 있습니다.",
  "cypher": "MATCH ...",
  "rows": [{"cylinder_id": "300002", "component_id": "103504"}],
  "path": {
    "nodes": [],
    "relationships": []
  },
  "attempts": 1,
  "status": "success",
  "validation_errors": [],
  "elapsed_ms": 820
}
```

상태값:

- `success`
- `empty`
- `blocked`
- `failed`
- `needs_clarification`

### 산출물

- `backend/app/services/query_service.py`
- 요청·응답 Pydantic 모델
- Mock 서비스
- `docs/service-contract.md`

### 완료 조건

- Python 테스트에서 세 함수를 호출할 수 있다.
- Streamlit이 Agent 구현 여부와 무관하게 mock 응답으로 개발 가능하다.
- 빈 결과와 실패 결과 형식까지 정의돼 있다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/streamlit_app.py`
  - Streamlit 세션 상태와 Agent 호출 분리 패턴
- `AskOosu/src/app/api/chat/route.ts`
  - 선택적 API 확장 시 요청·응답 인터페이스 개념
- 가져오지 않을 내용
  - AskOosu의 기존 도구와 포트폴리오용 프롬프트

---

## 8단계. YAML few-shot 예제 검색기 연결

**상태: 완료 — Gold 15개 로드·선택 검증 PASS**

### 구현할 내용

6단계에서 만든 정답 질문·Cypher를 few-shot 예제로 사용한다. MVP에서는 VectorDB 검색을 사용하지 않고 YAML 전체 또는 질문 유형별 고정 예제를 제공한다.

### 산출물

- `data/examples/cypher_examples.yml`
- YAML 예제 로더
- 예제 포맷 테스트

### 완료 조건

- YAML을 읽어 프롬프트용 문자열로 변환한다.
- 중괄호가 포함된 Cypher도 프롬프트 오류 없이 전달된다.
- 애플리케이션 재시작 없이 예제 파일을 교체해 테스트할 수 있다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/.../retrievers/cypher_examples/yaml/yaml_example_retriever.py`
  - `YAMLCypherExampleRetriever`를 우선 재사용
  - 질문·Cypher 포맷팅 및 중괄호 escaping
- `ps-genai-agents/example-queries.yml`
  - YAML 스키마
- 가져오지 않을 내용
  - `neo4j_vector_example_retriever.py`

---

## 9단계. Cypher 생성 노드 구현

**상태: 구현 완료 — Gold provider 통합 검증 PASS, 실제 LLM 평가는 API 키 설정 후 진행**

### 구현할 내용

자연어 질문, Neo4j 스키마, few-shot 예제를 LLM에 전달하여 Cypher를 생성한다.

프롬프트 규칙:

- 읽기 전용 쿼리만 생성
- 제공된 라벨·관계·속성만 사용
- 설명문이나 Markdown 없이 Cypher만 반환
- 질문에 없는 값을 임의로 만들지 않음
- 결과 근거를 표시할 수 있도록 식별자와 경로를 반환
- 적절한 `LIMIT` 적용

### 산출물

- `backend/app/agent/nodes/generate_cypher.py`
- `backend/app/agent/prompts.py`
- 생성 노드 단위 테스트

### 완료 조건

- Gold 질문 15개 모두에 Cypher 문자열을 생성한다.
- 코드 블록 표시 등 불필요한 출력이 제거된다.
- 프롬프트에 실제 그래프 스키마가 포함된다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/.../components/text2cypher/generation/node.py`
  - `질문 + few-shot + graph.schema → Cypher` 생성 구조
- `ps-genai-agents/.../components/text2cypher/generation/prompts.py`
  - 프롬프트 구성 방식
- 수정할 내용
  - 제조 스키마와 읽기 전용 규칙
  - 결과 경로·식별자 반환 규칙

---

## 10단계. 최소 검증과 실행 전 안전장치 구현

**상태: 완료 — 쓰기·procedure·다중 statement 차단 및 실제 EXPLAIN 검증 PASS**

### 구현할 내용

MVP 검증은 다음 세 층으로 구성한다.

1. 문자열 수준 쓰기 명령 차단
2. Neo4j `EXPLAIN`을 이용한 문법 검증
3. 읽기 전용 Neo4j 계정으로 실제 실행

최소 차단 대상:

- `CREATE`
- `DELETE`
- `DETACH DELETE`
- `SET`
- `REMOVE`
- `MERGE`
- `DROP`
- `LOAD CSV`
- 승인되지 않은 `CALL` 또는 APOC procedure

검증 결과에는 통과 여부와 오류 이유를 함께 남긴다.

### 산출물

- `backend/app/agent/nodes/validate_cypher.py`
- `backend/app/security/read_only.py`
- 악성·쓰기 요청 테스트

### 완료 조건

- 쓰기 쿼리 테스트가 모두 차단된다.
- 문법 오류가 실행 전에 탐지된다.
- 검증기를 우회해도 읽기 전용 계정이 DB 변경을 막는다.
- 마지막 시도에서 검증 실패한 쿼리를 강제로 실행하지 않는다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/.../validation/validators.py`
  - `validate_no_writes_in_cypher_query`
  - `validate_cypher_query_syntax`
- `ps-genai-agents/.../validation/node.py`
  - 오류 목록과 다음 행동을 결정하는 구조
- 단순화할 내용
  - 관계 방향 자동 교정 제외
  - LLM 검증 제외
  - enum/range와 값 매핑 검증 제외
  - 필요한 두 validator만 호출하는 자체 validation node 작성

---

## 11단계. 수정·재검증·실행 LangGraph 구성

**상태: 완료 — 실제 Neo4j 교정 경로·재시도 초과 안전 종료·reader 모드 PASS**

### 구현할 내용

다음 StateGraph를 구현한다.

```text
START
  → generate_cypher
  → validate_cypher
      ├─ 통과 → execute_cypher → END
      ├─ 실패·재시도 가능 → correct_cypher → validate_cypher
      └─ 재시도 초과 → END
```

상태에 저장할 값:

- 원본 질문
- 생성 Cypher
- 검증 오류
- 시도 횟수
- 실행 결과
- 실행 단계 기록
- 처리 시간

MVP는 최초 생성 후 수정 1~2회까지만 허용한다. 재시도 초과 시 잘못된 쿼리를 실행하지 않고 `failed` 또는 `needs_clarification`을 반환한다.

### 산출물

- `backend/app/agent/state.py`
- `backend/app/agent/workflow.py`
- `generate`, `validate`, `correct`, `execute` 노드
- 워크플로 테스트

### 완료 조건

- 정상 쿼리는 한 번에 실행된다.
- 문법 오류는 수정 노드로 이동한 뒤 재검증된다.
- 수정 실패 시 안전하게 종료된다.
- 상태에 전체 실행 이력이 남는다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/.../workflows/single_agent/text2cypher.py`
  - StateGraph 노드와 조건부 edge 구조
  - `attempt_cypher_execution_on_final_attempt=False` 원칙
- `ps-genai-agents/.../components/text2cypher/correction/node.py`
  - 오류 메시지와 기존 Cypher를 이용한 수정 방식
- `ps-genai-agents/.../components/text2cypher/execution/node.py`
  - Neo4j 실행 결과를 state에 저장하는 방식
- 수정할 내용
  - 상태를 MVP API 응답 구조에 맞게 축소
  - 재시도 횟수와 종료 메시지 명확화
- 가져오지 않을 내용
  - multi-agent workflow

---

## 12단계. 결과 해석과 근거 데이터 구성

**상태: 완료 — Gold 15개 UI 출력 계약·부분 그래프·빈 결과 처리 PASS**

### 구현할 내용

Neo4j 실행 결과를 사용자에게 보여줄 형태로 변환한다.

표시할 정보:

- 한 줄 답변
- 조회 결과 테이블
- 생성된 Cypher
- 사용된 노드와 관계 경로
- 재시도 횟수
- 처리 상태
- 빈 결과 안내

답변은 실행 결과 안에 있는 사실만 사용해야 한다. 결과가 없으면 원인을 지어내지 않고 “조건에 해당하는 데이터를 찾지 못했습니다”라고 응답한다.

원본 레퍼런스의 single-agent workflow에는 summarizer가 없으므로 우리 프로젝트에서 별도로 추가해야 한다. MVP에서는 템플릿 기반 요약으로 시작하고, 필요할 때만 결과 기반 LLM 요약을 붙인다.

### 산출물

- `backend/app/services/result_formatter.py`
- 그래프 시각화용 node/relationship 변환기
- 빈 결과·실패 응답 처리

### 완료 조건

- 답변의 모든 식별자와 수치가 실제 조회 결과에 존재한다.
- 빈 결과에서 허위 원인이나 엔티티를 만들지 않는다.
- Cypher와 경로를 UI가 바로 렌더링할 수 있는 JSON으로 반환한다.

### 레퍼런스에서 가져올 내용

- `AskOosu/src/components/chat/rag-evidence.tsx`
  - 답변과 근거를 분리해 표시하는 UI 개념
- `AskOosu/src/components/chat/tool-renderer.tsx`
  - 도구 실행 결과를 별도 블록으로 렌더링하는 구조
- 가져오지 않을 내용
  - 기존 RAG 출처 데이터 구조

---

## 13단계. Streamlit UI 통합

**상태: 완료 — Chat·Evidence·Dashboard 및 실제 Gold Agent 연결 PASS**

### 구현할 내용

PPT에 명시된 Streamlit을 공식 MVP UI로 사용한다. 채팅·결과표·Cypher·
근거 경로·평가 대시보드를 하나의 Python 앱에서 먼저 완성한다.
CodeMap과 AskOosu는 MVP 완료 후 포트폴리오용 Next.js 확장의 시각
레퍼런스로만 사용한다.

필요 화면:

1. `Chat`: 자연어 RCA 질문
2. `Dashboard`: 그래프 현황·평가 지표
3. `Evidence`: 생성 Cypher·결과표·부분 그래프

### 산출물

- `frontend/streamlit_app.py`
- P3 용어로 정리된 Streamlit 페이지·탭
- Mock 또는 실제 Python 서비스 연결

### 완료 조건

- mock 데이터로 질문·답변·Cypher·표·경로가 모두 표시된다.
- 공식 요구 스택만으로 데스크톱 발표 화면이 안정적으로 열린다.
- 답변과 근거를 같은 화면에서 검증할 수 있다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents/streamlit_app.py`
  - `st.session_state`에 Agent와 대화 이력을 저장하는 패턴
- CodeMap·AskOosu
  - 정보 구조와 근거 표시 UX만 참고하고 React 코드는 MVP에 이식하지 않음

가져오지 않을 내용:

- Next.js·React 앱 전체와 인증·기존 API
- CodeMap의 GitHub 저장소 분석 기능

---

## 14단계. 실제 Agent 서비스와 UI 연결

**상태: 조건부 완료 — 실제 Neo4j·Gold Agent, 상태별 UI, 자유 질문
OpenAI 어댑터와 키 부재 경계를 검증했다. 실제 OpenAI live smoke만 API 키
설정 후 실행하면 된다. 전체 회귀 테스트 43/43 PASS.**

### 구현할 내용

Mock 서비스를 실제 Text-to-Cypher Agent 서비스로 교체한다.

사용자 흐름:

```text
추천 질문 선택 또는 직접 입력
→ 로딩 및 현재 단계 표시
→ Agent 실행
→ 답변
→ 결과 테이블
→ 그래프 경로
→ 생성 Cypher와 검증 정보 펼쳐보기
```

오류 UX:

- 질문이 모호함: 추가 조건 요청
- 빈 결과: 조건에 맞는 데이터가 없다고 표시
- 쓰기 요청: 읽기 전용 시스템임을 안내
- 수정 실패: 답변 보류 및 오류 이유 표시
- Neo4j 또는 LLM 연결 실패: 재시도 버튼

### 산출물

- Streamlit 서비스 호출 계층
- 실제 응답 연결
- 로딩·빈 결과·오류 화면

### 완료 조건

- 사용자가 브라우저에서 질문하고 실제 Neo4j 결과를 확인한다.
- 실패 상태가 무한 로딩이나 빈 화면으로 끝나지 않는다.
- 생성 Cypher와 근거 경로를 숨기지 않고 확인할 수 있다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents` Streamlit 실행·세션 상태 패턴
- AskOosu의 로딩·근거 펼쳐보기 정보 구조

---

## 15단계. 대시보드와 그래프 시각화

**상태: 완료 — 실제 Neo4j 집계·질의 감사로그·Evidence 필터와 상세보기를
구현하고 자동 테스트 29/29를 통과했다. Blind 결과 정확도는 16단계 전까지
`평가 전`으로 유지한다.**

### 구현할 내용

대시보드는 장식용 차트가 아니라 시스템 상태와 평가 결과를 보여준다.

최소 지표:

- 노드·관계 수
- 노드 유형별 건수
- 질문 실행 성공률
- 결과 정확도
- 읽기 전용 준수율
- 평균 응답 시간
- 수정 시도와 수정 성공률

그래프 경로는 “예쁜 전체 그래프”보다 현재 답변의 근거가 된 부분 그래프만 보여준다.

### 산출물

- Streamlit `Dashboard` 페이지
- 질문별 근거 경로 시각화
- 평가 결과 JSON/CSV 로더

### 완료 조건

- 대시보드 수치가 실제 Neo4j와 평가 결과에서 계산된다.
- 사용자가 답변의 완제품·구성품·공정·품질검사 연결을 확인할 수 있다.
- 전체 그래프를 한 화면에 과도하게 렌더링하지 않는다.

### 레퍼런스에서 가져올 내용

- Streamlit `st.metric`, `st.dataframe`, `st.graphviz_chart`
  - 실제 수치와 근거 부분 그래프 표현
- CodeMap의 차트·구조 카드 정보 배치
- 참고만 할 내용
  - `create-context-graph`의 Agent 채팅과 그래프 패널 배치

---

## 16단계. Blind 평가와 회귀 테스트

**상태: 평가 실행 대기 — Gold와 다른 Blind 26문항, 수동 정답 Cypher,
23개 DB 결과 스냅샷, Baseline·Few-shot·자기수정 평가기와 실패 분류를
구현했다. 정답 기준선 23/23 및 전체 테스트 49/49 PASS. 현재 OpenAI 키와
로컬 LLM이 없어 실제 생성 모델 비교 점수만 미실행 상태다.**

### 구현할 내용

Gold 업무 질문 15개와 겹치지 않는 Blind 질문 20~30개를 만든다.

질문 유형:

- 단일 노드 조회
- 조건 필터
- 집계
- 2~4 hop 경로
- 공통 원인 후보
- 역방향 영향 분석
- 존재하지 않는 엔티티
- 모호한 질문
- 쓰기·삭제 요청

평가 지표:

1. 실행 성공률
2. 결과 정확도
3. 스키마 준수율
4. 읽기 전용 준수율
5. 빈 결과 처리율
6. 자기수정 성공률
7. 근거 표시율
8. 평균 응답 시간

Cypher 문자열이 Gold와 완전히 같은지는 핵심 지표로 쓰지 않는다. 다른 Cypher도 같은 결과를 반환할 수 있으므로 정규화된 결과 집합을 비교한다.

비교 실험:

```text
Baseline: 스키마만 제공
→ Few-shot 추가
→ 검증·수정 추가
```

### 산출물

- `evaluation/blind_questions.yml`
- `evaluation/run_evaluation.py`
- `evaluation/results/`
- 실패 유형 분류표

### 완료 조건

- 같은 설정과 데이터에서 평가를 재실행할 수 있다.
- 성공 사례뿐 아니라 실패 사례와 원인이 기록된다.
- 개선 단계별 성능 변화가 수치로 남는다.
- 읽기 전용 준수율은 100%다.

### 레퍼런스에서 가져올 내용

- `ps-genai-agents`의 Text-to-Cypher 상태와 단계 기록 방식
- `langgraph-workflow-orchestrator/tests/test_workflows.py`
  - 워크플로 단계와 조건 분기를 테스트하는 방식만 참고
- 가져오지 않을 내용
  - 레퍼런스 데이터와 예상 결과

---

## 17단계. 데모 고정과 실행 패키징

### 구현할 내용

Blind 평가와 별개로 발표용 질문 3~5개를 고정한다.

데모에 포함할 상황:

1. 정상 RCA 질문
2. 여러 관계를 따라가는 질문
3. 존재하지 않는 엔티티
4. 쓰기 요청 차단
5. 최초 오류 후 자동 수정 성공

한 명령 또는 명확한 두 명령으로 백엔드·프론트·Neo4j를 실행할 수 있게 정리한다.

### 산출물

- 루트 실행 README
- 데모 시나리오
- 초기 데이터 적재 명령
- 환경변수 예시
- 최종 평가표와 아키텍처 그림

### 완료 조건

- 새로운 컴퓨터에서 문서만 보고 실행 가능하다.
- 데모 질문의 기대 결과가 고정돼 있다.
- 네트워크나 LLM 장애 시 보여줄 사전 실행 결과가 준비돼 있다.
- 발표에서 기술 목록이 아니라 문제→근거→검증 흐름을 설명할 수 있다.

### 레퍼런스에서 가져올 내용

- `langgraph-workflow-orchestrator/ARCHITECTURE.md`
  - Agent 단계와 조건 분기를 문서화하는 방식
- CodeMap
  - 대시보드 중심 데모 구성
- 가져오지 않을 내용
  - P4의 병렬 에이전트·승인 workflow 전체

---

## 18단계. MVP 통과 후 선택적 P4-lite 확장

이 단계는 1~17단계가 안정적으로 끝난 경우에만 진행한다.

가능한 확장:

- 질문 유형 분류
- Graph RCA Tool과 문서 검색 Tool 분기
- 결과 근거가 부족할 때 추가 질문
- 현업 사용자 승인
- 승인·거절·실행 로그

참고할 레퍼런스:

- `langgraph-workflow-orchestrator/backend/workflows/conditional_workflow.py`
- `langgraph-workflow-orchestrator/backend/workflows/approval_workflow.py`
- `langgraph-workflow-orchestrator/backend/nodes/approval_node.py`
- `create-context-graph`

MVP가 불안정한 상태에서는 이 단계를 시작하지 않는다.

---

## 레퍼런스 사용 요약

| 레퍼런스 | 가져올 핵심 | 가져오지 않을 것 |
|---|---|---|
| `ps-genai-agents` | Text-to-Cypher StateGraph, YAML 예제 로더, 생성·수정·실행 노드 구조, 쓰기·문법 검증 | multi-agent, vector 예제 검색, LLM 검증 전체 |
| `graphrag-contract-review` | `MERGE` 기반 그래프 적재, 인덱스, 환경변수, 데이터→그래프 흐름 | 계약 스키마, 임베딩, VectorDB |
| `ps-genai-agents Streamlit` | 세션 상태, Agent 호출, 채팅 UI 패턴 | 도메인 예제와 불필요한 검증 전체 |
| `CodeMap` | MVP 이후 대시보드 정보 구조·시각 디자인 | Next.js 앱과 GitHub 코드 분석 기능 |
| `AskOosu` | MVP 이후 채팅·근거·Tool 결과 UX | 전체 앱, 기존 API·프롬프트·인증 |
| `langgraph-workflow-orchestrator` | 조건 분기·테스트·승인 구조의 확장 참고 | P3 MVP에 P4 전체 workflow 도입 |
| `create-context-graph` | 채팅과 부분 그래프를 함께 보여주는 화면 참고 | 전체 Context Graph 플랫폼 |

## 구현 중단 기준

아래 조건에서는 다음 단계로 넘어가지 않는다.

- 완제품과 구성품·공정·품질검사를 연결할 키가 없음
- 수동 Cypher로도 핵심 RCA 질문에 답할 수 없음
- ETL 재실행 시 중복 데이터가 누적됨
- 애플리케이션 계정으로 쓰기 쿼리가 실행됨
- 답변의 근거가 되는 결과·Cypher·경로를 표시할 수 없음

이 기준을 지키면 LLM이나 UI 완성도에 가려진 데이터 문제를 초기에 발견할 수 있다.
