# P3 제조 지식그래프 RCA · Text-to-Cypher MVP

CiP-DMD의 완제품·구성품·공정·품질 관계를 Neo4j로 구조화하고, 자연어 질문을 읽기 전용 Cypher로 변환해 RCA 후보와 근거 경로를 보여주는 MVP다.

구현 순서와 완료 조건은 [MVP_단계별_구현_계획.md](./MVP_단계별_구현_계획.md)를 따른다.
PPT 대조 후 수정 근거는 [방향 수정 기록](./docs/direction-correction-2026-07-27.md)에 정리했다.

## 현재 진행 상태

| 단계 | 상태 | 산출물 |
|---|---|---|
| 1단계 — MVP 질문과 성공 조건 고정 | **재검증 완료** | `docs/mvp-scope.md`, `docs/scope-validation.md`, `evaluation/gold_questions.yml` |
| 2단계 — 원본 데이터와 연결 키 점검 | **완료** | `docs/data-dictionary.md`, `docs/data-profile.md`, `docs/data-gap.md`, `data/processed/cip_dmd_profile.json` |
| 3단계 — 최소 그래프 스키마 설계 | **v1.1 수정 완료** | 장비·이상 분류·QualityFailure 포함 |
| 4단계 — Neo4j 실행 환경과 권한 | **완료** | 실제 Neo4j 스키마 적용·read-only 차단 검증 |
| 5단계 — 재실행 가능한 ETL | **v1.1 재검증 완료** | 실제 데이터 적재·재적재 멱등성 PASS |
| 6단계 — 그래프 무결성과 수동 Cypher | **완료** | Gold 결과 스냅샷 15/15 일치, 무결성·전체 테스트 38/38 PASS |
| 8~11단계 — Text-to-Cypher Agent | **구현 완료** | 생성·차단·EXPLAIN·교정·재검증·실행 PASS |
| 12단계 — 결과 해석·근거 구성 | **완료** | 답변·표·Cypher·부분 그래프 출력 계약 15/15 PASS |
| 13단계 — Streamlit UI | **제품형 UX 보강 완료** | 인라인 근거·세션 대화 기록·Graph Explorer·데이터 사전검증 |
| 14단계 — 실제 Agent·UI 연결 | **완료** | OpenAI 키가 없으면 Vertex Gemini 자동 연결, 실제 자유 질문 PASS |
| 15단계 — 대시보드·그래프 시각화 | **완료** | 무결성·런타임·토큰·비용 지표와 Evidence 필터 구현 |
| 16단계 — Blind 평가·회귀 테스트 | **완료** | Gemini 26문항 의미값 정확도 50.0%→50.0%→61.5%, 엄격 계약 정확도 38.5%, 자기수정 스트레스 8건 |
| 17단계 — 데모 고정·실행 패키징 | **완료** | 원커맨드 프리플라이트·Gold 고정 시나리오 4/4·장애 시 안전 폴백·인라인 Evidence |
| 제품 리팩터링 5단계 — Data Intake | **구현 완료** | ZIP staging·dry-run·승인 적재·reader 복귀·감사로그 |
| 제품 리팩터링 6단계 — 검색형 Graph Explorer | **구현 완료** | 부분 문자열 노드 검색·선택·1~3-hop 읽기 전용 탐색 |
| 제품 리팩터링 7단계 — 전문가 검증(HITL) | **구현 완료** | 3단계 판정·의견·질의 지문·append-only 감사기록 |
| 제품 리팩터링 8단계 — 배포·E2E | **구현 완료** | 5-service Compose·health gate·보안 헤더·black-box smoke |

## 확정 데이터

- 데이터셋: CiP-DMD
- MVP 입력: 메타데이터 JSON, 품질 CSV, 생산 로그 XLSX
- 1차 MVP 제외: 대용량 HDF5 센서 원본
- 유효 완제품: 802개
- 구성품까지 완전히 연결된 완제품: 767개(95.6%)
- 검증 가능한 사례: 압력 불합격 19건, 표면거칠기 불합격 190건, 밀링 anomaly class 2 39건

