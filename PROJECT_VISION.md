# Conductor — Project Vision (High Level)

This document describes **what we are building**, **how pieces connect**, and **what role each piece plays**. It is intentionally vague: enough structure to orient yourself, not a detailed design. A precise spec (APIs, schemas, stream names, Docker layout) comes later, after the concepts settle.

**Reference codebase:** `../numatix/nautilus_trader` — especially Node Manager and Trading Node Controller. Conductor is our own implementation of similar *ideas*, not a fork of Nautilus.

---

## What we are building

**Conductor** is a control platform for **live trading strategies running in isolated workers**.

From a web UI (or API), you should be able to:

- **Deploy** dockerized trading nodes — each node is its own long-running process/container
- **Run different strategy instances** on different nodes (same strategy code, different config, or different strategies entirely)
- **Start, stop, restart** strategies on a running node
- **Change configuration** in a controlled way (including cases where a change must wait until it is safe)
- **See what happened** — status, errors, and a trail of commands and events

The hard problem is not “run Python in Docker.” It is **orchestrating stateful workers remotely** while keeping the UI, database, and runtime in sync.

---

## Mental model: two layers of control

Think of two separate jobs:

| Layer | Question it answers |
|-------|---------------------|
| **Node orchestration** | “Should this container exist? Which image, which bootstrap config, which host?” |
| **In-node control** | “Inside a running container, should this strategy be started, stopped, or reconfigured?” |

Conductor has components for both. Mixing them in one place tends to get messy; keeping the split clear helps when reading Nautilus/Numatix and when designing Conductor.

---

## Main roles (who does what)

These are **roles**, not final service names or file layouts.

### 1. Frontend

**Role:** Surface for operators.

Shows nodes and strategies, sends user intent (deploy, start, stop, apply config), displays status and history. Does not talk to workers directly.

### 2. API / control plane

**Role:** System of record for **desired state** and **audit**.

Accepts requests from the frontend, validates them, writes to a database, and **publishes commands** outward. Also ingests **events** from workers and exposes them for the UI. The API is the boundary between “what humans want” and “what the runtime does.”

### 3. Node orchestrator

**Role:** **Container lifecycle** on a host.

When the platform decides a new trading node should exist, something must start a Docker container (and stop/remove it later). That logic lives here — not inside the strategy and not inside the generic API CRUD layer. It may read config from the database and pass a bootstrap payload into the container at start time.

One orchestrator typically serves one machine (or one pool); scaling to many hosts is a later concern.

### 4. Trading node (worker)

**Role:** **Long-lived runtime** inside Docker.

One container ≈ one trading node: engines, cache, message bus, and whatever actually runs markets/strategies. This is where work happens over minutes or hours, not a one-shot job.

For early phases this might be a simplified runner; later it can be a real Nautilus `TradingNode`. The orchestration layer around it should not depend on that choice.

### 5. In-node controller

**Role:** **Remote control inside the worker process.**

Subscribes to commands targeted at this node, dispatches to handlers (start/stop/apply config, etc.), and publishes events back. This is the pattern Numatix calls Trading Node Controller: same process as the trader, different concern from “spawn Docker.”

### 6. Strategy instance

**Role:** **The thing that trades (or simulates trading).**

A configured instance of strategy logic on a node — identified by a stable slot/id and a config version. Multiple nodes can run the same strategy code with different configs.

### 7. Message bus (Redis or similar)

**Role:** **Async command and event pipe** between control plane and workers.

The API and orchestrator publish commands; workers consume and reply with events. This decouples processes and survives restarts better than direct HTTP into containers. Exact stream/topic layout is for detailed design.

### 8. Database

**Role:** **Durable desired state + history.**

Which nodes exist, which strategies belong to which node, intended run/stop state, config versions, command log, event log. Runtime truth also lives in workers and Redis; the DB is what the UI and API query for “what should the system look like” and “what already happened.”

---

## General flow (happy path)

High level only — no wire formats yet.

### Deploy a new node with a strategy

```
User (UI)
  → API: "create node + attach strategy config"
  → DB: record node as pending / desired running
  → Node orchestrator: start Docker container with bootstrap info
  → Worker boots: controller starts, strategy may auto-start or wait for command
  → Worker: publish "ready" / heartbeat events
  → API: update node status; UI shows ONLINE
```

