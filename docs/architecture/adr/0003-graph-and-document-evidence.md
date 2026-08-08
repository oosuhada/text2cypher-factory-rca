# ADR-0003: Graph evidence와 Document evidence를 Tool Registry 뒤에서 분리한다

- Status: Accepted
- Date: 2026-07-29
- Owners: Agent·Security Owner, Graph Schema Owner, Evaluation Owner

## Context

사용자 질문에는 서로 다른 종류의 지식이 필요하다.

- 이력, 건수, 비용, 관계, 구성품, 공정과 품질 사실은 Neo4j의 구조화 그래프에 있다.
- 매뉴얼, SOP, 품질 기준서와 점검 절차는 비정형 문서에 있다.

두 근거를 하나의 추상적인 답변 생성 단계에 섞으면 다음 위험이 생긴다.

- 문서에서 찾지 않은 citation을 생성할 수 있다.
- 그래프 행과 문서 문장을 같은 신뢰 수준으로 표현할 수 있다.
- 프로젝트·역할·문서 version 필터가 누락될 수 있다.
- 어느 Tool이 어떤 근거를 만들었는지 audit하기 어렵다.

## Decision

구조화 graph evidence와 document evidence는 서로 다른 retrieval path로 유지한다.

- `graph_query_tool`은 LangGraph Text-to-Cypher와 Neo4j READ-only path를 사용한다.
- `search_docs_tool`은 LlamaIndex의 프로젝트별 persisted index를 사용한다.
- 두 Tool은 공통 Tool Registry의 input/output schema, 역할, timeout, retry, 오류 taxonomy와 audit를 적용받는다.
- 질문은 graph, document, hybrid 중 하나로 선택된다.
- hybrid 결과에서도 `evidence.nodes/relationships`와 `evidence.documents`를 분리한다.
- 문서 citation은 실제 retrieval source metadata에서만 생성한다.
- current/superseded version과 allowed roles를 retrieval 전에 필터링한다.
- 이 단계의 문서 검색은 근거 제공이며 자동 원인 확정이나 조치를 수행하지 않는다.

## Consequences

### Positive

- 근거 유형과 provenance가 명확하다.
- 그래프와 문서의 검증·평가 기준을 독립적으로 운영할 수 있다.
- document-only 질문은 불필요한 Cypher와 Neo4j 실행을 피한다.
- 프로젝트 간·역할 간 문서 누출을 별도 Gate로 검증할 수 있다.
- 향후 embedding이나 vector store를 바꿔도 Tool·API·UI 계약을 유지할 수 있다.

### Negative / Trade-offs

- hybrid 응답 조합과 UI 표시가 복잡해진다.
- 단순 intent rule은 질문의 의미를 완벽히 분류하지 못한다.
- 두 path의 latency와 오류를 함께 관리해야 한다.
- 현재 deterministic embedding은 운영 의미 검색 품질을 대표하지 않는다.

## Alternatives considered

### 모든 질문을 GraphRAG 하나로 통합

초기 구현과 평가가 복잡해지고 graph fact와 document text의 provenance가 흐려진다.

### LLM이 필요에 따라 직접 Neo4j와 문서 저장소 호출

공통 schema, 역할, timeout과 audit를 우회할 위험이 있다.

### 문서를 Neo4j 노드로만 저장

문서 version·chunk·semantic retrieval을 그래프 질의에 과도하게 결합하며 LlamaIndex의 ingestion·retrieval 기능을 활용하기 어렵다.

## Validation

- `scripts/tool_registry_gate.py`
- `scripts/document_rag_gate.py`
- document-only 질문은 Neo4j와 Cypher를 실행하지 않는다.
- hybrid 질문은 두 Tool trace를 남긴다.
- Recall@5와 citation precision 기준선을 충족한다.
- fabricated, cross-project, unauthorized, superseded citation이 0건이다.
- React와 Streamlit은 graph/document evidence를 별도 영역으로 렌더링한다.
