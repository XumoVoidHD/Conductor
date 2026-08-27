# Multi-tenancy

How Conductor isolates users without running one orchestrator per account.

---

## Model

| Question | Answer |
|----------|--------|
| One Conductor per user? | **No** — one shared Conductor for the platform |
| Isolation key | `user_id` on every Conductor command = authenticated **username** |
| Who stamps `user_id`? | API only — never trust the client body |
| What scales horizontally? | Trading nodes (and later observe traffic), not Conductor count |

---

## Enforcement points

1. **JWT** — every dashboard route requires a valid user.
2. **Postgres** — `trading_nodes.user_id`, strategy ownership / `strategy_access`.
3. **Conductor** — list/stop/run/… reject nodes that don’t belong to `cmd.user_id`.
4. **Quota** — per-user `trading_nodes` limit on deploy.
5. **Ports** — unique control ports across **all** users so Docker host binds never collide.

---

## Why username as Conductor `user_id`?

The control plane historically keyed messages by a string user id. The API maps JWT subject (UUID) → `username` for Conductor. Ownership and quota still use UUID FKs in Postgres. Keep both consistent when adding features: **DB for durable ownership, username for Redis/Conductor message scope**.

---

## What is not isolated yet

- Shared Bybit `.env` credentials (all users share testnet keys until broker vault lands)
- Conductor process crash domains (one bad handler can affect the shared orchestrator — keep handlers defensive)

See [Broker credentials](broker-credentials.md) and [Design decisions](../architecture/design-decisions.md).
