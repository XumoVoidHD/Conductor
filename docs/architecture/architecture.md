# Architecture

How the system is structured, what each piece does, and how it runs today.

**Product goals:** [Vision](../vision.md) · **Status:** [Status & roadmap](../status-and-roadmap.md) · **Run:** [Quickstart](../getting-started/quickstart.md)

**Foundation:** [Nautilus Trader](https://nautilus.trader/) runs strategies and brokers. Conductor is a control layer around Nautilus, not a replacement.

---

## Goals

- One **shared Conductor service** for all users
- Many **trading nodes** (one process/container per deploy)
- Deploy with a **complete command** (broker + strategy fully specified by the caller)
- Multi-tenancy via **`user_id` on every command**, not one Conductor per user
- Per-user **node quota**; stop keeps the slot, delete frees it
- Separate **control** from **observe** (TCP snapshot/summary today; Streams later)

---

## High-level picture

```text
┌─────────────────────────────────────────────────────────────┐
│              Frontend / Bruno (optional UI)                  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (+ JWT)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                            API                               │
│  auth · JWT · dashboard · vault · trading_nodes · Postgres   │
└───────────────┬─────────────────────────────┬───────────────┘
                │ control (Redis lists)       │ snapshot/summary (TCP)
                ▼                             │ Streams (planned)
┌───────────────────────────┐                 ▼
│     Conductor Node        │    ┌────────────────────────────┐
│  (ONE for all users)      │    │  Redis Streams observe     │
│  deploy · stop · restart  │    │  (planned)                 │
│  delete · list · run/halt │    └─────────────▲──────────────┘
└─────────────┬─────────────┘                  │
              │ spawn / tear down              │
              ▼                                │
┌───────────────────────────┐                  │
│      Trading Nodes        │── TCP observe ───┘
│  Nautilus + broker + strat│
└─────────────┬─────────────┘
              ▼
        Broker (Bybit testnet; IBKR later)
```

---

## Implementation status (summary)

| Piece | Status |
|-------|--------|
| Conductor + trading node | Done — subprocess or Docker |
| Redis control lists | Done |
| Unique control ports | Done |
| JWT + dashboard → Conductor | Done — `user_id` = username |
| Postgres vault + trading_nodes | Done |
| Quota stop vs delete | Done |
| Bybit testnet deploy | Done |
| Snapshot + traders summary | Done |
| Frontend | Basic |
| Conductor registry reconcile | Gap |
| Observe Streams / broker vault / IB Gateway | Planned |

Full detail: [Status & roadmap](../status-and-roadmap.md).

---

## Component notes

### Frontend (`frontend/`)

**Vite + React** dashboard — register/login, strategies, nodes, **Trades** panel, log streaming, **Live / Paper / Backtest** mode switcher (Paper/Backtest UI-only today). TanStack Query polling; JWT in `localStorage`; glassmorphism dark UI. See [Frontend](../developers/frontend.md) and [Dashboard UI](../guides/dashboard.md).

### Backend (`backend/`)

FastAPI. Auth (Argon2 + JWT). Dashboard stamps Conductor commands. Vault resolve. Soft-delete and quota. Direct TCP for snapshot/traders/trades via control clients. Docker log WebSocket for the UI.

### Conductor (`conductor_node/`)

`BRPOP` commands → handlers → `deploy.py` / `docker_runtime.py` / `control_client.py` → `LPUSH` events. In-memory `NodeRegistry` allocates ports and tracks running nodes.

### Trading node (`trading_node/`)

Reads bootstrap → builds Nautilus `TradingNode` → strategy STOPPED until `run`. TCP: `run`, `halt`, `status`, `reset`, `shutdown`, `kill`, `snapshot`, `summary`.

### Database

Alembic in `backend/alembic/`: users → strategies → source fields → trading_nodes. Compose service `postgres` under `conductor-core/`.

---

## Docker grouping

| Group | How | Labels |
|-------|-----|--------|
| **conductor-core** | Compose project | `conductor.stack=core`, `conductor.role=<service>` |
| **Trading nodes** | Spawned on deploy | `conductor.stack=trading`, `conductor.role=trading-node` |

```bash
docker compose -f conductor-core/docker-compose.yml up -d
docker compose -f conductor-core/docker-compose.yml run --rm backend alembic upgrade head
docker compose -f conductor-core/docker-compose.yml --profile build build trading-node
```

---

## Design rules (short)

1. Complete deploy commands — Conductor does not invent broker fields.
2. Opaque `broker.config` — only trading_node brokers interpret it.
3. One Conductor, many nodes — multi-tenancy via `user_id`.
4. Control ≠ observe.
5. Don’t expose trading-node sockets to the public internet.
6. Nautilus-native trading — no custom order engine.
7. Stop ≠ delete.

Deep dive: [Design decisions](design-decisions.md), [Data flows](data-flows.md), [Ports & networking](ports-and-networking.md).
