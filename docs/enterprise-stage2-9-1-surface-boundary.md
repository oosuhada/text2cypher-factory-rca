# 엔터프라이즈 2.9-1 — 단일 제품 UI와 Surface 경계 고정

검증일: 2026-07-28  
상태: **구현·검증 완료**

## 1. 목적

P3의 최종 사용자 제품과 내부 개발·평가·운영 도구를 분리한다.
React와 Streamlit이 같은 기능을 서로 다른 UX로 경쟁하지 않도록 기능
소유권, 기본 진입점, 메뉴와 호환 URL을 코드·문서·테스트에 고정한다.

## 2. 최종 Surface 결정

| Surface | 기본 URL | 대상 | 소유 기능 |
|---|---|---|---|
| React Product UI | `http://localhost:3000` | 분석가, 도메인 전문가, 발표 평가자 | 프로젝트 선택, RCA 질문, 답변·결과표, Evidence·Graph, History, Expert Review |
| Streamlit Internal Console | `http://localhost:8501` | 개발자, Data Steward, 평가 담당자, Admin | 데이터 소스, Pipeline, 평가, 감사, 모델·운영 진단 |
| FastAPI | `http://127.0.0.1:8000` | 두 UI와 자동화 클라이언트 | 프로젝트·질의·평가·상태의 source of truth |
| Neo4j Browser | `http://localhost:7474` | 개발자·DB 운영자 | 스키마·데이터·Cypher 진단 |

React가 최종 사용자와 발표의 단일 제품 진입점이다. Streamlit은 제품
랜딩을 소유하지 않으며 `Internal Console`로 표시한다.

## 3. 제품 내비게이션

React 기본 내비게이션은 다음 네 항목으로 축소했다.

```text
Projects → Query → Evidence / Graph → History
```

Expert Review는 Query 결과 내부에서 권한이 있는 사용자에게 제공한다.
Data, Schema, Operations는 제품 헤더에서 제거했다.

## 4. 중복 기능 축소 방식

| 기존 React 경로 | 소유 Surface | 처리 |
|---|---|---|
| `/data` | Streamlit Data Sources | `workspace=data_sources`로 리디렉션 |
| `/schema` | Streamlit Pipeline | `workspace=pipeline`으로 리디렉션 |
| `/operations` | Streamlit Dashboard | `workspace=dashboard`로 리디렉션 |

리디렉션은 `project_id`를 함께 전달한다. Streamlit은 URL의
`project_id`를 읽어 Registry와 session context를 전환한다. 따라서 준비되지
않은 프로젝트의 다음 작업을 내부 콘솔에서 열어도 다른 프로젝트 데이터가
표시되는 것을 방지한다.

예시:

```text
http://localhost:3000/data?project_id=equipment-history
→ http://localhost:8501/?workspace=data_sources&project_id=equipment-history
```

## 5. 공통 용어

### 프로젝트 상태

| 내부 값 | 사용자 표시 |
|---|---|
| `draft` | 초안 |
| `profiling` | 프로파일링 |
| `mapping_review` | 매핑 검토 |
| `loading` | 적재 중 |
| `validating` | 무결성 검증 |
| `evaluation_required` | 평가 필요 |
| `ready` | 질의 가능 |
| `failed` | 조치 필요 |
| `archived` | 보관됨 |

React 프로젝트 카드와 헤더 선택기는 raw 상태값이나 영어 운영 문구 대신
이 용어를 사용한다. Streamlit의 기존 `status_presentation`과 의미를 맞췄다.

### 역할

- Viewer
- Analyst
- Domain Expert
- Data Steward
- Admin

실제 역할 노출과 개발용 역할 미리보기 격리는 2.9-3에서 완결한다.

## 6. 구현 변경

### 공통 계약

- `frontend/design_system.py`
  - `PRODUCT_UI_NAVIGATION`
  - `INTERNAL_CONSOLE_NAVIGATION`
  - `SURFACE_OWNERSHIP`
  - React·Streamlit·Backend 경계 재정의
