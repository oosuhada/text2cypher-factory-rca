# 엔터프라이즈 트랙 2-5 — Interactive Graph Explorer

## 구현 결과

정적 Graphviz 결과를 공식 Neo4j Visualization Library 기반의
상호작용형 탐색 화면으로 교체했다.

- 스키마 manifest에서 노드 라벨과 identity를 동적으로 로드
- 속성 검색 또는 정확한 identity로 탐색 시작
- pan, zoom, drag, 노드·관계 선택과 레이아웃 전환
- 선택 노드를 기준으로 1~3 hop 이웃 누적 확장
- 노드·관계 타입 필터와 고립 노드 표시 제어
- 루트부터 선택 노드까지 현재 화면의 최단 경로 강조
- 선택 노드·관계 속성 상세 패널
- 확장 이력과 원본 노드·관계 테이블
- 서버 경로 제한과 truncation 안내
- 인터랙티브 컴포넌트 장애 시 Graphviz 자동 폴백

`neo4j-viz`의 Streamlit Components v2 통합은 아직 PyPI 1.7.0에
포함되지 않아 공식 저장소의 검증한 commit을 고정했다. 버전이 PyPI에
정식 배포되면 동일 1.8 API의 release pin으로 교체한다.

현재 패키지의 license expression은 `GPL-3.0-only`다. 교육·발표용
저장소에서는 출처와 license를 유지하고, 폐쇄형 상용 배포 전에는
Neo4j commercial agreement 검토 또는 허용 license의 renderer로
교체해야 한다.

## 상태 동기화

NVL widget의 `GraphSelection.nodeIds`와 `relationshipIds`를
Streamlit project context에 저장한다.

- 브라우저 → Python: 그래프 클릭 결과를 상세 패널과 N-hop 확장 입력으로 사용
- Python → 브라우저: `선택 동기화`로 고른 노드를 widget 초기 선택에 주입
- 프로젝트 전환: 선택·필터·확장 이력·widget revision까지 프로젝트별 보존

그래프에 전달하는 ID는 Neo4j `element_id`와 동일하며, 상세 패널과
확장 API가 같은 ID 계약을 사용한다.

## 프로젝트 격리

API 경로는 기존과 같이 schema contract에서 허용한 label·identity만
사용하고, 비 CiP 프로젝트는 root와 모든 path node에 `project_id`를
강제한다.

이번 단계에서는 Streamlit의 direct transport에도
`_DirectProjectGraph`를 추가해 API 우회 시 같은 scope가 반드시
들어가도록 수정했다. 렌더링 직전에는 `validate_project_scope`가 노드와
관계의 `project_id`를 다시 검사하며, 다른 프로젝트 엔티티가 하나라도
섞이면 화면 표시를 차단한다.

CiP-DMD는 manifest의 `isolation_mode: database`와 기존 적재 계약을
유지하므로 legacy node에 `project_id`를 요구하지 않는다.

## 1천·1만 노드 성능 경계

실측 원본은
`evaluation/graph_explorer_performance.json`에 기록했다. 이 값은
renderer-neutral Python payload 생성 시간이며 브라우저 FPS 측정값은
아니다.

| 노드 | 관계 | 전처리 중앙값 | 직렬화 크기 | 정책 |
|---:|---:|---:|---:|---|
| 1,000 | 999 | 1.424 ms | 321,327 bytes | Canvas, 전체 라벨 |
| 10,000 | 9,999 | 36.940 ms | 3,154,325 bytes | WebGL, 선택 라벨, 샘플링 필수 |

운영 UI의 neighborhood API는 요청당 최대 100개 경로로 제한한다.
따라서 1만 노드를 브라우저에 한 번에 보내는 기능이 아니라, 검색과
N-hop 확장으로 업무 대상만 점진적으로 읽는 구조다.

- 1천 이하: Canvas 전체 라벨 허용
- 1천 초과: WebGL과 서버 샘플링, 선택한 노드만 라벨
- 1만 초과: 직접 렌더링 금지, 집계·검색·N-hop으로 1천 이하 축소

재측정:

```bash
.venv/bin/python scripts/benchmark_graph_explorer.py --repeats 7
```

## 검증

- 최단 경로·highlight style의 entity ID 일치
- browser selection → 도메인 entity 상세 매핑
- 여러 neighborhood 병합 시 노드·관계 dedup
- 타 프로젝트 노드·관계 렌더링 차단
- direct transport에서도 `project_id`와 identity property 강제
- 1천·1만·1만 초과 성능 정책 회귀
- Streamlit Graph Explorer navigation 회귀
- 전체 Python·release gate·Next.js lint/build·브라우저 검증

## 상용화 시 후속 과제

- SSO tenant와 Neo4j database를 1:1로 묶는 DB-level isolation
- 실제 배포 기기별 WebGL FPS·메모리·상호작용 latency 수집
- 10만 노드 이상을 위한 서버 집계와 community collapse
- graph export, saved view, 공유 가능한 탐색 URL
