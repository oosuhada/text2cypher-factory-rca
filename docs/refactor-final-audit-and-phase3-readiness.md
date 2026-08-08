# P3 엔터프라이즈 플랫폼 최종 리팩토링 감사와 3단계 준비도

검증일: 2026-07-28  
대상: Streamlit 운영 프로토타입, React 제품 UI, FastAPI, Neo4j

## 1. 최종 판정

**P3 필수 백엔드와 2단계 엔터프라이즈 UI 기준선은 PASS다.
2.9 실제 사용자 검토는 계속 PENDING이며, 복원 tag를 먼저 고정한 뒤
3-1 LangGraph State·Checkpoint foundation만 선행 구현했다.**

이번 판정은 코드 존재 여부만 확인한 것이 아니다.

- Python 회귀 테스트 226개
- React Playwright 사용자 여정 7개
- Next.js lint·production build
- Streamlit 11개 작업공간 실브라우저 순회
- React 8개 route 실브라우저 순회
- API·Neo4j 실제 연결
- 프로젝트 전환·질의·Evidence·쓰기 요청 차단
- 데스크톱 가로 overflow와 Streamlit URL 지속성
- GitHub Actions 3개 job

을 함께 기준으로 삼았다.

## 2. 지금까지 완성한 기준선

### P3 필수 백엔드 1-1~1-8

- 데이터·스키마·질의 시나리오 계약
- 범용 파일 intake, profile, mapping, dry-run, ETL
- Neo4j 프로젝트 스코프·무결성·멱등성
- 프로젝트별 schema/prompt/Gold/evaluation version
- Text-to-Cypher 생성·READ-only·EXPLAIN·자기수정
- Gold 15문항과 Blind 26문항 평가
- FastAPI와 구조화된 오류 계약
- 보안·lineage·troubleshooting·발표 증적 Release Gate

기준 태그: `p3-required-backend-v1`

### 엔터프라이즈 UI 2-1~2-8

- Home·Projects·Data Sources·Pipeline
- Query Studio·Graph Explorer
- Dashboard·Evaluations
- History·Audit·운영 진단
- 역할별 화면·행동 계약
- CiP-DMD와 Equipment Maintenance History 두 도메인
- Streamlit 운영 UI와 React 제품 UI의 공통 API 계약

기준 태그: `p3-enterprise-ui-v1`

### 이후 공통 플랫폼·제품 리팩토링

- 프로젝트 생성→업로드/연결→mapping→ETL→평가→질의 상태 전이
- 프로젝트 진입 시 권장 작업공간으로 원자적 전환
- Streamlit 세션·대화·사이드바·네비게이션·공통 상태 분리
- Streamlit 10개 page module 분리
- `streamlit_app.py`를 117행 `main()` router로 축소
- React Query를 114행 orchestrator와 6개 전용 module로 분리
- React Projects 공통 카드·생성 폼 분리
- 양쪽 UI의 Evidence·전문가 검증·빈 상태·반응형 개선
- 9단계 교차 UI Release Gate 도입

## 3. 구조 리팩토링 결과

### Streamlit

| 구분 | 결과 |
|---|---|
| 진입점 | `frontend/streamlit_app.py`, 117행, `main()`만 유지 |
| 공통 기반 | `runtime.py`, `session_state.py`, `navigation.py`, `sidebar.py`, `common_ui.py` |
| 페이지 | `frontend/pages/` 10개 module |
| Query 근거 | 결과·Cypher·관계 경로·검증 탭 |
| 전문가 검증 | 권한 확인 후 기본 접힘, 전문가 전용 표시 |
| 네비게이션 | pending state와 `workspace` URL을 원자적으로 갱신 |

### React

| 구분 | 결과 |
|---|---|
| Query orchestrator | `query-workspace.tsx`, 114행 |
| Query module | config, session hook, sidebar, conversation, evidence, expert review |
| Projects | 공통 `ProjectCard`, `ProjectCreateForm` |
| 모바일/노트북 header | 1,600px 이하 drawer, 프로젝트 선택 포함 |
| 질의 | 예시 질문은 preview만 수행, 전송 후 입력 초기화, 동시 중복 제출 방지 |
| Evidence | 결과표 기본, 답변→Evidence 바로가기 |

