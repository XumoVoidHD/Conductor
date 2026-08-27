# Conductor — Architecture

How the system is structured, what each piece does, and how it runs today.

> **Canonical docs:** [`docs/architecture/`](docs/architecture/architecture.md) (GitBook). Prefer editing there; this file is a convenience mirror.

**Product goals:** [`PROJECT_VISION.md`](PROJECT_VISION.md) · [`docs/vision.md`](docs/vision.md)  
**Build checklist:** [`TASKS.md`](TASKS.md) · [`docs/status-and-roadmap.md`](docs/status-and-roadmap.md)  
**Startup commands:** [`cmd.txt`](cmd.txt)

**Foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer around Nautilus, not a replacement.

---

## Goals

- One **shared Conductor service** for all users (orchestration)
- Many **trading nodes** (one process/container per deploy) running Nautilus
- Deploy with a **complete command** (broker + strategy fully specified by the caller)
- Multi-tenancy via **`user_id` on every command**, not one Conductor per user
- Per-user **node quota** (`users.trading_nodes`); stop keeps the slot, delete frees it
- Separate **control** (deploy / lifecycle / strategy TCP) from **observe** (live positions — Streams still planned; on-demand TCP snapshot exists)

---

## High-level picture

```
┌─────────────────────────────────────────────────────────────┐
│              Frontend / Bruno (optional UI)                  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (+ JWT)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                            API                               │
│  auth · JWT · dashboard · vault · trading_nodes · Postgres   │
└───────────────┬─────────────────────────────┬───────────────┘
                │ control commands            │ snapshot (TCP)
                │ (Redis lists)               │ observe Streams
                ▼                             │ (planned)
┌───────────────────────────┐                 ▼
│     Conductor Node        │    ┌────────────────────────────┐
│  (ONE for all users)      │    │  Redis Streams observe     │
│  deploy · stop · restart  │    │  observe:events + snapshots│
│  delete · list · run/halt │    │  (planned)                 │
└─────────────┬─────────────┘    └─────────────▲──────────────┘
              │ spawn / tear down              │
              ▼                                │
┌───────────────────────────┐                  │
│      Trading Nodes        │── TCP snapshot ──┘ (API can also
│  (N — one per deploy)     │   talk to node TCP directly)
│  Nautilus + broker + strat│
└─────────────┬─────────────┘
              ▼
        Broker (Bybit testnet, IBKR later)
```

### Implementation status

| Piece | Status |
|-------|--------|
| Conductor Node + Trading Node | **Done** — subprocess or Docker |
| Redis control lists | **Done** — deploy/stop/restart/delete/list/run/halt/status/reset |
| Unique control ports (multi-user) | **Done** — from `CONDUCTOR_CONTROL_PORT_BASE` (default 9000) |
| API auth (register, login, JWT) | **Done** |
| API dashboard → Conductor | **Done** — JWT required; `user_id` = username |
| Shared PostgreSQL | **Done** — under `conductor-core/` compose |
| Strategy vault (Postgres) | **Done** — globals + owned + share; register + artifact URIs |
| Durable `trading_nodes` table | **Done** — API source of truth for list/quota/ownership |
| Node quota (stop vs delete) | **Done** — stopped still counts; delete frees slot |
| Bybit testnet deploy | **Done** — default broker for dashboard |
| On-demand node snapshot | **Done** — API → node TCP (offline DB fallback) |
| Frontend static UI | **Basic** — toasts, 10s poll, optimistic status; Bruno for API |
| CLI `scripts/send_conductor_command.py` | **Done** — bypass API for Conductor |
| Conductor registry restart recovery | **Gap** — in-memory only; DB rows survive, live control may need redeploy |
| Observe plane (Redis Streams) | **Planned** |
| Per-user broker secrets | **Planned** — shared server `.env` Bybit keys today |

---

## Repository layout

