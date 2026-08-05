# Streamlit Dashboard Plotly 연동 실험

## 목적

기존 Streamlit 운영·품질 대시보드의 기본 `st.bar_chart`를 Plotly 기반
인터랙티브 차트로 확장했다. 기존 데이터 서비스와 화면 정보 구조는 유지하고,
차트 렌더링 계층만 별도 모듈로 분리했다.

공개 확인 주소:

```text
https://plotly-streamlit.oosu.dev/?workspace=dashboard
```

기본 Plotly Express와 개선된 제품 스타일을 같은 데이터로 비교하는 주소:

```text
https://plotly-streamlit.oosu.dev/?compare=plotly-ui
```

## 구현 범위

`frontend/dashboard_plotly.py`에 순수 figure builder를 구성하고
`frontend/pages/dashboard.py`에서 `st.plotly_chart`로 렌더링한다.

| # | 차트 | 표현 방식 |
|---:|---|---|
| 1 | 노드 유형별 규모 | Horizontal bar |
| 2 | 관계 유형별 규모 | Horizontal bar |
| 3 | 장비별 공정 실행 | Horizontal bar |
| 4 | 이상 유형 분포 | Bar |
| 5 | 품질 불합격 상위 항목 | Horizontal bar |
| 6 | 질의 상태 구성 | Donut |
| 7 | Provider별 질의량 | Horizontal bar |
| 8 | 최근 질의 응답시간 | Line + marker |
| 9 | Blind 평가 variant 품질 비교 | Grouped bar |

## 설계 기준

- 기존 Dashboard service payload를 변경하지 않는다.
- figure 생성 함수를 Streamlit 렌더링 코드와 분리해 단위 테스트한다.
- 빈 데이터에서도 오류 대신 안내 annotation이 있는 figure를 반환한다.
- Blind 비교는 단일 정확도만 보여주지 않고 실행·의미값·엄격 계약·schema·읽기
  전용 지표를 한 화면에서 비교한다.
- Plotly는 Streamlit 앱 의존성에 명시적으로 고정한다.

## UI 개선 범위

- ECharts Dashboard와 동일한 제품 series·semantic 색상 팔레트
- Pretendard·Inter 기반 공통 typography
- Figure 내부 중복 제목 제거
- 카드 배경, 테두리, 모서리 반경과 hover border
- 축·grid·tick·숫자 축약 형식 통일
- 차트 종류와 데이터 밀도에 따른 높이 정규화
- semantic status color와 Donut 중앙 합계
- 제품형 hover tooltip
- 발표에 불필요한 Plotly logo·Modebar 제거
- 빈 데이터 전용 안내 상태
- 루트 query 기반 Before/After 비교 페이지

## 검증

```bash
python -m pytest tests/test_dashboard_plotly.py -q
```

검증 항목:

- 8개 운영 figure builder가 실제 Plotly `Figure`를 반환
- Blind 비교 grouped bar가 5개 rate series를 생성
- 빈 입력이 안전한 empty-state figure를 반환
- 공통 투명 canvas, grid, bar corner와 hover template 적용
- Donut 합계 annotation과 semantic 색상 적용
- 비교 페이지가 동일 snapshot에서 기본·개선 Figure를 함께 렌더링

추가로 `streamlit.testing.v1.AppTest`에 실제 Dashboard snapshot을 주입해 전체
화면을 렌더링했다.

```text
exceptions: 0
plotly_chart elements: 9
metrics: 21
tabs: 그래프 구조 / 공정·장비 / 이상·품질
```

2026-08-05 UI 개선 후 검증:

```text
targeted Streamlit tests: 20 passed
cross-surface release gate: PASS
comparison page exceptions: 0
comparison page failed requests: 0
```

