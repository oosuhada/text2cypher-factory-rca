# 제품 리팩터링 3~4단계 검증

## 결론

FastAPI로 분리한 1~2단계 경계 위에 Next.js 제품 UI를 추가했다.
Streamlit MVP를 폐기하거나 iframe으로 감싸지 않고, 검증된 Python
엔진은 API 뒤에 유지하면서 외부 사용자 경험만 독립시켰다.

## 3단계 — 랜딩·제품 구조·디자인 시스템

구현한 경로:

| 경로 | 역할 |
|---|---|
| `/` | 제품 가치, 실제 RCA 흐름, 핵심 기능, CTA를 보여주는 랜딩 |
| `/query` | 자연어 질의와 근거 확인이 이어지는 핵심 업무 화면 |
| `/history` | 이 브라우저에 저장된 최근 대화 20개 조회·재실행 |
| `/graph` | 노드 라벨·ID·탐색 깊이를 지정하는 부분 그래프 탐색기 |
| `/data` | 검증된 CiP-DMD ETL 범위, 적재 절차, 다음 업로드 단계 명시 |
| `/operations` | FastAPI·Neo4j·모델 준비 상태와 평가 지표 확인 |

디자인은 AskOosu의 대화 지속성, CodeMap의 제품형 랜딩·정보 계층을
참고했지만 해당 프로젝트의 코드를 복사하지 않았다. FactoryGraph의
근거 중심 워크플로에 맞춰 CSS 토큰, 반응형 내비게이션, 라이트·다크
테마, 상태 표시를 새로 작성했다.

## 4단계 — Query Studio와 근거 워크스페이스

질문 실행 후 페이지를 이동하지 않고 다음 결과를 함께 확인한다.

1. 자연어 답변과 제한사항
2. 반환 행 수, 근거 노드·관계 수, 생성 모델
3. 결과표와 CSV 다운로드
4. Cytoscape 기반 인터랙티브 근거 그래프
5. 읽기 전용 Cypher와 복사 기능
6. 검증·교정 시도 이력

FastAPI가 끊기면 오류 원인과 재시도 동작을 표시한다. 응답은
`localStorage`에 최대 20개만 저장하며, 계정 기반 서버 저장으로
오인하지 않도록 화면에 범위를 표시했다.

## 의도적으로 남긴 경계

- 임의 CSV 업로드는 파일 형식만 받는 가짜 UI로 만들지 않았다.
- 현재 ETL은 CiP-DMD 계약과 무결성 검증을 전제로 한다.
- 범용 업로드는 파일 검사 → 스키마 매핑 → 미리보기 → 비동기 적재 →
  롤백·감사로그가 함께 구현되는 다음 단계로 분리한다.
- Streamlit은 발표·운영용 콘솔, Next.js는 사용자용 제품 UI로 병행한다.

## 검증

```bash
cd web
pnpm install --frozen-lockfile
pnpm lint
pnpm build
```

- ESLint: PASS
- TypeScript: PASS
- Next.js production build: PASS
- 정적 생성 경로: `/`, `/query`, `/history`, `/graph`, `/data`,
  `/operations`
- Python 회귀 테스트: 기존 FastAPI·Agent·ETL 테스트와 함께 별도 실행
- GitHub Actions: Python 테스트와 Web lint/build를 독립 job으로 실행

## 실행

```bash
./scripts/run_product.sh
```

스크립트는 FastAPI의 liveness를 먼저 확인하고 제품 UI를 시작한다.
기본 주소는 제품 UI `http://127.0.0.1:3000`, API 문서
`http://127.0.0.1:8000/docs`다.