```
Conductor/
├── cmd.txt                 # How to turn on the project (commands only)
├── ARCHITECTURE.md         # This file
├── PROJECT_VISION.md       # Product vision
├── TASKS.md                # Build checklist
├── .env                    # Secrets + config (not committed)
├── conductor-core/         # Compose: postgres, redis, backend, conductor, frontend
│   └── docker-compose.yml  # Canonical compose file
├── backend/                # FastAPI — auth, dashboard, Alembic, Bruno
│   ├── app/
│   ├── alembic/            # 001 users · 002 strategies · 003 source · 004 trading_nodes
│   └── bruno/
├── frontend/               # Static UI (nginx :5500)
├── conductor_node/         # Shared orchestrator
├── trading_node/           # Nautilus worker + brokers/ + snapshot
├── strategies/             # Example strategies (also seeded as SYSTEM vault)
├── scripts/                # CLI → Redis
├── shared/                 # .env loader, artifact materialize
├── docker/                 # Dockerfiles for conductor + trading-node
└── worker.py / control.py  # Early local prototype (legacy)
```

**Docker grouping**

| Group | How it exists | Labels |
|-------|---------------|--------|
| **conductor-core** | Compose project `conductor-core` — postgres, redis, backend, conductor, frontend | `conductor.stack=core`, `conductor.role=<service>` |
| **Trading nodes** | Spawned by Conductor on deploy (not in compose) | `conductor.stack=trading`, `conductor.role=trading-node` |

```bash
docker compose -f conductor-core/docker-compose.yml up -d
docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head
docker compose -f conductor-core/docker-compose.yml --profile build build trading-node
```

---

## Environment

Single `.env` at **repo root**. The API loads it automatically (`backend/app/core/config.py` also checks `backend/.env` if present).

```env
# --- PostgreSQL ---
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=conductor
POSTGRES_PASSWORD=conductor
POSTGRES_DB=conductor

# --- API ---
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO
CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
SECRET_KEY=change-me-to-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CONDUCTOR_EVENT_TIMEOUT_SEC=20

# --- Bybit (dashboard deploy — https://testnet.bybit.com) ---
BYBIT_ENVIRONMENT=testnet
BYBIT_TESTNET_API_KEY=
BYBIT_TESTNET_API_SECRET=
BYBIT_PRODUCT_TYPE=linear
BYBIT_INSTRUMENT_ID=BTCUSDT-LINEAR.BYBIT

# --- Conductor / Redis ---
REDIS_URL=redis://127.0.0.1:6379/0
CONDUCTOR_COMMANDS_KEY=conductor:commands
CONDUCTOR_EVENTS_KEY=conductor:events
CONDUCTOR_NODES_DIR=data/nodes
CONDUCTOR_CONTROL_PORT_BASE=9000
CONDUCTOR_NODE_RUNTIME=subprocess
TRADING_NODE_IMAGE=conductor-trading-node:latest
DOCKER_NETWORK=conductor-net
DOCKER_PUBLISH_CONTROL_PORT=false
BROKER_ADAPTER=bybit

# --- IBKR (later) ---
TWS_ACCOUNT=DU1234567
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=10
```

| Variable | Used by | Purpose |
|----------|---------|---------|
| `POSTGRES_*` | API, compose | Shared platform database |
| `SECRET_KEY` | API | JWT signing |
| `BYBIT_TESTNET_*` | API dashboard | Injected into deploy `broker.config` (never from browser) |
| `REDIS_URL` | API, Conductor, CLI | Control plane |
| `CONDUCTOR_NODE_RUNTIME` | Conductor | `subprocess` (local) or `docker` |
| `CONDUCTOR_CONTROL_PORT_BASE` | Conductor | First free port for new nodes (unique across all users) |
| `DOCKER_PUBLISH_CONTROL_PORT` | Conductor | If true, publish `host:port → container:port` (compose sets true) |
| `CONDUCTOR_EVENT_TIMEOUT_SEC` | API | Wait for Conductor reply on dashboard calls |

---

## Components

### 1. Frontend (`frontend/`)

Static HTML/JS — register, login, strategy dashboard.

- Talks to API only (`Authorization: Bearer`)
- Served on port **5500** (must match `CORS_ORIGINS`)
- Top-right **toasts** (green run/deploy, yellow stop/restart, red delete/errors); auto-dismiss ~3.5s
- Nodes **poll every 10s**; optimistic Starting / Stopping / Restarting / Deleting
- Actions: Deploy, Run, Stop, Restart, Delete (Halt is API-only today)
- Deploy disabled when node quota is full
- **Bruno** (`backend/bruno/`) remains preferred for full API testing

