# 엔터프라이즈 트랙 1-4~1-5 구현·검증

## 1. 1-4 Neo4j 적재·무결성

범용 적재 경로를 다음 순서로 고정했다.

1. 승인된 정규화 파일 SHA-256 재검증
2. 프로젝트 ID와 자연키의 복합 uniqueness constraint 적용
3. 설정 가능한 크기의 `UNWIND` batch 적재
4. 하나의 write transaction 안에서 노드·관계 건수 reconciliation
5. 교차 프로젝트 관계 검사
6. 검증 실패 시 transaction rollback 및 `load_failed` 보고서 저장
7. 성공 시 lineage·schema object·counter·integrity 보고서 저장

조회는 `Neo4jReadGraph`의 READ 세션을 유지하고, 적재 서비스는 선택적으로
`NEO4J_LOADER_USERNAME`·`NEO4J_LOADER_PASSWORD`를 사용한다.

### 레거시 그래프 migration

기존 CiP-DMD 그래프의 단일 자연키 제약은 멀티 프로젝트에서 같은 장비 ID를
사용하지 못하게 했다. `scripts/migrate_project_scoped_schema.py`로 다음을
수행했다.

- 기존 CiP-DMD 노드 13,075개에 `project_id=cip-dmd` 부여
- 기존 관계 27,741개에 같은 project scope 부여
- 복합 `(project_id, identity)` 제약 적용
- 충돌하는 레거시 전역 uniqueness constraint 제거
- migration 이후 미지정 노드·관계 0건 확인

### 실제 Neo4j 재적재 검증

Equipment history 데이터를 별도 `loader-integration` 프로젝트로 적재했다.

| 검증 | 결과 |
|---|---|
| 첫 적재 | 노드 20개·관계 24개 생성 |
| 같은 upload 재적재 | 신규 노드 0개·신규 관계 0개 |
| projection reconciliation | PASS |
| 교차 프로젝트 관계 | 0건 |
| reader 모드 복구 | PASS |
| 검증용 프로젝트 정리 | PASS |

## 2. 1-5 Gold·Blind 평가 일반화

`EvaluationRegistry`가 프로젝트별 다음 계약을 검증한다.

- evaluation/schema/source/prompt version
- Gold 15~20문항과 snapshot
- Blind 질문 분리와 snapshot
- READ 전용 Gold Cypher
- Gold·Blind 질문 문구 비중복
- 의미값 기준과 엄격 계약 기준
- 질문·snapshot·manifest 전체 SHA-256 fingerprint

등록 프로젝트:

| 프로젝트 | Gold | Blind | 실제 snapshot 검증 |
|---|---:|---:|---|
| CiP-DMD | 15 | 26 | 23개 실행형 Blind PASS |
| Equipment history | 15 | 20 | Gold 15 + 실행형 Blind 18 PASS |

평가 결과에는 다음이 포함된다.

- 의미값 정확도와 엄격 계약 정확도
- 상태별 Precision·Recall·F1
- 상태 혼동행렬
- 실패 taxonomy와 건수
- 모델·프롬프트·schema·source·evaluation version
- 평가 fingerprint와 실행 시각
- JSON과 Markdown 보고서

실행 예:

```bash
.venv/bin/python evaluation/run_evaluation.py \
  --project equipment-history \
  --verify-expected
```

실제 모델 평가는 `--verify-expected`를 제거하고 `--provider gemini` 또는
`--provider openai`를 지정한다.

### Equipment history Gemini 실측

Gemini 2.5 Flash로 Blind 20문항을 3조건에서 실행했다.

| 조건 | 의미값 정확도 | 엄격 정확도 | 실행 성공률 | 상태 정확도 |
|---|---:|---:|---:|---:|
| Baseline | 5% | 5% | 0% | 5% |
| Few-shot | **80%** | 25% | 100% | **90%** |
| Self-correction | **80%** | 25% | 100% | **90%** |

- 57회 모델 호출
- 총 52,546 input / 4,609 output tokens
- 추정 비용 $0.0106473
- Few-shot부터 모든 실행형 쿼리가 schema·project scope 검증을 통과
- 실패 4건은 도메인 값 번역 1건, 기대 필드 누락 2건,
  모호 질문 확인 요청 실패 1건
- 이번 표본에서는 검증 오류가 발생하지 않아 self-correction이 실제로
  발동하지 않았으며 Few-shot과 같은 점수를 기록

Baseline의 낮은 점수는 자연어 질문만 제공했을 때 모델이 필수
`project_id` 범위를 생략하여 안전 검증에서 실행 전 차단된 결과다. 이는
Few-shot·프로젝트 컨텍스트가 단순 성능 장식이 아니라 데이터 격리를 위한
필수 계약임을 보여준다.
