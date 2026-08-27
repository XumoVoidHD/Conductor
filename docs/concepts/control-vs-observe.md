# Control vs observe

Why Conductor is not on the path for live positions — and how that shapes the code.

---

## Two planes

| Plane | Purpose | Path today |
|-------|---------|------------|
| **Control** | Deploy, stop, restart, delete, run, halt, status | API → Redis lists → Conductor → (Docker) → TCP |
| **Observe (point-in-time)** | Snapshot / trader summary | API → TCP → trading node (bypass Conductor) |
| **Observe (continuous)** | Heartbeats, streaming positions | Planned: node → Redis Streams → API → WebSocket |

---

## Why not “everything through Conductor”?

Conductor’s job is **orchestration**: create/destroy workers, allocate ports, proxy infrequent strategy commands. If every UI refresh for positions also went through Conductor:

1. **Wrong responsibility** — the orchestrator becomes a fan-in bottleneck for market state.
2. **Restart fragility** — restarting Conductor would interrupt observe even when workers are healthy.
3. **Coupling** — scaling read traffic would force you to scale the orchestrator.

So: **control lists for rare, authoritative actions; observe out-of-band.**

---

## Phase 1 observe (shipped)

- TCP command `snapshot` — large JSON: positions, orders, fills, health, strategy, …
- TCP command `summary` — small JSON for list rows
- `GET /dashboard/traders` — batch summaries with bounded concurrency
- Offline stub when TCP fails — still returns strategy identity from Postgres

Frontend filters (node / broker) are **client-side** on that batch — quotas are small, so re-fetching on every filter change would only burn TCP.

---

## Phase 2 observe (planned)

- Trading nodes publish heartbeats and position deltas to Redis Streams
- API consumes Streams, optionally maintains snapshot keys
- Frontend WebSocket (or SSE) for live Traders
- Heartbeat miss → mark dead / soft-delete without waiting for a user click

Conductor must **not** fan-in that traffic.

---

## Practical rule for contributors

| Change | Where it belongs |
|--------|------------------|
| New lifecycle action (e.g. pause container) | Conductor + Redis command |
| New “what is Nautilus doing?” field | Trading node TCP summary/snapshot (and later Streams) |
| New dashboard list column for live PnL | Observe path, not Conductor `list` |

See also [Traders panel](../guides/traders.md) and [TCP protocol](../developers/tcp-protocol.md).
