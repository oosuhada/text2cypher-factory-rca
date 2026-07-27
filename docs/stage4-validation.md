# 4단계 Neo4j 실행 검증 결과

## 판정

**PASS — Community Edition 로컬 프로필**

실제 Neo4j 2026.06.0 Community 서버를 설치·기동하고 스키마 적용, 읽기, 쓰기, 데이터베이스 read-only 차단을 확인했다.

## 검증 결과

| 항목 | 실제 결과 | 판정 |
|---|---|---|
| Bolt 연결 | `neo4j://localhost:7687` 연결 성공 | PASS |
| Browser | `http://localhost:7474` 기동 확인 | PASS |
| 스키마 적용 | `infra/schema.cypher` 실행 성공 | PASS |
| 고유 제약조건 | 6개 생성 | PASS |
| 사용자 정의 인덱스 | 3개와 제약 인덱스 6개 모두 ONLINE | PASS |
| 쓰기 모드 | probe 노드 생성·조회 성공 | PASS |
| read-only 조회 | 기존 probe `MATCH` 성공 | PASS |
| read-only 쓰기 | `CREATE`가 read-only 오류로 차단 | PASS |
| 정리 | probe 노드 0개, 쓰기 모드 복구 | PASS |
| 서비스 상태 | Homebrew 서비스 started | PASS |

read-only 쓰기 테스트에서 확인한 오류:

```text
42N18: syntax error or access rule violation - read-only database.
The database is in read-only mode.
```

## 현재 상태

- Neo4j 서비스 실행 중
- 기본 데이터베이스는 Agent 실행을 위해 read-only 상태
- 테스트 노드 없음
- 스키마 제약조건·인덱스 유지
- 로컬 비밀번호는 macOS Keychain에 저장

## 남은 권한 차이

Community Edition에는 역할이 없어 동일 서버 안에서 `graph_loader`와 `graph_reader`의 권한을 분리할 수 없다. 개발 환경에서는 ETL 전후로 데이터베이스 전체 모드를 전환한다.

실제 운영 환경에서는 Enterprise 또는 RBAC 지원 배포에서 `graph_reader`에 built-in `reader` 역할을 부여해야 한다. 이 차이는 4단계 실패가 아니라 배포 에디션에 따른 보안 프로필 차이로 기록한다.
