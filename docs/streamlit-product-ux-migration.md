# Streamlit 제품형 UX 이전

## 결정

회사 가이드의 “자연어 질문 입력, 생성된 Cypher·조회 결과·자연어
답변 표시 화면 개발(Streamlit)”을 공식 제출 기준으로 삼는다.
Next.js 구현은 삭제하지 않지만 공식 프로토타입의 대체물이 아니라
FastAPI 기반 상용화 확장으로 분리한다.

## Streamlit으로 이전한 핵심 UX

| 사용자 경험 | 구현 |
|---|---|
| 제품 랜딩·내비게이션 | Home 랜딩과 6개 업무 화면의 sidebar routing |
| 자연어 질문 | 추천 질문과 `st.chat_input` |
| 답변과 근거의 연결 | 답변 직하에서 결과·경로·Cypher·검증 이력 표시 |
| 대화 내용 기록 | 현재 브라우저 세션의 최근 대화 12개 저장·다시 열기 |
| 지식그래프 탐색 | 노드 유형·ID·1~3 hop을 지정해 실제 Neo4j 탐색 |
| 데이터 진입점 | JSON·CSV 업로드 후보의 형식과 공통 ID 사전검증 |
| 운영 신뢰성 | 최근 ETL, 그래프 무결성, 모델·평가 지표 표시 |

## React와 별도 구현으로 유지하는 요소

- 브라우저 `localStorage` 영구 기록
- 세밀한 애니메이션과 React 수준의 완전한 반응형 레이아웃
- Cytoscape 자유 확대·노드 드래그
- 사용자 계정과 서버 동기화

React 랜딩의 정보 계층과 CTA는 Streamlit 네이티브 랜딩으로 다시
구현했다. 위 기능들은 Streamlit 제약을 우회하기 위한 별도 React
컴포넌트를 삽입하지 않고 Next.js 상용화 확장에 유지한다.

## 안전 경계

업로드 UI는 운영 그래프를 즉시 변경하지 않는다. 임의 파일을 실제
적재하려면 스키마 매핑, dry-run, 격리 레코드 확인, loader 권한 전환,
롤백과 감사로그가 함께 필요하다. 현재 UI는 파일 구조와 공통 ID
후보를 메모리에서 검사하고 검증된 ETL 명령으로 연결한다.

## 검증

- Python·Streamlit 자동 테스트: 71/71 PASS
- Gold 질의 실행 후 세션 대화 기록 생성: PASS
- 답변 직하 결과표·Cypher·근거 그래프: PASS
- GraphCatalog 응답의 Evidence 계약 정규화: PASS
- 기존 Agent·ETL·Neo4j 회귀 테스트: PASS
