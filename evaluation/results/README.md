# Blind 평가 실행 결과

실제 생성 모델 평가를 실행하면 다음 파일이 생성된다.

- `blind_evaluation_<UTC timestamp>.json`: 실행별 보존 결과
- `latest.json`: Streamlit Dashboard가 읽는 최신 결과

현재 `latest.json`이 없는 것은 평가 질문이나 DB 기준선이 없어서가 아니라
`OPENAI_API_KEY` 또는 승인된 로컬 생성 모델이 아직 연결되지 않았기
때문이다. 모델 미실행 상태에서는 결과 정확도를 임의로 기록하지 않는다.
