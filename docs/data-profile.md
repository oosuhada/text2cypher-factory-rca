# CiP-DMD 데이터 프로파일

## 점검 범위

- 데이터: CiP-DMD
- 로컬 원본: `mvp/data/raw/cip_dmd/`
- 사용 파일: 메타데이터 JSON 4개, 품질 CSV 4개, 생산 로그 XLSX 3개
- 제외 파일: 대용량 HDF5 센서 신호
- 프로파일 결과: `mvp/data/processed/cip_dmd_profile.json`

## 엔티티 수

| 원본 | 레코드 | 고유 `part_id` |
|---|---:|---:|
| Cylinder 원본 | 803 | 803 |
| 유효 Cylinder | 802 | 802 |
| Cylinder bottom | 985 | 984 |
| Piston rod | 898 | 898 |
| Reworked piston rod | 52 | 52 |

`CylinderBottom 103604`가 완전히 동일하게 두 번 들어 있어 ETL에서 한 건으로 중복 제거한다.

## 연결 무결성

| 검사 | 결과 |
|---|---:|
| placeholder 제외 | 1건 |
| bottom 참조가 유효한 Cylinder | 801/802 |
| rod 참조가 유효한 Cylinder | 768/802 |
| 양쪽 구성품이 모두 연결된 Cylinder | 767/802 |
| 완전 genealogy 비율 | 95.6% |

불완전 genealogy 35개는 ETL에서 격리 로그로 남기고, 완전 경로를 요구하는 Gold 질의의 기본 모집단에서는 제외한다.

## 공정 및 anomaly

| 공정 | 기록 수 | anomaly 분포 |
|---|---:|---|
| Saw | 985 | 0: 904, 1: 81 |
| CNC milling machine | 847 | 0: 699, 1: 98, 2: 39, 3: 11 |
| CNC lathe | 928 | 0: 928 |

anomaly class의 물리적 의미는 원본 문서에 정의된 범위까지만 사용하고 임의의 고장명을 붙이지 않는다.

## 품질 측정과 불합격

| Feature | 측정 수 | 불합격 |
|---|---:|---:|
| Pressure | 801 | 19 |
| Rework | 801 | 52 |
| Weight | 985 | 0 |
| Surface roughness | 845 | 190 |
| Parallelism | 845 | 70 |
| Groove diameter | 845 | 22 |
| Groove depth | 845 | 15 |
| Coaxiality | 536 | 65 |
| Diameter | 536 | 9 |
| Length | 536 | 1 |

## 핵심 질문 교차검증

- 압력 불합격 완제품: 19개, 모두 완전 genealogy
- 표면거칠기 불합격 bottom 190개의 milling anomaly: 0=102, 1=79, 2=6, 3=3
- milling anomaly class 2 bottom: 39개
- 그중 완제품 연결: 37개
- 연결된 완제품 압력검사: 합격 36개, 불합격 1개
- `Cylinder 300002`: bottom `103504`, rod `200102`로 완전 연결

## 생산 로그

XLSX는 모두 `Tabelle1` 한 시트이며 `Date`, `Time`, `Event` 3열 구조다.

| 로그 | 이벤트 행 | 예시 |
|---|---:|---|
| Milling | 22 | cutting insert 교체, spindle 청소, machine error |
| Sawing | 3 | new material, software error |
| Turning | 6 | cutting insert/thread cutter 교체 |

생산 로그는 날짜·시간 기반 보조 컨텍스트로 사용할 수 있지만 개별 `part_id`가 없어 MVP 핵심 genealogy에 직접 연결하지 않는다.

## 판정

CiP-DMD는 대규모 센서 모델링 데이터가 아니라 **제조 genealogy와 품질 관계를 그래프로 조회하는 P3 MVP**에 충분하다. 핵심 질문마다 실제 사례가 있고, 95.6%의 완제품은 양쪽 구성품까지 연결된다. 2단계 데이터 게이트는 **PASS**다.
