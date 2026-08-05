# equipment-history Text-to-Cypher 평가

- Dataset: Equipment Maintenance History example
- Provider / model: gemini / gemini-2.5-flash
- Evaluation version: 1.0
- Schema / source: 1.0 / synthetic-equipment-history-v1
- Prompt version: text2cypher-v1
- Evaluation fingerprint: `2812f3e1c20dffabedd90cab385302c069d584ecd913dbb5eb5f5cd6f3b16415`
- Evaluated at: 2026-07-28T01:58:48.154787+00:00

## Variant 비교

| Variant | 의미값 정확도 | 엄격 정확도 | 실행 성공률 | 미검증 실행 | 상태 Macro F1 |
|---|---:|---:|---:|---:|---:|
| baseline | 50.0% | 10.0% | 55.6% | 0 | 59.0% |
| few_shot | 85.0% | 30.0% | 100.0% | 0 | 74.2% |
| self_correction | 85.0% | 30.0% | 100.0% | 0 | 74.2% |

## Self-correction 상태 분류

- Accuracy: 95.0%
- Macro precision: 73.5%
- Macro recall: 75.0%
- Macro F1: 74.2%

### 혼동행렬

| Expected \ Actual | success | empty | blocked | needs_clarification | failed |
|---|---:|---:|---:|---:|---:|
| success | 16 | 0 | 0 | 0 | 0 |
| empty | 0 | 2 | 0 | 0 | 0 |
| blocked | 0 | 0 | 1 | 0 | 0 |
| needs_clarification | 1 | 0 | 0 | 0 | 0 |
| failed | 0 | 0 | 0 | 0 | 0 |

## 실패 유형

- `wrong_status`: 1
- `wrong_value_or_rowset`: 2
