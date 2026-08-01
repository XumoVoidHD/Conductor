# Conductor — Project Vision

What we are building, why, and how the pieces fit together at a product level.

**Technical detail:** [`ARCHITECTURE.md`](ARCHITECTURE.md) — components, data flows, env, API, brokers.  
**Build checklist:** [`TASKS.md`](TASKS.md)  
**How to run locally:** [`cmd.txt`](cmd.txt) — startup commands only.

**Runtime foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer **around** Nautilus, not a replacement.

---

## What we are building

**Conductor** is a hosted control platform for **running your own Nautilus strategies** on live (or paper) workers.

Each user gets:

- A **strategy vault** — their library of Nautilus strategy classes and configs (code they own), plus shared SYSTEM examples
- **Trading nodes** — long-running workers connected to a broker, capped by a per-account quota
- A **UI / API** to deploy nodes, start/stop/restart/delete them, and inspect status (and on-demand snapshots)

The product goal is **simplicity**: run standard Nautilus strategies remotely without building your own infrastructure. We orchestrate workers; Nautilus does the trading.

### What Conductor offers

- Deploy and manage **Nautilus `TradingNode` workers** (subprocess locally, Docker in production)
- Connect workers to **officially Nautilus-supported brokers** we operate and test
- **Start, stop, restart, delete** workers; **run / halt** the strategy inside a running worker
- **Apply configuration** via Nautilus `StrategyConfig` (JSON-serializable params) at deploy time
- **Per-user isolation** — vault access, nodes, and runtime scoped to the account
- **Quota** — each account has `trading_nodes` slots; a stopped node still occupies a slot until deleted

### What Conductor deliberately does not offer

- **No strategy builder** — users write normal Nautilus `Strategy` subclasses
- **No universal instrument provider** — instruments come from the broker adapter Nautilus ships
- **No custom abstractions on top of Nautilus** — no proprietary order engine or data models
- **No broad broker support** — only adapters we choose to operate
- **No full artifact registry product** — vault is storage + metadata, not devpi/commit

If Nautilus can do it natively inside a `TradingNode`, we may expose it. If it requires a custom framework on top, we do not.

---

## Strategy vault

The **vault** is each user's store of runnable Nautilus strategies (plus SYSTEM globals everyone can use).

It holds:

- **Strategy entrypoint** — import path (e.g. `strategies.ema_cross:EmaCross`)
- **Config defaults** — `StrategyConfig` fields for that instance
- **Artifact location** — `source_url` + `source_path` (`local://`, `s3://`, `gs://`)

On deploy, the API resolves the vault entry → builds a complete Conductor deploy payload → node registers the strategy on its `Trader`.

**Today:** Postgres vault — SYSTEM seeds (`running_ping`, `hello_bars`, `ema_cross`), user-owned register-from-file, and share via `strategy_access`. **Still open:** zip/package upload and strategy versioning.

The vault is **storage + metadata**, not a code generator.

---

## Supported brokers

Small, fixed set of brokers with mature **Nautilus live adapters**.

| Phase | Broker | Notes |
|-------|--------|-------|
| **Now (dev/test)** | **Bybit testnet** | Default for local and dashboard deploys |
| v1 prod | Interactive Brokers (TWS / Gateway) | Paper and live via `interactive_brokers` adapter |
| v2 | TBD | Added when adapter + ops are ready |

Users will connect **their own broker credentials** (shared server `.env` today; per-user secrets TBD). Conductor wires the worker; it does not replace the broker.

---

## Mental model: two layers of control

| Layer | Question it answers |
|-------|---------------------|
| **Node orchestration** | Should this container/process exist? Bootstrap, broker creds, control port? Stop vs delete? |
| **In-node control** | Inside a running worker, should this strategy start, stop, or reconfigure? |

Docker lifecycle vs strategy lifecycle inside an already-running Nautilus process.

**Quota rule:** **stop** parks the worker but keeps the slot; **delete** destroys it and frees the slot.

---

## Main roles

### 1. Frontend

UI for nodes, vault, deploy, run/stop/restart/delete, live status. Talks **only** to the API.

**Today:** static HTML/JS in `frontend/` (login + dashboard with toasts and polling). **Primary API testing:** Bruno in `backend/bruno/`.

### 2. API / control plane

Auth, stamp `user_id` on commands, durable node records + quota, vault resolve, enqueue Conductor commands, serve node list, on-demand TCP snapshot. Later: consume observe stream, WebSockets, audit log.

**Today:** FastAPI — register/login/JWT, vault CRUD/share, dashboard lifecycle (deploy/run/halt/stop/restart/delete/status/snapshot).

### 3. Node orchestrator (Conductor Node)

