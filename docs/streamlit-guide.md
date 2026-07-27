# Streamlit UI 실행 가이드

## 실행

Neo4j가 reader 모드로 실행 중인지 확인한다.

```bash
./infra/set_homebrew_mode.sh reader
./infra/health_check.sh
```

발표·데모에서는 프리플라이트와 고정 질문 검증을 포함한 원커맨드를
사용한다.

```bash
./scripts/run_demo.sh
```

브라우저에서 `http://localhost:8501`을 연다.

## 화면

### Query Studio

- 추천 질문 4개
- 자연어 직접 입력
- 답변 상태: 조회 완료, 결과 없음, 요청 차단, 처리 실패
- 결과 행·검증 횟수·응답 시간 요약
- 답변 바로 아래 결과표·Cypher·관계 경로 인라인 표시

기본 `자동` 모드는 OpenAI 키가 있으면 OpenAI를, 없으면 로컬 Vertex AI
인증정보로 Gemini를 선택한다. 새 질문은 Gemini가 처리하며, `Gold 데모`
모드는 등록된 15문항의 회귀검증에만 사용한다.

### Evidence Lab

- 결과표와 CSV 다운로드
- 실제 반환 ID 기반 부분 그래프
- 노드·관계 유형 필터와 고립 노드 표시 선택
- 좌→우·위→아래 레이아웃 전환
- 노드·관계 범례와 원본 속성 상세표
- 생성된 Cypher
- 생성·검증·교정·실행 trace와 오류
- 시각화 생략·상한 여부

### Operations

- 실제 Neo4j 노드·관계 수
- 노드·관계 유형별 건수
- 제품 Genealogy 완전성, 불완전 연결, 고아 공정·측정
- 장비별 공정 실행 건수
- 이상 유형 분포
- 품질 불합격 항목
- Gold 실행·읽기 전용 준수·테스트 현황
- Blind Baseline/Few-shot/Self-correction 실제 비교
- 모델 호출 수·입출력 토큰·추정비용
- UI 누적 질의 성공률·평균 응답시간·자기수정 성공률
- 최근 질의와 상태 분포
- Agent 처리 흐름
- 상태 분류 혼동행렬과 Precision·Recall·F1
- 자기수정 오류 주입 스트레스 결과

### Data & Health

- CiP-DMD·Neo4j·LLM·평가 결과 실행 진단
- 최근 ETL 시간·상태·멱등성·격리 레코드
- 검증용 CiP-DMD ZIP 다운로드
- ZIP 경로·크기·필수 파일 8개·SHA-256 기준 원본 일치 검사
- Extract → Transform → Validate dry-run과 projection 건수 미리보기
- 30분 승인 토큰·전체 Run ID 확인 후 Neo4j 적재
- loader 단일 잠금·적재 결과 검증·reader 모드 자동 복귀
- 최근 Data Intake 실행과 JSONL 감사로그
- 개별 JSON/CSV의 `part_id` 계열 공통 키 빠른 사전검증

실제 적재 버튼은 기본 비활성화한다. 관리자가 로컬 환경에서 아래처럼
명시적으로 허용한 경우에만 활성화된다.

```bash
P3_ENABLE_UI_LOAD=1 ./scripts/run_demo.sh
```

승인 적재는 검증 기준과 SHA-256이 동일한 CiP-DMD 번들만 지원한다.
변경된 데이터나 다른 제조 데이터셋은 자동 적재하지 않는다.

UI 질의 이력은 `data/processed/query_audit.jsonl`에 로컬 JSONL로 저장한다.
대시보드는 최근 1,000건을 읽고 최근 20건을 표로 보여준다. 질문 원문이
기록되므로 실제 고객 데이터로 시연할 때는 보존 기간과 접근 권한을 별도로
정해야 한다.

## 발표 시연 순서

1. `제품 Genealogy` 추천 질문 실행
2. Query Studio 답변 직하의 결과표 → Cypher → 관계 경로 확인
3. Evidence Lab에서 필터와 검증 이력 확인
4. `없는 엔티티 검증`으로 빈 결과와 비환각 동작 시연
5. Operations에서 데이터 규모·정확도·혼동행렬 확인
6. Data & Health에서 ZIP staging → dry-run PASS와 감사로그 확인

## 문제 해결

`서비스를 시작하지 못했습니다`:

- `brew services info neo4j`
- `./infra/health_check.sh`
- `NEO4J_PASSWORD` 또는 macOS Keychain 확인

Gemini 모드 오류:

- 저장소 밖의 인증 JSON 경로를 확인
- 기본 경로: `~/.config/p3-cip-dmd/vertex-service-account.json`
- `GOOGLE_VERTEX_PROJECT`, `GOOGLE_VERTEX_LOCATION`,
  `GOOGLE_VERTEX_MODEL` 확인
- 인증 JSON은 저장소에 복사하거나 커밋하지 않음

OpenAI 모드 오류:

- `OPENAI_API_KEY`와 `OPENAI_MODEL` 확인
- API 키가 없으면 자동 또는 Gemini 모드로 전환
- 일시적인 LLM·Neo4j 장애는 `서비스 다시 연결` 또는
  `마지막 질문 다시 시도` 버튼 사용

OpenAI live smoke:

```bash
export OPENAI_API_KEY="..."
.venv/bin/python scripts/validate_openai_mode.py
```

API 키가 없으면 외부 호출을 시도하지 않고 명확하게 종료한다.

Gemini live smoke:

```bash
.venv/bin/python -m backend.app.agent.cli \
  --provider gemini \
  "장비별 공정 실행 횟수를 많은 순서대로 알려줘."
```

ETL을 다시 실행해야 할 때:

```bash
./infra/set_homebrew_mode.sh loader
# ETL 실행
./infra/set_homebrew_mode.sh reader
```
