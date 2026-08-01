# 17단계 데모 고정·실행 패키징

검증일: 2026-07-27

## 판정

**PASS — 원커맨드 실행과 발표 고정 시나리오 4/4 검증**

## 원커맨드 실행

```bash
./scripts/run_demo.sh
```

스크립트가 순서대로 수행하는 작업:

1. Python 가상환경 확인
2. Neo4j 상태 확인, 필요 시 reader 모드로 재시작
3. CiP-DMD·ETL·Neo4j·생성 모델·평가 결과 프리플라이트
4. Gold 고정 시나리오 4개 실제 Neo4j 스모크
5. 결과를 `data/processed/demo_smoke_latest.json`에 캐시
6. Streamlit 실행

## 고정 발표 시나리오

| 순서 | 시나리오 | 기대 | 실측 |
|---|---|---|---|
| 1 | Q3 제품 Genealogy | success | PASS · 2행 |
| 2 | Q2 품질 실패×이상 분포 | success | PASS · 4행 |
| 3 | Q4 역방향 영향분석 | success | PASS · 37행 |
| 4 | Q5 없는 엔티티 | empty | PASS · 0행 |

## 장애 대응

- `auto` provider는 OpenAI → Vertex Gemini → Gold 순으로 시작한다.
- 실시간 모델이 질의 도중 실패하고 질문이 Gold 고정 문구와 일치하면,
  동일 Neo4j에서 검증된 Gold Cypher로 자동 전환한다.
- Gold 범위 밖 자유 질문은 실패를 숨기지 않고 재연결 안내를 표시한다.
- Neo4j 자체가 연결되지 않으면 앱을 중단된 빈 화면으로 만들지 않고
  진단 표와 복구 명령을 표시한다.

## UI 리팩토링

- Query Studio 답변 바로 아래 결과표·Cypher·관계 그래프 인라인 표시
- 별도 Evidence Lab은 필터·CSV·검증 이력용 상세 화면으로 유지
- Operations에 상태 혼동행렬과 Precision/Recall/F1 추가
- Data & Health에 최근 ETL 시각 증거와 업로드 프리플라이트 추가
- 랜딩 Hero 아래에 Ask→Generate→Verify→Trace 흐름 표시

업로드 UI는 보안상 임의 파일을 운영 Neo4j에 즉시 쓰지 않는다. JSON/CSV를
메모리에서 파싱하고 `part_id` 계열 공통 키를 확인한 뒤, 별도 ETL
`--dry-run`을 거치도록 설계했다.

Blind 26문항의 `success/empty/blocked/needs_clarification` 상태 분류는
정확도·Macro F1 모두 100%다. 이는 질의 결과값 정확도 61.5%와 다른
지표이므로 발표에서도 분리해 설명한다.

## 검증

```bash
.venv/bin/python scripts/demo_preflight.py
.venv/bin/python scripts/demo_smoke.py
.venv/bin/python -m unittest discover -s tests -v
```

- 프리플라이트: 5/5 PASS
- 고정 데모: 4/4 PASS
- 자동 테스트: 62/62 PASS
