# CiP-DMD ETL 실행 가이드

## 구조

```text
extract.py
  원본 JSON 4개 로드
  품질 CSV 4개 행·컬럼 교차검증
      ↓
transform.py
  placeholder·완전 중복 제거
  공정명·ID·수치 타입 정규화
  그래프용 batch payload 생성
      ↓
validate.py
  고유키·예상 건수·참조 무결성 검사
  누락 구성품 격리
      ↓
load.py
  파라미터화된 UNWIND + MERGE batch 적재
      ↓
cli.py
  실행 리포트와 quarantine 파일 저장
```

원본이 중첩 JSON이므로 pandas DataFrame으로 억지로 평탄화하지 않고 Python
표준 `json`·`csv` 모듈을 사용한다. Neo4j 연결은 공식 Python Driver를
사용한다.

## 설치

```bash
cd "비스텔리전스 파이널 프로젝트/mvp"
python3 -m venv .venv
./.venv/bin/python -m pip install -r backend/requirements.txt
```

## Dry-run

데이터베이스를 변경하지 않고 추출·변환·검증만 실행한다.

```bash
./.venv/bin/python -m backend.app.etl.cli --dry-run
```

## 실제 적재와 멱등성 검증

```bash
./infra/set_homebrew_mode.sh loader
./.venv/bin/python -m backend.app.etl.cli \
  --verify-idempotency \
  --batch-size 500
```

Docker나 다른 컴퓨터에서는 `NEO4J_URI`, `NEO4J_DATABASE`,
`NEO4J_USERNAME`, `NEO4J_PASSWORD`를 환경변수로 설정한다.

## 테스트

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

## 생성 파일

- `data/processed/cip_dmd_etl_summary.json`: 최신 실행 결과
- `data/processed/etl_runs/etl_*.json`: 실행별 이력
- `data/processed/quarantine/missing_component_references.json`: 누락 참조 35건 전체

## 적재 정책

- `MERGE`의 고유키는 `part_id`, `run_id`, `measurement_id`, process `name`,
  `equipment_id`, anomaly `code`
- 모든 batch 데이터는 Cypher 문자열에 결합하지 않고 `$rows` 파라미터로 전달
- batch 기본 크기는 500
- `Cylinder 300001` placeholder 제외
- `CylinderBottom 103604` 완전 중복 1건 제거
- 존재하지 않는 component를 가짜 노드로 생성하지 않음
- `cnc_mill`을 `cnc_milling_machine`으로 정규화
- 숫자로 변환 가능한 품질값은 `value_numeric`에도 저장
- 원본 값은 항상 `value_text`로 보존
- 공정 실행을 원본 README의 장비 모델과 `RUN_ON`으로 연결
- anomaly 0~3을 `AnomalyClass`와 `CLASSIFIED_AS`로 연결
- `qc_pass=false` 측정에 `QualityFailure` 보조 라벨 부여

참고: [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/),
[UNWIND batch 권장 방식](https://neo4j.com/docs/python-manual/current/performance/)
