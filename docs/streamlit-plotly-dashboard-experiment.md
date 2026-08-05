# Streamlit Dashboard Plotly 연동 실험

## 목적

기존 Streamlit 운영·품질 대시보드의 기본 `st.bar_chart`를 Plotly 기반
인터랙티브 차트로 확장했다. 기존 데이터 서비스와 화면 정보 구조는 유지하고,
차트 렌더링 계층만 별도 모듈로 분리했다.

공개 확인 주소:

```text
https://plotly-streamlit.oosu.dev/?workspace=dashboard
```

동일 데이터와 동일 차트 의도를 Plotly Express, Plotly Graph Objects,
React + ECharts로 실제 렌더링하고 최종 기술 선택 근거를 확인하는 주소:

```text
https://plotly-streamlit.oosu.dev/?compare=plotly-ui
```

## 구현 범위

`frontend/dashboard_plotly.py`에 Plotly Graph Objects 기반 순수 figure builder를 구성하고
`frontend/pages/dashboard.py`에서 `st.plotly_chart`로 렌더링한다.

비교 페이지는 Dashboard snapshot을 하나의 `category/value` payload로 정규화한 뒤
세 렌더러에 그대로 전달한다.

1. Plotly Express + Streamlit
2. Plotly Graph Objects + Streamlit
3. React + Apache ECharts 공개 embed route

React 구현은 `https://dashboard.oosu.dev/visualization-compare/echarts`에서
인증 없이 실제 ECharts Canvas를 렌더링한다. iframe 내부에는 현재 chart ready
시간과 payload 크기를 표시하고, 비교 페이지에는 Figure 생성 시간, 직렬화 크기와
공개 URL 반복 측정 중앙값을 함께 표시한다.

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
- 1024px 이하 차트 Board 1열 전환
- KPI 카드 3열·2열·1열 반응형 재배치
- Plotly card와 Figure 높이 불일치로 발생하던 축 clipping 제거
- 루트 query 기반 3개 구현 비교·기술 선택 페이지
- 세 렌더러 동시 실제 출력과 동일 payload 검증
- Figure build 시간·직렬화 크기·브라우저 ready 중앙값 표시
- React ECharts 인증 없는 전용 embed route

## 기술 선택 결론

| 구현 | 검증한 목적 | 결론 |
|---|---|---|
| Plotly Express + Streamlit | 최소 코드로 데이터 연결과 차트 생성 속도 확인 | 연결성 PoC에 유지 |
| Plotly Graph Objects + Streamlit | trace, hover, semantic color와 margin 직접 제어 | 분석·내부 보고에 유지 |
| React + Apache ECharts | Board grid, Inspector, selection·brush cross-filter, 역할·Object context 통합 | 최종 사용자 Dashboard로 선택 |

Plotly 자체의 표현력은 충분하지만 최종 제품의 핵심 요구사항은 개별 Figure보다
Dashboard layout, Board 상태 계약, cross-filter, 저장된 view와 AI 시각화 전환이다.
이 요구사항은 이미 React + ECharts runtime에 구현되어 있으므로 최종 제품은 해당
구조를 사용하고 Streamlit Plotly는 실험·진단 화면으로 범위를 제한한다.

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
- 비교 페이지가 동일 snapshot에서 Express·Graph Objects·ECharts 결과를 동시에 렌더링
- React iframe payload와 두 Plotly trace가 같은 category/value를 사용하는지 검증
- React + ECharts 구현 범위와 최종 선택 기준표 표시

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
1440px chart label clipping: 0
1024px chart label clipping: 0
768px chart label clipping: 0
1024px structure/runtime columns: full-width stacked
768px KPI cards: 2 columns
```

공개 Cloudflare URL을 새 Chromium context, `1600×1000` viewport에서 케이스별
3회 실행한 browser-ready 중앙값:

| 데이터 | Plotly Express | Plotly Graph Objects | React + ECharts iframe |
|---|---:|---:|---:|
| 범주 비교 | 3,618ms | 3,618ms | 5,274ms |
| 상태 구성 | 3,626ms | 3,626ms | 4,410ms |
| 시간 추세 | 3,193ms | 3,193ms | 4,893ms |

두 Plotly 구현은 같은 Streamlit rerun과 Plotly component 로딩 경로를 사용하므로
end-to-end ready 시간이 거의 동일했다. React + ECharts 수치는 별도 도메인의 iframe
초기화까지 포함한다. iframe 내부에서 측정한 순수 ECharts chart-ready 시간은 각 실행에서
약 `488~1,049ms`였다. 따라서 이 측정은 라이브러리 단독 성능 순위가 아니라 현재 배포
구조에서 사용자가 세 결과를 보게 되는 시점을 비교한 값으로 해석한다.

