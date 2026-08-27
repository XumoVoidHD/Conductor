# Traders & snapshot API

Observe path: API → trading node TCP (not via Conductor). JWT required.

---

## List traders

`GET /api/v1/dashboard/traders`

Returns one summary per active `trading_nodes` row:

- `node_id`, `trader_id`, `strategy_*`, `broker_adapter`
- `reachable`, `strategy_state`, `positions_open`, `orders_open`
- Offline stub when TCP fails (`strategy_state: offline`, `offline_reason`)

Implementation: bounded thread pool; TCP `summary` with fallback to full `snapshot` + trim for older node images.

Filter on the client — the API always returns the full set for the user.

---

## Node snapshot

`POST /api/v1/dashboard/nodes/snapshot`

```json
{ "node_id": "tn-abc12345" }
```

Also accepts `container_name` or `node` (either id or name).

**When reachable:** full Nautilus snapshot (positions, orders, fills, balances, health, strategy, indicators, …).

**When not:** HTTP 200 with `reachable: false` and a DB-backed offline snapshot (strategy identity + last status).

---

## TCP commands (node side)

| Command | Reply prefix |
|---------|----------------|
| `summary` | `OK SUMMARY {json}` |
| `snapshot` | `OK SNAPSHOT {json}` |

Protocol details: [TCP protocol](../developers/tcp-protocol.md).
