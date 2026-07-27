# Neo4j 로컬 실행과 권한 구성

## 현재 검증 환경

- Neo4j Community 2026.06.0
- OpenJDK 21
- Cypher Shell 2026.06.0
- Bolt: `neo4j://localhost:7687`
- Browser: `http://localhost:7474`
- 서비스: Homebrew `brew services`

로컬 비밀번호는 프로젝트 파일에 저장하지 않고 macOS Keychain의
`p3-cip-dmd-neo4j` 서비스에 저장했다.

## 현재 Mac에서 실행

```bash
brew services start neo4j
./infra/health_check.sh
./infra/apply_schema.sh
```

비밀번호가 Keychain에 없는 다른 컴퓨터에서는 다음처럼 환경변수를 사용한다.

```bash
cp .env.example .env
export NEO4J_PASSWORD='각자 설정한 로컬 비밀번호'
./infra/health_check.sh
```

## 팀 공통 Docker 방식

Docker Desktop이 설치된 환경에서는 프로젝트 루트에서 실행한다.

```bash
cp .env.example .env
# .env의 NEO4J_PASSWORD를 변경
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
./infra/apply_schema.sh
```

현재 Mac에는 Docker가 없어 Compose 파일 자체의 컨테이너 실행 검증은 하지 않았다. 동일 버전의 Homebrew Neo4j에서 스키마 실행 검증을 완료했다.

## Community Edition의 권한 제한

Community Edition은 여러 사용자를 만들 수 있지만 역할이 없으며 모든 사용자가 묵시적 관리자 권한을 가진다. 따라서 `graph_reader` 사용자 이름만 추가해서는 읽기 전용이 보장되지 않는다.

로컬 Community 환경에서는 다음 두 모드로 분리한다.

```bash
# ETL·스키마 적용 시
./infra/set_homebrew_mode.sh loader

# Agent와 데모 실행 시: DB 전체 쓰기 차단
./infra/set_homebrew_mode.sh reader
```

`reader` 모드는 `server.databases.read_only=neo4j`를 적용하고 Neo4j를 재시작한다. 이 상태에서는 `MATCH`는 가능하지만 `CREATE`, `MERGE`, `SET`, `DELETE`가 DB 수준에서 차단된다.

Enterprise 또는 RBAC 지원 배포에서는 `infra/roles-enterprise.cypher`를 사용해 다음처럼 분리한다.

- `graph_loader`: `architect`
- `graph_reader`: `reader`

공식 문서:

- [macOS 설치](https://neo4j.com/docs/operations-manual/current/installation/osx/)
- [사용자 관리와 Community 제한](https://neo4j.com/docs/operations-manual/current/authentication-authorization/manage-users/)
- [데이터베이스 read-only 설정](https://neo4j.com/docs/operations-manual/current/database-administration/standard-databases/configuration-parameters/)
