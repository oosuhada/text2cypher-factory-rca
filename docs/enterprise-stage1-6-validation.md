# 엔터프라이즈 트랙 1-6 구현·검증

## 구현 결과

Text-to-Cypher의 생성 → 검증 → 교정 → 재검증 → 실행 흐름을 두
프로젝트가 같은 LangGraph workflow로 사용하도록 완결했다.

- `PromptRegistry`와 `prompts/{project_id}/manifest.yml`을 추가해
  schema context, few-shot, 시도 횟수, timeout을 프로젝트별로 분리했다.
- schema·source·prompt·evaluation version과 prompt template hash를
  응답 metadata, evidence provenance, 감사로그에 기록한다.
- READ 전용·다중 statement 차단 뒤 schema 기반 domain value 검사와
  Neo4j `EXPLAIN`을 수행한다.
- 검증을 통과한 Cypher SHA-256과 실행 직전 문자열을 비교한다. 일치하지
  않는 쿼리는 `VERIFICATION_REQUIRED`로 종료하므로 미검증 실행 경로가 없다.
- 모델, 검증기, Neo4j 실행 오류와 전체 처리 timeout을 `failed` 계약으로
  정규화했다.
- 실제 서비스와 Blind 평가가 같은 `TextToCypherAgent`를 사용하도록
  중복 평가 루프를 제거했다.
- 사용자 질문에 직접 포함된 미등록 ID는 빈 결과 확인을 위해 허용하되,
  enum 번역 오류와 모델이 새로 만든 값은 계속 차단한다.

## 검증 결과

2026-07-28 로컬 Neo4j와 Vertex Gemini 2.5 Flash 기준이다.

| 검증 | CiP-DMD | 설비 정비 이력 |
|---|---:|---:|
| Gold 수동 Cypher | 15/15 PASS | 15/15 PASS |
| Blind 정답 snapshot | 23/23 PASS | 18/18 PASS |
| Blind 전체 질문 | 26 | 20 |
| Self-correction 실행 성공률 | 100% | 100% |
| 의미 결과 정확도 | 61.5% | 85.0% |
| 엄격 계약 정확도 | 34.6% | 30.0% |
| schema 준수율 | 100% | 100% |
| READ 전용 준수율 | 100% | 100% |
| 빈 결과 처리율 | 100% | 100% |
| 상태 분류 정확도 | 100% | 95.0% |

실측 보고서는 다음 파일에 고정했다.

- `evaluation/results/cip-dmd/latest.json`
- `evaluation/results/cip-dmd/latest.md`
- `evaluation/results/equipment-history/latest.json`
- `evaluation/results/equipment-history/latest.md`

## 발견·수정한 결함

첫 실측에서 범용 domain validator가 `Process.name`과 `Equipment.name`을
속성명만으로 비교해 정상 Cypher를 거절했고 CiP-DMD 정확도가 42.3%까지
떨어졌다. 노드 라벨과 변수 별칭을 함께 추적하도록 수정한 후 의미 정확도
61.5%, 실행·schema 준수율 100%를 회복했다.

또한 존재하지 않는 장비를 묻는 질문까지 환각 방지 규칙이 차단하던 문제를
수정했다. schema identity 속성의 값이 사용자 질문에 직접 등장하면 READ
필터로 유지하여 DB가 `empty`를 반환하게 하고, enum 값과 모델이 새로 만든
식별자는 계속 차단한다.

## 남은 한계

- CiP-DMD 의미 정확도 61.5%는 통합 명세의 목표 70%에 미달한다.
  남은 오류는 주로 올바르게 실행되지만 반환 행·집계가 Gold와 다른 경우다.
- 관계 속성 별칭 오류 한 건은 3회 자기수정 후에도 복구되지 않았다.
- 설비 정비 이력의 확인 필요 질문 한 건을 Gemini가 일반 질의로 처리해
  상태 분류 정확도가 95%였다. 자연어 모호성 분류는 3단계 Router에서
  별도 평가한다.
- 정규식 project scope는 학생 프로젝트 수준의 방어이며, 실제 다중
  고객 운영에서는 Neo4j database 분리나 DB 수준 멀티테넌시가 필요하다.
