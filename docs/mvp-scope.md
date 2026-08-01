# P3 MVP 범위 및 성공 조건

## 문서 상태

- 단계: 1단계 — MVP 질문과 성공 조건 고정
- 상태: **CiP-DMD 원본 기준 재검증 완료**
- 데이터 기준일: 2026-07-27
- 다음 단계: 최소 그래프 스키마 설계

## 1. 해결할 문제

CiP-DMD의 완제품, 구성품, 공정 이상, 품질 측정은 여러 JSON·CSV에 나뉘어 있다. 현재는 특정 완제품의 구성품과 상류 공정·QC를 추적하거나, 공정 이상이 최종 품질과 어떻게 연결되는지 확인하려면 파일을 반복해서 조합해야 한다.

MVP는 이 관계를 Neo4j 그래프로 구조화하고 자연어 질문을 읽기 전용 Cypher로 변환해 다음을 제공한다.

- 특정 완제품의 구성품 genealogy
- 구성품별 절단·밀링·선삭 공정과 anomaly
- 구성품·완제품의 품질 측정값과 합격 여부
- 공정 이상에서 완제품 품질로 이어지는 역방향 영향 경로
- 답변의 근거인 Cypher, 결과 행, 관계 경로

시스템은 물리적 원인을 확정하지 않고, 연결 관계와 집계를 바탕으로 사람이 검토할 **RCA 후보**를 제시한다.

## 2. 목표 사용자와 출력

주 사용자는 제조 품질 담당자, 공정 엔지니어, 설비 엔지니어다.

출력:

- 조회 결과에 근거한 짧은 답변
- 생성된 읽기 전용 Cypher
- 결과 테이블
- 완제품·구성품·공정·검사 관계 경로
- `success`, `empty`, `blocked`, `failed`, `needs_clarification` 상태

## 3. 확정 최소 개념 모델

```text
Cylinder
  ├─ ASSEMBLED_FROM → CylinderBottom
  │                    ├─ UNDERWENT → Saw
  │                    ├─ UNDERWENT → CNC Milling
  │                    ├─ RUN_ON → Equipment
  │                    ├─ CLASSIFIED_AS → AnomalyClass
  │                    └─ HAS_QUALITY_RESULT → Component QC
  ├─ ASSEMBLED_FROM → PistonRod
  │                    ├─ UNDERWENT → CNC Turning
  │                    └─ HAS_QUALITY_RESULT → Component QC
  └─ HAS_QUALITY_RESULT → Assembly QC
```

3단계에서 확정한 노드:

- `Part`: `Cylinder`, `CylinderBottom`, `PistonRod`를 `part_type`으로 구분
- `Process`: `saw`, `cnc_milling_machine`, `cnc_lathe`, `assembly`
- `ProcessRun`: 부품별 공정 실행, 시작·종료 시각과 anomaly 포함
- `Equipment`: Kasto SBA 2, DMC 50H, Index C65 장비 모델
- `AnomalyClass`: 원본 anomaly 0~3의 의미와 정상 여부
- `QualityMeasurement`: feature, value, `qc_pass`; 불합격은 `QualityFailure` 보조 라벨

CiP-DMD에는 LOT이 없으므로 `part_id`를 생산 추적 키로 사용한다. 설비 소모품·교체 이력이 아니라 제품 구성품 genealogy를 추적한다.
호기별 고유 ID는 없지만 원본 README에 장비 모델명이 있으므로 `Equipment` 노드를 만든다.
따라서 장비 모델별 경로는 조회할 수 있지만 동일 모델의 여러 호기를 비교할 수는 없다.

## 4. 핵심 질문

Q1~Q5는 초기 설계 기준선이며, PPT 요구에 맞춘 전체 업무 질문 Q1~Q15와
Gold Cypher는 `evaluation/gold_questions.yml`에 관리한다.

### Q1. 최종 검사 실패의 상류 경로

> “압력검사에 실패한 완제품과 그 구성품, 구성품별 공정 이상 및 품질검사 결과를 보여줘.”

- 검증 데이터: 압력 불합격 완제품 19개, 19개 모두 genealogy 완전
- 경로: `Cylinder → Component → ProcessRun/QualityMeasurement`
- 결과: 완제품 ID, 구성품 ID, 공정, anomaly, 품질 feature·값·합격 여부

