# 리팩토링 5단계 — 최종 Release Gate

## 목적

백엔드 단위 테스트와 빌드 성공만으로 릴리스를 승인하지 않는다. Streamlit과
React 두 사용자 화면의 구조, 핵심 UX, 실제 브라우저 사용자 여정을 하나의
교차 표면(cross-surface) 계약으로 묶는다.

## 릴리스 조건

1. Python 전체 회귀 테스트 통과
2. P3 필수 API·요구사항 추적성·비밀정보 검사 통과
3. Streamlit UI 품질 및 승인된 시각 계약 통과
4. 교차 UI 구조·핵심 UX 계약 통과
5. Next.js lint 및 production build 통과
6. Playwright 실제 사용자 여정 통과
7. 실행 스크립트 문법 검사 통과
8. Docker Compose 배포 계약 통과
9. 필수 발표·운영 문서 존재 확인

## 교차 UI 구조 계약

- `frontend/streamlit_app.py`는 `main()`만 갖는 150행 이하 진입점이다.
- Streamlit의 10개 작업공간은 `frontend/pages/`에 분리한다.
- React Query는 150행 이하 orchestrator이고 상태·사이드바·대화·근거·전문가
  검증을 별도 컴포넌트로 유지한다.
- React Projects의 개요·목록·생성 폼은 공통 카드와 폼을 사용한다.

## 교차 UI 핵심 UX 계약

- 모바일 React 내비게이션은 메뉴·드로어와 별도 프로젝트 선택기를 제공한다.
- 표준 노트북 폭에서도 header가 넘치기 전에 드로어로 전환한다.
- 예시 질문은 입력창을 채우고, 제출 후 입력은 비우며 동시 중복 제출을 막는다.
- Evidence는 결과표를 기본 탭으로 열고 답변에서 근거 패널로 바로 이동한다.
- 전문가 검증은 기본 접힘 상태이며 전문가 전용임을 표시한다.
- History 빈 상태는 현재 프로젝트를 유지한 Query CTA를 제공한다.
- Streamlit 답변 근거는 결과·Cypher·관계 경로·검증 탭으로 나눈다.
- Streamlit 프로그램 이동은 상태와 `workspace` URL을 함께 갱신한다.

## 실행

```bash
./scripts/release_check.sh
```

교차 계약만 빠르게 검사하려면 다음을 사용한다.

```bash
.venv/bin/python scripts/cross_surface_release_gate.py
```

최종 화면 승인에는 자동 게이트와 별도로 실제 브라우저 데스크톱·모바일 검증을
수행하고 결과를 최종 감사 문서에 기록한다.
