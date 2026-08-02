# 제품 리팩터링 7단계 — 도메인 전문가 검증(HITL)

## 목적

LLM과 그래프 조회가 반환한 결과를 최종 사실로 확정하지 않고, 도메인
전문가가 근거를 확인해 판정하고 그 이력을 추적할 수 있게 한다.

## 판정

- `verified`: 원장·현업 기준과 대조해 검증 완료
- `needs_followup`: 추가 데이터나 담당자 확인 필요
- `disputed`: 결과 또는 해석에 이견 있음

판정은 기존 답변이나 Cypher를 수정하지 않는다. 질문과 실행 Cypher의
SHA-256 지문, 상태, 모델, 결과 행 수, 검토자 표시, 의견을 새로운 감사
이벤트로 추가한다.

## 구현

- `FeedbackService`
  - `data/processed/expert_feedback.jsonl` append-only 저장
  - 동일 질문·Cypher 지문과 복수 판정 이력 보존
  - 전체/고유 질의/판정별 건수와 최근 기록 요약
- FastAPI
  - `POST /api/v1/feedback`
  - `GET /api/v1/feedback/summary`
- Streamlit
  - 최신 답변 바로 아래 전문가 판정 폼
  - Dashboard 판정 건수와 최근 감사기록
- Next.js
  - Query Studio 답변 카드 내 판정·의견 입력
  - Operations에 판정 건수와 최근 검토 표시

## 신뢰 경계

- 현재 검토자 값은 계정 인증이 아닌 표시명이다.
- 감사로그는 서버 로컬 파일이며 운영 배포에서는 인증, 접근 제어,
  중앙 로그 저장소 또는 업무 DB로 교체해야 한다.
- 판정은 append-only로 남고 기존 기록을 덮어쓰지 않는다.
- 결과 행 원문은 중복 저장하지 않고 질문·Cypher·메타데이터만 기록한다.

## 완료 기준

- 세 판정 중 하나와 선택적 의견을 기록할 수 있다.
- 동일 질의에 여러 판정이 남아도 기존 기록이 유지된다.
- API, Streamlit, Next.js가 동일한 서비스 계약을 사용한다.
- 운영 화면에서 판정 분포와 최근 이력을 확인할 수 있다.
