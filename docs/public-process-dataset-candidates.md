# P3 공개 제조 공정 데이터 후보 조사

## 결론

P3의 1순위 공개 데이터 후보는 **CiP-DMD(Center for industrial Productivity – Discrete Manufacturing Dataset)**다.

CiP-DMD는 단순 센서 테이블이 아니라 완제품, 구성 부품, 여러 제조 공정, 실제 가공 기계, 공정 이상 유형, 품질검사 결과와 이들의 추적 관계를 제공한다. 전체 시계열 약 90GB를 받지 않아도 작은 메타데이터 JSON과 품질 CSV만으로 P3 MVP 그래프를 구성할 수 있다.

## 평가 기준

| 기준 | 확인 내용 |
|---|---|
| 추적성 | 하나의 제품·부품이 어떤 공정과 설비를 거쳤는가 |
| 품질·이상 | 공정 이상과 품질검사 결과가 있는가 |
| 관계 다양성 | 제품·부품·공정·설비·품질을 그래프로 연결할 수 있는가 |
| 도메인 해석성 | 익명 변수보다 실제 제조 용어가 제공되는가 |
| MVP 접근성 | 한 달 프로젝트에서 필요한 부분만 빠르게 받을 수 있는가 |

## 후보 비교

| 후보 | P3 적합도 | 장점 | 주요 한계 |
|---|---:|---|---|
| **CiP-DMD** | **9.5/10** | 다단계 제조, 구성품 추적, 실제 기계명, anomaly, QC 결과, 공개 메타데이터 | LOT 없음, 일부 component 참조 누락, 전체 시계열은 큼 |
| Bosch Production Line Performance | 7.0/10 | 제품별 station 경로와 failure label, 데이터 규모 큼 | 익명화, 약 14GB, Kaggle 약관·로그인, 극심한 불균형 |
| NIST SMS Test Bed | 6.5/10 | CNC·검사 장비와 digital thread, 실시간 MTConnect | 데이터 통합 복잡, 정답 RCA·불량 라벨이 바로 제공되지 않음 |
| Five-Axis CNC Changeover | 5.5/10 | 제품·공구·NC code·changeover·실제 기계 신호 | 기계 한 대, 30 session, 품질·불량 관계 약함 |
| SECOM | 4.5/10 | 반도체 공정, 1,567개 생산 단위와 pass/fail, 작고 쉬움 | 590개 변수가 익명, 공정·설비·부품 경로 없음 |
| BOSCH Plasma-Etching | 4.0/10 | 반도체 식각, 88개 웨이퍼의 시계열·공간 계측 | 단일 식각 공정, 설비·구성품·불량 이벤트·다단계 추적 없음 |

---

## 1. CiP-DMD — 최우선 후보

### 공식 출처

- 데이터 접근 정보: https://zenodo.org/records/10118474
- 데이터 설명 논문: https://zenodo.org/records/8420132
- 논문 DOI: https://doi.org/10.1016/j.procir.2024.08.390

### 제조 대상과 규모

공압 실린더를 생산하는 다단계 이산 제조 데이터다.

- piston rod: README 기준 928개
- cylinder bottom: README 기준 847개
- assembled cylinder: 802개

데이터 저장소의 메타데이터에는 README의 집계와 다른 추가·중간 부품 레코드도 존재한다. 따라서 실제 ETL에서는 README 숫자를 하드코딩하지 않고 파일별 유효 레코드와 참조 무결성을 다시 계산해야 한다.

### 제조 공정과 기계

| 구성품 | 공정 | 실제 기계 |
|---|---|---|
| Piston rod | CNC 선삭 | Index C65 |
| Cylinder bottom | 절단 | Kasto SBA 2 |
| Cylinder bottom | CNC 밀링 | DMC 50H |
| Cylinder | 조립·압력검사 | Assembly |

### 제공되는 관계

```text
Cylinder
  ├─ ASSEMBLED_FROM → CylinderBottom
  └─ ASSEMBLED_FROM → PistonRod

CylinderBottom
  ├─ PROCESSED_BY → Saw
  ├─ PROCESSED_BY → CNC Milling Machine
  └─ HAS_QUALITY_RESULT → Weight / Roughness / Parallelism / Groove

PistonRod
  ├─ PROCESSED_BY → CNC Lathe
  └─ HAS_QUALITY_RESULT → Coaxiality / Diameter / Length

Cylinder
  └─ HAS_QUALITY_RESULT → Rework / Pressure
```

