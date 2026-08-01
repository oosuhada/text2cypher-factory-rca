# 관계형 조회와 그래프 조회 비교 계획

## 목적

PPT의 “복잡한 JOIN 기반 관계 추적을 그래프 경로 탐색으로 개선”한다는 설명을
발표에서 검증하기 위한 경량 비교다. Neo4j가 항상 더 빠르다고 주장하는 실험이
아니라, 제조 genealogy·RCA 질문을 어떤 구조로 표현하고 유지하는지가 비교 대상이다.

## 비교 질문

> 압력검사에 실패한 완제품의 구성품, 구성품별 공정 장비와 이상 유형을 보여줘.

### 관계형 모델에서 필요한 논리 테이블

- `parts`
- `assemblies`
- `process_runs`
- `processes`
- `equipment`
- `anomaly_classes`
- `quality_measurements`

SQL에서는 완제품 QC에서 시작해 assemblies와 부품 공정 이력까지 여러 JOIN을
명시해야 한다. 관계가 한 단계 추가되면 JOIN과 alias도 함께 수정해야 한다.

### 그래프 모델의 경로

```cypher
MATCH (c:Cylinder)-[:HAS_MEASUREMENT]->
      (:QualityMeasurement:QualityFailure {feature: 'pressure'}),
      (c)-[:ASSEMBLED_FROM]->(component:Part)
      -[:UNDERWENT]->(run:ProcessRun),
      (run)-[:RUN_ON]->(equipment:Equipment),
      (run)-[:CLASSIFIED_AS]->(anomaly:AnomalyClass)
RETURN c, component, run, equipment, anomaly
```

Cypher는 업무 질문의 관계 경로를 그대로 읽을 수 있고, 같은 패턴을 역방향
영향 분석에도 사용할 수 있다.

## 측정 항목

| 항목 | 측정 방식 |
|---|---|
| 결과 동일성 | 동일 질문의 정규화된 ID·집계 결과 비교 |
| 질의 복잡도 | JOIN 또는 MATCH 관계 수, 쿼리 줄 수 |
| 변경 영향 | 장비·이상 분류 관계 추가 시 수정 위치 수 |
| 설명 가능성 | 결과를 구성한 관계 경로를 UI에 표시할 수 있는지 |
| 실행 시간 | 동일 로컬 환경에서 20회 반복 중앙값; 참고 지표로만 사용 |

## 구현 범위

- 별도 운영 RDB를 구축하지 않는다.
- CiP-DMD의 동일 논리 테이블을 SQLite 또는 DuckDB에 임시 적재한다.
- Gold 질문 중 genealogy/RCA 성격이 강한 3개만 비교한다.
- 데이터 규모가 작으므로 속도 우위를 일반화하지 않는다.

## 발표 문구

“그래프 DB가 무조건 더 빠르다”가 아니라 “제품·구성품·공정·장비·이상·검사로
이어지는 제조 관계를 질의와 근거 경로에 직접 표현하기 쉽다”를 결론으로 삼는다.