## 목표 구조

```text
Cylinder ──ASSEMBLED_FROM──> CylinderBottom ──UNDERWENT──> ProcessRun
   │                              │                        ├──RUN_ON──> Equipment
   │                              │                        └──CLASSIFIED_AS──> AnomalyClass
   │                              └──HAS_QUALITY_RESULT───────┘
   ├──ASSEMBLED_FROM──> PistonRod ──UNDERWENT──> Turning
   └──HAS_QUALITY_RESULT──> Assembly QC
```

## MVP에서 반드시 남길 것

- 재실행 가능하고 중복 적재를 막는 ETL
- 사람이 검증한 Gold 질문·수동 Cypher
- 장비 모델·이상 유형·품질 불합격을 명시한 검증 가능한 경로
- 자연어 → Cypher 생성·검증·수정·실행
- 쓰기 쿼리 차단과 Neo4j 읽기 전용 계정
- 답변·Cypher·결과표·관계 경로를 함께 표시하는 UI
- 실행 성공률·결과 정확도·읽기 전용 준수율 평가

실행 방법은 [Text-to-Cypher 가이드](./docs/text2cypher-guide.md),
검증 근거는 [8~11단계 검증 결과](./docs/stage8-11-validation.md)를 참고한다.
UI 출력 구조는 [질의 서비스 계약](./docs/service-contract.md),
12단계 검증은 [결과 해석·근거 검증](./docs/stage12-validation.md)에 정리했다.
Streamlit 실행은 [UI 실행 가이드](./docs/streamlit-guide.md),
검증 근거는 [13단계 검증](./docs/stage13-validation.md)을 참고한다.
대시보드·그래프 고도화 결과는 [15단계 검증](./docs/stage15-validation.md)에
정리했다.
Gold 결과와 그래프 무결성 검증은
[6단계 검증](./docs/stage6-validation.md)에 정리했다.
실제 Agent·UI 상태별 검증은
[14단계 검증](./docs/stage14-validation.md)에 정리했다.
Blind 실제 평가와 남은 생성 품질 한계는
[16단계 검증](./docs/stage16-validation.md)에 정리했다.
발표 실행 패키지와 장애 대응은
[17단계 검증](./docs/stage17-demo-packaging.md)에 정리했다.
발표에서 함께 밝혀야 할 데이터·모델 한계는
[발표용 제한사항](./docs/presentation-limitations.md)에 요약했다.

## 제품 리팩터링 1차 — FastAPI

검증된 Streamlit MVP는 발표·운영 콘솔로 유지하고, 외부 제품 UI가 같은
Text-to-Cypher 엔진을 사용할 수 있도록 FastAPI 경계를 추가했다.

```bash
./scripts/run_api.sh
```

- OpenAPI 문서: `http://127.0.0.1:8000/docs`
- 준비 상태: `http://127.0.0.1:8000/api/v1/health`
- 자연어 질의: `POST http://127.0.0.1:8000/api/v1/query`
- 전문가 판정: `POST http://127.0.0.1:8000/api/v1/feedback`
- 전문가 판정 요약: `GET http://127.0.0.1:8000/api/v1/feedback/summary`
- 그래프 스키마: `GET http://127.0.0.1:8000/api/v1/graph/schema`
- 노드 검색: `GET http://127.0.0.1:8000/api/v1/graph/search`
- 부분 그래프: `GET http://127.0.0.1:8000/api/v1/graph/subgraph`

구조 변경과 완료 조건은
[제품 리팩터링 1~2단계 검증](./docs/refactor-stage1-2-validation.md)에
정리했다.

## 선택적 확장 — Next.js 제품 UI

AskOosu와 CodeMap에서 참고한 랜딩·내비게이션·대화 기록 패턴을
FactoryGraph RCA의 실제 업무 흐름에 맞게 다시 설계했다. 다만 회사
가이드에 명시된 공식 사내 프로토타입은 Streamlit이며, Next.js는
같은 FastAPI를 사용하는 상용화·포트폴리오 확장 화면으로 분리한다.

