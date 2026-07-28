# 엔터프라이즈 트랙 2-4 — Query Studio

## 구현 결과

질문과 답변 근거를 다른 상위 화면으로 이동하지 않고 연속해서
검토할 수 있도록 Query Studio를 재구성했다.

- 활성 project·source·schema·prompt·evaluation version 고정 표시
- 자연어 질문 실행 중 스키마 고정→생성→검증→실행 단계를 상태 UI로 표시
- `success`, `empty`, `blocked`, `failed`, `needs_clarification`,
  `unsupported` 상태별 명시적 문구와 사용자 행동
- 자연어 답변과 결과 건수·검증 횟수·latency·provider 표시
- 결과 표와 CSV 다운로드
- 최초 생성 Cypher와 각 self-correction Cypher를 시도 순서대로 표시
- 실제 조회 결과에서만 관계 경로를 구성하고 빈 결과·차단에서는 생성 금지
- validation·self-correction trace와 오류 표시
- append-only 도메인 전문가 피드백
- 모든 답변의 `이 질문 다시 실행` 행동
- 프로젝트별 대화를 SQLite에 저장하고 재시작 후 재열기·검색·삭제

## 데이터·검증 계약

`CypherState.statement_history`는 생성·수정 statement를 append 방식으로
보존한다. 최종 응답은 기존 최종 `cypher`와 함께 statement history,
검증 trace, 검증된 statement hash, 실행 여부를 제공한다. 따라서
화면은 “최종 쿼리”만 보여주는 대신 어떤 생성 결과가 왜 수정됐는지
감사 가능한 순서로 표시한다.

대화 저장소는 `project_id + conversation_id` 복합키를 사용한다. 다른
프로젝트로 전환하면 메시지·마지막 결과·검색 범위가 섞이지 않는다.
credential과 모델 내부 prompt는 저장하지 않는다.

## 검증

- 5개 필수 runtime 상태의 UI presentation 계약
- 응답 metadata가 현재 version 카드에 우선 적용되는지 검증
- generated→corrected statement 순서 보존
- 대화의 재시작 복원·검색·project scope·삭제
- 기존 Text-to-Cypher 보안·자기수정·실행 회귀
- Streamlit 질문→답변→근거 인라인 E2E
- 전체 Python 회귀, backend release gate, Next.js lint/build