---

### 2. Backend (`backend/`)

FastAPI — auth + dashboard control plane + vault + durable node records.

**Auth**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/auth/register` | — | Create account (Argon2) |
| POST | `/api/v1/auth/login` | — | Returns JWT (`sub` = user UUID) |
| GET | `/api/v1/auth/me` | Bearer | Current user |

**Dashboard** (all require JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/dashboard/status` | Redis ping + username |
| GET | `/api/v1/dashboard/strategies` | Vault: global / owned / shared |
| POST | `/api/v1/dashboard/strategies/register` | Register strategy artifact |
| POST | `/api/v1/dashboard/strategies/{slug}/access` | Share with another user |
| GET | `/api/v1/dashboard/nodes` | DB nodes merged with live Conductor probe |
| POST | `/api/v1/dashboard/deploy` | Deploy (Bybit creds from server env) |
| POST | `/api/v1/dashboard/nodes/run` | Start strategy (starts container if stopped) |
| POST | `/api/v1/dashboard/nodes/halt` | Stop strategy only; node stays up |
| POST | `/api/v1/dashboard/nodes/status` | Probe: Stopped / Initializing / Ready / Running |
| POST | `/api/v1/dashboard/nodes/stop` | Stop process/container; **slot kept** |
| POST | `/api/v1/dashboard/nodes/restart` | Restart process/container |
| POST | `/api/v1/dashboard/nodes/delete` | Destroy node; **frees slot** |
| POST | `/api/v1/dashboard/nodes/snapshot` | Live Nautilus snapshot via TCP (or offline DB stub) |

**Multi-tenancy:** `DashboardService` stamps Conductor commands with `user_id` = authenticated **username**. Ownership and quota come from Postgres `trading_nodes` (`deleted_at IS NULL`).

**Quota:** `users.trading_nodes` (default 2). Stopped nodes still count. Only soft-delete frees a slot. Checked in API and again on Conductor deploy (`max_trading_nodes` in payload).

**Strategy vault:** Postgres `strategies` + `strategy_access`. Seeds: `running_ping`, `hello_bars`, `ema_cross`. Deploy resolves vault → full Conductor payload.

**Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Passlib (Argon2), python-jose (JWT), Redis client for Conductor.

---

### 3. Database

Shared PostgreSQL for the platform (compose service `postgres` in `conductor-core/`).

- **Migrations:** `backend/alembic/`
- **Tables today:** `users`, `strategies`, `strategy_access`, `trading_nodes`
- **Later:** audit log, per-user broker secrets, observe snapshots

Default connection: `postgresql://conductor:conductor@127.0.0.1:5432/conductor`

**Split of truth**

| Concern | Source |
|---------|--------|
| List / quota / ownership / soft-delete | API Postgres `trading_nodes` |
| Live spawn / TCP proxy / in-memory ports | Conductor `NodeRegistry` |

After Conductor restart, DB rows remain; live registry is empty until nodes are redeployed (no reconcile yet).

---

### 4. Conductor Node (`conductor_node/`)

One shared long-lived service for the platform.

| Concern | Behavior |
|---------|----------|
| Listen | Redis list `conductor:commands` (`BRPOP`) |
| Deploy | Validate → allocate unique control port → bootstrap → subprocess or Docker |
| Stop | Stop process/container; keep registry entry (slot reserved) |
| Restart | Restart process/container |
| Delete | Tear down + remove from registry (frees port + slot) |
| List | In-memory nodes for `user_id` |
| Strategy control | Proxy `run` / `halt` / `status` / `reset` over TCP |
| Reply | Push to `conductor:events` |

**Port allocation:** unique ports from `CONDUCTOR_CONTROL_PORT_BASE` across **all users**. Reserved until delete. Also skips host ports already bound by labeled trading-node containers.

**Deploy envelope:**

```json
{
  "command": "deploy",
  "correlation_id": "...",
  "user_id": "alice",
  "payload": {
    "max_trading_nodes": 2,
    "broker": { "adapter": "bybit", "config": { } },
    "strategy": {
      "module": "strategies.running_ping",
      "class_name": "RunningPing",
      "config_class": "RunningPingConfig",
      "config": { }
    }
  }
}
```

