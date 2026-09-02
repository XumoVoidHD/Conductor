# Status & roadmap

What works today, what is intentionally incomplete, and the planned build order.

Status legend: **Done** · **Partial** · **Planned** · **Gap** (known hole in an otherwise shipped path)

---

## Working end-to-end path

You can already:

1. Register / login (JWT) via API, Bruno, or the **Vite + React** frontend
2. List strategies from Postgres (SYSTEM globals + owned + shared)
3. Register a strategy from `strategies/<file>.py` (ADMIN → SYSTEM; USER → owned)
4. Share a user-owned strategy with another username
5. Deploy a trading node (Bybit testnet credentials from server `.env`) via Redis → Conductor
6. Run / halt / status / stop / restart / delete that node
7. Respect **quota** — stopped nodes still count; delete frees the slot; missing containers soft-delete and free quota on command failure
8. Get **unique control ports** per node (multi-user safe)
9. Persist nodes in Postgres (`trading_nodes`); list merges DB + live Conductor probe
10. Pull an on-demand **snapshot** (`POST /dashboard/nodes/snapshot`)
11. List **trader summaries** (`GET /dashboard/traders`) — API + Bruno; UI uses **Trades** panel instead
12. List **aggregated trades** (`GET /dashboard/trades`) — positions, orders, fills in the dashboard
13. **Stream node logs** in the UI (WebSocket → Docker `logs -f`, Redis fallback)
14. Use the **Live / Paper / Backtest** mode switcher in the header (UI state only for Paper/Backtest today)
15. Run the Docker core stack: postgres, redis, backend, conductor, frontend

Compose: `conductor-core/docker-compose.yml`.

---

## Capability matrix

### Platform core

| Capability | Status | Notes |
|------------|--------|-------|
| Shared Conductor orchestrator | Done | One process for all users |
| Trading node (subprocess / Docker) | Done | Nautilus worker + TCP control |
| Redis control lists | Done | `conductor:commands` / `conductor:events` |
| Unique control ports | Done | From `CONDUCTOR_CONTROL_PORT_BASE` (default 9000) |
| JWT auth | Done | Register, login, `/me` |
| Durable `trading_nodes` | Done | Soft-delete; quota source of truth |
| Strategy vault | Done | Globals, owned, share, artifact URIs |
| Bybit testnet deploy | Done | Shared `.env` keys today |
| Frontend dashboard | Partial | Vite + React, glass UI, trades + logs; Paper/Backtest not wired to API |
| Trading mode switcher | Partial | Live / Paper / Backtest tabs; backend routing planned |
| Conductor registry after restart | Gap | In-memory only; DB rows survive, live control may need redeploy |
| Bruno collection | Done | `backend/bruno/` |

### Observe

| Capability | Status | Notes |
|------------|--------|-------|
| TCP `snapshot` | Done | Full Nautilus state; offline DB stub |
| TCP `summary` | Done | Lightweight trader row |
| `GET /dashboard/traders` | Done | Batch summaries; API/Bruno |
| `GET /dashboard/trades` | Done | Positions / orders / fills for dashboard |
| Node log WebSocket | Done | `WS /dashboard/nodes/{id}/logs/stream` |
| Heartbeats | Planned | Auto-detect dead containers without a user command |
| Redis Streams observe | Partial | Trading node can publish; full UI pipeline incomplete |
| WebSocket live trades feed | Planned | Push updates instead of poll-only |

### Credentials & brokers

| Capability | Status | Notes |
|------------|--------|-------|
| Shared Bybit `.env` for dashboard | Done (temporary) | Not multi-tenant safe long-term |
| Per-user broker vault | Planned | Encrypted API keys / profiles |
| IBKR dockerized Gateway sidecar | Planned | Nautilus Gateway image pattern |
| Per-user IB login in vault | Planned | Paper / live |
| Paper mode (Nautilus sandbox) | Planned | UI tab exists; deploy profile TBD |
| Backtest mode | Planned | UI tab exists; job API TBD |

### Product polish

| Capability | Status | Notes |
|------------|--------|-------|
| Zip strategy upload / versioning | Planned | |
| Attach / detach / apply_config at runtime | Planned | |
| Halt button in UI | Planned | API exists |
| Command/event audit log | Planned | |
| Mode-specific deploy (live vs paper vs backtest) | Planned | |
| Multi-host / K8s | Planned | |

---

## Detailed checklist (from engineering tasks)

### Strategy vault

- [x] DB model + access grants + SYSTEM seeds
- [x] Artifact URIs (`local://` / `s3://` / `gs://`) + materialize
- [x] Register-from-file + list + share + resolve on deploy
- [ ] Zip/package upload
- [ ] Version / label per revision

### Broker vault

- [ ] Encrypted credentials schema + REST (masked)
- [ ] Deploy injects vault profile (replace shared Bybit env)
- [ ] IBKR: vault login + Gateway container lifecycle + labels

### Conductor

- [x] Deploy / stop / restart / delete / list / run / halt / status / reset
- [x] Unique ports; drop registry when container missing
- [ ] Reconcile registry from Docker/DB after Conductor restart
- [ ] IB Gateway sidecar spawn/teardown
- [ ] Paper / backtest deploy profiles

### Trading node

- [x] Bootstrap, brokers (Bybit + IBKR code), TCP including `snapshot` / `summary`
- [x] Observe log publish to Redis (for log stream fallback)
- [ ] Runtime attach/detach + apply_config
- [ ] Nautilus sandbox profile for paper mode
- [ ] Backtest runner integration

### Frontend

- [x] Vite + React dashboard (auth, strategies, nodes, trades, logs)
- [x] Glassmorphism UI + black/green theme
- [x] Live / Paper / Backtest mode switcher (UI)
- [ ] Wire mode to deploy API
- [ ] Backtest results panel
- [ ] Halt in UI

### Observe Phase 2

- [ ] Publish events + Streams + heartbeat
- [ ] WebSocket live feed for trades (beyond log stream)
- [ ] Frontend live updates without full poll

---

## Suggested build order (remaining)

1. **Paper mode** — Nautilus sandbox on deploy when mode = paper
2. **Backtest** — job API + results UI
3. Broker vault (encrypted) + migrate Bybit off shared `.env`
4. IBKR: vaulted login + dockerized Gateway + wire-up
5. Conductor registry (+ Gateway) reconcile after restart
6. Zip upload / attach-detach / apply_config (as needed)
7. Observe Phase 2: heartbeats + Streams → WebSocket trades feed

---

## Why some gaps exist on purpose

| Gap | Reason |
|-----|--------|
| Paper/Backtest UI without API | Establish UX and `useTradingMode()` before branching deploy paths |
| No Streams for trades yet | Control path + TCP trades list had to work first; poll is enough for v1 |
| Shared Bybit keys | Fastest path to a working dashboard; vault is the correct multi-tenant design |
| In-memory Conductor registry | Simple and correct for a single orchestrator instance; persistence/reconcile is the next reliability step |
| Stop keeps quota | Prevents “stop to free slots then spam deploy”; delete is the intentional free |

For the product narrative behind these choices, see [Vision](vision.md) and [Design decisions](architecture/design-decisions.md).