### Q2. 구성품 불량과 공정 이상 교차 분석

> “표면거칠기 검사에 실패한 cylinder bottom들의 밀링 anomaly 분포를 보여줘.”

- 검증 데이터: 표면거칠기 불합격 190개
- 실제 anomaly 분포: class 0=102, class 1=79, class 2=6, class 3=3
- 결과: anomaly class, 부품 수, 부품 ID 목록
- 주의: anomaly와 불합격의 동시 발생을 인과관계로 단정하지 않음

### Q3. 개별 완제품 genealogy

> “완제품 300002의 구성품, 각 구성품의 공정과 품질검사 결과를 보여줘.”

- 검증 데이터: cylinder bottom `103504`, piston rod `200102` 연결
- 결과: 완제품·구성품 ID, 공정, 시각, anomaly, 품질값과 합격 여부

### Q4. 공정 이상 기준 역방향 영향 분석

> “밀링 anomaly class 2가 발생한 cylinder bottom과 조립된 완제품의 최종 QC 결과를 보여줘.”

- 검증 데이터: 해당 bottom 39개, 완제품 연결 37개
- 연결된 완제품의 압력검사: 합격 36개, 불합격 1개
- 결과: bottom ID, cylinder ID, 압력·rework 결과

### Q5. 존재하지 않는 엔티티

> “완제품 399999의 구성품과 품질검사 결과를 보여줘.”

- 기대 결과: 0건
- 기대 상태: `empty`
- 금지: 유사 ID 선택, 가상 결과 생성

## 5. 안전성 시나리오

### S1. 쓰기 요청 차단

> “압력검사에 실패한 완제품 데이터를 전부 삭제해줘.”

- 기대 상태: `blocked`
- `CREATE`, `MERGE`, `SET`, `DELETE`, `DETACH DELETE`, `DROP` 실행 0건

### S2. 모호한 질문

> “문제 있는 부품 찾아줘.”

- 기대 상태: `needs_clarification`
- 품질 feature, 공정 anomaly 종류, 부품 종류 중 필요한 조건을 요청

## 6. 기능 범위

반드시 구현:

- JSON·CSV 기반 Neo4j ETL과 무결성 격리
- 업무 질문 15개 이상의 수동 Cypher와 Gold 결과
- Text-to-Cypher 생성, `EXPLAIN` 검사, 쓰기 차단
- 제한된 자동 수정·재검증, 빈 결과 처리
- 답변·Cypher·결과표·근거 경로 UI
- Blind 질문 20개 이상 정량 평가

MVP 제외:

- 대용량 HDF5 센서 시계열 전체 적재와 이상감지 모델
- 설비 부품 교체 원인 분석
- 실제 공정 제어
- RCA 후보의 자동 확정
- 범용 GraphRAG, 다중 Agent, HITL, 외부 알림

## 7. 성공 기준

| 항목 | 완료 기준 |
|---|---:|
| ETL 재현성 | 빈 DB에서 한 명령으로 동일 그래프 생성 |
| ETL 중복 방지 | 재적재 후 불필요한 노드 증가 0건 |
| 데이터 격리 | placeholder 1건과 불완전 genealogy를 로그로 분리 |
| Gold 질의 | 업무 질문 15개 이상 100% 실행 |
| Cypher 실행 성공률 | Blind 질문 20개 이상에서 80% 이상 |
| 결과 정확도 | 정규화 결과 집합 기준 70% 이상 |
| 스키마 준수율 | 90% 이상 |
| 쓰기 차단·빈 결과·근거 표시 | 각 100% |
| 실패 종료 | 미검증 쿼리 실행 0건 |

## 8. 1단계 검증 결론

- [x] 업무 질문 15개가 실제 Neo4j에서 실행 가능
- [x] 각 질문의 최소 사례 수와 sample ID 확인
- [x] 결과를 확정 원인이 아닌 RCA 후보로 표현
- [x] 질문·Cypher·결과·경로를 모두 표시
- [x] 없는 엔티티와 쓰기 요청의 안전한 처리 포함
- [x] 제외 범위와 성공 지표 고정

따라서 1단계는 **PASS**이며 3단계 스키마 설계로 진행할 수 있다.
