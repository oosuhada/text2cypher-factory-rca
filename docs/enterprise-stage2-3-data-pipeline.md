# 엔터프라이즈 트랙 2-3 — Data Sources·Pipeline UX

## 구현 결과

데이터 등록부터 실제 적재 승인 직전과 무결성 확인까지 하나의
온보딩 흐름으로 연결했다.

- CSV·JSON·XLSX·ZIP drag-and-drop 업로드
- 원본 보존, 정규화 테이블 프로파일, 샘플과 품질 경고
- 기존 Neo4j 연결·READ 권한·스키마 검증과 명시적 승인
- 프로젝트 상태 기반 8단계 온보딩 progress
- 노드·관계 매핑 JSON 검토와 운영 DB 비변경 ETL dry-run
- dry-run의 예상 노드·관계, 격리 후보, lineage, schema 표시
- 승인 매핑이 없으면 실제 적재 버튼 비활성화
- 프로젝트명을 재입력하고 서버가 허용한 경우에만 실제 적재
- 적재 후 프로젝트 scope, 교차 프로젝트 관계, reader 복구,
  readiness gate 표시
- SQLite 작업 저장소에 progress·처리량·경과시간·로그·오류·재시도
  계보를 보존

## 안전 경계

프로파일이나 dry-run은 운영 Neo4j를 변경하지 않는다. 매핑 승인은
schema와 mapping 버전만 고정하며 프로젝트를 `ready`로 올리지 않는다.
실제 적재는 `P3_ENABLE_UI_LOAD=1`, 승인 매핑, 프로젝트명 확인의 세
조건을 모두 만족해야 한다. 적재 성공 후에도 상태는
`evaluation_required`이며 Gold·Blind·prompt 계약을 통과해야
`ready`가 된다.

## 실패·재개 계약

작업과 로그는 `data/processed/pipeline_jobs.sqlite3`에 저장되므로
브라우저를 새로고침해도 사라지지 않는다. 실행 중 작업은 취소할 수
있고 실패·취소 작업은 원본 작업 ID를 부모로 갖는 새 시도로
재등록한다. 업로드 본문이나 DB 비밀번호는 작업 로그에 보존하지
않으며, 재시도 시 사용자가 해당 입력을 다시 확인한다.

## 검증

- 작업 상태·로그·결과의 프로세스 재생성 후 복원
- terminal 작업 변경 차단과 retry lineage
- 상태별 온보딩 progress
- ID 후보 부재·고결측 컬럼 품질 경고
- terminal 작업 경과시간 고정
- Python 전체 회귀, backend release gate, Next.js lint/build
- Streamlit Data Sources·Pipeline 브라우저 렌더링

## 알려진 운영 경계

현재 Streamlit worker가 요청을 동기 실행하되 작업 상태를 영속화한다.
대용량 생산 환경에서는 동일한 `PipelineJobStore` 계약 앞에
Celery·RQ·사내 작업 큐를 연결해 프로세스 외 worker로 실행해야 한다.
이 경계는 UI나 프로젝트 생명주기를 변경하지 않는다.
