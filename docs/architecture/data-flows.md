# Data flows

End-to-end sequences for the main operations.

---

## Deploy

```text
POST /dashboard/deploy { strategy_id, config? }
  → API: auth, quota check, vault resolve, Bybit creds from env
  → Redis: deploy (user_id=username, max_trading_nodes, broker, strategy)
  → Conductor: allocate unique control port
  → bootstrap.json + spawn (Docker or subprocess)
  → Redis: ok event (node_id, control_port, …)
  → API: INSERT trading_nodes
  → Node: Nautilus up, strategy STOPPED (Initializing → Ready)
```

---

## Run / halt / stop / restart / delete

```text
POST /dashboard/nodes/{action} { node_id }
  → API: ownership check
  → Redis command → Conductor
  → Docker lifecycle and/or TCP to node
  → API updates trading_nodes (soft-delete on delete)
```

On “node/container not found”: soft-delete + `410 node_gone` + frontend removes row and frees displayed quota.

---

## List nodes

```text
GET /dashboard/nodes
  → API: SELECT active trading_nodes for user
  → Best-effort Conductor list (merge live status)
  → Return nodes + node_count + max_trading_nodes
```

---

## Traders (batch summary)

```text
GET /dashboard/traders
  → API: for each active node (max ~3 concurrent TCP):
        summary command (fallback: snapshot → trim)
        or offline stub if ConnectionError
  → Return full list; UI filters client-side
```

---

## Snapshot (single node)

```text
POST /dashboard/nodes/snapshot { node_id | container_name | node }
  → API: ownership
  → TCP snapshot
  → If down: offline snapshot from DB row (reachable=false)
```

---

## Direct CLI (bypass API)

```bash
python scripts/send_conductor_command.py deploy --user-id alice
python scripts/send_conductor_command.py run --user-id alice --node-id tn-...
python scripts/send_conductor_command.py events
```

Useful for Conductor debugging without JWT. Still respects Conductor’s `user_id` scoping.
