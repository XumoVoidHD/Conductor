# Conductor — Architecture

How the system is structured today, what each piece does, and how multi-user / live status is meant to work.

Related: [`PROJECT_VISION.md`](PROJECT_VISION.md) (product goals and scope). This file is the technical architecture.

**Foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer around Nautilus, not a replacement for it.

---

## Goals

- One **shared Conductor service** for all users (orchestration)
- Many **trading nodes** (one process/container per deploy) that actually run Nautilus
- Deploy with a **complete command** (broker + strategy fully specified by the caller)
- Multi-tenancy via **`user_id` on every command**, not one Conductor per user
- Separate **control** (deploy/stop) from **observe** (live positions, heartbeats) so live UI does not go through Conductor

---

## High-level picture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│         (nodes, vault, start/stop, live positions)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                            API                               │
│         auth · stamp user_id · desired state · audit         │
└───────────────┬─────────────────────────────┬───────────────┘
                │ control commands            │ read observe /
                │ (Redis)                     │ subscribe live
                ▼                             ▼
┌───────────────────────────┐    ┌────────────────────────────┐
│     Conductor Node        │    │  Redis Streams observe     │
│  (ONE for all users)      │    │  observe:events + snapshots│
│  deploy · stop · list     │    └─────────────▲──────────────┘
└─────────────┬─────────────┘                  │
              │ spawn / tear down              │ XADD
              ▼                                │
┌───────────────────────────┐                  │
│      Trading Nodes        │──────────────────┘
│  (N — one per deploy)     │  publish observe events
│  Nautilus + broker + strat│
└─────────────┬─────────────┘
              │
              ▼
        Broker (IBKR, …)
```

**Today (implemented):** Conductor Node + Trading Node + Redis command/event lists + temp CLI sender.  
**Later:** API, DB, vault, Docker, Frontend, **Redis Streams observe pipeline** (see below).

---

## Observe plane: Redis Streams *(planned — not implemented)*

Live data from trading nodes (positions, heartbeats, strategy state) uses **Redis Streams**, separate from Conductor’s command lists.

### Why Redis Streams (for now)

| Choice | Role |
|--------|------|
| **Redis Streams** | Primary observe bus — durable enough, consumer groups, already running Redis |
| **Redis keys (snapshot store)** | Latest position/heartbeat per `user_id` + `node_id` for fast API reads |
| **Redis PubSub** | Not used as system of record (no snapshot on page load) |
| **Kafka** | Deferred until volume, retention, or multi-consumer needs justify it |

Control traffic stays on Redis **lists** (`conductor:commands` / `conductor:events`). Observe traffic uses Redis **streams** — different primitives, same Redis server.

### Data flow

```
Trading node (Nautilus events)
  → XADD observe:events  { user_id, node_id, type, payload, ts }
  → API observe consumer (consumer group)
       → update snapshot keys (latest state per node)
       → optional: persist to DB for history
  → API WebSocket → Frontend (filtered by auth user_id)
