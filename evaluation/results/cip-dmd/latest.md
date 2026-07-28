# cip-dmd Text-to-Cypher 평가

- Dataset: CiP-DMD
- Provider / model: gemini / gemini-2.5-flash
- Evaluation version: 1.0
- Schema / source: 1.1 / CiP-DMD public release
- Prompt version: text2cypher-v1
- Evaluation fingerprint: `59480c94c6de0af1a57fdffefb36f49c424f701a4decda5bb5dbfb337be0d75c`
- Evaluated at: 2026-07-28T01:57:39.268332+00:00

## Variant 비교

| Variant | 의미값 정확도 | 엄격 정확도 | 실행 성공률 | 미검증 실행 | 상태 Macro F1 |
|---|---:|---:|---:|---:|---:|
| baseline | 34.6% | 19.2% | 91.3% | 0 | 75.5% |
| few_shot | 61.5% | 34.6% | 91.3% | 0 | 98.8% |
| self_correction | 61.5% | 34.6% | 100.0% | 0 | 100.0% |

## Self-correction 상태 분류

- Accuracy: 100.0%
- Macro precision: 100.0%
- Macro recall: 100.0%
- Macro F1: 100.0%

### 혼동행렬

| Expected \ Actual | success | empty | blocked | needs_clarification | failed |
|---|---:|---:|---:|---:|---:|
| success | 21 | 0 | 0 | 0 | 0 |
| empty | 0 | 2 | 0 | 0 | 0 |
| blocked | 0 | 0 | 2 | 0 | 0 |
| needs_clarification | 0 | 0 | 0 | 1 | 0 |
| failed | 0 | 0 | 0 | 0 | 0 |

## 실패 유형

- `wrong_value_or_rowset`: 10
