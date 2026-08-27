# TCP protocol (trading node)

Each trading node exposes a **control TCP** listener (host port unique per node, typically from base **9000**). The backend talks to it for observe and some control probes; Conductor uses it for run/halt/status after the container exists.

---

## Framing

- Newline-delimited text commands  
- Replies start with `OK` or `ERR`  
- Payload after the status token is often JSON  

Examples:

```text
summary
OK SUMMARY {"trader_id":"…","strategy_state":"running",…}

snapshot
OK SNAPSHOT {"positions":[…],…}

status
OK STATUS {"…":…}
```

Exact command set lives in `trading_node/` (runtime / control server). Prefer reading the source when extending.

---

## Commands used by the dashboard today

| Command | Used for |
|---------|----------|
| `summary` | Traders table (fast path) |
| `snapshot` | Full node detail; fallback if `summary` missing |
| `status` / run / halt | Lifecycle via Conductor + API actions |

---

## Why TCP (not HTTP on the node)?

- Tiny attack/surface and dependency footprint inside the worker image  
- Fits “one control socket” mental model  
- Easy for Conductor and backend to share the same client helpers  

Trade-off: clients must handle timeouts, partial reads, and version skew (summary vs snapshot fallback).

---

## Networking

- Containers join `conductor-net`  
- Host port mapped uniquely so API on the host (or another container) can reach the node  
- See [Ports & networking](../architecture/ports-and-networking.md)

---

## Compatibility

Older images without `summary` still work: backend falls back to `snapshot` and trims fields for the Traders list. Rebuild/redeploy nodes when you add new observe fields.