```

Conductor does **not** read or write `observe:*` streams.

### Stream and snapshot keys (convention TBD)

| Name | Type | Purpose |
|------|------|---------|
| `observe:events` | Stream | All observe events from all trading nodes |
| `observe:{user_id}:{node_id}:positions` | String/Hash | Latest position snapshot for API `GET` |
| `observe:{user_id}:{node_id}:heartbeat` | String | Last seen timestamp / ONLINE hint |

Exact key names and stream trimming (`MAXLEN`) to be fixed at implementation time.

### Event envelope (every message includes)

```json
{
  "type": "position_snapshot | position_changed | heartbeat | strategy_state",
  "user_id": "alice",
  "node_id": "tn-abc123",
  "ts": "2026-07-08T12:00:00Z",
  "payload": { }
}
```

Every event is tagged with **`user_id`** and **`node_id`** so the API can:

- Show **one node** — filter by `node_id`
- Show **all nodes for a user** — aggregate snapshots across that user’s nodes

The frontend never subscribes to Redis directly; the API filters by authenticated `user_id`.

### API responsibilities (observe)

| Endpoint / channel | Purpose |
|--------------------|---------|
| `GET /me/nodes/{node_id}/positions` | Snapshot for one node (from snapshot store) |
| `GET /me/positions` | Aggregate across all of the user’s nodes |
| `WebSocket /me/observe` | Push live updates after initial snapshot |

On connect: send current snapshots for all user nodes, then stream deltas from the consumer.

### Trading node responsibilities (observe)

- Publish to `observe:events` from an in-node observer (controller actor or similar)
- Map Nautilus portfolio / position events → observe envelope
- Include `user_id` and `node_id` from bootstrap on every message

### What Conductor does *not* do

- Forward positions or heartbeats
- Consume `observe:events`
- Act as fan-in between trading nodes and the frontend

---

## Multi-tenancy: one Conductor, many nodes

| Question | Answer |
|----------|--------|
| One Conductor per user? | **No** — Conductor is shared platform infra |
| Isolation? | Every command carries `user_id`; list/stop are scoped to that user |
| What scales with users? | **Trading nodes** (and later observe traffic), not Conductor processes |

Conductor is the fleet manager. Trading nodes are the cars. Users get cars; they do not get their own dispatcher.

---

## Two planes: control vs observe

Live “what’s in my trading node?” (positions, PnL, heartbeats) is **not** Conductor’s job.

| Plane | Purpose | Path | Volume |
|-------|---------|------|--------|
| **Control** | Deploy, stop, list nodes; start/stop strategy | API → Conductor → node (or TCP/Redis to node) | Low |
| **Observe** | Live positions, fills, heartbeats, strategy state | Trading node → bus/store → API → Frontend | Higher |

### Why live positions should not go through Conductor

- Wrong responsibility (orchestrator would become a portfolio fan-in)
- Bottleneck when users × nodes × updates all hit one process
- Conductor restart would break monitoring even if trading continues
- Multi-tenant unfairness (one busy node starves others)

### Target observe flow

See **Observe plane: Redis Streams** above. Summary:

1. Trading node `XADD`s to `observe:events` with `user_id` + `node_id`
2. API consumer (not Conductor) updates snapshot store + optional DB
3. Frontend uses API `GET` + WebSocket — never talks to trading nodes or Redis

Conductor remains: create / destroy / answer “what nodes exist for this user?”

---

## Components

### 1. Frontend *(later)*

**Does:** UI for vault, nodes, deploy, strategy run/stop, history, live status.

**Talks to:** API only.

**Does not:** Talk to Redis, Conductor, or trading nodes directly.

---

### 2. API *(later)*

**Does:**

- Authenticate users and stamp `user_id` on commands
- Persist desired state and audit (DB)
- Enqueue control commands for Conductor (same shape as today’s Redis deploy)
- Serve node list / history from DB
- Later: consume `observe:events` stream; serve live positions / WebSockets from snapshot store

**Does not:** Run Nautilus or spawn processes itself (Conductor does spawn).

---

### 3. Conductor Node *(implemented — `conductor_node/`)*

**One shared long-lived service** for the whole platform (single host for now).

**Does:**

| Concern | Behavior |
|---------|----------|
| Listen | Redis list `conductor:commands` (`BRPOP`) |
| Deploy | Validate envelope → write bootstrap JSON → spawn subprocess **or** Docker container |
| Stop | Graceful shutdown via in-node TCP → remove container/process |
| List | Return nodes for a given `user_id` from in-memory registry |
| Strategy control | Proxy `run` / `halt` / `status` / `reset` to trading node TCP |
| Reply | Push results to `conductor:events` |

**Command envelope (deploy):**

```json
{
  "command": "deploy",
  "correlation_id": "...",
  "user_id": "alice",
  "payload": {
    "broker": { "adapter": "interactive_brokers", "config": { } },
    "strategy": {
      "module": "...",
      "class_name": "...",
      "config_class": "..."
    }
  }
}
```

- **`broker.config` is opaque** to Conductor — it must be complete (caller/API supplies IBKR client id, contracts, etc.)
- Conductor only allowlists `adapter` and checks structure, then forwards config into bootstrap
- May allocate a free **control_port** (host TCP resource); does **not** invent broker fields

**Internal pieces:**

| Module | Role |
|--------|------|
| `service.py` | Main loop: dequeue → handle → publish event |
| `redis_bus.py` | Redis command/event lists |
| `handlers.py` | `deploy` / `stop` / `list` / `run` / `halt` / `status` / `reset` |
| `schemas.py` | Parse/validate command envelope |
| `deploy.py` | Bootstrap file + spawn subprocess or Docker container |
| `docker_runtime.py` | `docker run` / stop for trading node containers |
| `control_client.py` | TCP proxy to trading node control socket |
| `registry.py` | In-memory map of running nodes (DB later) |

**Does not:**

- Run strategies or connect to the broker
- Parse IBKR contracts / build data/exec clients
- Stream live positions to the UI
- Authenticate users (API later)

---

### 4. Trading Node *(implemented — `trading_node/`)*

**The Nautilus runtime.** One process or **Docker container** per deploy.

**Does:**

1. Read bootstrap from `CONDUCTOR_BOOTSTRAP`
2. Resolve broker via `trading_node/brokers/` registry
3. Build Nautilus `TradingNode` (data + exec clients + factories)
4. Load strategy from import paths in bootstrap
5. Start engines; leave strategy **stopped** until told to run
6. Expose in-node control (TCP socket — `run` / `halt` / `status` / `reset` / `shutdown` / `kill`)
7. **Later:** publish observe events to Redis Stream `observe:events`

**Broker wiring (`trading_node/brokers/`):**

| Piece | Role |
|-------|------|
| `build_broker(adapter, config)` | Registry lookup |
| `interactive_brokers.py` | Interprets IBKR `config`; builds Nautilus IBKR data/exec clients + factories |
| `types.BrokerSetup` | Clients + factories handed to `TradingNode` |

Adding another broker = new module + registry entry. Conductor schemas stay opaque.

**Strategy load (current):** hardcoded allowlist for `strategies.running_ping` (smoke test). Target: Nautilus `ImportableStrategyConfig` + opaque `strategy.config` dict.

**Does not:**

- Talk to the frontend
- Own multi-user registry (that’s Conductor / DB)
- Interpret deploy envelopes from Redis (Conductor does that)

---

### 5. Message bus *(Redis)*

**Control plane** (implemented) — Redis lists:

| Key | Direction | Content |
|-----|-----------|---------|
| `conductor:commands` | Client/API → Conductor | deploy, stop, list, run, halt, status, reset |
| `conductor:events` | Conductor → Client/API | command results |

**Observe plane** (planned) — Redis Streams:

| Key | Direction | Content |
|-----|-----------|---------|
| `observe:events` | Trading node → API consumer | positions, heartbeats, strategy state |

Plus snapshot keys (`observe:{user_id}:{node_id}:…`) written by the API consumer for fast reads.

Keep control and observe on **separate** Redis primitives. Do not mix position updates into `conductor:events`.

---

### 6. Strategy vault *(later)*

Per-user store of strategy packages / import paths / config templates.

On deploy, API or Conductor resolves vault entry → fills `strategy` (and config) in the standardized command. Vault is storage + metadata, not a strategy builder.

---

### 7. Database *(later)*

Desired state + durable node records (`user_id`, `node_id`, deploy status) + audit.  
Observe **snapshots** may live in Redis keys initially; **history** can move to Postgres later.

Today: in-memory `NodeRegistry` only (lost on Conductor restart).

---

### 8. Broker *(external)*

Nautilus adapters (v1: **Bybit testnet** for dev; IBKR later via dockerized TWS/Gateway). User credentials come in deploy `broker.config`. Conductor and the platform do not replace the broker.

---

## Docker deployment *(implemented)*

Conductor runs in one container. Each deploy spawns a **sibling trading node container** via the Docker socket.

```
┌─────────────────────────────────────────────────────────────┐
│  Host                                                        │
│  ┌─────────┐   ┌──────────────────┐   ┌─────────────────┐ │
│  │  Redis  │◄──│ Conductor Node   │──►│ docker.sock     │ │
│  └─────────┘   │ (orchestrator)   │   └────────┬────────┘ │
│                └────────┬─────────┘            │ spawn     │
│                         │ TCP control          ▼           │
│                ┌────────┴──────────────────────────────┐ │
│                │  conductor-net (bridge)               │ │
│                │  ┌─────────────┐  ┌─────────────┐     │ │
│                │  │ trading tn-a│  │ trading tn-b│ ... │ │
│                │  └─────────────┘  └─────────────┘     │ │
│                └─────────────────────────────────────────┘ │
│                         │ host.docker.internal             │
│                         ▼                                  │
│                    IBKR TWS / Gateway (on host)              │
└─────────────────────────────────────────────────────────────┘
```

### Images

| Image | Dockerfile | Runs |
|-------|------------|------|
| `conductor-node:latest` | `docker/Dockerfile.conductor` | `python -m conductor_node` |
| `conductor-trading-node:latest` | `docker/Dockerfile.trading-node` | `python -m trading_node` |

### Runtime modes

| `CONDUCTOR_NODE_RUNTIME` | Deploy behavior |
|--------------------------|-----------------|
| `subprocess` | Local dev — `python -m trading_node` on host |
| `docker` | `docker run` sibling container on `DOCKER_NETWORK` |

### Docker settings

| Variable | Purpose |
|----------|---------|
| `TRADING_NODE_IMAGE` | Image for spawned trading nodes |
| `DOCKER_NETWORK` | Bridge network (default `conductor-net`) |
| `DOCKER_NODES_VOLUME` | Named volume for bootstrap files (required when Conductor is in Docker) |
| `TRADING_NODE_CONTROL_PORT` | Control port inside each container (default `9000`) |
| `DOCKER_PUBLISH_CONTROL_PORT` | Publish control port to host for `control.py` debugging |

### Bootstrap sharing

Conductor writes `data/nodes/{node_id}/bootstrap.json`. In Docker Compose this uses the named volume `conductor-nodes` mounted at `/app/data/nodes` on both Conductor and spawned trading nodes.

### Control path (Docker)

1. Conductor connects to trading node by **container DNS name** (`conductor-{node_id}`) on `conductor-net`
2. Trading node binds control socket on `0.0.0.0` (`CONTROL_BIND_HOST`)
3. Redis commands `run` / `halt` / `status` / `reset` are proxied over TCP by Conductor

`stop` destroys the container (after graceful `shutdown` if possible).

### Local Docker Compose

```bash
docker compose build trading-node
docker compose up -d redis conductor
python scripts/send_conductor_command.py deploy --user-id alice --ib-host host.docker.internal
python scripts/send_conductor_command.py run --user-id alice --node-id tn-...
python scripts/send_conductor_command.py halt --user-id alice --node-id tn-...
python scripts/send_conductor_command.py stop --user-id alice --node-id tn-...
```

When trading nodes run in Docker, set `ibg_host` to `host.docker.internal` (or the host IP on Linux).

---

## Control flows (what’s implemented)

### Deploy a node

```
CLI / future API
  → Redis: deploy command (complete broker + strategy + user_id)
  → Conductor: parse → bootstrap.json → subprocess OR docker run
  → Redis: ok event (node_id, control_port, pid/container_id, …)
  → Trading node: load bootstrap → build Nautilus → listen for control
