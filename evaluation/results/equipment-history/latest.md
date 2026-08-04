# equipment-history Text-to-Cypher 평가

- Dataset: Equipment Maintenance History example
- Provider / model: gemini / gemini-2.5-flash
- Evaluation version: 1.0
- Schema / source: 1.0 / synthetic-equipment-history-v1
- Prompt version: text2cypher-v1
- Evaluation fingerprint: `2812f3e1c20dffabedd90cab385302c069d584ecd913dbb5eb5f5cd6f3b16415`
- Evaluated at: 2026-07-28T01:15:33.028304+00:00

## Variant 비교

| Variant | 의미값 정확도 | 엄격 정확도 | 실행 성공률 | 상태 Macro F1 |
|---|---:|---:|---:|---:|
| baseline | 5.0% | 5.0% | 0.0% | 25.0% |
| few_shot | 80.0% | 25.0% | 100.0% | 68.4% |
| self_correction | 80.0% | 25.0% | 100.0% | 68.4% |

## Self-correction 상태 분류

- Accuracy: 90.0%
- Macro precision: 65.1%
- Macro recall: 73.4%
- Macro F1: 68.4%

### 혼동행렬

| Expected \ Actual | success | empty | blocked | needs_clarification | failed |
|---|---:|---:|---:|---:|---:|
| success | 15 | 1 | 0 | 0 | 0 |
| empty | 0 | 2 | 0 | 0 | 0 |
| blocked | 0 | 0 | 1 | 0 | 0 |
| needs_clarification | 1 | 0 | 0 | 0 | 0 |
| failed | 0 | 0 | 0 | 0 | 0 |

## 실패 유형

- `wrong_status`: 2
- `wrong_value_or_rowset`: 2
