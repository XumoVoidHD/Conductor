# Conductor — Architecture

How the system is structured, what each piece does, and how it runs today.

**Product goals:** [`PROJECT_VISION.md`](PROJECT_VISION.md)  
**Startup commands:** [`cmd.txt`](cmd.txt) — turn on Postgres, Redis, Conductor, API.

**Foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer around Nautilus, not a replacement.

---

## Goals

- One **shared Conductor service** for all users (orchestration)
- Many **trading nodes** (one process/container per deploy) running Nautilus
- Deploy with a **complete command** (broker + strategy fully specified by the caller)
- Multi-tenancy via **`user_id` on every command**, not one Conductor per user
- Separate **control** (deploy/stop) from **observe** (live positions, heartbeats)

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
│     auth · JWT · dashboard · stamp user_id · Postgres        │
└───────────────┬─────────────────────────────┬───────────────┘
                │ control commands            │ read observe /
                │ (Redis lists)               │ subscribe live
                ▼                             ▼
┌───────────────────────────┐    ┌────────────────────────────┐
│     Conductor Node        │    │  Redis Streams observe     │
│  (ONE for all users)      │    │  observe:events + snapshots│
│  deploy · stop · list     │    │  (planned)                 │
└─────────────┬─────────────┘    └─────────────▲──────────────┘
              │ spawn / tear down              │
              ▼                                │
┌───────────────────────────┐                  │
│      Trading Nodes        │──────────────────┘
│  (N — one per deploy)     │  publish observe events (planned)
│  Nautilus + broker + strat│
└─────────────┬─────────────┘
              ▼
        Broker (Bybit testnet, IBKR later)
```

### Implementation status

| Piece | Status |
|-------|--------|
| Conductor Node + Trading Node | **Done** — subprocess or Docker |
| Redis control lists | **Done** — deploy/stop/list/run/halt/status/reset |
| API auth (register, login, JWT) | **Done** |
| API dashboard → Conductor | **Done** — JWT required; `user_id` = username |
| Shared PostgreSQL (`db/`) | **Done** — users table; Alembic in `backend/` |
| Bybit testnet deploy | **Done** — default broker for dashboard |
| Strategy catalog | **Done** — in-repo list (vault later) |
| Strategy `config` in deploy | **Done** — opaque dict passed to bootstrap |
| Frontend static UI | **Basic** — Bruno preferred for API testing |
| CLI `scripts/send_conductor_command.py` | **Done** — bypass API for Conductor |
| Observe plane (Redis Streams) | **Planned** |
| Durable node records in DB | **Planned** — in-memory registry today |
| Per-user strategy vault | **Planned** |

---

## Repository layout

```
Conductor/
├── cmd.txt                 # How to turn on the project (commands only)
├── ARCHITECTURE.md         # This file
├── PROJECT_VISION.md       # Product vision
├── .env                    # All config (create from template below)
├── docker-compose.yml      # Redis + Conductor (Docker mode)
├── backend/                # FastAPI — auth, dashboard, Alembic migrations
│   ├── app/
│   ├── alembic/
│   └── bruno/              # API request collection
├── db/                     # Shared PostgreSQL (docker compose only)
├── frontend/               # Static UI (optional)
├── conductor_node/         # Shared orchestrator
├── trading_node/           # Nautilus worker + brokers/
├── strategies/             # Example strategies
├── scripts/                # CLI → Redis
├── shared/                 # Shared helpers (.env loader)
├── docker/                 # Dockerfiles
└── worker.py / control.py  # Early local prototype
```

---

## Environment

Single `.env` at **repo root**. The API loads it automatically (`backend/app/core/config.py` also checks `backend/.env` if present).

```env
# --- PostgreSQL (db/docker-compose.yml) ---
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
TRADING_NODE_CONTROL_PORT=9000
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
| `POSTGRES_*` | API, `db/` compose | Shared platform database |
| `SECRET_KEY` | API | JWT signing |
| `BYBIT_TESTNET_*` | API dashboard | Injected into deploy `broker.config` (never from browser) |
| `REDIS_URL` | API, Conductor, CLI | Control plane |
| `CONDUCTOR_NODE_RUNTIME` | Conductor | `subprocess` (local) or `docker` |
| `CONDUCTOR_EVENT_TIMEOUT_SEC` | API | Wait for Conductor reply on dashboard calls |