```bash
./scripts/run_product.sh
```

- 제품 랜딩: `http://127.0.0.1:3000`
- Query Studio: `http://127.0.0.1:3000/query`
- 최근 대화: `http://127.0.0.1:3000/history`
- 그래프 탐색: `http://127.0.0.1:3000/graph`
- 데이터 운영: `http://127.0.0.1:3000/data`
- 시스템 상태: `http://127.0.0.1:3000/operations`

Query Studio는 한 화면에서 자연어 답변, 결과표, 인터랙티브 근거
그래프, 생성 Cypher, 검증·자기수정 이력을 확인한다. 최근 대화 20개는
브라우저에 로컬 저장한다. 현재 데이터 운영 화면은 검증된 CiP-DMD
ETL을 안내·진단하는 범위이며, 임의 파일 업로드와 비동기 적재 작업은
다음 단계로 명시적으로 분리했다.

구현 범위와 검증 결과는
[제품 리팩터링 3~4단계 검증](./docs/refactor-stage3-4-validation.md)에
정리했다.

## 공식 프로토타입 — Streamlit 제품형 UX

```bash
./scripts/run_demo.sh
```

Streamlit 안에서 다음 사용자 흐름을 완결한다.

- 자연어 질문과 세션 내 최근 대화 다시 열기
- 답변 직하에서 결과표·관계 경로·Cypher·검증 이력 확인
- 답변에 대한 도메인 전문가 판정과 의견 기록
- 노드 속성 검색 또는 정확한 ID를 기준으로 최대 3-hop 지식그래프 탐색
- CiP-DMD ZIP staging·고정 매핑·해시 검증·ETL dry-run
- 명시적 승인 후 적재·reader 복귀·감사로그
- 실제 ETL·그래프 무결성·Agent 평가 지표 확인

구현 경계와 검증 결과는
[Streamlit 제품형 UX 이전](./docs/streamlit-product-ux-migration.md)에
정리했다.

제품 리팩터링 5단계 Data Intake의 안전 경계는
[Data Intake 검증](./docs/refactor-stage5-data-intake.md)에 정리했다.
검색형 Graph Explorer의 계약과 안전 경계는
[6단계 Graph Discovery](./docs/refactor-stage6-graph-discovery.md)에 정리했다.
도메인 전문가 검증과 감사기록의 신뢰 경계는
[7단계 HITL 검증](./docs/refactor-stage7-expert-verification.md)에
정리했다.

## 제품형 전체 스택 실행

Docker Desktop 또는 Docker Engine이 있는 환경에서는 Neo4j부터 두 UI까지
한 번에 재현할 수 있다.

```bash
cp .env.example .env
# .env의 NEO4J_PASSWORD를 실제 비밀값으로 변경
./scripts/run_product_stack.sh
```

- Next.js 제품 UI: `http://127.0.0.1:3000`
- FastAPI 문서: `http://127.0.0.1:8000/docs`
- Streamlit 사내 프로토타입: `http://127.0.0.1:8501`
- Neo4j Browser: `http://127.0.0.1:7474`

전체 회귀·빌드·패키지 계약은 `./scripts/release_check.sh`로 확인한다.
컨테이너 구성과 E2E 범위, Neo4j Community 권한 한계는
[8단계 배포·E2E 검증](./docs/refactor-stage8-deployment-e2e.md)에
정리했다.

## MVP 이후로 미룰 것

- HDF5 센서 시계열 전체 적재
- VectorDB 기반 예제 검색
- 범용 GraphRAG와 다중 Agent
- 인증된 다단계 승인, 외부 알림, PostgreSQL·pgvector·n8n 통합
- 사용자 계정·서버 동기화 대화 기록
- 임의 데이터셋 스키마 매핑·비동기 ETL 작업 관리

## 발표용 실행

```bash
./scripts/run_demo.sh
```

Neo4j reader 모드, 환경 프리플라이트, 고정 데모 4개를 검증한 뒤
Streamlit을 실행한다.
