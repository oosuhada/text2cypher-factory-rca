# 엔터프라이즈 2-2 — Home·Projects Workspace

## 구현 결과

- Home
  - 실제 Project Registry 기반 활성·전체·ready·즐겨찾기 요약
  - 최근 프로젝트 3개와 명시적 전환
  - 기존 제품 가치·RCA 검증 지표·시작 CTA 유지
- Projects
  - 이름·ID·도메인·담당자 검색
  - lifecycle 상태 필터와 즐겨찾기 필터
  - 즐겨찾기 우선·활성 프로젝트 우선 정렬
  - lifecycle 진행률과 readiness 다음 행동
  - 담당자·산업·보안등급·source type을 포함한 생성 Wizard
  - 생성 직후 프로젝트 활성화와 Data Sources 이동
- 프로젝트 컨텍스트
  - 대화·마지막 결과
  - Graph Explorer 검색·부분 그래프
  - 최근 upload·load 결과
  - Query·Evaluation 필터
  - 위 상태를 프로젝트별로 deep copy하여 격리·복원

## 권한

| 기능 | Viewer | Analyst | Domain Expert | Data Steward | Admin |
|---|:---:|:---:|:---:|:---:|:---:|
| 프로젝트 조회·전환 | O | O | O | O | O |
| 개인 즐겨찾기 | O | O | O | O | O |
| 프로젝트 생성 | - | - | - | O | O |
| 모델/provider 설정 | - | - | - | O | O |

현재 role selector는 UI 계약 검증용이다. 서버 측 인증·RBAC가 연결되기
전까지 보안 경계로 간주하지 않는다.

## 상태와 다음 행동

```text
draft/profiling → Data Sources
mapping_review → Pipeline
loading/validating → Pipeline
evaluation_required → Evaluations
ready → Query Studio
failed → 소스 유형에 따라 업로드 또는 연결 재시도
```

FastAPI가 실행 중이면 `/projects/{id}/readiness`의 실제 gate 결과를
사용한다. API가 없는 로컬 UI 개발 환경에서는 lifecycle 기반 안내만
표시하며 readiness를 통과한 것으로 가장하지 않는다.

## 검증

- 즐겨찾기 DB migration·영속성
- 프로젝트 검색·상태 필터·정렬
- 프로젝트 컨텍스트 deep-copy 격리와 빈 컨텍스트 복원
- status·next action·relative time 표시 계약
- 기존 API·Registry·Streamlit 회귀
- 새 프로젝트 생성 이후 `Data Sources` 이동 계약

## 잔여 범위

- 실제 SSO 사용자별 즐겨찾기는 Admin/Auth 단계에서 사용자 ID와 분리한다.
- 장시간 데이터 작업의 영속 Job과 재개는 2-3에서 구현한다.

