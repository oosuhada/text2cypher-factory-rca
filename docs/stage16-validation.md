# 16단계 Blind 평가·회귀 테스트

검증일: 2026-07-27

## 판정

**실제 Gemini 생성·값 기준 평가·자기수정 스트레스 테스트 완료**

Vertex AI `gemini-2.5-flash`가 Gold에 없는 26개 자연어 질문에서 Cypher를
직접 생성하도록 연결해 Baseline → Few-shot → Self-correction 세 조건을
실행했다. `temperature=0`, `seed=42`로 재현 조건을 고정했다.

## 평가셋

- 전체 26문항
- 실제 Neo4j 결과 비교형 23문항
- 모호한 질문 1문항
- 쓰기·삭제 요청 2문항
- Gold Q1~Q15와 같은 문구 0개
- 수동 Gold Cypher의 실제 결과 스냅샷: **23/23 PASS**

## 이중 결과 평가

Cypher 문자열은 평가하지 않는다. 승인된 Neo4j 결과와 다음 두 기준을
동시에 계산한다.

| 지표 | 기준 |
|---|---|
| 의미값 정확도 `result_accuracy` | 컬럼 별칭을 무시하고 각 기대 행의 값을 모두 포함하는지 확인. 추가 근거 컬럼은 허용 |
| 엄격 계약 정확도 `strict_result_accuracy` | 컬럼 이름·행·값·결과 형태가 모두 동일한지 확인 |

기대 필드 누락, 잘못된 값, 행 수 또는 행 집합 차이는 두 기준 모두
오답이다. 값은 맞지만 `count`와 `part_count`처럼 별칭만 다르거나 추가
근거 필드가 붙은 경우는 의미값 정답·엄격 계약 오답으로 기록한다.

## 최신 고정-seed 회귀 결과

| 조건 | 의미값 정확도 | 엄격 계약 정확도 | 실행 성공률 | 빈 결과 처리 | 추정비용 |
|---|---:|---:|---:|---:|---:|
| Baseline | 50.0% | 15.4% | 91.3% | 50.0% | $0.0033 |
| Few-shot | 50.0% | 30.8% | 87.0% | 50.0% | $0.0069 |
| Self-correction | **61.5%** | **38.5%** | **100%** | **100%** | $0.0073 |

Self-correction 결과 26건의 차이:

- 컬럼 계약까지 정확: 10건
- 값은 맞고 별칭/추가 필드만 다름: 6건
- 실제 값·필드·행 집합 오류: 10건

공통 및 부가 지표:

- 읽기 전용 준수율: 세 조건 모두 **100%**
- Self-correction 스키마 준수율: **100%**
- Self-correction 근거 표시율: **100%**
- Blind에서 자기수정이 발동한 3건(B06·B17·B18): **3/3 의미값 회복**
- Self-correction 평균 응답시간: **1,036.2ms**
- 전체 72회 호출: 입력 95,408토큰 / 출력 5,368토큰
- 전체 추정비용: **$0.017532**

## B06 원인 규명

`is_normal`은 모든 노드에서 `BOOLEAN NOT NULL`이고 다음 두 필터는 모두
81건을 반환했다.

- `WHERE NOT anomaly.is_normal`
- `(:AnomalyClass {is_normal: false})`

0건의 원인은 ETL 타입이 아니라 Gemini가 관계를
`ProcessRun→Equipment→AnomalyClass`로 잘못 연결한 것이었다. Neo4j
EXPLAIN은 문법상 유효한 이 경로를 통과시켰다.

`Equipment-[:CLASSIFIED_AS]->AnomalyClass`를 차단하는 관계 토폴로지
검증을 추가했고, Self-correction에서 올바른 두 경로로 수정해 B06 81건을
회복했다. 상세 근거는 [B06 타입 검증](./b06-type-verification.md)에 있다.

## 자기수정 스트레스 테스트

Blind에서 우연히 발생한 오류만으로 성공률을 계산하지 않도록 별도 8건에
문법·미정의 변수·장비 ID·관계 토폴로지·필수 필드 누락 오류를 주입했다.

| 지표 | 결과 |
|---|---:|
| 케이스 | 8 |
| 수정 후 검증 통과 | 100% |
| 의미값 정답 회복 | 37.5% |
| 엄격 계약 회복 | 25.0% |
| Gemini 호출 | 9회 |
| 추정비용 | $0.00120705 |

이 결과는 문법·검증 오류를 없애는 것과 원 질문의 업무 정답을 완전히
복원하는 것이 다름을 보여준다. 발표에서는 Blind 3/3만 제시하지 않고
이 스트레스 테스트도 함께 제시한다.

파일:

- `evaluation/correction_cases.yml`
- `evaluation/run_correction_evaluation.py`
- `evaluation/results/correction_latest.json`

## 실행

```bash
.venv/bin/python evaluation/run_evaluation.py \
  --provider gemini --model gemini-2.5-flash

.venv/bin/python evaluation/run_correction_evaluation.py \
  --provider gemini --model gemini-2.5-flash
```

최신 결과:

- `evaluation/results/blind_evaluation_20260727T105245Z.json`
- `evaluation/results/latest.json`
- `evaluation/results/correction_evaluation_20260727T105120Z.json`
- `evaluation/results/correction_latest.json`
- `evaluation/metrics.json`

비용은 Gemini 2.5 Flash 표준 입력 $0.15/백만 토큰, 비사고 출력
$0.60/백만 토큰을 적용한 추정치다. `thinking_budget=0`으로 실행했다.

## 해석 제한

최초 Blind 실행 후 실패를 분석해 평가기와 의미 검증을 보완했으므로 최신
수치는 완전히 손대지 않은 신규 holdout이 아니라 회귀 측정이다. 외부
일반화 성능을 주장하려면 별도의 신규 holdout을 한 번만 실행해야 한다.

남은 주요 실패는 필수 출력 필드 누락, 잘못된 공정/품질 경로, 집계 결과
형태 차이다. 생성 품질이 완성됐다고 표현하지 않는다.

## 자동 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
```

결과: **62/62 PASS**
