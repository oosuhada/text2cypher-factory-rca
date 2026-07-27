# 8~11단계 Text-to-Cypher 검증 결과

## 판정

**PASS — 구현 및 로컬 Neo4j 통합 검증 완료**

## 검증 결과

| 항목 | 결과 |
|---|---:|
| Gold YAML 로드 | 15/15 |
| Gold workflow 실제 실행 | 15/15 |
| 빈 결과 Q5 | `empty`, 실행 오류 없음 |
| 정상 질의 경로 | 생성 → 검증 → 실행 |
| 실제 EXPLAIN 문법 오류 감지 | PASS |
| 실제 교정·재검증 경로 | 2회째 통과 후 실행 |
| 반복 오류 안전 종료 | 실행 0회 |
| 생성된 쓰기 쿼리 차단 | EXPLAIN·실행 각 0회 |
| 사용자 쓰기 의도 차단 | 모델 호출·실행 각 0회 |
| 단위 테스트 전체 | 16/16 PASS |
| Neo4j DB 자체 쓰기 차단 | PASS |

## 구현한 상태

- `question`
- `statement`
- `errors`
- `attempts`, `max_attempts`
- `records`
- `status`
- `next_action`
- 노드별 `trace`
- `elapsed_ms`

## 보안 판정

애플리케이션과 데이터베이스의 이중 차단을 사용한다.

1. 사용자 질문의 쓰기 의도 사전 차단
2. 생성 쿼리에서 쓰기 절·procedure·다중 statement 차단
3. `EXPLAIN` 성공 전 실행 금지
4. 실행 직전 동일 검증 반복
5. Neo4j Community 데이터베이스 전체 reader 모드

현재 Neo4j 서비스는 reader 모드이며 Homebrew 서비스로 정상 실행 중이다.

## 미검증 항목

`OPENAI_API_KEY`가 현재 환경에 설정되어 있지 않아 새로운 자연어 질문에 대한
실제 LLM 생성 정확도와 자기수정 품질은 아직 측정하지 않았다. Gold provider와
결정적 테스트 모델로 워크플로·보안·실행 경로는 검증했다.