- `broker.config` is **opaque** to Conductor
- Adapter allowlist: `bybit`, `interactive_brokers`
- Does **not** authenticate users (API does) or stream live positions

**Key modules:** `service.py`, `redis_bus.py`, `handlers.py`, `deploy.py`, `docker_runtime.py`, `control_client.py`, `registry.py`

---

### 5. Trading Node (`trading_node/`)

Nautilus runtime — one process or container per deploy.

1. Read bootstrap from `CONDUCTOR_BOOTSTRAP` / `CONDUCTOR_BOOTSTRAP_JSON`
2. Resolve broker via `trading_node/brokers/`
3. Build Nautilus `TradingNode`
4. Load strategy from bootstrap (+ optional artifact materialize)
5. Start engines; strategy **STOPPED** until `run`
6. TCP control: `run`, `halt`, `status`, `reset`, `shutdown`, `kill`, `snapshot`

**Brokers:** `bybit` (dashboard default), `interactive_brokers` (lazy-loaded, deferred).

**Statuses (Conductor probe):** `Stopped` | `Initializing` | `Ready` | `Running`.

---

### 6. Message bus (Redis)

**Control plane** (implemented) — Redis lists:

| Key | Direction | Content |
|-----|-----------|---------|
| `conductor:commands` | API/CLI → Conductor | deploy, stop, restart, delete, list, run, halt, status, reset |
| `conductor:events` | Conductor → API/CLI | command results |

**Observe plane** (planned) — Redis Streams — see below.

**Partial observe (done):** `POST /dashboard/nodes/snapshot` — API opens TCP to the node directly (`node_control_client.py`), not via Conductor.

---

### 7. Strategy vault

Per-user (and SYSTEM global) strategy store in Postgres.

| Access | Who sees it |
|--------|-------------|
| SYSTEM / global | Everyone |
| Owned | Owner |
| Shared | Via `strategy_access` |

Register with `filename` under `strategies/` or `source_url` + `source_path` (`local://`, `s3://`, `gs://`). ADMIN → SYSTEM; USER → owned. Artifacts materialize via `shared/artifacts/`.

---

### 8. Broker *(external)*

Nautilus adapters. **Bybit testnet** for dev; **IBKR** when TWS/Gateway ops are ready. Dashboard injects Bybit credentials from server env into `broker.config`.

---

## Observe plane: Redis Streams *(planned)*

Continuous live data (positions, heartbeats) will use **Redis Streams**, separate from Conductor command lists.

```
Trading node → XADD observe:events { user_id, node_id, type, payload }
API consumer → snapshot keys + WebSocket → Frontend
```

Conductor does **not** read or write `observe:*`.

| Key | Type | Purpose |
|-----|------|---------|
| `observe:events` | Stream | All observe events |
| `observe:{user_id}:{node_id}:positions` | Hash | Latest position snapshot |
| `observe:{user_id}:{node_id}:heartbeat` | String | Last seen / ONLINE |

Frontend never talks to Redis directly.

**Today:** on-demand TCP `snapshot` (+ offline DB-backed response when the node is down).

---

## Multi-tenancy

| Question | Answer |
|----------|--------|
| One Conductor per user? | **No** — shared platform infra |
| Isolation? | `user_id` on every command; list/stop/delete scoped to that user |
| Quota? | `users.trading_nodes`; stopped still counts; delete frees |
| Ports? | Unique control ports across all users (no shared 9000 bind) |
| What scales? | Trading nodes (and observe traffic), not Conductor count |

---

## Two planes: control vs observe

| Plane | Purpose | Path |
|-------|---------|------|
| **Control** | Deploy, lifecycle, run/halt | API → Redis lists → Conductor → TCP → node |
| **Snapshot** | Point-in-time Nautilus state | API → TCP → node (bypass Conductor) |
| **Observe** | Continuous positions / heartbeats | Node → Redis streams → API → Frontend *(planned)* |

Live continuous positions must **not** go through Conductor.

---

## Docker deployment

Conductor in Docker spawns sibling **trading node containers** via Docker socket.

| Image | Runs |
|-------|------|
| `conductor-node:latest` | `python -m conductor_node` |
| `conductor-trading-node:latest` | `python -m trading_node` |

