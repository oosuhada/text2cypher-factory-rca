# Text-to-Cypher Agent 실행 가이드

## 구현 흐름

```text
사용자 질문
  → 쓰기 의도 사전 차단
  → Gold few-shot 선택
  → LLM Cypher 생성
  → 문자열 읽기 전용 검증
  → 도메인 값·질문 필수 필드 의미 검증
  → Neo4j EXPLAIN
      ├─ 통과: 읽기 모드 실행
      └─ 실패: LLM 교정 → 재검증
  → 성공·빈 결과·차단·실패 상태 반환
```

최대 검증 횟수는 기본 3회다. 마지막 검증에 실패하면 쿼리를 실행하지 않는다.

## 실행

### API 키 없이 Gold 질문으로 파이프라인 확인

```bash
./.venv/bin/python -m backend.app.agent.cli \
  --provider gold \
  "완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘."
```

`gold` provider는 `evaluation/gold_questions.yml`과 정확히 같은 질문만
지원하는 개발·회귀검증용 생성기다.
기본 출력은 Streamlit용 답변·표·근거 JSON이다. LangGraph 원본 상태를
확인하려면 명령에 `--raw`를 추가한다.

### OpenAI 모델로 새 질문 생성

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4.1-mini"

./.venv/bin/python -m backend.app.agent.cli \
  --provider openai \
  "표면거칠기 불합격이 가장 많이 발생한 이상 유형을 보여줘."
```

모델명은 환경변수로 교체할 수 있다. API 키는 `.env`나 저장소에 커밋하지 않는다.

### OpenAI 키 없이 Vertex Gemini로 새 질문 생성

AskOosu 운영 환경의 서비스 계정 인증을 저장소 밖 전용 경로에 분리했다.
인증 JSON 원문은 이 프로젝트에 포함하지 않는다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/p3-cip-dmd/vertex-service-account.json"
export GOOGLE_VERTEX_LOCATION="us-central1"
export GOOGLE_VERTEX_MODEL="gemini-2.5-flash"

./.venv/bin/python -m backend.app.agent.cli \
  --provider gemini \
  "장비별 공정 실행 횟수를 많은 순서대로 알려줘."
```

`--provider auto`는 OpenAI 키 → Vertex 인증 → Gold 순으로 선택한다.

## 안전장치

애플리케이션 검증:

- `CREATE`, `MERGE`, `SET`, `REMOVE`, `DELETE`, `DROP`, `LOAD CSV`,
  `FOREACH` 등 차단
- `CALL`, APOC, 관리 명령과 다중 statement 차단
- 문자열·주석 안에 등장한 단어는 명령으로 오인하지 않음
- 검증 전과 실제 실행 직전에 각각 읽기 전용 검사
- 장비 표시명/slug 혼동과 질문이 요구한 핵심 필드 누락 검사
- 실행 timeout 10초, 반환 최대 500행

데이터베이스 검증:

```bash
./infra/set_homebrew_mode.sh reader
```

Neo4j Community는 역할 기반 reader 계정이 없으므로 데모·Agent 실행 중에는
DB 전체를 read-only로 둔다. ETL을 다시 수행할 때만 `loader` 모드로 전환한다.

## 주요 파일

| 파일 | 역할 |
|---|---|
| `backend/app/agent/examples.py` | Gold YAML 로드·few-shot 선택 |
| `backend/app/agent/model.py` | OpenAI·Vertex Gemini·Gold·테스트 모델 어댑터 |
| `backend/app/agent/semantic_validation.py` | 도메인 값과 질문-결과 필드 검사 |
| `backend/app/security/read_only.py` | 쓰기·명령·다중 쿼리 차단 |
| `backend/app/agent/graph.py` | EXPLAIN과 읽기 모드 실행 |
| `backend/app/agent/workflow.py` | LangGraph 생성·검증·교정·실행 |
| `backend/app/agent/cli.py` | 로컬 실행 진입점 |

## 현재 한계

- OpenAI 실호출은 미실시지만 Gemini 실제 생성·Blind 평가는 완료했다.
- 고정-seed 26문항 회귀 평가의 의미값 정확도는 61.5%, 엄격 계약
  정확도는 38.5%로 개선이 필요하다.
- 자기수정 오류 주입 8건은 검증 통과 100%, 정답값 회복 37.5%였다.
- 현재 few-shot은 단순 토큰 중복 기반이며 VectorDB 검색은 사용하지 않는다.
- 답변은 조회 결과 기반 템플릿이며 별도 생성 모델로 서술하지 않는다.