Container/process lifecycle. Validates deploy envelope, allocates a unique control port, writes bootstrap, spawns trading node. Proxies strategy control over TCP.

**Today:** `conductor_node/` — one shared service for all users.

### 4. Trading node (worker)

Long-lived Nautilus runtime. Data/exec engines, broker clients, strategy load, in-node TCP control (including `snapshot`).

**Today:** `trading_node/` — subprocess or Docker container per deploy.

### 5. In-node controller

Remote control inside the worker: `run`, `halt`, `status`, `reset`, `shutdown`, `kill`, `snapshot`. Uses Nautilus Trader APIs.

**Today:** TCP socket in `trading_node/` (Conductor proxies Redis commands; API snapshot talks TCP directly).

### 6. Message bus (Redis)

Async command/event pipe. Control plane uses Redis **lists**. Observe plane (planned) uses Redis **streams**.

### 7. Database

Durable users, vault, trading node records, (later) audit and secrets.

**Today:** shared PostgreSQL via `conductor-core` — `users`, `strategies`, `strategy_access`, `trading_nodes`. Conductor’s live registry remains in-memory.

---

## General flow (happy path)

### Register and deploy (current)

```
User → API: register / login (JWT)
     → API: POST /dashboard/deploy { strategy_id }
     → Conductor: unique port + spawn (user_id = username, Bybit from server env)
     → API: persist trading_nodes row (counts toward quota)
     → Trading node: boots Nautilus, strategy STOPPED → Ready
     → API: POST /dashboard/nodes/run { node_id }
     → Conductor → TCP → strategy.start()
```

### Stop vs delete

```
stop   → container/process down, row kept, quota still used
delete → container removed, soft-delete in DB, quota freed
```

### Target (observe + secrets)

```
User → API: pick vault strategy + config + own broker credentials
     → DB: node record + desired state + audit
     → Conductor: spawn worker (reconciled after restarts)
     → Worker → observe:events → API → WebSocket → Frontend
```

---

## Nautilus boundary

| Nautilus provides | Conductor provides |
|-------------------|-------------------|
| `Strategy`, `StrategyConfig`, indicators | Vault storage + deploy wiring |
| `TradingNode`, engines, cache, msgbus | Worker + bootstrap |
| Broker adapters (Bybit, IBKR, …) | Credential config (shared env → per-user later) |
| `ImportableStrategyConfig`, `Controller` | In-node control handlers |
| Live data, order execution | UI/API to start/stop/monitor |

Conductor should feel like **"run my Nautilus strategies in the cloud with a start/stop button"** — not a new trading framework.

---

## Where we are today

| Area | Status |
|------|--------|
| Conductor Node + Trading Node | Working — subprocess + Docker |
| Redis control plane | Working — deploy/stop/restart/delete/list/run/halt/status/reset |
| Unique multi-user control ports | Working — from port base 9000 |
| Bybit testnet broker | Working — default for dashboard deploy |
| IBKR adapter | Code exists; deferred until TWS/Gateway ops |
| API auth (register, login, JWT) | Working |
| API dashboard lifecycle + snapshot | Working — JWT + username as `user_id` |
| Shared PostgreSQL (`conductor-core`) | Working — users, vault, trading_nodes |
| Strategy vault | Working — DB globals / owned / share; zip upload later |
| Node quota (stop keeps / delete frees) | Working |
| Frontend | Basic static UI (toasts, poll, optimistic); Bruno for full API |
| Observe pipeline (continuous positions) | Planned — Redis Streams |
| Conductor registry reconcile on restart | Gap |
| Per-user broker secrets | Planned |
| Command/event audit log | Planned |

---

## Learning path (this repo)

| Stage | Where | Status |
|-------|--------|--------|
| 1 | `learn/`, `strategies/` | Backtest + example strategies |
| 2 | `trading_node/brokers/` | Live Bybit + IBKR adapters |
| 3 | `worker.py`, `control.py` | Early local socket prototype |
| 4 | `conductor_node/`, Redis | Orchestrator — **done** |
| 5 | `backend/`, vault, trading_nodes, Bruno | Auth + dashboard + durable nodes — **done** |
| 6 | Observe Streams, secrets, production UI, IBKR ops | **Next** |

---

## Success in one paragraph

Conductor succeeds when a user can put Nautilus strategies in a vault, connect a supported broker, deploy a worker from the UI within their quota, start and stop it remotely, inspect live state when they need it, and trust the dashboard because ownership and lifecycle are durable — without SSH, without a custom strategy framework, and without brokers or features Nautilus does not already support.

---

*Vision doc — product scope and roles. Implementation contracts live in ARCHITECTURE.md.*