---

## Components

### 1. Frontend (`frontend/`)

Static HTML/JS — register, login, strategy dashboard.

- Talks to API only (`Authorization: Bearer` on dashboard calls)
- Served on port **5500** (must match `CORS_ORIGINS`)
- **Bruno** (`backend/bruno/`) is the preferred way to test the API during development

---

### 2. Backend (`backend/`)

FastAPI service — auth + dashboard control plane.

**Auth**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/auth/register` | — | Create account (Argon2 password hash) |
| POST | `/api/v1/auth/login` | — | Returns JWT (`sub` = user UUID) |
| GET | `/api/v1/auth/me` | Bearer | Current user |

**Dashboard** (all require JWT)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/dashboard/status` | Redis / Conductor connectivity |
| GET | `/api/v1/dashboard/strategies` | Strategy catalog |
| GET | `/api/v1/dashboard/nodes` | List nodes for authenticated user |
| POST | `/api/v1/dashboard/deploy` | Deploy node + strategy (Bybit creds from server env) |
| POST | `/api/v1/dashboard/nodes/run` | Start strategy |
| POST | `/api/v1/dashboard/nodes/halt` | Stop strategy |
| POST | `/api/v1/dashboard/nodes/status` | Strategy state |
| POST | `/api/v1/dashboard/nodes/stop` | Destroy node |

**Multi-tenancy:** `DashboardService` stamps Conductor commands with `user_id` = authenticated **username** (not from request body).

**Strategy catalog:** `backend/app/catalog/strategies.py` — `running_ping`, `hello_bars`, `ema_cross`. Deploy merges catalog defaults with optional `config` overrides.

**Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Passlib (Argon2), python-jose (JWT), Redis client for Conductor.

---

### 3. Database (`db/`)

Shared PostgreSQL for the whole platform — not owned by `backend/`.

- **Compose:** `db/docker-compose.yml` → container `conductor-postgres`, volume `conductor-postgres`
- **Migrations:** `backend/alembic/` (models live in `backend/app/db/models/`)
- **Today:** `users` table (UUID id, username, email, password_hash, role, trading_nodes limit, is_active, timestamps)
- **Later:** node records, audit log, vault metadata

Default connection: `postgresql://conductor:conductor@127.0.0.1:5432/conductor`

---

### 4. Conductor Node (`conductor_node/`)

One shared long-lived service for the platform.

| Concern | Behavior |
|---------|----------|
| Listen | Redis list `conductor:commands` (`BRPOP`) |
| Deploy | Validate → bootstrap JSON → subprocess or Docker |
| Stop | TCP shutdown → remove process/container |
| List | Nodes for `user_id` from in-memory registry |
| Strategy control | Proxy `run` / `halt` / `status` / `reset` over TCP |
| Reply | Push to `conductor:events` |

**Deploy envelope:**