### 공정 이상 유형

메타데이터에 공정별 anomaly class가 포함된다.

| 코드 | 의미 |
|---:|---|
| 0 | 정상 |
| 1 | 절단 원재료 정렬 불량 |
| 2 | 밀링 지그의 불균일한 클램핑 |
| 3 | 공정 신호에서 보이지 않는 기타 오류 |

### 품질검사

| 공정 | 품질 항목 |
|---|---|
| 선삭 | coaxiality, diameter, length |
| 절단 | weight |
| 밀링 | groove depth, groove diameter, parallelism, surface roughness |
| 조립 | rework, pressure |

각 측정값에는 `qc_pass`가 있어 정상·불량을 바로 구분할 수 있다.

### 직접 확인한 메타데이터

- 유효 완제품 조립 레코드: 802
- 각 완제품은 cylinder bottom과 piston rod ID 2개를 참조
- cylinder bottom 메타데이터: 985 레코드
  - saw 공정: 985
  - milling 공정: 847
- piston rod 기본 메타데이터: 898 레코드
- reworked piston rod 메타데이터: 52 레코드

품질 실패 사례도 충분히 존재한다.

| 대상 | 품질 항목 | 실패 건수 |
|---|---|---:|
| Assembly | pressure | 19 |
| Assembly | rework | 52 |
| Cylinder bottom | surface roughness | 190 |
| Cylinder bottom | parallelism | 70 |
| Cylinder bottom | groove diameter | 22 |
| Cylinder bottom | groove depth | 15 |
| Piston rod | coaxiality | 62 |
| Piston rod | diameter | 9 |
| Piston rod | length | 1 |

### 데이터 품질 이슈

- 802개 완제품 중 cylinder bottom 참조는 801개가 현재 bottom 메타데이터와 일치
- piston rod 참조는 기본·reworked 메타데이터를 합쳐 768개가 일치
- README의 부품 수와 실제 메타데이터 레코드 수가 일부 다름
- anomaly 값이 파일 안에서 문자열 `"0"`과 숫자 `0`으로 혼재
- 첫 예제 레코드에 placeholder component ID가 있어 제외 필요

이 문제는 단점이지만, ETL 무결성 검사와 데이터 품질 리포트를 보여줄 좋은 발표 소재이기도 하다.

### P3에 맞게 바꾼 질문

1. 압력검사에 실패한 실린더에 조립된 cylinder bottom과 piston rod는 무엇인가?
2. 조립 불량 제품의 구성 부품이 이전 공정에서 받은 anomaly와 QC 결과를 보여줘.
3. 표면 거칠기 검사에 실패한 cylinder bottom들이 공통으로 거친 공정과 기계는 무엇인가?
4. anomaly class 2가 발생한 cylinder bottom과 이후 QC 실패 항목을 보여줘.
5. 특정 piston rod가 어떤 완제품에 조립됐으며, 해당 제품의 압력검사 결과는 무엇인가?
6. rework된 piston rod가 포함된 완제품과 최종 QC 결과를 보여줘.

### 권장 MVP 다운로드 범위

먼저 다음 파일만 사용한다.

```text
README.md
cylinder/meta_data.json
cylinder_bottom/meta_data.json
piston_rod/meta_data.json
piston_rod/reworked_piston_rods_meta_data.json
cylinder/assembly/quality_data/quality_data.csv
cylinder_bottom/saw/quality_data/quality_data.csv
cylinder_bottom/cnc_milling_machine/quality_data/quality_data.csv
piston_rod/cnc_lathe/quality_data/quality_data.csv
production_logs/*.xlsx
dataset_structure.png
```

이 파일들은 수 MB 수준이며 Neo4j 그래프와 RCA 질문을 만들기에 충분하다.

HDF5 센서 시계열 약 90GB는 P3 MVP에서 받지 않는다. 나중에 상세 근거 또는 P4-lite Tool로 일부 process run만 추가한다.

### 주의

Zenodo 레코드는 공개 접근 방법을 제공하지만 데이터 라이선스 표기가 명확한지 별도 확인해야 한다. 원본을 Git 저장소에 재배포하지 않고 다운로드 스크립트와 출처만 제공하는 편이 안전하다.

---

## 2. Bosch Production Line Performance

