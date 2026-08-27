# Node lifecycle & quota

How deploy / run / stop / restart / delete relate — and why quota works the way it does.

---

## Actions

| Action | API | What happens | Quota slot |
|--------|-----|--------------|------------|
| **Deploy** | `POST /dashboard/deploy` | Bootstrap + spawn node; strategy starts **STOPPED** | Consumes a slot (blocked if at limit) |
| **Run** | `POST /dashboard/nodes/run` | Start container if needed, then TCP `run` | Unchanged |
| **Halt** | `POST /dashboard/nodes/halt` | Strategy stop only; worker stays up | Unchanged |
| **Status** | `POST /dashboard/nodes/status` | Probe Ready / Running / … | Unchanged |
| **Stop** | `POST /dashboard/nodes/stop` | Stop process/container; keep registry/DB row | **Kept** |
| **Restart** | `POST /dashboard/nodes/restart` | Restart worker; strategy Ready (stopped) | **Kept** |
| **Delete** | `POST /dashboard/nodes/delete` | Destroy worker + soft-delete DB + drop registry | **Freed** |

Frontend today exposes Deploy / Run / Stop / Restart / Delete. Halt exists on the API.

---

## Quota model

- Limit: `users.trading_nodes` (default **2**).
- Count: rows in `trading_nodes` with `deleted_at IS NULL`.
- **Stopped nodes still count.** Only soft-delete frees a slot.
- Enforced in the API before deploy and again in Conductor via `max_trading_nodes` in the deploy payload.

### Why stop doesn’t free a slot

If stop freed quota, a user could stop all workers, deploy new ones, and leave orphaned stopped containers or confuse “parked” vs “gone”. Delete is the explicit “I release this slot” action.

---

## Gone / crashed containers

When a command fails because Conductor doesn’t know the node or Docker has no container:

1. Conductor drops the registry entry (when applicable).
2. API soft-deletes the DB row → **quota decrements**.
3. Frontend shows an error toast and removes the row (`410` / `node_gone`).

Heartbeats (auto-detect without a command) are Phase 2 — see [Status & roadmap](../status-and-roadmap.md).

---

## Happy path

```text
Deploy → Initializing → Ready
Run    → Running
Halt   → Ready (worker still up)
Stop   → Stopped (slot kept)
Delete → gone (slot freed)
```

Or: Stop → Restart → Ready → Run → Running.
