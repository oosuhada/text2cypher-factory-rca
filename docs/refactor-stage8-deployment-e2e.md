# 제품 리팩터링 8단계 — 배포 패키징과 E2E 운영 검증

## 목적

개발자 환경에 이미 설치된 Python·Node.js에 의존하지 않고 Neo4j, ETL
초기화, FastAPI, Streamlit, Next.js를 같은 계약으로 재현한다. 패키지가
단순히 빌드되는 것뿐 아니라 실제 질문·검색·UI가 동작하는지 외부 HTTP
경계에서 확인한다.

## 패키지 구성

| 서비스 | 역할 | 공개 포트 |
|---|---|---|
| `neo4j` | CiP-DMD 그래프 저장소 | 7474, 7687 |
| `initialize` | 스키마·ETL 적재와 멱등성 확인 후 종료 | 없음 |
| `api` | Text-to-Cypher, 검색, HITL API | 8000 |
| `streamlit` | 회사 가이드 기준 사내 프로토타입 | 8501 |
| `web` | 상용화 확장 Next.js UI | 3000 |

`initialize`가 성공해야 API와 Streamlit이 시작하고, API health가
통과해야 Next.js가 시작한다. Python과 Node 런타임 이미지는 root가 아닌
`factorygraph` 사용자로 실행한다.

## 실행

```bash
cp .env.example .env
# NEO4J_PASSWORD를 실제 로컬 비밀값으로 변경
./scripts/run_product_stack.sh
```

`run_product_stack.sh`는 Compose stack을 빌드·시작하고
`scripts/e2e_smoke.py`를 실행한다.

## E2E 확인 범위

- FastAPI liveness와 보안 헤더
- 그래프 스키마 계약
- 실제 Cylinder 부분 검색
- 고정 Gold 자연어 질문 → Cypher → Neo4j 결과
- 전문가 검증 요약 API
- Next.js 랜딩과 Graph Explorer HTML
- Streamlit health endpoint

## 릴리스 검사

```bash
./scripts/release_check.sh
```

Python 전체 회귀 테스트, Next.js lint/production build, shell·Python
문법, Docker Compose 계약을 한 번에 확인한다. GitHub Actions에서는
새 볼륨에 전체 stack을 올리고 같은 E2E smoke를 실행한다.

## 보안·운영 경계

- `.env`, API 키, Google credential JSON은 이미지에 포함하지 않는다.
- 로컬 포트는 기본적으로 `127.0.0.1`에만 바인딩한다.
- API와 Next.js는 framing, MIME sniffing, referrer 관련 기본 보안
  헤더를 설정한다.
- 공개 배포에서는 TLS reverse proxy, 사용자 인증, rate limit, 중앙
  감사로그 저장소를 별도로 구성해야 한다.
- Neo4j Community 컨테이너의 단일 계정은 ETL 쓰기 권한도 가진다.
  애플리케이션은 읽기 전용 검증을 유지하지만, 실제 고객 환경에서는
  Neo4j Enterprise 역할 분리 또는 ETL/조회 DB 계정 분리가 필요하다.
- Vertex Gemini를 컨테이너에서 사용할 때는 credential JSON을 저장소
  밖에서 read-only secret으로 마운트하고 컨테이너 내부 경로를
  `GOOGLE_APPLICATION_CREDENTIALS`로 지정해야 한다. 기본 패키지는
  외부 키가 없어도 Gold 모드로 재현된다.