### 출처

- https://www.kaggle.com/competitions/bosch-production-line-performance/data

### 구조

- 약 118만 개 학습 부품
- numeric, categorical, date 데이터
- feature 이름에 line·station·feature 번호가 포함
- 최종 `Response` failure label

### P3 활용

```text
Product → Line → Station → Measurement → Failure
```

제품이 거친 station과 failure를 연결할 수 있어 Text-to-Cypher용 그래프는 만들 수 있다.

### 한계

- 변수와 station 의미가 익명화됨
- 원인 설명이 “L1_S24_F1846” 같은 코드에 머물 수 있음
- 다운로드와 사용에 Kaggle 계정·경쟁 약관 동의 필요
- 원본이 크고 희소하여 전처리 부담이 큼
- 구성 부품과 품질검사 항목의 의미가 없음

CiP-DMD 접근이 막힐 때의 2순위다.

---

## 3. NIST Smart Manufacturing Systems Test Bed

### 출처

- https://www.nist.gov/laboratories/tools-instruments/smart-manufacturing-systems-sms-test-bed

### 구조

- CNC milling·turning
- CMM과 측정 장비
- CAD/CAM/inspection/product lifecycle
- MTConnect 실시간 stream
- query repository와 technical data package

### P3 활용

Digital thread 관점에서 `제품 설계 → 제조 장비 → 가공 → 검사` 그래프를 만들기에 좋다.

### 한계

- 여러 API와 패키지를 해석해야 함
- Text-to-Cypher 정답 질문을 만들기까지 전처리가 큼
- 불량·원인 label이 CiP-DMD처럼 바로 정리돼 있지 않음

실시간 데이터 확장에는 매력적이지만 빠른 MVP에는 CiP-DMD보다 어렵다.

---

## 4. Five-Axis CNC Milling with Multiple Changeovers

### 출처

- https://doi.org/10.5281/zenodo.15735480
- https://github.com/ElMoe/Production-Data-Set-for-Five-Axis-CNC-Milling-with-Multiple-Changeovers

### 구조

- 제품 3종
- 30개 제조 session
- Spinner U5-620 5축 밀링 머신
- changeover, 생산, NC code, tool 정보
- Siemens 840D-SL 제어 데이터

### P3 활용

```text
Session → Product → Changeover → NC Program → Tool → Machine Signal
```

### 한계

- 설비가 사실상 한 대
- 품질·불량 결과가 핵심 데이터가 아님
- RCA보다 changeover와 공정 모니터링에 가까움

---

## 5. UCI SECOM

### 출처

- https://archive.ics.uci.edu/dataset/179/secom

### 구조

- 반도체 생산 단위 1,567개
- 익명 센서·공정 변수 590개
- pass/fail label
- fail 104개

### P3 활용

측정 변수와 pass/fail을 노드로 만들 수는 있지만 공정 경로가 없다.

```text
ProductionEntity → MeasurementFeature → Pass/Fail
```

### 한계

- feature 의미가 익명
- LOT·설비·부품·공정 순서 없음
- 지식그래프보다 feature selection 또는 분류 모델에 적합

---

## 6. BOSCH Plasma-Etching

### 출처

- https://zenodo.org/records/17122442

### 구조

- 10 LOT, 88개 유효 웨이퍼
- 공정 파라미터 시계열 31종
- OES 3,648채널
- 9점·89점 식각 계측

### P3 활용

```text
Lot → Wafer → EtchRun → ProcessSignal → SpatialMeasurement
```

### 한계

- 단일 식각 공정·장비
- 실제 불량 코드 없음
- 구성 부품과 복수 공정 경로 없음

P1 모델링에는 좋지만 P3 RCA 데이터로는 우선순위가 낮다.

## 최종 제안

P3 데이터는 다음과 같이 확정하는 것이 가장 현실적이다.

> CiP-DMD의 메타데이터와 품질 CSV를 이용해 완제품·구성품·가공 공정·실제 기계·공정 이상·품질검사 관계를 Neo4j로 구축하고, 자연어 질문으로 최종 불량에서 상류 공정과 부품을 추적하는 RCA Agent를 구현한다.

이 방향이면 합성 데이터 없이도 다단계 제조 추적과 품질 RCA를 구현할 수 있고, 센서 HDF5를 제외해도 MVP 완성도가 유지된다.