| `CONDUCTOR_NODE_RUNTIME` | Behavior |
|--------------------------|----------|
| `subprocess` | Local dev — trading node as host process |
| `docker` | `docker run` on `DOCKER_NETWORK`; control host = container name |

Bootstrap: `data/nodes/{node_id}/bootstrap.json` (named volume `conductor-nodes` in Docker mode).

Compose sets `DOCKER_PUBLISH_CONTROL_PORT=true` so each node publishes its unique host port for host-side access. On the Docker network, Conductor/backend reach nodes as `conductor-{node_id}:{control_port}`.

---

## Control flows

### Deploy (via API)

```
POST /dashboard/deploy { strategy_id, config? }
  → API checks quota + resolves vault + Bybit creds
  → Redis: deploy (user_id = username, max_trading_nodes)
  → Conductor: allocate port → bootstrap → spawn node
  → Redis: ok event (node_id, control_port, …)
  → API: persist trading_nodes row
  → Trading node: Nautilus ready, strategy STOPPED (Initializing → Ready)
```

### Lifecycle / strategy control

```
POST /dashboard/nodes/run|halt|status|stop|restart|delete { node_id }
  → Redis command → Conductor → Docker/TCP as needed
  → API updates trading_nodes (soft-delete on delete)
```

| Action | Container/process | Strategy | Quota slot |
|--------|-------------------|----------|------------|
| **stop** | Stopped | — | Kept |
| **restart** | Restarted | Ready (STOPPED) | Kept |
| **delete** | Removed | — | Freed |
| **halt** | Stays up | Stopped | Kept |
| **run** | Started if needed | Running | Kept |

### Snapshot (bypass Conductor)

```
POST /dashboard/nodes/snapshot { node_id | container_name | node }
  → API ownership check (DB)
  → TCP snapshot to control_host:control_port
  → If unreachable: offline snapshot from DB row
```

### Direct CLI (no API)

```
python scripts/send_conductor_command.py deploy --user-id alice
python scripts/send_conductor_command.py run --user-id alice --node-id tn-...
python scripts/send_conductor_command.py events
```

---

## Testing with Bruno

Collection: `backend/bruno/` — environment **Local**, `baseUrl = http://127.0.0.1:8000`.

```
auth/        Register, Login, Me
health/      Health
dashboard/   Status, Strategies, Register, Deploy, Nodes,
             Run / Stop / Halt / Status / Restart / Delete, Snapshot
```

1. **auth/Register** (once)
2. **auth/Login** — saves `accessToken`
3. **dashboard/** — Bearer token required

Requires full stack: Postgres + migrations + Redis + Conductor + API (+ trading-node image for Docker runtime).

---

## Broker and strategy status

| Concern | Conductor | Trading node |
|---------|-----------|--------------|
| Broker config | Opaque pass-through | `bybit.py`, `interactive_brokers.py` |
| Strategy module | Required in command | Dynamic import from `strategies.*` / artifacts |
| Strategy config | In command `strategy.config` | Coerced into `StrategyConfig` |

---

## Design rules

1. **Complete deploy commands** — Conductor does not invent broker fields.
2. **Opaque `broker.config`** — only trading_node brokers interpret adapter config.
3. **One Conductor, many trading nodes** — multi-tenancy via `user_id`.
4. **Control ≠ observe** — lists vs streams; snapshot may use direct TCP.
5. **Frontend/API → Conductor** — never expose trading-node sockets to the public internet.
6. **Nautilus-native trading** — no custom order engine.
7. **Small broker set** — Bybit first for testing; IBKR when ops-ready.
8. **Stop ≠ delete** — stop keeps quota; delete frees it.

---

## Phased delivery

| Phase | Contents |
|-------|----------|
| **Now** | Conductor + Trading Node + Redis control + API auth + vault + durable nodes + quota + snapshot + Bybit + basic frontend |
| **Next** | Conductor registry reconcile on restart; per-user broker secrets; zip upload vault |
| **Then** | Observe pipeline (Redis Streams → API → WebSocket); richer frontend |
| **Later** | IBKR production path; attach/detach + apply_config; multi-host / K8s |

---

*Architecture and responsibility boundaries. Wire formats may evolve; control vs observe split and one-Conductor model stay stable.*