```

### Run / halt / reset strategy (via Conductor)

```
CLI / future API
  → Redis: run | halt | status | reset (user_id + node_id)
  → Conductor: TCP to trading node control socket
  → Redis: ok/error event with control reply
```

### Run strategy on a node (direct TCP — local dev)

```
control.py → TCP control_port → trading_node
  → reset if needed → strategy.start()
```

Same operations are available via Conductor Redis commands (`run`, `halt`, `status`, `reset`).

### Stop a node

```
Redis: stop (user_id + node_id)
  → Conductor ownership check
  → TCP shutdown (or kill) on trading node
  → wait for process exit → remove from registry
```

### List nodes for a user

```
Redis: list (user_id)
  → registry filtered by user_id
  → event with node summaries (not live positions)
```

### Live positions for a user *(planned — Redis Streams)*

```
Trading node: Nautilus position event
  → XADD observe:events { user_id, node_id, type, payload }

API consumer (consumer group on observe:events):
  → update observe:{user_id}:{node_id}:positions snapshot
  → push to WebSocket subscribers for that user_id

Frontend:
  → GET /me/positions (all nodes) or GET /me/nodes/{id}/positions (one node)
  → WebSocket /me/observe for live updates
```

---

## Broker and strategy independence (status)

| Concern | Conductor | Trading node |
|---------|-----------|--------------|
| Broker config shape | Opaque pass-through | Interprets in adapter module |
| Brokers supported | Allowlist (`bybit`, `interactive_brokers`) | Bybit + IBKR builders |
| Strategy paths | Required in command | RunningPing allowlist for now |
| Strategy config JSON | Not in command yet | Empty `StrategyConfig()` today |

**Next for strategies:** opaque `strategy.config` + `ImportableStrategyConfig` / `StrategyFactory`.

---

## Repository layout (backend focus)

```
api/                     # FastAPI auth (self-contained: app, alembic, compose, reqs)
frontend/                # Basic static UI (registration → API)
conductor_node/          # Shared orchestrator (Redis → spawn trading nodes)
trading_node/            # Nautilus worker process
  brokers/               # Adapter registry (Bybit + IBKR)
