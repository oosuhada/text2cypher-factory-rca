# 5단계 ETL 및 실제 적재 검증 결과 — 스키마 v1.1

## 판정

**PASS**

CiP-DMD 원본을 변환해 실제 로컬 Neo4j에 적재했으며, 같은 ETL을 반복해도
노드와 관계 수가 증가하지 않음을 확인했다.

## 실제 적재 결과

| 항목 | v1.1 적용 전 | v1.1 적용 후 | 재적재 후 |
|---|---:|---:|---:|
| Part | 2,736 | 2,736 | 2,736 |
| Process | 4 | 4 | 4 |
| Equipment | 0 | 3 | 3 |
| AnomalyClass | 0 | 4 | 4 |
| ProcessRun | 2,758 | 2,758 | 2,758 |
| QualityMeasurement | 7,570 | 7,570 | 7,570 |
| QualityFailure(보조 라벨) | 0 | 443 | 443 |
| ASSEMBLED_FROM | 1,569 | 1,569 | 1,569 |
| UNDERWENT | 2,758 | 2,758 | 2,758 |
| INSTANCE_OF | 2,758 | 2,758 | 2,758 |
| RUN_ON | 0 | 2,758 | 2,758 |
| CLASSIFIED_AS | 0 | 2,758 | 2,758 |
| HAS_MEASUREMENT | 7,570 | 7,570 | 7,570 |
| FOR_PROCESS | 7,570 | 7,570 | 7,570 |

- 전체 고유 노드: 13,075개
- 전체 관계: 27,741개
- 두 번째 실행 신규 노드: 0개
- 두 번째 실행 신규 관계: 0개
- 멱등성: PASS

## 무결성 검증

| 검증 | 실제 결과 | 판정 |
|---|---:|---|
| Transform 단위 테스트 | 6/6 | PASS |
| 품질 CSV 구조 점검 | 4/4 | PASS |
| 누락 component 참조 | 35건 격리 | PASS |
| 완전 genealogy | 767개 | 원본과 일치 |
| Bottom 관계 | 801개 | 원본과 일치 |
| Rod 관계 | 768개 | 원본과 일치 |
| 고아 ProcessRun | 0개 | PASS |
| 고아 QualityMeasurement | 0개 | PASS |
| 압력 불합격 | 19건 | 원본과 일치 |
| 전체 QualityFailure | 443건 | 원본과 일치 |
| 장비 없는 ProcessRun | 0건 | PASS |
| 이상 분류 없는 ProcessRun | 0건 | PASS |
| Cylinder 300002 구성품 | `103504`, `200102` | 원본과 일치 |

## v1.1 마이그레이션 생성량

| 구간 | 노드 생성 | 관계 생성 |
|---|---:|---:|
| Equipment | 3 | 0 |
| AnomalyClass | 4 | 0 |
| ProcessRun 확장 | 0 | 5,516 |
| QualityMeasurement 라벨 확장 | 0 | 0 |

`QualityFailure`는 기존 `QualityMeasurement` 443개에 붙인 보조 라벨이므로
고유 노드 수를 늘리지 않는다.

## 현재 상태

- Neo4j에 전체 CiP-DMD 그래프 적재 완료
- 서비스는 6단계 수동 Cypher 검증을 위해 read-write 상태
- 스키마 제약조건과 인덱스 유지
- 최신 실행 리포트: `data/processed/cip_dmd_etl_summary.json`
- 전체 격리 목록: `data/processed/quarantine/missing_component_references.json`
