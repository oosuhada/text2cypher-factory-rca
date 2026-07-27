# P3 원본 데이터 위치

현재 실제 P3 관계 데이터는 확보되지 않았다.

이 폴더에는 다음 중 하나가 확정된 뒤 원본을 수정하지 않은 상태로 저장한다.

1. 회사 또는 멘토가 제공한 익명화 P3 데이터
2. 멘토가 승인한 공개 제조 관계 데이터
3. 생성 규칙을 문서화한 합성 제조 데이터

필요한 최소 테이블:

- `lots.csv`
- `process_runs.csv`
- `equipment.csv`
- `equipment_part_history.csv`
- `defects.csv`

필수 키와 컬럼 정의는 `../../docs/data-dictionary.md`의 “P3에 필요한 최소 데이터 계약”을 참고한다.

BOSCH 플라즈마 식각 파일은 현재 P3 주제와 맞지 않으므로 이 저장소에 포함하지 않았다.
