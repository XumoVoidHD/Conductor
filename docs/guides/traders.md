# Traders panel

Phase-1 observe API: one row per trading node’s Nautilus trader.

> **Dashboard UI:** The current React dashboard uses the **[Trades](dashboard.md)** panel (`GET /dashboard/trades`) instead of this Traders table. The traders API remains available for Bruno and integrations.

---

## What you see

| Column | Meaning |
|--------|---------|
| Trader | Nautilus `trader_id` (often `CONDUCTOR-TN-…`) |
| Node | `node_id` |
| Strategy | Name/slug from DB |
| State | running / stopped / offline / … |
| Broker | e.g. `bybit` |
| Pos / Orders | Open counts from summary |
| Reachable | TCP succeeded |

---

## How data is loaded

```text
GET /api/v1/dashboard/traders
  → for each active trading_nodes row:
        TCP summary (or snapshot fallback)
        else offline stub
```

Bounded concurrency (about 3 TCP calls at a time). Frontend keeps the full list and filters locally.

**Why not filter on the server?** Quotas are small; changing a dropdown should not re-probe every container. See [Design decisions](../architecture/design-decisions.md).

---

## Filters

**Node** and **Broker** dropdowns apply to **Nodes + Traders** tables together.

---

## Phase 2 (planned)

Heartbeats, Streams, WebSocket live updates, click-through full snapshot panel. Tracked in [Status & roadmap](../status-and-roadmap.md).
