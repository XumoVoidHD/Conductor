# Conductor — Project Vision

What we are building, why, and how the pieces fit together at a product level.

**Technical detail:** [`ARCHITECTURE.md`](ARCHITECTURE.md) — components, data flows, env, API, brokers.  
**How to run locally:** [`cmd.txt`](cmd.txt) — startup commands only.

**Runtime foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer **around** Nautilus, not a replacement.

---

## What we are building

**Conductor** is a hosted control platform for **running your own Nautilus strategies** on live (or paper) workers.

Each user gets:

- A **strategy vault** — their library of Nautilus strategy classes and configs (code they own)
- **Trading nodes** — long-running workers connected to a broker
- A **UI / API** to deploy nodes, attach strategies, start/stop them, and see status and history

The product goal is **simplicity**: run standard Nautilus strategies remotely without building your own infrastructure. We orchestrate workers; Nautilus does the trading.

### What Conductor offers

- Deploy and manage **Nautilus `TradingNode` workers** (subprocess locally, Docker in production)
- Connect workers to **officially Nautilus-supported brokers** we operate and test
- **Start, stop, restart** strategy instances on a running node
- **Apply configuration** via Nautilus `StrategyConfig` (JSON-serializable params)
- **Command and event audit** — every action traceable from UI/API intent to worker outcome
- **Per-user isolation** — vault, nodes, credentials, and runtime scoped to the account

### What Conductor deliberately does not offer

- **No strategy builder** — users write normal Nautilus `Strategy` subclasses
- **No universal instrument provider** — instruments come from the broker adapter Nautilus ships
- **No custom abstractions on top of Nautilus** — no proprietary order engine or data models
- **No broad broker support** — only adapters we choose to operate
- **No full artifact registry product** — vault is storage + metadata, not devpi/commit

If Nautilus can do it natively inside a `TradingNode`, we may expose it. If it requires a custom framework on top, we do not.

---

## Strategy vault

The **vault** is each user's private store of runnable Nautilus strategies.

It holds:

- **Strategy entrypoint** — import path (e.g. `strategies.ema_cross:EmaCross`)
- **Config schema / values** — `StrategyConfig` fields for that instance
- **Version or label** — pick which revision to deploy

On deploy, the platform resolves the vault entry → builds `ImportableStrategyConfig` → registers on the node's `Trader`.

**Today:** a fixed in-repo catalog (`backend/app/catalog/strategies.py`) — `running_ping`, `hello_bars`, `ema_cross`. **Target:** per-user vault in DB + upload/storage.

The vault is **storage + metadata**, not a code generator.

---

## Supported brokers

Small, fixed set of brokers with mature **Nautilus live adapters**.

| Phase | Broker | Notes |
|-------|--------|-------|
| **Now (dev/test)** | **Bybit testnet** | Default for local and dashboard deploys |
| v1 prod | Interactive Brokers (TWS / Gateway) | Paper and live via `interactive_brokers` adapter |
| v2 | TBD | Added when adapter + ops are ready |

Users connect **their own broker credentials** (env today; secrets layer TBD). Conductor wires the worker; it does not replace the broker.

---

## Mental model: two layers of control

| Layer | Question it answers |
|-------|---------------------|
| **Node orchestration** | Should this container/process exist? Bootstrap, broker creds, control port? |
| **In-node control** | Inside a running worker, should this strategy start, stop, or reconfigure? |

Docker lifecycle vs strategy lifecycle inside an already-running Nautilus process.

---

## Main roles

### 1. Frontend

UI for nodes, vault, deploy, run/stop, live status. Talks **only** to the API.

**Today:** static HTML/JS in `frontend/` (login + dashboard). **Primary dev testing:** Bruno collection in `backend/bruno/`.

### 2. API / control plane

Auth, stamp `user_id` on commands, desired state + audit (DB), enqueue Conductor commands, serve node list. Later: consume observe stream, WebSockets.

**Today:** FastAPI — register/login/JWT, dashboard deploy/run/halt/stop via Redis → Conductor.

