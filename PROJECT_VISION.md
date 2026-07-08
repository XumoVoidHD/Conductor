# Conductor — Project Vision (High Level)

This document describes **what we are building**, **how pieces connect**, and **what role each piece plays**. It is intentionally high level: enough structure to orient yourself, not a detailed design. A precise spec (APIs, schemas, stream names, Docker layout) comes later, after the concepts settle.

**Runtime foundation:** [Nautilus Trader](https://nautilus.trader/) — strategies, adapters, `TradingNode`, backtest and live engines. Conductor is a control layer **around** Nautilus, not a replacement for it.

---

## What we are building

**Conductor** is a hosted control platform for **running your own Nautilus strategies** on live (or paper) workers.

Each user gets:

- A **strategy vault** — their library of Nautilus strategy classes and configs (code they own and upload)
- **Trading nodes** — long-running Docker workers connected to a broker
- A **UI / API** to deploy nodes, attach strategies from the vault, start/stop them, and see status and history

The product goal is **simplicity**: make it easy to run standard Nautilus strategies remotely without building your own infrastructure. We orchestrate workers; Nautilus does the trading.

### What Conductor offers

- Deploy and manage dockerized **Nautilus `TradingNode` workers**
- Connect workers to **one or two officially Nautilus-supported brokers** (initial target: Interactive Brokers; a second broker TBD)
- **Start, stop, restart** strategy instances on a running node
- **Apply configuration** to a strategy instance (Nautilus `StrategyConfig` — JSON-serializable params users define)
- **Command and event audit** — every action traceable from UI intent to worker outcome
- **Per-user isolation** — vault, nodes, credentials, and runtime scoped to the account

### What Conductor deliberately does not offer

These are out of scope. Users who need them use Nautilus directly or extend their own code:

- **No strategy builder** — we do not generate or compose strategies in the UI. Users write normal Nautilus `Strategy` subclasses and register them in their vault.
- **No universal instrument provider** — instruments come from the broker adapter Nautilus already ships (e.g. IB instrument provider), not a custom cross-market catalog layer.
- **No custom abstractions on top of Nautilus** — no proprietary strategy runtime, order types, or data models beyond what Nautilus exposes.
- **No broad broker support** — only brokers with official Nautilus adapters that we choose to operate and test.
- **No commit/registry/devpi-style package orchestration** — vault storage is simpler (see below); not a full artifact registry product.

If Nautilus can do it natively inside a `TradingNode`, we may expose it. If it requires a custom framework on top of Nautilus, we do not.

---

## Strategy vault

The **vault** is each user's private store of runnable Nautilus strategies.

Conceptually it holds:

- **Strategy entrypoint** — import path to a `Strategy` subclass (e.g. `my_strategies.ema_cross:EmaCross`)
- **Config schema / values** — the `StrategyConfig` fields that instance needs (instrument, bar type, EMA periods, size, etc.)
- **Version or label** — so the user can pick which revision to deploy

When a user deploys a strategy to a node, Conductor:

1. Resolves the vault entry
2. Builds a Nautilus `ImportableStrategyConfig` (or equivalent) for the worker bootstrap
3. Registers the strategy on the node's `Trader` via the in-node controller

The vault is **storage + metadata**, not a code generator. Strategies are ordinary Nautilus code — the same classes that work in a local backtest or `TradingNode` should run on Conductor with minimal changes.

---

## Supported brokers

Conductor officially supports a **small, fixed set** of brokers — those with mature **Nautilus live adapters** we are willing to run in production.

| Phase | Broker | Notes |
|-------|--------|-------|
| v1 | Interactive Brokers (TWS / Gateway) | Paper and live via `interactive_brokers` adapter |
| v2 | TBD (e.g. Binance, another Nautilus adapter) | Added only when adapter + ops are ready |

Users connect **their own broker credentials** (stored securely — vault/secrets layer TBD). Conductor wires the worker to the adapter; it does not replace the broker.

Market data, order routing, and instrument definitions follow **Nautilus adapter behavior** for that broker — we do not add a parallel data or symbology layer.

---

## Mental model: two layers of control

| Layer | Question it answers |
|-------|---------------------|
| **Node orchestration** | Should this container exist? Which image, bootstrap config, broker credentials, which host? |
| **In-node control** | Inside a running container, should this strategy be started, stopped, or reconfigured? |

Keeping this split clear is important: Docker lifecycle vs. strategy lifecycle inside an already-running Nautilus process.

---

## Main roles (who does what)

These are **roles**, not final service names or file layouts.

### 1. Frontend

**Role:** Surface for operators.

Shows nodes, vault strategies, and running instances. Sends intent (deploy node, attach strategy, start, stop, update config). Displays status, logs, and command/event history. Talks **only** to the API.

### 2. API / control plane

**Role:** System of record for **desired state** and **audit**.

Accepts requests from the frontend, validates them, writes to a database, publishes **commands** to workers, and ingests **events** back. Per-user auth and vault access control live here (detail TBD).

### 3. Node orchestrator

**Role:** **Container lifecycle** on a host.

Starts and stops Docker workers when the platform decides a node should exist. Passes bootstrap payload (broker config, node id, bus credentials) into the container at start. Does not trade; does not run strategy logic.

### 4. Trading node (worker)

**Role:** **Long-lived Nautilus runtime** inside Docker.

One container ≈ one `TradingNode`: data engine, exec engine, cache, message bus, broker clients. This is where strategies actually run. Early learning used a local process (`worker.py`); production target is the same pattern inside Docker.

### 5. In-node controller

**Role:** **Remote control inside the worker process.**

Subscribes to commands for this node (via message bus), dispatches to handlers (`start_strategy`, `stop_strategy`, `apply_config`, etc.), and publishes events back. Same process as the trader; different concern from spawning Docker.

Uses Nautilus APIs directly: `Trader.start_strategy`, `Trader.stop_strategy`, `Controller`, strategy state machine (`reset` / `start` after stop), etc.

### 6. Strategy instance

**Role:** A **vault strategy + config** running on a specific node.

Identified by a stable slot/id on that node. Multiple instances can use different vault entries or the same strategy with different configs. Multiple nodes can run the same vault strategy independently.

### 7. Message bus (Redis or similar)

**Role:** **Async command and event pipe** between control plane and workers.

API publishes commands; workers consume and reply with events. Decouples processes and survives restarts better than direct HTTP into containers.

### 8. Database

**Role:** **Durable desired state + audit + vault metadata.**

Users, nodes, vault entries, which strategies are attached to which node, intended run/stop state, config versions, command log, event log. Workers and Redis hold runtime truth; the DB holds what the system **should** look like and **what happened**.

---

## General flow (happy path)

High level only — no wire formats yet.

### User uploads a strategy to the vault

```
User → API: register strategy (import path + config template)
     → DB: vault entry for this user
     → UI: strategy appears in library
```

No compilation or strategy generation in Conductor — validation is "can we import and construct this config" (detail TBD).

### Deploy a node and attach a vault strategy

```
User (UI)
  → API: create node + pick vault strategy + config values + broker credentials
  → DB: record node as pending; record desired strategy instance
  → Node orchestrator: start Docker container with bootstrap (Nautilus TradingNodeConfig)
  → Worker boots: broker connects; controller ready; strategy registered but may wait for start command
  → Worker: publish ready / heartbeat events
  → API: node ONLINE; UI shows node + attached strategy (stopped or running per policy)
```

### Start / stop a strategy on an existing node

```
User (UI)
  → API: start strategy instance X on node Y
  → DB: update desired state; append command record
  → Message bus: command to node Y
  → In-node controller: start/stop via Nautilus Trader API
  → Message bus: accepted / failed event
  → API: persist event; UI updates status
```

### Change configuration

```
User (UI)
  → API: apply new config to strategy instance X on node Y
  → DB + message bus: same pattern as start/stop
  → Controller: stop → reset → update config → start (or defer if not safe — e.g. open position)
  → Events describe outcome (applied, pending, failed)
```

Config changes are **Nautilus strategy config** changes, not a separate config language.

---

## How things wire together (conceptual)

```
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │ HTTP
┌──────▼───────┐         ┌─────────────┐     ┌──────────────┐
│     API      │◄───────►│  Database   │     │ Strategy     │
│ (control     │         │ (desired +  │     │ vault (per   │
│  plane)      │         │  audit)     │     │ user)        │
└──────┬───────┘         └─────────────┘     └──────────────┘
       │
       │ publish commands / consume events
       │
┌──────▼───────────────────────────────────┐
│           Message bus                     │
└──────┬───────────────────────┬───────────┘
       │                       │
┌──────▼──────────┐    ┌───────▼──────────┐
│ Node            │    │ Worker container │
│ orchestrator    │    │ Nautilus         │
│ (Docker up/down)│    │ TradingNode      │
└─────────────────┘    │  ┌─────────────┐ │
                       │  │ Controller  │ │
                       │  └──────┬──────┘ │
                       │         │        │
                       │  ┌──────▼──────┐ │
                       │  │ Vault       │ │
                       │  │ strategies  │ │
                       │  │ (Nautilus)  │ │
                       │  └─────────────┘ │
                       └──────────────────┘
                              │
                              ▼
                    Broker (IBKR, …)
                    via Nautilus adapter
```

**Wiring rules:**

- Frontend **only** talks to the API.
- Workers **do not** expose public strategy control to the internet; they consume from the bus (or a private channel).
- Node orchestrator **starts** containers; in-node controller **operates** what is inside them.
- Every mutating action: **command in → event out**, with a correlation id.
- Trading logic stays in **user vault code** + **Nautilus**; Conductor never executes custom order logic of its own.

---

## Nautilus boundary (what we reuse vs what we build)

| Nautilus provides | Conductor provides |
|-------------------|-------------------|
| `Strategy`, `StrategyConfig`, indicators | Vault storage + deploy wiring |
| `TradingNode`, engines, cache, msgbus | Docker worker + bootstrap |
| Broker adapters (IBKR, …) | Credential storage + adapter config per user |
| `ImportableStrategyConfig`, `Controller` | In-node controller handlers |
| Live data subscriptions, order execution | UI/API to start/stop/monitor |
| Backtest (local / user machine) | Optional later: hosted backtest is not v1 |

Conductor should feel like **"run my Nautilus strategies in the cloud with a start/stop button"** — not a new trading framework.

---

## Current learning path (this repo)

Before the full platform, we learn Nautilus in stages:

| Stage | Where | Purpose |
|-------|--------|---------|
| 1 | `learn/run_backtest.py`, `strategies/` | Strategy + backtest in one process |
| 2 | `learn/run_ibkr_live.py` | Live IBKR + `TradingNode` |
| 3 | `worker.py`, `control.py` | Remote start/stop (socket today → Redis later) |
| 4 | API + DB + Docker + vault | Full Conductor |

The prototype worker (`worker.py` + `control.py`) validates in-node control patterns that the production controller will use with Redis instead of a local socket.

---

## What we are not committing to yet

Left open for detailed design:

- Exact vault format (git repo, zip upload, package registry lite)
- Auth provider, multi-tenancy, billing
- Second broker choice and timeline
- Whether node orchestrator is a separate process or part of the API at first
- Multi-host scheduling, Kubernetes
- Hosted backtests, market data products, or research tools
- Defer-until-safe config rules (beyond basic stop → reconfigure → start)

---

## Success in one paragraph

Conductor succeeds when a user can upload their Nautilus strategies to a vault, connect a supported broker, deploy a worker from the UI, attach a vault strategy with a config, start and stop it remotely, and trust the dashboard because every command and event is recorded — without SSH, without a custom strategy framework, and without brokers or features Nautilus does not already support.

Detailed design (schemas, handlers, Dockerfiles, stream names, vault API) is the next document, written after this model feels clear.

---

*Last updated: high-level vision. Scope = Nautilus-native, vault-based, small broker set. No implementation contract implied.*