## 4. Streamlit 시각 리뷰 반영 결과

| 기존 지적 | 최종 결과 |
|---|---|
| 대화 세트가 18회 이상 무한 중복 | 해결. 저장 대화와 현재 turn을 한 번만 복원하며 refresh 회귀 테스트 추가 |
| 중복 widget 때문에 navigation 클릭 불가 | 해결. 실제 Query→Graph Explorer 클릭 성공 |
| 쓰기 요청 처리 상태가 불명확 | 해결. “요청 차단”, “읽기 전용 시스템이므로 실행하지 않음”을 화면에 표시 |
| 근거가 한 컬럼에 길게 쌓임 | 결과·Cypher·관계 경로·검증을 tab으로 분리 |
| 전문가 검증이 항상 펼쳐짐 | 권한 확인 후 접힌 전문가 전용 영역으로 표시 |
| 사이드바 순서 불일치 | 프로젝트→작업공간→대화→실행→역할→언어→안전 순서 확인 |
| 프로젝트 열기 후 복귀/새로고침 문제 | Query 이동과 URL을 함께 갱신하며 refresh 후에도 유지 |
| `Gold` 의미 불명확 | `Gold Question 15/15`로 표기 |

실브라우저에서는 Home, Projects, Data Sources, Pipeline, Query Studio,
Graph Explorer, Dashboard, Evaluations, Approval Queue, Audit Logs, Admin
전체에서 Streamlit exception 0건을 확인했다.

## 5. React 시각 리뷰 반영 결과

| 기존 지적 | 최종 결과 |
|---|---|
| 모바일 header·nav 붕괴 | drawer와 backdrop, 모바일 프로젝트 선택기로 변경 |
| 표준 노트북에서도 header 가로 overflow | 1,600px 이하에서 drawer로 전환, 1,280·1,440·390px 회귀 고정 |
| 예시 질문이 즉시 전송 | 입력창 preview만 수행 |
| 전송 후 질문이 남음 | 전송 직후 입력 초기화 |
| 중복 전송 가능 | in-flight ref로 동시 제출 차단 |
| 답변과 Evidence 관계 불명확 | “같은 조회의 근거 확인” anchor와 공통 설명 추가 |
| Evidence 기본이 그래프 | 결과표를 기본 tab으로 변경 |
| 전문가 검증 목적 불명확 | 기본 접힘과 “전문가 전용” 표시 |
| History 빈 상태 안내 부족 | 현재 프로젝트를 보존하는 첫 질문 CTA |
| 다크 모드 보조 텍스트 대비 | dark `text-soft`와 경계선 대비 강화 |
| 프로젝트 카드 Query가 이전 프로젝트 사용 | project switch와 route 이동을 하나의 transaction으로 처리 |

실브라우저에서는 Home, Projects, Query, Graph, History, Data, Schema,
Operations를 순회했고 API 상태는 `Graph ready`, UI 오류 0건이었다.
실제 CiP-DMD 질문은 2행을 반환했고 입력 초기화, 결과 tab 기본 선택,
Evidence, 접힌 전문가 검증을 확인했다.

## 6. 최종 Release Gate

`./scripts/release_check.sh`는 다음 9개 단계를 순서대로 검사한다.

1. Python 회귀 테스트
2. API·요구사항 추적성·비밀정보
3. Streamlit UI·승인 visual contract
4. 교차 UI 구조·핵심 UX
5. Next.js lint·production build
6. React Playwright
7. script syntax
8. Docker Compose contract
9. 발표·운영 문서

`scripts/cross_surface_release_gate.py`는 다음 퇴행을 병합 전에 차단한다.

- Streamlit 거대 단일 파일 회귀
- React Query·Projects 거대 컴포넌트 회귀
- Streamlit navigation state/URL 불일치
- 모바일 header, 입력 초기화, 중복 제출, Evidence 기본값 회귀
- 전문가 검증과 History empty-state 회귀