### 3. Node orchestrator (Conductor Node)

Container/process lifecycle. Validates deploy envelope, writes bootstrap, spawns trading node. Proxies strategy control over TCP.

**Today:** `conductor_node/` — one shared service for all users.

### 4. Trading node (worker)

Long-lived Nautilus runtime. Data/exec engines, broker clients, strategy load, in-node TCP control.

**Today:** `trading_node/` — subprocess or Docker container per deploy.

### 5. In-node controller

Remote control inside the worker: `run`, `halt`, `status`, `reset`, `shutdown`. Uses Nautilus Trader APIs.

**Today:** TCP socket in `trading_node/` (Conductor proxies Redis commands to it).

### 6. Message bus (Redis)

Async command/event pipe. Control plane uses Redis **lists**. Observe plane (planned) uses Redis **streams**.

### 7. Database

Durable users, desired state, audit, vault metadata.

**Today:** shared PostgreSQL in `db/` — `users` table only. Node registry still in-memory in Conductor.

---

## General flow (happy path)

### Register and deploy (current)

```
User → API: register / login (JWT)
     → API: POST /dashboard/deploy { strategy_id }
     → Conductor: deploy command (user_id = username, Bybit creds from server env)
     → Trading node: boots Nautilus, strategy STOPPED
     → API: POST /dashboard/nodes/run { node_id }
     → Conductor → TCP → strategy.start()
```

### Target (vault + observe)

```
User → API: pick vault strategy + config + broker credentials
     → DB: node record + desired state
     → Conductor: spawn worker
     → Worker: ready event
     → Worker → observe:events → API → WebSocket → Frontend
```

---

## Nautilus boundary

| Nautilus provides | Conductor provides |
|-------------------|-------------------|
| `Strategy`, `StrategyConfig`, indicators | Vault storage + deploy wiring |
| `TradingNode`, engines, cache, msgbus | Worker + bootstrap |
| Broker adapters (Bybit, IBKR, …) | Credential config per user |
| `ImportableStrategyConfig`, `Controller` | In-node control handlers |
| Live data, order execution | UI/API to start/stop/monitor |

Conductor should feel like **"run my Nautilus strategies in the cloud with a start/stop button"** — not a new trading framework.

---

## Where we are today

| Area | Status |
|------|--------|
| Conductor Node + Trading Node | Working — subprocess + Docker |
| Redis control plane | Working — deploy/stop/list/run/halt/status/reset |
| Bybit testnet broker | Working — default for dashboard deploy |
| IBKR adapter | Code exists; deferred until TWS/Gateway ops |
| API auth (register, login, JWT) | Working |
| API dashboard (deploy, run, halt, stop) | Working — JWT + username as `user_id` |
| Shared PostgreSQL (`db/`) | Working — users table |
| Strategy catalog | In-repo fixed list (vault later) |
| Frontend | Basic static UI; Bruno preferred for now |
| Observe pipeline (positions, heartbeats) | Planned — Redis Streams |
| Durable node records in DB | Planned |
| Per-user vault upload | Planned |

---

## Learning path (this repo)

| Stage | Where | Status |
|-------|--------|--------|
| 1 | `learn/`, `strategies/` | Backtest + example strategies |
| 2 | `trading_node/brokers/` | Live Bybit + IBKR adapters |
| 3 | `worker.py`, `control.py` | Early local socket prototype |
| 4 | `conductor_node/`, Redis | Orchestrator — **done** |
| 5 | `backend/`, `db/`, Bruno | Auth + dashboard control — **in progress** |
| 6 | Vault, observe, production Frontend | **Next** |

---

## Success in one paragraph

Conductor succeeds when a user can upload Nautilus strategies to a vault, connect a supported broker, deploy a worker from the UI, attach a strategy with config, start and stop it remotely, and trust the dashboard because every command and event is recorded — without SSH, without a custom strategy framework, and without brokers or features Nautilus does not already support.

---

*Vision doc — product scope and roles. Implementation contracts live in ARCHITECTURE.md.*
