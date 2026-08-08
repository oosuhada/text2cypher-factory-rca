# 엔터프라이즈 3-4 · LlamaIndex 문서 RAG Tool

## 상태

- 구현: **완료**
- LlamaIndex core: **0.14.23**
- 자동 RAG Gate: **PASS**
- `search_docs_tool`: **Tool Registry 등록 완료**
- React 문서 근거 UI: **완료**
- Streamlit 문서 운영·평가 UI: **완료**
- 2.9 실제 사용자 수동 검토: **PENDING 유지**

## 목표와 경계

구조화된 제조 사실은 기존 Neo4j Text-to-Cypher 경로가 담당하고, 매뉴얼·SOP·품질 기준서 같은 비정형 지식은 LlamaIndex가 담당한다.

```text
Project Router
  → Tool Registry
      ├─ graph_query_tool → LangGraph Text-to-Cypher → Neo4j
      └─ search_docs_tool → LlamaIndex → project document index
```

기존 LangGraph orchestration은 유지한다. LlamaIndex Agent나 별도 Workflow를 중첩하지 않고 ingestion, chunking, embedding, persisted vector index, retrieval과 citation에만 사용한다.

## 의존성과 실행 환경

```text
llama-index-core==0.14.23
pypdf==6.14.2
Python 3.14.6 검증 완료
```

LAN 데모와 CI가 외부 embedding 인증에 의존하지 않도록 `DeterministicHashEmbedding`을 사용한다. 이 embedding은 LlamaIndex `BaseEmbedding` 계약을 구현하고, 한국어 bigram과 영문 trigram feature hashing으로 동일 입력에 동일 vector를 만든다.

```text
framework: LlamaIndex
index_version: llamaindex-rag-v1
embedding_model: factorygraph-hash-embedding-v1
```

운영 품질 고도화 시 embedding 구현만 교체할 수 있고, DocumentRagService·Tool·API·UI 계약은 유지한다.

## 문서 ingestion

지원 형식:

```text
.md
.markdown
.txt
.pdf (텍스트 레이어가 있는 PDF)
```

스캔 PDF에서 텍스트가 한 페이지도 추출되지 않으면 빈 index를 만들지 않고 등록을 실패시킨다. OCR은 이번 범위에 포함하지 않는다.

문서 metadata:

```text
project_id
document_id
title
version
document_type
effective_date
security_classification
allowed_roles
is_current
source_filename
source_sha256
indexed_at
index_version
page_number
section_title
```

같은 `document_id + version + source_sha256` 재등록은 duplicate로 반환하며 chunk를 추가하지 않는다. 새 current 버전이 등록되면 같은 document ID의 이전 버전은 `is_current=false`로 바뀌지만 삭제하지 않는다.

## 저장과 프로젝트 격리

CiP-DMD:

```text
data/processed/rag/
  documents.json
  sources/
  index/
```

추가 프로젝트:

```text
data/processed/projects/<project_id>/rag/
  documents.json
  sources/
  index/
```

각 프로젝트는 별도 LlamaIndex persisted storage를 사용한다. 검색 시에도 node metadata의 `project_id`를 다시 검사한다. 저장된 index는 서버 재시작 후 `StorageContext`와 `load_index_from_storage`로 복구한다.

## 검색과 citation

`search_docs_tool` 입력:

```json
{
  "query": "유압 펌프 교체 후 점검 절차",
  "top_k": 5,
  "current_only": true,
  "document_types": ["maintenance_manual"]
}
```

응답에는 raw retrieval match와 citation을 분리해 제공한다.

```json
{
  "status": "success",
  "framework": "LlamaIndex",
  "framework_version": "0.14.23",
  "index_version": "llamaindex-rag-v1",
  "matches": [
    {
      "citation_id": "press-maintenance-manual@2.0:p1",
      "title": "프레스 정비 매뉴얼",
      "version": "2.0",
      "page_number": 1,
      "text": "...",
      "score": 0.28,
      "is_current": true
    }
  ],
  "citations": []
}
```

검색 결과가 없거나 접근 가능한 문서가 없으면 `status=empty`, `matches=[]`, `citations=[]`를 반환한다. source node에 없는 문서명·버전·페이지를 생성하지 않는다.

## 문서 접근 권한

