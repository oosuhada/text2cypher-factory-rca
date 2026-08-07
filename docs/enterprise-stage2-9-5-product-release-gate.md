# 2.9-5 실제 사용자 기준 Product Release Gate

## 판정

- 자동 Release Gate: **PASS**
- 실제 사용자 무설명 수행 검토: **PENDING**
- P3 최종 사용자 서비스 최종 판정: **NOT READY — MANUAL USER REVIEW PENDING**
- 3단계 진입: **HOLD**

자동화 통과를 실제 사용자 검토 통과로 대신 선언하지 않는다. 최종 `READY`는
아래 수동 검토를 실제 사용자 1인 이상이 수행하고 기록한 뒤에만 판정한다.

## 산출물

| 산출물 | 역할 |
|---|---|
| `evaluation/product_user_release_baseline.json` | 제품 route·내비게이션·화면 폭·금지 문구·fixture·수동 검토 기준선 |
| `scripts/product_user_release_gate.py` | React·Streamlit·접근성·fixture 계약과 Streamlit 표시 메뉴 실행 Gate |
| `tests/test_product_user_release_gate.py` | 자동 Gate가 수동 검토를 `READY`로 오판하지 않는 Python 회귀 |
| `web/tests/product-release-gate.spec.ts` | 표시 링크·DOM·console·반응형·키보드·극단 fixture·핵심 여정 Playwright Gate |
| `scripts/release_check.sh` | 기존 전체 Release Gate에 제품 사용자 Gate 통합 |

## 자동 Gate 범위

### React 제품

- 제품 기본 진입점은 React 하나로 고정한다.
- 표시 제품 메뉴는 `Projects`, `Query Studio`, `Evidence / Graph`, `History`다.
- Home·Projects·Query·Graph·History의 `h1`, 의미 있는 본문과 다음 행동을 확인한다.
- 모든 표시 링크를 실제 클릭하고 제품 route, Streamlit, 새 창 외부 링크의 비어 있지 않은 목적지를 확인한다.
- 브라우저 `console.error`와 uncaught page error를 0건으로 강제한다.
- production·demo 배포 금지 문구를 DOM과 제품 source에서 검사한다.
- 390·768·1280·1440px에서 document·body 가로 overflow를 0건으로 강제한다.
- 표시된 link·button·input·select·textarea·summary에 접근 가능한 이름이 있는지 검사한다.
- 첫 Tab으로 skip link에 진입하고 `focus-visible` outline과 본문 이동을 확인한다.

### Streamlit Internal Console

- 자동 Streamlit sidebar navigation은 비활성화되어야 한다.
- 커스텀 `작업공간 이동` 그룹은 정확히 하나여야 한다.
- demo·production의 Data Steward 표시 메뉴는 9개로 고정한다.
- AppTest로 Home부터 Audit Logs까지 9개 표시 메뉴를 모두 선택한다.
- 각 메뉴의 exception 0건, 빈 markdown 본문 0건, 배포 금지 문구 0건을 확인한다.
- Playwright가 Next와 Streamlit을 함께 기동해 React에서 Internal Console로 이동하는 링크도 실제로 연다.

### 극단 fixture와 핵심 여정

- 78자 프로젝트명
- 프로젝트 0건 상태
- 결과 120행
- 질의 API 503 오류
- 프로젝트 전환
- 추천 질문 미리보기 후 1회 전송
- 입력 초기화와 중복 제출 차단
- 답변에서 Evidence 이동
- Graph 검색·경로 열기
- History 저장·재열기
- 쓰기 요청 차단
- 오류 후 질문 보존·재시도

## 자동 검증 결과

2026-07-29 실제 checkout의 `main`에서 실행했다.

