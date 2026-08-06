# 엔터프라이즈 트랙 2-8 — UI 품질 Gate

## 구현 결과

Streamlit을 발표용 단일 화면이 아니라 역할과 프로젝트 상태를 가진 사내
운영 프로토타입으로 검증하는 품질 Gate를 추가했다.

### 반응형·접근성

- 760px 모바일 breakpoint와 column stacking
- 키보드 사용자를 위한 skip link
- 모든 control의 명확한 `focus-visible` outline
- 최소 control 높이
- `prefers-reduced-motion`
- Windows high-contrast `forced-colors`
- 표와 차트를 함께 제공해 색상만으로 상태를 전달하지 않음

### 한국어·영어

사이드바에서 한국어/English를 전환한다. workspace 이름과 데이터·모델
고유명은 유지하며 page description, 운영/계획 badge, 접근성 안내 문구를
선택한 언어로 표시한다. 제조 질문·Cypher·원본 속성은 감사 재현성을 위해
번역하지 않는다.

### 역할 기반 UI

메뉴뿐 아니라 행동 권한을 별도 계약으로 고정했다.

| 역할 | 핵심 여정 |
|---|---|
| Viewer | 조회·그래프·Dashboard·증적 export |
| Analyst | Viewer + 평가·감사·질문 재실행 |
| Domain Expert | Analyst + 결과 판정·승인 큐 |
| Data Steward | Expert + Data Sources·Pipeline·적재 관리 |
| Admin | 전체 메뉴·플랫폼 관리 |

Viewer는 전문가 판정과 질문 재실행을 할 수 없고, Data Steward/Admin만
데이터 적재 관련 화면에 접근한다. 현재 역할 선택기는 제품 검증용
preview이며 상용 배포에서는 SSO claim을 같은 action matrix에 연결한다.

### 상태·복구

- 질의·검색·적재의 spinner/status/progress
- 프로젝트 전환 toast
- 빈 상태와 actionable error
- API/Neo4j 장애 시 diagnostics와 “서비스 다시 연결”
- 모델 인증 부재 시 Gold 고정 데모 fallback
- 프로젝트별 conversation/filter/explorer 상태 격리
- `st.cache_resource` service bundle versioning과 명시적 cache clear

## 브라우저·visual regression

실제 브라우저에서 다음 화면을 확인했다.

- Home
- Dashboard
- Evaluations
- Audit Logs의 History·Timeline·Run detail
- 한국어/영어 전환
- desktop/mobile breakpoint

CI에는 픽셀 이미지 자체 대신
`evaluation/ui_visual_baseline.json`을 승인된 visual contract로 둔다.
이 파일은 CSS SHA-256, breakpoint, 접근성 계약, 주요 화면 landmark와
navigation delivery 상태를 고정한다. UI 변경으로 hash나 핵심 landmark가
달라지면 `scripts/ui_quality_gate.py`가 실패하며, 브라우저 확인 후
baseline을 명시적으로 갱신해야 한다. 폰트·OS 렌더링 차이로 인한 불안정한
pixel diff보다 재현 가능한 구조 회귀를 CI 기준으로 사용하고, 실제 화면은
릴리스마다 브라우저에서 추가 확인한다.

## 두 도메인·릴리스 여정

Gate는 `cip-dmd`와 `equipment-history` schema가 모두 존재하는지 확인한다.
프로젝트별 conversation, evaluation filter, graph selection과 cache가
분리되는 기존 회귀 테스트를 함께 실행한다.

두 번째 도메인 실측 중 파일 업로드의 실행 ID(UUID)를 데이터셋의 의미적
`source_version`으로 취급하던 lineage 결함을 발견했다. 이를 다음과 같이
수정하고 실제 Equipment History 그래프에서 재검증했다.

- 업로드 ID: 어떤 파일 묶음을 승인했는지 추적하는 실행 lineage
- source version: schema·prompt·evaluation을 묶는 데이터셋 버전
- 승인 mapping: 현재 프로젝트의 실제 upload ID와 연결됐는지 별도 확인
- mapping schema version: top-level 또는 `manifest.version`에서 확인
- 결과: readiness 9/9 PASS, 20 nodes / 24 relationships, Gemini 질의
  `success` 및 4행 반환
- Query Studio 추천 질문과 입력 예시도 project별 schema 용어로 격리해,
  Equipment History 화면에 CiP-DMD의 완제품·품질검사 질문이 노출되지 않음

최종 UI 여정:

`Projects → Data Sources → Pipeline → Evaluations → Query Studio → Graph Explorer → Audit Logs`

즉 프로젝트 생성 → 데이터 업로드/연결 → mapping·적재·무결성 → 평가 →
질의 → 근거 탐색 → 실행 증적 보관을 Streamlit 안에서 끝낼 수 있다.

## 자동 검증

```bash
.venv/bin/python scripts/ui_quality_gate.py
./scripts/release_check.sh
```

`release_check.sh`는 Python 회귀, API·비밀정보 계약, UI quality/visual
baseline, Next.js lint/build, script syntax, container contract와 릴리스
문서를 한 번에 검증한다.