strategies/              # Example / smoke strategies (vault later)
scripts/                 # Temp CLI → Redis (API later)
shared/                  # Shared helpers (.env) for conductor/trading
docker/                  # Conductor + trading-node Dockerfiles
docker-compose.yml       # Conductor/Redis stack only
worker.py / control.py   # Earlier local prototype (still usable standalone)
```

---

## Design rules

1. **Complete deploy commands** — Conductor does not invent account, client id, or contracts.
2. **Opaque `broker.config`** — only trading_node brokers understand adapter-specific fields.
3. **One Conductor, many trading nodes** — multi-tenancy via `user_id`.
4. **Control ≠ observe** — control uses Redis lists; observe uses **Redis Streams** + snapshot keys → API → frontend. Not through Conductor.
5. **Frontend → API only** — never public sockets into trading nodes.
6. **Nautilus-native trading** — no custom order engine or universal instrument layer.
7. **Small broker set** — official Nautilus adapters we operate (**Bybit** first for testing; IBKR later).

---

## Phased delivery

| Phase | What’s in |
|-------|-----------|
| **Now** | Conductor + Trading Node + Redis deploy/stop/list + strategy control (run/halt/reset) + subprocess or Docker spawn + IBKR + RunningPing |
| **Next** | Durable node records (DB); strategy-generic load |
| **Then** | API + auth; vault; Frontend |
| **Observe (then)** | Trading node → **Redis Stream** `observe:events` → API consumer → snapshot keys → `GET` + WebSocket; node-wise and all-nodes views |

---

*This document describes architecture and responsibility boundaries. Wire formats may evolve; the control vs observe split and “one Conductor” model should stay stable.*
