# UX 내비게이션 재검증 및 수정

## 문제

기존 검증은 화면 요소의 존재와 백엔드 연결을 주로 확인해 다음 실제
사용 흐름을 놓쳤다.

- Streamlit 사이드바가 대화 중심의 운영 순서가 아니었다.
- Home의 `모든 프로젝트 보기` 버튼이 Projects 화면으로 이동하지 않았다.
- Projects 화면의 `운영 화면` 표시는 버튼처럼 보였지만 배지라서 복귀할
  수 없었다.
- React Home에는 최근 프로젝트, 전체 프로젝트, 프로젝트 생성 진입점이
  없었다.

## 원인

Streamlit 버튼은 사이드바 라디오가 생성된 뒤 같은 widget key를 직접
변경했다. Streamlit의 widget 상태 규칙상 이 값이 다음 렌더에서
유지되지 않았고, 실제 브라우저에서는 기존 Home 라디오 값이 서버의
Projects 값을 다시 덮어써 이동이 무효화됐다. `운영 화면`은 상태
배지로만 구현되어 있어 클릭 이벤트 자체가 없었다. React는
Query·Graph 중심 화면만 구현되고 Project Registry의 홈 진입점이
누락됐다.

## 수정

- 페이지 이동을 `pending_page`에 예약하고 다음 렌더에서 Navigation
  widget 생성 전에 반영한다. 프로그램 이동 시
  `navigation_widget_revision`을 올려 브라우저의 오래된 radio 값을
  재사용하지 않는다.
- 모든 하위 Streamlit 화면 오른쪽에 `← 운영 홈으로` 버튼을 제공한다.
- Streamlit 사이드바를 다음 순서로 고정한다.
  `대화 → 역할 미리보기 → 프로젝트 → 언어 → 실행 설정 → 작업공간 이동`
- React Home에 최근 프로젝트 카드와 `모든 프로젝트 보기`,
  `새 프로젝트 만들기` CTA를 추가한다.
- React `/projects`에 전체 Registry, 프로젝트 전환, 새 프로젝트 생성
  폼을 제공한다.

## 검증 기준

- 버튼 label 존재가 아니라 클릭 후 Navigation 값과 URL이 실제로
  변경되는지 확인한다.
- Streamlit sidebar의 화면상 순서를 확인한다.
- React Home → Projects → 새 프로젝트 anchor 흐름을 확인한다.
- Python 테스트, Streamlit AppTest, React lint/build와 실제 브라우저
  콘솔 오류를 함께 확인한다.