- `web/lib/product-surface.ts`
  - 제품 메뉴
  - 내부 콘솔 URL 생성
  - 프로젝트 상태·readiness 사용자 문구
  - 기능 소유권 계약

### React

- `site-header.tsx`의 내부 운영 메뉴 제거
- `site-footer.tsx`에 Internal Console handoff 추가
- 제품 홈에서 Gold·Blind·provider 중심 개발 문구 제거
- `/data`, `/schema`, `/operations`를 내부 콘솔 호환 리디렉션으로 변경
- 프로젝트 상태를 한국어 업무 용어로 통일

### Streamlit

- 브라우저·앱 제목을 `Factory Graph RCA — Internal Console`로 변경
- 제품형 RCA 랜딩을 내부 운영 홈으로 교체
- React 제품 UI 이동 링크 제공
- Data·Pipeline·Evaluations·Audit 바로가기 제공
- 사이드바에 내부 콘솔 역할을 명시
- React에서 전달한 `project_id`를 소비해 프로젝트 컨텍스트 전환

### 문서·실행 안내

- README의 공식 제품 UI를 React로 변경
- Streamlit을 내부 운영 콘솔로 재분류
- 발표 시작 주소와 사용자 동선을 React 기준으로 변경
- 제품·내부 콘솔·API·DB URL을 역할별로 구분

## 7. 자동 검증

- Python 전체 회귀: **226/226 PASS**
- 교차 Surface Gate: **PASS**
- React ESLint: **PASS**
- Next.js production build: **PASS**
- React Playwright: **7/7 PASS**

Playwright는 다음을 포함한다.

- 제품 메뉴에 Data·Schema·Operations가 없는지
- 모바일·노트북 내비게이션과 overflow
- 프로젝트 전환과 Query 딥링크
- 준비 상태별 Internal Console handoff
- `project_id` 보존
- 질문 preview, 중복 제출 차단
- 답변·Evidence·Expert Review 연결

## 8. 실제 브라우저 검증

실행 중인 로컬 서버에서 확인했다.

### React `:3000`

- 표시 메뉴: Projects, Query, Evidence / Graph, History
- Data, Schema, Operations 메뉴: 0건
- 제품 홈의 `Gold Question`, Gemini fallback 설명: 0건
- `/data?project_id=equipment-history`가 해당 프로젝트 ID를 유지한 채
  Streamlit Data Sources로 이동

### Streamlit `:8501`

- 첫 화면과 사이드바에 `Internal Console` 표시
- React 제품 UI 이동 링크 표시
- URL의 `project_id`가 Registry 활성 프로젝트에 반영됨
- Internal Console 각 화면에 의미 있는 본문 존재

## 9. 완료 판정

2.9-1 Gate는 통과했다.

- 제품 기본 진입점은 React 하나다.
- Streamlit은 내부 콘솔로 명시됐다.
- 메뉴·기능 소유권과 URL map이 코드와 문서에 고정됐다.
- 중복 React 운영 경로는 내부 콘솔 리디렉션으로 축소됐다.
- 발표 핵심 여정은 React의 Projects → Query → Evidence / Graph → History로
  구성된다.

## 10. 다음 단계에 남기는 경계

다음 문제는 2.9-1 완료로 해결됐다고 표현하지 않는다.

- Streamlit의 자동 `stSidebarNavItems`와 내부 모듈 파일 노출
- 자동 페이지 링크 클릭 시 흰 빈 화면
- provider·model·API 키 fallback·Gold mode·역할 미리보기 노출
- `Stage 3-x`, foundation과 미완성 화면 노출
- production·demo·development 런타임 프로필
- 실제 사용자 기준 전체 RCA Release Gate

다음 작업은 계획서의 **2.9-2 Streamlit 자동 페이지 충돌 제거**다.
3단계 Agentic AI 진입 상태는 계속 `HOLD`다.
