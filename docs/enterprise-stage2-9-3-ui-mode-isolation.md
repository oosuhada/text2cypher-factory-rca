# 2.9-3 개발·평가 기능 격리 구현·검증

## 목적

제품·데모 화면에서 개발 환경 설명과 회귀평가 제어를 제거하고, 필요한 진단 기능만 development 프로필에서 사용할 수 있게 한다.

## 런타임 프로필

| 모드 | 용도 | 노출 정책 |
|---|---|---|
| `production` | 배포 환경 | 서버 관리 provider·role 사용, 개발 제어 숨김 |
| `demo` | 발표·검증 기본값 | production과 동일한 노출 정책 |
| `development` | 로컬 개발·QA | provider·model 선택, Gold 회귀, 역할 미리보기, 내부 연결 진단 허용 |

환경변수:

```text
P3_UI_MODE=production|demo|development
P3_UI_ROLE=Data Steward
P3_API_PROVIDER=auto
P3_API_MODEL=
```

기본값은 `demo`다. 인증 연결 전 production·demo 역할은 `P3_UI_ROLE`로 고정하며 기본 역할은 `Data Steward`다.

## 구현 내용

- `frontend/ui_mode.py`에 모드·고정 역할·workspace visibility·서버 관리 provider 계약을 추가했다.
- production·demo에서 생성 모드, 생성 모델, provider fallback 설명과 역할 미리보기를 렌더링하지 않는다.
- provider와 model은 `P3_API_PROVIDER`, `P3_API_MODEL`에서 읽는다.
- production·demo 메뉴에서 `Approval Queue`, `Admin` foundation 화면을 숨긴다.
- 페이지 헤더는 개발 단계 대신 `운영 화면` 상태만 표시한다.
- 실제 provider·model·transport 정보는 development에서만 `개발 진단`으로 표시한다.
- 시작 실패 화면은 production·demo에서 환경변수명, 내부 예외 문자열, 복구 명령을 숨긴다.
- Gold·Blind 실행과 비교 기능은 Streamlit `Evaluations` 내부 콘솔에 유지한다.

## 배포 금지 문구

production·demo 렌더링 결과에서 다음 문구를 금지한다.

- OpenAI 키
- Gemini를 자동 사용
- Gold Question 데모
- 역할 미리보기
- Stage 3-
- foundation
- 실제 연결:
- transport

## 검증

- 기본 모드가 `demo`인지 확인
- 잘못된 `P3_UI_MODE` 거부
- demo에서 foundation workspace 숨김
- development에서 내부 제어 유지
- demo Streamlit DOM 배포 금지 문구 0건
- 기존 development Gold 질의·프로젝트 전환·복구 테스트 유지
- 전체 Python·UI·React Release Gate 통과

## 완료 판정

production·demo는 개발자 설명 없이 내부 운영 업무만 표시한다. 개발·회귀평가 제어는 development 또는 Evaluations 내부 작업공간으로 격리됐다. 2.9-4 핵심 RCA 사용자 여정 완성 단계로 이동할 수 있다.
