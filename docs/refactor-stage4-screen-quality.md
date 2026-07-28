# 리팩토링 4단계 · 화면별 품질 개선

## 반영한 시각 리뷰

### Streamlit

- 대화 중복 렌더링과 네비게이션 차단 회귀 계약 유지
- 답변 근거를 결과·Cypher·관계 경로·검증 4개 탭으로 정리
- 전문가 검증은 권한이 있는 역할에만 접힌 패널로 표시
- Home, Projects, Data Sources, Pipeline, Query, Graph, Dashboard,
  Evaluations, Audit의 독립 페이지 렌더링 유지

### React

- 모바일 헤더는 900px 이하에서 drawer로 전환
- 데모 질문은 입력창 미리보기 후 사용자가 전송
- 전송 후 입력창 초기화와 중복 요청 차단
- Evidence 기본 탭을 결과표로 고정
- 답변 카드에 같은 실행의 Evidence 링크 추가
- 전문가 검증을 `details` 기반 기본 접힘·전문가 전용 UI로 변경
- 다크 모드 보조 텍스트와 경계선 대비 강화
- History 빈 상태 CTA가 현재 프로젝트 컨텍스트를 유지

## 정보 계층

- 질문과 답변이 1차 작업 영역이다.
- 결과표·그래프·Cypher·검증은 같은 실행의 Evidence 영역이다.
- 전문가 판정은 일반 조회와 구분되는 3차 운영 동작이다.
- 데이터가 없는 화면은 다음 행동 CTA를 제공한다.

## 자동 검증

- Query 답변→Evidence 링크
- 결과표 기본 선택
- 전문가 검증 기본 접힘·전문가 라벨
- 모바일 drawer·가로 overflow 방지
- 데모 질문 미리보기·중복 전송 방지
- Streamlit AppTest와 전체 Python 회귀 테스트
