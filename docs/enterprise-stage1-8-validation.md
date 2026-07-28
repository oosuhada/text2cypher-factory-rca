# 엔터프라이즈 트랙 1-8 백엔드 Release Gate·문서화

## 결론

P3 필수 백엔드를 `backend-v1` 릴리스로 고정했다. 단위 테스트가
통과한다는 사실만으로 릴리스하지 않고, OpenAPI·오류 계약·비밀정보·요구사항
추적·새 Docker volume E2E·문서 존재 여부를 하나의 gate로 묶었다.

이 gate를 통과하기 전에는 P4 확장 기능을 백엔드 핵심 경로에 병합하지
않는다.

## 구현 내용

### 1. 로컬 release gate

```bash
./scripts/release_check.sh
```

검사 순서:

1. Python 전체 단위·통합·보안 회귀
2. OpenAPI·요구사항 추적·tracked secret 검사
3. Next.js ESLint·production build
4. shell·Python script 문법
5. Docker Compose contract
6. 필수 릴리스 문서

### 2. Fresh-environment gate

```bash
./scripts/fresh_release_gate.sh
```

기존 `.venv`, node_modules, Neo4j data volume을 사용하지 않는다.

```text
임시 환경파일
→ Compose config
→ 5개 서비스 image build
→ 새 Neo4j volume에 CiP-DMD 적재·멱등성 확인
→ API·Streamlit·Next.js health
→ schema·readiness·검색·Gold 질의·feedback HTTP E2E
→ 서비스·volume·임시 비밀파일 정리
```

GitHub Actions의 `packaged-e2e`도 같은 스크립트를 실행해 로컬과 CI의
검증 드리프트를 없앴다.

### 3. API·오류 계약

- 모든 HTTP 애플리케이션 오류에 `detail`과 구조화된 `error`를 반환
- code, category, message, retryable, request_id 제공
- 모든 응답에 `X-Request-ID`
- OpenAPI에 공통 ErrorEnvelope와 409·422·502 등을 명시
- 일반 PATCH를 통한 ready 우회 차단 유지

### 4. 자동 release contract

`scripts/release_gate.py`가 다음을 차단한다.

- OpenAI, Google, AWS, GitHub token·private key 형태의 tracked secret
- `.env`, credential JSON 등 금지 파일
- 필수 API endpoint 또는 Error schema 누락
- `부분 완료`·`미구현`으로 남은 P3 필수 요구사항
- lineage·오류·troubleshooting·소유권·발표 evidence 문서 누락

### 5. 문서 기준선

- `api-contract.md`: endpoint·상태코드·오류 envelope
- `backend-lineage.md`: source→schema→ETL→평가→질의 계보
- `backend-troubleshooting.md`: 운영 오류별 확인·해결
- `module-ownership.md`: 모듈 소유 역할·교차 승인
- `final-presentation-evidence-pack.md`: PDF 6~7p 발표 증거
- `presentation-limitations.md`: 데이터·모델·배포 한계
- `release/backend-v1.yml`: 기계가 읽는 릴리스 기준

## 검증 결과

2026-07-28 기준 로컬:

- Python: **159/159 PASS**
- API release contract: **26 paths, 24 schemas PASS**
- P3 요구사항: **38/38 완료**
- tracked secret findings: **0**
- Next.js lint·production build: **PASS**
- shell·Python syntax: **PASS**
- 필수 릴리스 문서: **8/8**

Docker CLI가 없는 현재 macOS 실행 환경에서는 로컬 fresh stack 실행을
건너뛰고, 동일 스크립트를 실행하는 GitHub Actions `packaged-e2e`를
fresh-environment 최종 근거로 사용한다.

## Release 결정

다음 조건을 모두 만족할 때만 `backend-v1`을 PASS로 본다.

- local release check PASS
- GitHub `unit-tests`, `web-quality`, `packaged-e2e` PASS
- 비밀정보 발견 0건
- P3 필수 요구사항 추적률 100%
- worktree clean, 해당 commit이 원격 main과 일치
