# CiP-DMD 기반 1단계 범위 검증

## 판정

**PASS.** 기존 LOT·파티클·설비부품 가정은 CiP-DMD에 맞지 않아 제거했고, 완제품·제품 구성품·공정 anomaly·품질검사 기반 RCA 질문으로 교체했다.

## 질문별 실데이터 검증

| 질문 | 원본에서 확인한 근거 | 판정 |
|---|---|---|
| Q1 압력검사 실패 상류 경로 | 불합격 19개, 19개 모두 bottom·rod 연결 | PASS |
| Q2 표면거칠기 실패와 밀링 anomaly | 불합격 190개; anomaly 0/1/2/3 = 102/79/6/3 | PASS |
| Q3 완제품 300002 genealogy | bottom `103504`, rod `200102`, QC 결과 존재 | PASS |
| Q4 밀링 anomaly 2 역방향 영향 | bottom 39개, 완제품 연결 37개; 압력 불합격 1개 | PASS |
| Q5 존재하지 않는 완제품 | `399999` 없음 | PASS |
| S1 쓰기 차단 | 데이터와 무관한 안전장치 | 구현 대상 |
| S2 모호성 처리 | feature·process·part type 추가 질문 가능 | 구현 대상 |

## 데이터 품질 처리 정책

- `cylinder 300001`은 component ID 대신 컬럼명이 들어간 placeholder이므로 제외한다.
- `cylinder_bottom 103604`의 완전 중복 레코드 1건은 한 건으로 축약한다.
- 유효 완제품 802개 중 완전 genealogy 767개만 전체 경로 질의의 기본 모집단으로 사용한다.
- bottom 또는 rod 참조가 누락된 35개 완제품은 삭제하지 않고 `incomplete_genealogy` 격리 로그에 남긴다.
- CSV 행 수가 메타데이터 JSON보다 적은 항목은 JSON을 관계·QC의 기준 원본으로 사용하고 CSV는 교차검증용으로 사용한다.
- anomaly는 원본 class 값 그대로 저장하며 의미를 임의로 명명하지 않는다.
- RCA 결과는 상관·연결 후보이며 물리적 원인으로 단정하지 않는다.

## 3단계에 넘길 고정사항

- 기본 키: `part_id`
- 관계 기준 원본: 메타데이터 JSON
- 추적 단위: 완제품 `Cylinder`와 구성품 `CylinderBottom`, `PistonRod`
- 품질 실패 기준: 원본 `qc_pass == false`
- 최소 경로: `Cylinder → Component → ProcessRun/QualityMeasurement`
- Gold Cypher는 3단계 스키마 이름을 확정한 직후 작성한다.