로컬에 Docker CLI가 없는 경우 Compose 실행 검증은 GitHub Actions
`packaged-e2e`의 clean stack에서 수행한다.

## 7. 3단계 시작 전 정직하게 남기는 경계

다음 항목은 누락이 아니라 `p3-enterprise-platform-implementation-plan.md`
3단계의 구현 대상이다.

- 3-1에서 구현한 공통 LangGraph State·SQLite 영속 Checkpoint의 운영용 PostgreSQL 전환
- 3-2 Router의 실제 운영 질문 기반 threshold 재보정
- 3-3 Tool Registry에 후속 권고·알림 Tool 추가
- 3-4 LlamaIndex RAG의 운영 embedding·vector DB·문서 보존정책 고도화
- RCA 조치 권고
- LangGraph Interrupt 기반 HITL과 실 Approval Queue
- 승인 후 notification adapter
- 질문→라우팅→Tool→권고→승인→알림 통합 감사 run
- 라우팅·Tool 선택·권고 품질 평가
- SSO/OIDC, DB 수준 멀티테넌시, secret manager

현재 Approval Queue와 Admin은 3단계 화면 구조를 보여주는 foundation이며,
실제 interrupt·approval resume·관리 기능 완료로 표현하면 안 된다.
React 대화 기록은 브라우저 local storage이고 계정 동기화는 아직 없다.
프로젝트 스코프는 앱 계층에서도 강제하지만 실제 상용 배포에서는 DB/tenant
계층의 물리적 또는 논리적 격리를 추가해야 한다.

## 8. 3단계 진입 순서

이 문서의 이전 `READY` 판정은 2.9 제품 사용자 Gate 결과로 대체한다.

준비도 판정:

- 2.9-5: **AUTOMATION PASS · MANUAL USER REVIEW PENDING**
- 3-1 foundation: **IMPLEMENTED · AUTOMATIC VALIDATION PASS**
- 3-2 Project Router: **IMPLEMENTED · EVALUATION PASS**
- 3-3 Tool Registry: **IMPLEMENTED · TOOL GATE PASS**
- 3-4 LlamaIndex 문서 RAG: **IMPLEMENTED · RAG GATE PASS**
- 3-5 이후 제품 통합: **HOLD**

자동 Gate는 통과했지만 실제 사용자 1인 이상의 무설명 대표 여정 검토는
아직 완료되지 않았다. 따라서 P3 최종 사용자 서비스를 `READY`로 선언하지
않는다. 사용자의 명시적 결정에 따라 3-1 시작 전 현재 제품 기준선을 원격
annotated tag `p3-stage2-9-pre-stage3-v1`로 고정하고, 각 단계 완료 시 별도
복원 tag를 추가하면서 3-1부터 3-4까지 선행했다. 구현 기록은
[`enterprise-stage3-1-langgraph-state-checkpoint.md`](./enterprise-stage3-1-langgraph-state-checkpoint.md),
[`enterprise-stage3-2-project-router.md`](./enterprise-stage3-2-project-router.md),
[`enterprise-stage3-3-tool-registry.md`](./enterprise-stage3-3-tool-registry.md),
[`enterprise-stage3-4-llamaindex-document-rag.md`](./enterprise-stage3-4-llamaindex-document-rag.md)를,
수동 기록 양식은
[`enterprise-stage2-9-5-product-release-gate.md`](./enterprise-stage2-9-5-product-release-gate.md)를 따른다.

다음 권장 순서는 다음과 같다.

1. 3-5 RCA 권고
2. 3-6 HITL Interrupt·Approval Queue
3. 3-7 알림 Tool
4. 3-8 통합 감사로그·상태 UI
5. 3-9 판단 품질 평가
6. 3-10 이상감지 Tool은 데이터 적합 시에만 선택
7. 3-11 보안·운영·최종 E2E

3-1 이후 변경은 기존 P3 질의 경로와 단계별 복원 tag를 보존한다. 2.9-5 수동
Gate가 완료되기 전까지는 자동 Gate 통과를 최종 사용자 서비스 `READY`로
표현하지 않는다.
