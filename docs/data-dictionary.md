# CiP-DMD 데이터 사전

## 문서 상태

- 단계: 2단계 — 원본 데이터와 연결 키 점검
- 점검일: 2026-07-27
- 상태: **완료**
- 다음 단계 진입: **가능**

## 1. 기준 파일

| 파일 | 역할 | 관계 기준 사용 |
|---|---|---|
| `cylinder/meta_data.json` | 완제품, 구성품 참조, 조립 QC | 예 |
| `cylinder_bottom/meta_data.json` | bottom의 saw·milling 실행과 QC | 예 |
| `piston_rod/meta_data.json` | rod의 turning QC | 예 |
| `piston_rod/reworked_piston_rods_meta_data.json` | 재작업 rod의 공정·QC | 예 |
| 각 공정 `quality_data.csv` | 품질 수치 교차검증 | 보조 |
| `production_logs/*.xlsx` | 설비 이벤트 로그 | 보조 |

메타데이터 JSON이 구성품 관계, 공정, anomaly, QC를 함께 포함하므로 Neo4j ETL의 기준 원본으로 사용한다.

## 2. 공통 JSON 구조

| 필드 | 타입 | 의미 | 처리 |
|---|---|---|---|
| `part_type` | string | `cylinder`, `cylinder_bottom`, `piston_rod` | Part subtype |
| `part_id` | string | 개별 제품·구성품 ID | 고유 키 |
| `component_ids` | string[] | 완제품을 구성한 bottom·rod ID | `ASSEMBLED_FROM` |
| `process_data` | object[] | 부품별 공정 실행 | `ProcessRun` 생성 |
| `quality_data` | object[] | 공정별 품질검사 그룹 | `QualityMeasurement` 생성 |

### `process_data`

| 필드 | 의미 |
|---|---|
| `name` | `saw`, `cnc_milling_machine`, `cnc_lathe` |
| `start_time`, `end_time` | Unix timestamp |
| `anomaly` | 원본 anomaly class |
| `data_paths` | 해당 실행의 센서·타임스탬프 파일 경로 |

### `quality_data.measurements`

| 필드 | 의미 |
|---|---|
| `feature` | pressure, surface_roughness 등 검사 항목 |
| `value` | 측정값 또는 rework 여부 |
| `qc_pass` | 원본 합격 여부 boolean |

## 3. 키와 관계

### 기본 키

- 모든 제품·구성품: `part_id`
- Neo4j 권장 제약: `(:Part {part_id}) IS UNIQUE`

### 완제품 genealogy

`Cylinder.component_ids` 배열:

1. cylinder bottom ID
2. piston rod ID

예:

```text
Cylinder 300002
  ├─ CylinderBottom 103504
  └─ PistonRod 200102
```

### 공정 연결

| Part type | 공정 |
|---|---|
| Cylinder bottom | saw, cnc_milling_machine |
| Piston rod | cnc_lathe |
| Cylinder | assembly QC; 명시적 process_data는 없음 |

### 장비와 anomaly 분류

| 공정 | 장비 모델 | equipment_id |
|---|---|---|
| saw | Kasto SBA 2 | `kasto-sba-2` |
| cnc_milling_machine | DMC 50H | `dmc-50h` |
| cnc_lathe | Index C65 | `index-c65` |

이 값은 원본 README에 명시되어 있다. 호기별 식별자는 제공되지 않으므로
`Equipment`는 개별 설비가 아니라 장비 모델 단위로 해석한다.
anomaly code 0~3은 `AnomalyClass` 노드로 정규화한다.

## 4. CSV 구조

모든 CSV는 쉼표가 아니라 세미콜론(`;`) 구분자다.

| 파일 | 데이터 행 | 컬럼 |
|---|---:|---|
| Saw quality | 985 | `part_id`, `weight`, `anomaly` |
| Milling quality | 846 | `part_id`, `surface_roughness`, `parallelism`, `groove_depth`, `groove_diameter` |
| Assembly quality | 802 | `part_id_cylinder_bottom`, `part_id_piston_rod`, `rework`, `pressure` |
| Lathe quality | 673 | `part_id`, `coaxiality`, `diameter`, `length` |

CSV는 일부 항목에서 JSON 측정 수보다 적다. MVP는 JSON의 `qc_pass`와 관계를 기준으로 적재하고 CSV 값은 행 수·수치 교차검증에 사용한다.

## 5. 품질 feature

| 대상 | 공정 | feature |
|---|---|---|
| Cylinder | assembly | rework, pressure |
| Cylinder bottom | saw | weight |
| Cylinder bottom | cnc_mill | surface_roughness, parallelism, groove_depth, groove_diameter |
| Piston rod | cnc_lathe | coaxiality, diameter, length |

## 6. ETL 정규화 규칙

1. `part_id`는 숫자로 변환하지 않고 문자열로 보존한다.
2. anomaly는 문자열 또는 정수 혼용을 정규화하되 원본 class 값은 유지한다.
3. `qc_pass`는 boolean 그대로 사용한다.
4. `cylinder 300001`의 component header placeholder는 제외한다.
5. 참조가 없는 구성품은 가짜 노드로 보완하지 않고 격리 로그에 기록한다.
6. reworked rod 52개는 일반 rod ID 집합과 합쳐 참조를 검증하되 `reworked=true`를 표시한다.
7. 생산 로그는 개별 part와 직접 JOIN하지 않는다.
8. HDF5 `data_paths`는 경로 메타데이터만 저장하고 센서 본문은 1차 MVP에서 적재하지 않는다.

## 7. 3단계 스키마 입력 계약

| 개념 | 최소 속성 |
|---|---|
| Part | `part_id`, `part_type`, `reworked` |
| Process | `name` |
| ProcessRun | `run_id`, `start_time`, `end_time`, `anomaly` |
| Equipment | `equipment_id`, `name`, `equipment_type` |
| AnomalyClass | `code`, `name`, `description`, `is_normal` |
| QualityMeasurement | `measurement_id`, `feature`, `value`, `qc_pass`, `process` |

관계명과 `ProcessRun` 식별자 생성 규칙은 3단계에서 확정한다.