| 검사 | 결과 |
|---|---|
| Python 전체 회귀 | **242 PASS** |
| Backend API·traceability·secret Gate | **PASS** · secret 0건 · OpenAPI 28 paths/25 schemas · 요구사항 38 완료 |
| Enterprise UI quality Gate | **PASS** |
| Cross-surface Gate | **PASS** |
| Product-user Python Gate | **PASS** · 최종 `READY`는 false · manual `PENDING` |
| Streamlit 표시 메뉴 | **9/9 클릭 성공 · 빈 본문 0 · exception 0 · 금지 문구 0** |
| React 전용 Product Gate | **10/10 PASS** |
| 전체 Playwright | **20/20 PASS** |
| React 표시 링크 | **내부·Streamlit·새 창 외부 링크 클릭 성공률 100% · 빈 목적지 0** |
| 브라우저 오류 | **console error 0 · page error 0** |
| 반응형 | **390·768·1280·1440px overflow 0** |
| 접근성 계약 | **skip link·focus-visible·semantic main·form label·keyboard·reduced motion PASS** |
| Next.js ESLint | **PASS** |
| Next.js production build | **PASS** |
| 통합 `release_check.sh` | **PASS** · 로컬 Docker CLI 미설치로 Compose 실행 검증은 CI에 이관 |

Playwright 실행 중 Cytoscape가 개발 console에 wheel sensitivity 경고를 출력하지만,
이는 `console.error`가 아니며 테스트 실패나 브라우저 예외로 분류되지 않는다.
제품 Gate는 error 수준 console 메시지와 uncaught page error를 별도로 수집해 0건을 확인한다.

## 실행 절차

저장소 루트에서 Python Gate를 실행한다.

```bash
.venv/bin/python scripts/product_user_release_gate.py --json
```

React·Streamlit 브라우저 Gate는 Playwright 설정이 두 서버를 함께 기동한다.

```bash
cd web
corepack pnpm test:e2e
```

전체 회귀·Gate·lint·build·E2E·문서 계약은 한 번에 실행할 수 있다.

```bash
./scripts/release_check.sh
```

직접 설치된 `pnpm`이 없으면 `release_check.sh`는 저장소의
`packageManager` 선언에 맞춰 `corepack pnpm`을 사용한다. 실행 중인 개발용
Next 서버와 충돌하지 않도록 Playwright와 production build는 각각
`.next-playwright`, `.next-release` 디렉터리를 사용한다.

## 수동 사용자 검토 기록

현재 상태: **PENDING**

실제 사용자 1인 이상에게 사전 설명 없이 다음 기준 여정을 수행하게 한다.

```text
서비스 목적 파악
→ 준비된 프로젝트 선택
→ 추천 질문 확인과 질문 전송
→ 답변·결과표 확인
→ Evidence와 Graph 근거 찾기
→ History에서 결과 재열기
→ 쓰기 요청 차단 후 가능한 다음 행동 설명
```

검토자는 아래 질문에 답하고 막힌 지점·오해한 문구·불필요한 요소를 기록한다.

- 10초 안에 서비스 목적을 자신의 말로 설명했는가?
- 첫 화면에서 다음 행동을 도움 없이 찾았는가?
- 답변의 근거와 안전 검증을 도움 없이 찾았는가?
- 실패·차단 상태에서 가능한 다음 행동을 이해했는가?
- React 제품과 Streamlit Internal Console의 역할 차이를 이해했는가?

기록 형식:

| 항목 | 기록 |
|---|---|
| 검토 일시 | 미실시 |
| 검토자 | 미실시 |
| 완료 여부 | PENDING |
| 막힌 단계 | 미실시 |
| 오해한 문구 | 미실시 |
| 개선 필요 요소 | 미실시 |
| 최종 수동 판정 | PENDING |

## 최종 READY 전환 조건

다음 조건을 모두 만족할 때만 baseline의 `manual_review.status`를 `PASS`로 바꾸고
P3 최종 사용자 서비스를 `READY`로 판정한다.

1. 자동 Gate가 계속 전부 통과한다.
2. 실제 사용자 1인 이상의 무설명 대표 여정이 통과한다.
3. 수동 검토 기록에 막힌 지점과 조치 결과가 남는다.
4. 수정이 발생했다면 전체 `release_check.sh`를 다시 통과한다.
5. 수동 검토 통과를 포함한 별도 커밋 이후에만 3-1을 시작한다.

현재는 자동화 기준선만 통과했으므로 2.9 구현 상태는
`AUTOMATION PASS · MANUAL REVIEW PENDING`, 최종 서비스와 3단계 진입은 `HOLD`다.