문서의 `allowed_roles`가 비어 있으면 프로젝트 질의 사용자에게 공개된다. 값이 있으면 호출자의 역할과 하나 이상 겹칠 때만 retrieval 결과에 포함된다. 권한이 없는 문서는 검색뿐 아니라 문서 목록과 readiness 집계에서도 제목·개수·citation·metadata를 반환하지 않는다.

문서 등록과 전체 재색인은 다음 역할로 제한한다.

```text
Data Steward
Admin
```

## 질문별 Tool 선택

현재 v1은 명시적이고 평가 가능한 intent rule을 사용한다.

| 질문 | Tool |
|---|---|
| 이력·건수·비용·관계·구성품·공정 | `graph_query_tool` |
| 절차·매뉴얼·SOP·기준서 | `search_docs_tool` |
| 정비 이력과 매뉴얼 절차 | 두 Tool 모두 |

문서 전용 질문은 Neo4j와 Cypher를 실행하지 않는다. Hybrid 질문은 graph 결과와 document evidence를 분리해 반환하고, Tool trace에는 두 invocation이 모두 남는다.

## FastAPI API

```text
GET  /api/v1/projects/{project_id}/documents
POST /api/v1/projects/{project_id}/documents
POST /api/v1/projects/{project_id}/documents/index
GET  /api/v1/projects/{project_id}/rag/readiness
POST /api/v1/rag/search
POST /api/v1/rag/query
```

문서 검색 API도 `search_docs_tool`을 호출하므로 공통 timeout, error taxonomy와 Tool audit가 적용된다.

## React 제품 UI

Query Studio Evidence 영역에 `문서` 탭을 추가했다.

- 문서명과 version
- Current/Superseded
- citation ID
- 페이지와 section
- retrieval score
- 검색된 원문

문서 전용 질문은 결과 행이 0이어도 자동으로 문서 탭을 연다. History에서 다시 열어도 같은 문서 근거와 기본 탭을 복원한다. Graph evidence와 Document evidence는 같은 객체 안에서도 별도 영역으로 유지한다.

## Streamlit 운영 UI

Data Sources workspace에 LlamaIndex 문서 RAG 영역을 추가했다.

- RAG readiness와 index version
- 문서·버전 목록
- Markdown/TXT/PDF 업로드
- metadata·접근 역할 입력
- 새 버전 색인
- 전체 재색인
- current-only 또는 폐기 버전 포함 retrieval 테스트
- chunk 결과 citation·score 확인

Evidence workspace에서도 Query 결과의 문서 근거를 별도 탭으로 표시한다.

## 자동 평가

평가 기준선:

```text
evaluation/document_rag_baseline.json
evaluation/rag_fixtures.json
evaluation/fixtures/rag/
```

전용 Gate:

```bash
.venv/bin/python scripts/document_rag_gate.py
```

검증 항목:

- LlamaIndex framework·version·index version
- persisted index 재시작 복구
- Retrieval Recall@5
- citation precision
- 가짜 citation 0건
- cross-project 문서 노출 0건
- 권한 없는 문서 노출 0건
- current-only에서 폐기 버전 노출 0건
- current-only 해제 시 폐기 버전 검색 가능
- 무관 질문의 citation 0건
- 같은 문서 중복 chunk 0건
- text-layer 없는 PDF 차단

현재 fixture Gate 결과:

```text
Recall@5: 100%
Citation precision: 100%
Fabricated citation: 0
Cross-project leak: 0
Unauthorized document leak: 0
Superseded leak under current_only: 0
```

## 환경변수

```text
P3_RAG_BOOTSTRAP_FIXTURES=1
P3_RAG_SIMILARITY_CUTOFF=0.04
```

fixture bootstrap은 로컬·LAN 데모용이다. Docker 제품 계약은 기본값 `0`이며 승인된 문서를 API 또는 Streamlit 운영 화면에서 등록한다.

## 남은 경계

- 스캔 PDF OCR과 도면·이미지 이해
- cloud vector DB와 다중 인스턴스 동시 쓰기
- 실제 사용자 문서 기반 embedding benchmark
- semantic reranker와 multilingual production embedding
- 문서 삭제·보존기간·법적 hold
- 계정·OIDC 기반 역할 enforcement
- 3-5의 graph·SOP 근거 기반 조치 권고

이 단계의 검색 결과는 근거 제공이며 자동 조치나 원인 확정을 수행하지 않는다.
