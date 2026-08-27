# System overview

A map of the moving parts and how they relate — for users and for developers joining the codebase.

---

## Components

| Component | Path | Role |
|-----------|------|------|
| **Frontend** | `frontend/` | Static HTML/JS dashboard (nginx :5500). Talks **only** to the API with JWT. |
| **Backend (API)** | `backend/` | FastAPI: auth, strategy vault, trading_nodes, dashboard actions, traders/snapshot. |
| **Postgres** | compose `postgres` | Users, strategies, strategy_access, trading_nodes. |
| **Redis** | compose `redis` | Control-plane **lists** only today (`conductor:commands`, `conductor:events`). |
| **Conductor** | `conductor_node/` | One shared orchestrator. Consumes commands, spawns/stops nodes, proxies strategy TCP. |
| **Trading node** | `trading_node/` | One Nautilus worker per deploy. Listens on a TCP control port. |
| **Bruno** | `backend/bruno/` | Preferred API test collection during development. |

Trading nodes are **not** defined in compose as long-lived services. Conductor spawns them on deploy (`conductor.stack=trading`, `conductor.role=trading-node`).

---

## Request paths

### Control (mutate lifecycle / strategy)

```text
UI / Bruno → API (JWT) → Redis LPUSH command
                       → Conductor BRPOP → Docker/subprocess / TCP
                       → Redis LPUSH event → API waits → HTTP response
```

API stamps `user_id` = authenticated **username**. Clients cannot spoof another user’s Conductor identity.

### Observe (read live state)

```text
UI / Bruno → API (JWT) → ownership check in Postgres
                       → TCP to node (summary / snapshot) on Docker network
                       → JSON response (or offline stub if unreachable)
```

Observe **does not** go through Conductor. That keeps the orchestrator off the hot path for positions and lets snapshot survive Conductor restarts for nodes that still exist.

---

## Split of truth

| Concern | Source of truth |
|---------|-----------------|
| Who owns a node, quota, soft-delete | Postgres `trading_nodes` |
| Live spawn, in-memory ports, TCP proxy targets | Conductor `NodeRegistry` |
| Strategy catalog / access | Postgres `strategies` + `strategy_access` |
| Live Nautilus cache (positions, orders) | Trading node process (queried via TCP) |

After a Conductor restart, DB rows remain; the in-memory registry is empty until nodes are redeployed or a future reconcile job rebuilds it. See [Status & roadmap](../status-and-roadmap.md).

---

## Status vocabulary

Conductor probes map roughly to:

| Status | Meaning |
|--------|---------|
| **Initializing** | Container/process up; control socket not ready yet |
| **Ready** | Control up; strategy stopped |
| **Running** | Strategy running |
| **Stopped** | Worker stopped; **slot still reserved** |
| **Deleted** | Soft-deleted in DB; slot freed |

Frontend may show optimistic Starting / Stopping / Restarting / Deleting while a request is in flight.

---

## Related

- [Control vs observe](control-vs-observe.md)
- [Lifecycle & quota](lifecycle-and-quota.md)
- [Architecture](../architecture/architecture.md)
