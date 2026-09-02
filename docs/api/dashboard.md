# Dashboard & nodes API

All routes require JWT. Prefix: `/api/v1/dashboard`

The API stamps Conductor `user_id` from the authenticated username.

---

## Status

`GET /dashboard/status` — Redis ping + username.

---

## Strategies

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/strategies` | Accessible vault entries |
| POST | `/strategies/register` | Register from file or source_url/path |
| POST | `/strategies/{slug}/access` | Share with another username |

---

## Deploy

`POST /dashboard/deploy`

```json
{ "strategy_id": "running_ping", "config": {} }
```

Checks quota, resolves vault, injects Bybit env credentials, enqueues Conductor deploy, persists `trading_nodes`.

---

## Nodes

`GET /dashboard/nodes` — DB rows + live merge; includes `node_count`, `max_trading_nodes`.

| Method | Path | Effect |
|--------|------|--------|
| POST | `/nodes/run` | Start strategy (starts container if needed) |
| POST | `/nodes/halt` | Halt strategy only |
| POST | `/nodes/status` | Probe status |
| POST | `/nodes/stop` | Stop worker; **keep slot** |
| POST | `/nodes/restart` | Restart worker |
| POST | `/nodes/delete` | Destroy + soft-delete; **free slot** |

Body for actions:

```json
{ "node_id": "tn-abc12345" }
```

### Gone node

If Conductor/Docker no longer has the node, response is **410** with detail code `node_gone`; row is soft-deleted and quota decrements.

---

## Trades

`GET /dashboard/trades` — aggregated **positions**, **orders**, and **fills** across the user’s nodes (live TCP queries; empty stubs when offline).

---

## Log stream (WebSocket)

`GET /api/v1/dashboard/nodes/{node_id}/logs/stream?token=<JWT>`

Upgrades to WebSocket. Streams Docker container logs when the node runs in Docker; may fall back to Redis observe stream. Used by the dashboard **Logs** modal.

---

## See also

- [Traders & snapshot](traders-and-snapshot.md)
- [Lifecycle & quota](../concepts/lifecycle-and-quota.md)
- [Bruno](../guides/bruno.md)