### Start / stop a strategy on an existing node

```
User (UI)
  → API: "start strategy X on node Y"
  → DB: update desired state; append command record
  → Message bus: command to node Y
  → In-node controller: handler → start/stop strategy in process
  → Message bus: accepted / failed event
  → API: persist event; UI updates status
```

### Change configuration

```
User (UI)
  → API: "apply new config to strategy X on node Y"
  → DB + message bus: same pattern as start/stop
  → Controller: apply immediately OR defer if not safe (e.g. open exposure)
  → Events describe outcome (applied, pending, failed)
  → UI shows intermediate states, not just success/fail
```

The **defer-until-safe** behavior is a deliberate product of the controller layer, not the frontend guessing.

---

## How things wire together (conceptual)

```
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │ HTTP
┌──────▼───────┐         ┌─────────────┐
│     API      │◄───────►│  Database   │
│ (control     │         │ (desired +  │
│  plane)      │         │  audit)     │
└──────┬───────┘         └─────────────┘
       │
       │ publish commands / consume events
       │
┌──────▼───────────────────────────────────┐
│           Message bus                     │
└──────┬───────────────────────┬───────────┘
       │                       │
┌──────▼──────────┐    ┌───────▼──────────┐
│ Node            │    │ Worker container │
│ orchestrator    │    │ (trading node)   │
│ (Docker up/down)│    │  ┌─────────────┐ │
└─────────────────┘    │  │ Controller  │ │
                       │  └──────┬──────┘ │
                       │         │        │
                       │  ┌──────▼──────┐ │
                       │  │ Strategies  │ │
                       │  └─────────────┘ │
                       └──────────────────┘
```

**Important wiring rules (conceptual):**

- Frontend **only** talks to the API.
- Workers **do not** expose public strategy control endpoints to the internet; they consume from the bus (or a private channel).
- Node orchestrator **starts** containers; in-node controller **operates** what is inside them.
- Every user action that mutates runtime should be traceable: **command in → event out**, with a shared correlation id (detail later).

---

## Multiple nodes, multiple instances

This is a core goal, not an optional extra:

- Each **node** is an isolated Docker worker with its own id and bus channels.
- Each node can host one or more **strategy instances** (exact cardinality TBD).
- The same strategy **template** can run on many nodes with different configs.
- The UI lists **nodes** and **strategies**; actions are always scoped (node + strategy slot).

---

## What we are not committing to yet

Left open on purpose for detailed design:

- Exact tech choices beyond broad strokes (FastAPI, Postgres, Redis, Docker assumed but not frozen)
- Whether node orchestrator is a separate process or part of the API at first
- Real Nautilus vs mock worker for v1
- Full config/commit/registry model (devpi, component commits, etc.)
- Multi-host scheduling, Kubernetes, auth, rate limits
- Market data, brokers, backtests as first-class features

---

## Relationship to Nautilus Trader (reference)

When reading `nautilus_trader`, map concepts like this:

| Nautilus / Numatix | Conductor role |
|--------------------|----------------|
| Node Manager | Node orchestrator |
| Trading Node Controller | In-node controller |
| `TradingNode` in Docker | Worker container |
| Redis command/event streams | Message bus |
| Bootstrap JSON at container start | Worker bootstrap (TBD) |
| `ApplyNodeConfig`, pending config | Config apply + safe deferral (TBD) |

We learn patterns from there; Conductor stays smaller and owned by this repo.

---

## Success in one paragraph

Conductor succeeds when an operator can deploy several dockerized nodes from the UI, run different strategy instances on them, start/stop/change config remotely, and trust the dashboard because commands and events are recorded — without manually SSH-ing into containers.

Detailed design (schemas, handlers, Dockerfiles, stream names) is the next document, written after this model feels clear.

---

## Suggested reading order (reference repo)

1. `node-management/nodemanager/handlers/start_node.py` — spawning a worker  
2. `node-management/docker/trading-node/entrypoint.py` — what happens inside the container  
3. `tradingnodecontroller/trading_node_controller/dispatch.py` — bus → handlers  
4. `tradingnodecontroller/trading_node_controller/actor.py` — what the controller subscribes to  
5. `tradingnodecontroller/trading_node_controller/reconcile/pending.py` — deferring unsafe config changes  

---

*Last updated: high-level vision only. No implementation contract implied.*
