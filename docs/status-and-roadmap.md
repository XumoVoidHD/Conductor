# Status & roadmap

What works today, what is intentionally incomplete, and the planned build order.

Status legend: **Done** · **Partial** · **Planned** · **Gap** (known hole in an otherwise shipped path)

---

## Working end-to-end path

You can already:

1. Register / login (JWT) via API, Bruno, or the frontend
2. List strategies from Postgres (SYSTEM globals + owned + shared)
3. Register a strategy from `strategies/<file>.py` (ADMIN → SYSTEM; USER → owned)
4. Share a user-owned strategy with another username
5. Deploy a trading node (Bybit testnet credentials from server `.env`) via Redis → Conductor
6. Run / halt / status / stop / restart / delete that node
7. Respect **quota** — stopped nodes still count; delete frees the slot; missing containers soft-delete and free quota on command failure
8. Get **unique control ports** per node (multi-user safe)
9. Persist nodes in Postgres (`trading_nodes`); list merges DB + live Conductor probe
10. Pull an on-demand **snapshot** (`POST /dashboard/nodes/snapshot`)
11. List **trader summaries** (`GET /dashboard/traders`) with frontend filters (node / broker)
12. Run the Docker core stack: postgres, redis, backend, conductor, frontend

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
| Frontend dashboard | Partial | Toasts, polls, Traders table; not production UI |
| Conductor registry after restart | Gap | In-memory only; DB rows survive, live control may need redeploy |
| Bruno collection | Done | `backend/bruno/` |

### Observe

| Capability | Status | Notes |
|------------|--------|-------|
| TCP `snapshot` | Done | Full Nautilus state; offline DB stub |
| TCP `summary` | Done | Lightweight trader row |
| `GET /dashboard/traders` | Done | Batch summaries; client-side filters |
| Heartbeats | Planned | Auto-detect dead containers without a user command |
| Redis Streams observe | Planned | Continuous positions / heartbeats |
| WebSocket live feed | Planned | Frontend subscribe |

### Credentials & brokers

| Capability | Status | Notes |
|------------|--------|-------|
| Shared Bybit `.env` for dashboard | Done (temporary) | Not multi-tenant safe long-term |
| Per-user broker vault | Planned | Encrypted API keys / profiles |
| IBKR dockerized Gateway sidecar | Planned | Nautilus Gateway image pattern |
| Per-user IB login in vault | Planned | Paper / live |

### Product polish

| Capability | Status | Notes |
|------------|--------|-------|
| Zip strategy upload / versioning | Planned | |
| Attach / detach / apply_config at runtime | Planned | |
| Halt button in UI | Planned | API exists |
| Command/event audit log | Planned | |
| Production frontend | Planned | |
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

### Trading node

- [x] Bootstrap, brokers (Bybit + IBKR code), TCP including `snapshot` / `summary`
- [ ] Runtime attach/detach + apply_config
- [ ] Optional: Redis subscribe instead of TCP (redesign)

### Observe Phase 2

- [ ] Publish events + Streams + heartbeat
- [ ] API consumer → WebSocket
- [ ] Frontend live updates + trader drill-down

---

## Suggested build order (remaining)

1. Broker vault (encrypted) + migrate Bybit off shared `.env`
2. IBKR: vaulted login + dockerized Gateway + wire-up
3. Conductor registry (+ Gateway) reconcile after restart
4. Zip upload / attach-detach / apply_config (as needed)
5. Observe Phase 2: heartbeats + Streams → WebSocket
6. Production frontend

---

## Why some gaps exist on purpose

| Gap | Reason |
|-----|--------|
| No Streams yet | Control path had to be solid first; Phase-1 TCP summaries unblock the UI without a second bus |
| Shared Bybit keys | Fastest path to a working dashboard; vault is the correct multi-tenant design |
| In-memory Conductor registry | Simple and correct for a single orchestrator instance; persistence/reconcile is the next reliability step |
| Stop keeps quota | Prevents “stop to free slots then spam deploy”; delete is the intentional free |

For the product narrative behind these choices, see [Vision](vision.md) and [Design decisions](architecture/design-decisions.md).
