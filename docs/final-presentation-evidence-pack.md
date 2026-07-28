# P3 최종 발표 백엔드 Evidence Pack

## 1. 한 문장

공개 제조 데이터를 지식그래프로 구조화하고, 자연어를 검증 가능한
READ-only Cypher로 바꿔 RCA 후보와 근거 경로를 제시하는 다중 프로젝트
질의 플랫폼이다.

## 2. PDF 6~7p 요구사항별 발표 증거

| 발표 항목 | 화면·코드 증거 | 정량 증거 |
|---|---|---|
| 데이터 분석·스키마 | schema manifest와 질의 시나리오 | 6+ 노드·7 관계, schema validation |
| ETL·Neo4j 적재 | profile→mapping→load lineage | reconciliation PASS, 멱등 재적재 |
| 질의셋 | Gold·Blind manifest | Gold 15, Blind 26 |
| Text-to-Cypher | 생성→차단→EXPLAIN→수정→실행 trace | READ 차단 100%, 실행 성공률 100% |
| 결과 UI | 질문·자연어 답변·Cypher·표·관계 경로 | Evidence provenance·verified hash |
| 결과보고 | evaluation metrics·실패 taxonomy | 실제 Gemini 의미값 정확도 61.5% |
| 타 도메인 재적용 | equipment-history 또는 external connector | 동일 pipeline·별도 version contract |

## 3. 권장 데모 순서

1. CiP-DMD project readiness의 9개 gate PASS를 보여준다.
2. “완제품 300002…” 질문으로 답변·Cypher·표·경로를 한 화면에 보여준다.
3. 쓰기 요청이 실행 전에 차단되는 모습을 보여준다.
4. 준비되지 않은 새 프로젝트에서 질문이 HTTP 409로 차단되는 것을
   보여준다.
5. 파일 업로드 또는 외부 Neo4j schema introspection을 보여준다.
6. 적재 후 바로 ready가 아니라 evaluation_required가 되는 이유를
   설명한다.

## 4. 발표에서 숨기지 않을 수치와 한계

- Gemini Blind 의미값 정확도: 61.5%
- 목표 70%에는 미달하며 이는 배관 성공률과 구분한다.
- CiP-DMD genealogy 연결 완전성: 767/802
- RCA는 원인 확정이 아니라 검토 후보 제시다.
- 공유 DB의 `project_id` 격리는 프로토타입이며 고객 운영에서는
  DB/권한 분리가 우선이다.
- 임의 신규 도메인의 Gold 정답은 도메인 전문가 검증 없이 자동 승인하지
  않는다.

## 5. 재현 근거

```bash
./scripts/release_check.sh
./scripts/fresh_release_gate.sh
```

발표 직전 GitHub Actions의 unit-tests, web-quality, packaged-e2e가 모두
PASS인지 확인하고 커밋 SHA와 실행 URL을 발표자료 마지막 장에 기록한다.
