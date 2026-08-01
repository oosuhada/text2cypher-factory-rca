# PPT 중간 검증 후 방향 수정 기록

## 결론

P3의 핵심 방향인 `제조 데이터 → Neo4j 지식그래프 → Text-to-Cypher →
검증·자기수정 → Streamlit`은 유지한다. 데이터셋을 CiP-DMD로 구체화한 것도
과제 범위와 일치한다. 아래 세 가지 과소 설계와 한 가지 우선순위 오류를 수정했다.

## 수정한 내용

### 1. 장비를 그래프에서 제외했던 판단

- 이전: 호기별 고유 ID가 없다는 이유로 Machine 노드 전체를 제외
- 수정: 원본 README의 Kasto SBA 2, DMC 50H, Index C65를 `Equipment`로 적재
- 제한: 장비 모델 단위이며 같은 모델의 여러 호기를 구분하지 않음
- 검증: Equipment 3개, RUN_ON 2,758개, 장비 없는 ProcessRun 0개

### 2. 이상·불량을 속성에만 저장했던 설계

- 이전: `ProcessRun.anomaly`, `QualityMeasurement.qc_pass` 속성만 사용
- 수정: `AnomalyClass` 4개와 `CLASSIFIED_AS` 관계 추가
- 수정: 불합격 측정 443개에 `QualityFailure` 보조 라벨 추가
- 검증: 분류 없는 ProcessRun 0개, qc_pass/라벨 불일치 0개

### 3. 업무 질문 수가 부족했던 계획

- 이전: 핵심 질문 5개만 Gold로 관리
- 수정: PPT 범위에 맞춰 장비·불합격·genealogy 완전성 질문을 추가해 15개로 확대
- 검증: Q1~Q15 수동 Gold Cypher가 실제 Neo4j에서 모두 실행 성공

### 4. UI 구현 우선순위

- 이전: CodeMap 기반 Next.js를 공식 프론트엔드로 계획
- 수정: PPT에 명시된 Streamlit을 공식 MVP UI로 고정
- CodeMap·AskOosu: MVP 완료 후 포트폴리오용 화면 확장 레퍼런스로 유지
- FastAPI: 팀 분업 또는 외부 연동이 필요할 때만 선택적으로 추가

## 추가한 발표 검증

관계형 SQL JOIN과 그래프 Cypher를 동일한 genealogy/RCA 질문으로 비교한다.
속도 우위를 일반화하지 않고, 관계 표현·변경 영향·근거 경로 표시를 중심으로
비교한다. 상세 계획은 `docs/relational-vs-graph-comparison.md`에 있다.

## 유지하는 판단

- LOT이 없으므로 `part_id` 기반 제품 genealogy로 범위를 조정
- 물리적 원인을 확정하지 않고 검토할 RCA 후보를 반환
- 생산 로그 XLSX는 part_id 연결 키가 없어 1차 그래프에서 제외
- HDF5 센서 신호 전체 적재와 이상감지 모델은 P3 MVP 이후로 연기
- 쓰기 쿼리 차단, 빈 결과, 생성 Cypher와 근거 경로 표시는 필수

## 다음 구현 순서

1. 그래프 무결성 테스트와 Gold 결과 자동 저장·비교
2. Text-to-Cypher 생성 → 읽기 전용 검증 → EXPLAIN → 수정 → 실행
3. Streamlit Chat·Evidence·Dashboard
4. Blind 질문 20~30개 평가
5. 관계형 조회 비교 3개와 발표 시나리오
