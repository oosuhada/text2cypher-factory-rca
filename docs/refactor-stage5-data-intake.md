# 제품 리팩터링 5단계 — 승인형 Data Intake

## 판정

**구현·자동 검증 PASS**

기존의 개별 JSON/CSV 사전검증을 CiP-DMD 전체 번들의 안전한
staging·dry-run·승인 적재 워크플로로 확장했다. 운영 그래프 변경은
기본 비활성화 상태다.

## 사용자 흐름

1. 검증용 CiP-DMD ZIP을 받거나 같은 폴더 구조로 번들을 준비한다.
2. ZIP을 업로드해 staging한다.
3. 경로·압축 크기·필수 파일·기준 해시 검사를 통과한다.
4. Extract → Transform → Validate dry-run 결과와 격리 건수를 확인한다.
5. 관리자가 UI 적재를 허용한 환경에서 전체 Run ID 확인 문구를 입력한다.
6. 30분 승인 토큰을 검증한 뒤 loader 모드로 전환한다.
7. `MERGE` ETL을 실행하고 projection 건수를 재검증한다.
8. 성공·실패와 관계없이 reader 모드 복귀를 시도한다.
9. 실행 레코드와 JSONL 감사로그를 남긴다.

## 안전장치

| 위험 | 대응 |
|---|---|
| ZIP path traversal | 절대경로·`..`·역슬래시 차단, `extractall` 미사용 |
| ZIP bomb | 압축 25MB·해제 100MB·멤버 100개 상한 |
| 파일 오매핑 | 상대경로가 고정된 필수 파일 8개를 각각 1개만 허용 |
| 변경 데이터 오적재 | 프로젝트 기준 원본과 SHA-256이 모두 동일해야 진행 |
| 검증 없는 쓰기 | 기존 ETL 전체 validation과 projection 건수 강제 |
| 우발적 버튼 클릭 | 환경 허용 + 체크박스 + 전체 Run ID + 30분 토큰 |
| 동시 적재 | 배타적 lock file |
| 쓰기 모드 방치 | `finally`에서 reader 복귀 및 재연결 확인 |
| 토큰 재사용 | 적재 시작 시 서버 저장 토큰 해시 폐기 |
| 추적 불가 | run JSON과 `intake_audit.jsonl` 기록 |

## 저장 위치

- staging: `data/processed/intake_runs/<run_id>/`
- 실행 메타데이터: 각 run의 `run.json`
- 감사로그: `data/processed/intake_audit.jsonl`
- 최신 정상 적재 요약: `data/processed/cip_dmd_etl_summary.json`

staging 데이터와 감사로그는 Git에서 제외한다.

## 운영 경계

- 이 기능은 고정된 공개 CiP-DMD를 다시 적재하는 복구·데모 흐름이다.
- 임의 제조 데이터의 컬럼 매핑이나 증분 적재 기능이 아니다.
- 현재 ETL은 batch 단위 `MERGE`이므로 전체 트랜잭션 rollback을
  제공하지 않는다. 실패 시 reader로 복귀하고 실패 run을 보존한다.
- 다른 데이터셋을 지원하려면 별도 스키마 매핑, 충돌 미리보기,
  staging DB 또는 전체 트랜잭션 전략이 필요하다.

## 검증

- 전체 Python·Streamlit 테스트: 78/78 PASS
- 실제 기준 ZIP: 152,016 bytes, 필수 파일 8/8, SHA-256 PASS
- 실제 dry-run projection: Part 2,736, 관계 27,741, 격리 35
- 정상 번들 staging·dry-run
- 기준 번들 ZIP의 결정적 재생성
- 필수 파일 누락 차단
- ZIP path traversal 차단
- 잘못된 승인 토큰의 모드 전환 0회
- 정상 승인 적재의 loader → reader 순서
- 적재 실패 시에도 reader 복귀
