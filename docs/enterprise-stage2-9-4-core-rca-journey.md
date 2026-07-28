# 2.9-4 핵심 RCA 사용자 여정 완성 기록

## 판정

- 상태: 구현·자동 검증 완료
- 제품 Surface: React `http://localhost:3000`
- 다음 단계: 2.9-5 실제 사용자 기준 Release Gate

## 완성한 기준 여정

```text
Projects에서 준비된 프로젝트 선택
→ Query에서 자연어 RCA 질문
→ 의도·스키마·Cypher·READ-only·Neo4j·근거 진행 상태
→ 자연어 답변과 결과 건수
→ 결과표·관계 그래프·Cypher·검증 trace
→ 전문가 검토 또는 History 이동
→ 프로젝트 컨텍스트를 유지한 채 결과 재열기
```

## 사용자 상태별 다음 행동

| 상태 | 사용자 안내 | 다음 행동 |
|---|---|---|
| success | 조회 결과와 검증 완료 | 결과·관계 근거 확인, History 이동, 전문가 검토 |
| empty | 일치 관계 없음 | 식별자·공정·검사·기간 조건 수정 |
| blocked | 읽기 전용 정책으로 변경 요청 차단 | 삭제·수정 대신 영향 범위 조회로 변경 |
| needs_clarification | 조건 부족 | 설비·제품·부품 ID와 확인 조건 추가 |
| unsupported | 제조 RCA 지원 범위 밖 | genealogy·공정·품질·이상·영향 질문으로 변경 |
| failed | 질의 완료 실패 | 질문을 유지한 채 재시도 |

## 제품 문구와 컨텍스트 수정

- React 답변에서 provider 이름을 제거하고 `읽기 전용 검증 완료`로 표현했다.
- `rows`, `nodes`, `validation`을 한국어 업무 용어로 변경했다.
- Evidence 제목을 `조회 근거`로 변경하고 답변과 같은 조회라는 설명을 유지했다.
- History 카드에서 provider 표시를 제거하고 상태·결과·근거·검증을 표시한다.
- History 재열기 URL에 `project_id`와 `conversation`을 함께 보존한다.
- 준비되지 않은 프로젝트의 내부 콘솔 이동에도 `project_id`를 포함한다.
- 전문가 검토는 성공 결과에서만 노출한다.

## 자동 검증

Playwright 10개 시나리오가 통과한다.

1. 프로젝트 전환과 새로고침 컨텍스트 유지
2. readiness에 따른 React·Internal Console 이동
3. 프로젝트 전환 실패 시 기존 컨텍스트 유지
4. 추천 질문 미리보기와 중복 제출 차단
5. 성공 답변→Evidence→전문가 검토
6. empty·blocked·needs_clarification·unsupported 다음 행동
7. 성공 결과→History→프로젝트 컨텍스트 재열기
8. API 장애 시 질문 보존과 재시도
9. 390px 모바일 내비게이션·overflow
10. 1440px 노트북 헤더·overflow

추가 검증:

- Python 회귀 테스트 237개 PASS
- Backend release/secret/traceability Gate PASS
- UI quality Gate PASS
- Cross-surface architecture Gate PASS
- React ESLint PASS
- Next.js production build PASS

## 남은 제한과 2.9-5 범위

- 실제 사용자 인증·역할 서버 계약은 아직 연결되지 않았으며 현재 demo principal을 사용한다.
- 대량 결과와 768px·1280px 시각 회귀는 2.9-5 제품 Release Gate에서 확대한다.
- 실제 사용자 1인 이상의 무설명 수행 검토는 2.9-5 수동 Gate에 남긴다.
