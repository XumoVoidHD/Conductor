# Quickstart (Docker)

Bring up Conductor on a single machine with Docker Compose.

Canonical file: `conductor-core/docker-compose.yml`.

---

## Prerequisites

- Docker + Docker Compose
- Repo-root `.env` with at least `SECRET_KEY` and Bybit testnet keys (for dashboard deploy)
- From repo root in all commands below

---

## First time

```bash
# 1. Secrets
# Edit .env — SECRET_KEY, BYBIT_TESTNET_API_KEY, BYBIT_TESTNET_API_SECRET, POSTGRES_*

# 2. Build images
docker compose -f conductor-core/docker-compose.yml --profile build build trading-node
docker compose -f conductor-core/docker-compose.yml build conductor backend frontend

# 3. Postgres + migrations
docker compose -f conductor-core/docker-compose.yml up -d postgres
docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head
```

---

## Start core services

```bash
docker compose -f conductor-core/docker-compose.yml up -d
# or one-by-one: postgres → redis → backend → conductor → frontend
```

| Service | Role | Port |
|---------|------|------|
| postgres | users, strategies, trading_nodes | 5432 |
| redis | control bus | 6379 |
| backend | FastAPI | **8000** |
| conductor | orchestrator (docker.sock) | — |
| frontend | Vite + React UI | **5500** |

Trading nodes appear only after **deploy** (labels `conductor.role=trading-node`).

---

## Verify

```bash
docker compose -f conductor-core/docker-compose.yml ps
curl http://127.0.0.1:8000/health
```

- UI: http://127.0.0.1:5500  
- API: http://127.0.0.1:8000  

Next: [First deploy](first-deploy.md) · [Environment](environment.md)

---

## Rebuild after code changes

```bash
docker compose -f conductor-core/docker-compose.yml build backend
docker compose -f conductor-core/docker-compose.yml up -d --force-recreate backend

docker compose -f conductor-core/docker-compose.yml build frontend
docker compose -f conductor-core/docker-compose.yml up -d --force-recreate frontend

docker compose -f conductor-core/docker-compose.yml build conductor
docker compose -f conductor-core/docker-compose.yml up -d --force-recreate conductor

docker compose -f conductor-core/docker-compose.yml --profile build build trading-node
# Redeploy nodes to pick up a new trading-node image
```

---

## Stop

```bash
docker compose -f conductor-core/docker-compose.yml down
# Also remove trading nodes:
docker ps -q --filter label=conductor.role=trading-node | ForEach-Object { docker rm -f $_ }
```
