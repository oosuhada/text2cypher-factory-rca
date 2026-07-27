# 14단계 실제 Agent 서비스·UI 연결 검증

검증일: 2026-07-27

## 판정

**PASS — Vertex AI Gemini 실호출 포함**

실제 Neo4j, Gold 회귀검증, 자유 질문 Gemini 어댑터, 상태별 UI와 재시도
경로를 검증했다. OpenAI 키는 없지만 이것이 더 이상 자유 질문 실행의
블로커가 되지 않으며, `auto` 모드가 Vertex AI Gemini로 자동 전환한다.

## 검증 결과

| 시나리오 | 결과 |
|---|---|
| Gold 정상 질문 → 실제 Neo4j 결과·Cypher·근거 | PASS |
| Gold 미등록 질문 → 불필요한 3회 재시도 없이 지원 범위 안내 | PASS |
| Gemini 미등록 자유 질문 → Cypher 생성·검증·실행 | PASS |
| 존재하지 않는 엔티티 → 허위 생성 없이 `empty` | PASS |
| 쓰기·삭제 요청 → 모델·DB 실행 전 `blocked` | PASS |
| 모호한 질문 → `needs_clarification` | PASS |
| 의미/EXPLAIN 검증 실패 → Gemini 교정 후 재검증 | PASS |
| 서비스 초기화 실패 → 재연결 버튼 | PASS |
| 호출별 토큰·지연시간·추정비용 기록 | PASS |
| OpenAI 실제 호출 | 미실시·선택 사항 |

## Provider 선택 순서

1. `OPENAI_API_KEY`가 있으면 OpenAI
2. 없고 Vertex 인증정보가 있으면 Gemini
3. 둘 다 없으면 Gold 회귀검증 전용 모드

Vertex 서비스 계정 JSON은 저장소 밖
`~/.config/p3-cip-dmd/vertex-service-account.json`에 보관하며 파일 권한은
소유자 읽기·쓰기만 허용한다. 키 원문은 코드·로그·Git에 저장하지 않는다.

## 자동 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
```

결과: **62/62 PASS**

실제 생성 모델 수치는 [16단계 검증](./stage16-validation.md)에 기록했다.