```json
{
  "command": "deploy",
  "correlation_id": "...",
  "user_id": "alice",
  "payload": {
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
- Conductor allowlists adapters (`bybit`, `interactive_brokers`) and forwards config into bootstrap
- Does **not** authenticate users (API does) or stream live positions

**Key modules:** `service.py`, `redis_bus.py`, `handlers.py`, `deploy.py`, `docker_runtime.py`, `control_client.py`, `registry.py`

---

### 5. Trading Node (`trading_node/`)

Nautilus runtime — one process or container per deploy.

1. Read bootstrap from `CONDUCTOR_BOOTSTRAP_JSON` env
2. Resolve broker via `trading_node/brokers/` registry
3. Build Nautilus `TradingNode`
4. Load strategy from bootstrap import paths + optional `strategy.config`
5. Start engines; strategy **STOPPED** until `run`
6. TCP control socket: `run`, `halt`, `status`, `reset`, `shutdown`, `kill`

**Brokers:** `bybit` (default for testing), `interactive_brokers` (lazy-loaded, deferred).

**Strategies:** any `strategies.*` module referenced in bootstrap (no longer RunningPing-only).

---

### 6. Message bus (Redis)

**Control plane** (implemented) — Redis lists:

| Key | Direction | Content |
|-----|-----------|---------|
| `conductor:commands` | API/CLI → Conductor | deploy, stop, list, run, halt, status, reset |
| `conductor:events` | Conductor → API/CLI | command results |

**Observe plane** (planned) — Redis Streams — see below.

---

### 7. Strategy vault *(planned)*

Per-user strategy store. **Today:** fixed in-repo catalog. **Target:** upload + DB metadata → resolve on deploy.

---

### 8. Broker *(external)*

Nautilus adapters. **Bybit testnet** for dev; **IBKR** when TWS/Gateway ops are ready. Credentials in deploy `broker.config` (dashboard injects from server env).

---

## Observe plane: Redis Streams *(planned)*

Live data (positions, heartbeats) uses **Redis Streams**, separate from Conductor command lists.

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

---

## Multi-tenancy

| Question | Answer |
|----------|--------|
| One Conductor per user? | **No** — shared platform infra |
| Isolation? | `user_id` on every command; list/stop scoped to that user |
| What scales? | Trading nodes (and observe traffic), not Conductor count |

---

## Two planes: control vs observe

| Plane | Purpose | Path |
|-------|---------|------|
| **Control** | Deploy, stop, run/halt strategy | API → Redis lists → Conductor → TCP → node |
| **Observe** | Positions, heartbeats, strategy state | Node → Redis streams → API → Frontend |

Live positions must **not** go through Conductor (wrong responsibility, bottleneck, restart fragility).

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
| `docker` | `docker run` on `DOCKER_NETWORK` |

Bootstrap: `data/nodes/{node_id}/bootstrap.json` (shared volume in Docker mode).

When trading nodes run in Docker with IBKR: `ibg_host: host.docker.internal`.

See `cmd.txt` for Docker mode startup commands.

---

## Control flows

### Deploy (via API)

```
POST /dashboard/deploy { strategy_id, config? }
  → API builds complete deploy command (Bybit creds from env)
  → Redis: deploy (user_id = username)
  → Conductor: bootstrap → spawn node
  → Redis: ok event (node_id, control_port, …)
  → Trading node: Nautilus ready, strategy STOPPED
```

### Run / halt / stop (via API)

```
POST /dashboard/nodes/run|halt|status|stop { node_id }
  → Redis command
  → Conductor: TCP to node
  → Redis: ok/error event
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

1. **auth/Register** (once)
2. **auth/Login** — saves `accessToken`
3. **dashboard/** — Bearer token required

Requires full stack: Postgres + migrations + Redis + Conductor + API.

---

## Broker and strategy status

| Concern | Conductor | Trading node |
|---------|-----------|--------------|
| Broker config | Opaque pass-through | `bybit.py`, `interactive_brokers.py` |
| Strategy module | Required in command | Dynamic import from `strategies.*` |
| Strategy config | In command `strategy.config` | Coerced into `StrategyConfig` |

---

## Design rules

1. **Complete deploy commands** — Conductor does not invent broker fields.
2. **Opaque `broker.config`** — only trading_node brokers interpret adapter config.
3. **One Conductor, many trading nodes** — multi-tenancy via `user_id`.
4. **Control ≠ observe** — lists vs streams; not through Conductor.
5. **Frontend/API → Conductor** — never public sockets into trading nodes from internet.
6. **Nautilus-native trading** — no custom order engine.
7. **Small broker set** — Bybit first for testing; IBKR when ops-ready.

---

## Phased delivery

| Phase | Contents |
|-------|----------|
| **Now** | Conductor + Trading Node + Redis control + API auth + dashboard + shared Postgres + Bybit + strategy catalog |
| **Next** | Durable node records in DB; per-user vault |
| **Then** | Observe pipeline (Redis Streams → API → WebSocket); production frontend |
| **Later** | IBKR production path; multi-host / K8s |

---

*Architecture and responsibility boundaries. Wire formats may evolve; control vs observe split and one-Conductor model stay stable.*
