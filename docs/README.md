# Conductor

**Conductor** is a control platform for running [Nautilus Trader](https://nautilus.trader/) strategies on long-lived workers — without replacing Nautilus, inventing a new order engine, or forcing users onto a proprietary strategy framework.

This documentation is for:

| Audience | What you’ll find here |
|----------|------------------------|
| **Operators / users** | How to run the stack, deploy a strategy, manage nodes, read the Traders panel |
| **API consumers** | Auth, dashboard endpoints, snapshot / traders |
| **Developers** | Why the system is shaped this way, how control and observe are split, where to change code safely |

---

## What problem it solves

Running Nautilus live usually means: manage processes or containers, wire broker credentials, keep track of which strategy is on which machine, and build your own start/stop UI. Conductor turns that into a **multi-tenant control plane**:

1. Users authenticate to an API.
2. Strategies live in a **vault** (Postgres).
3. Deploying a strategy spawns a **trading node** (Docker or subprocess) via a shared **Conductor** orchestrator.
4. Run / halt / stop / restart / delete are first-class actions with a **per-user quota**.
5. Observe is separate from control: today via on-demand TCP **snapshot** / **summary**; later via Redis Streams.

Nautilus still owns trading. Conductor owns orchestration, tenancy, and the API/UI surface.

---

## Mental model (30 seconds)

```text
Browser / Bruno
      │  JWT HTTP
      ▼
   FastAPI  ──► Postgres (users, strategies, trading_nodes)
      │
      │  Redis lists (commands / events)
      ▼
 Conductor (one shared service)
      │  spawn / TCP proxy
      ▼
 Trading nodes (Nautilus)  ◄── API can also TCP directly for snapshot/summary
      │
      ▼
   Broker (Bybit today; IBKR planned with dockerized Gateway)
```

**Two layers of control**

| Layer | Question |
|-------|----------|
| **Node orchestration** | Does this worker exist? Stop vs delete? Which port? |
| **In-node control** | Inside that worker, is the strategy running or halted? |

**Stop ≠ delete** — Stopping parks the worker but **keeps the quota slot**. Delete destroys it and frees the slot.

---

## Where to go next

| Goal | Page |
|------|------|
| Understand the product | [Project vision](vision.md) |
| See what’s done vs planned | [Status & roadmap](status-and-roadmap.md) |
| Run it locally | [Quickstart](getting-started/quickstart.md) |
| Deep system design | [Architecture](architecture/architecture.md) |
| Why control ≠ observe | [Control vs observe](concepts/control-vs-observe.md) |
| Call the API | [Auth](api/auth.md), [Dashboard](api/dashboard.md) |

Canonical compose file: `conductor-core/docker-compose.yml`.

Root-repo files `ARCHITECTURE.md`, `PROJECT_VISION.md`, and `TASKS.md` remain for convenience; **this `docs/` tree is the GitBook source of truth**.
