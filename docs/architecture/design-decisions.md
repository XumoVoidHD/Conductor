# Design decisions

Why the system looks the way it does — useful when you’re tempted to “simplify” something that was deliberate.

---

## 1. One Conductor, many trading nodes

**Decision:** Shared orchestrator; scale out workers.

**Why:** Per-user orchestrators multiply Redis consumers, deploy logic, and ops surface. Tenancy is a `user_id` field and DB ownership, not a process per customer.

---

## 2. Complete deploy commands

**Decision:** API (or CLI) sends full broker + strategy payloads. Conductor does not load vault rows or `.env` Bybit keys itself.

**Why:** Keeps Conductor free of Postgres and auth policy. The same deploy envelope works from API, CLI, or future services.

---

## 3. Opaque `broker.config`

**Decision:** Conductor allowlists adapter names; config is a dict passed to the trading node.

**Why:** Exchange-specific validation belongs next to Nautilus adapters in `trading_node/brokers/`.

---

## 4. Control lists ≠ observe Streams

**Decision:** Redis lists for rare control; TCP (then Streams) for observe.

**Why:** See [Control vs observe](../concepts/control-vs-observe.md). Orchestrators make bad fan-in proxies for positions.

---

## 5. Stop keeps quota; delete frees it

**Decision:** Soft reservation until delete.

**Why:** Prevents slot thrashing and makes “parked” workers explicit. See [Lifecycle & quota](../concepts/lifecycle-and-quota.md).

---

## 6. Durable nodes in API DB; live registry in Conductor

**Decision:** Postgres for list/quota/ownership; in-memory registry for spawn/TCP targets.

**Why:** Fast iteration on orchestration without coupling Conductor to migrations. Cost: Conductor restart loses live registry (**known gap** — reconcile is planned).

---

## 7. Username as Conductor `user_id`

**Decision:** API stamps Conductor messages with username; DB uses UUID FKs.

**Why:** Historical control-plane string key; human-readable in Redis events. Don’t mix UUID into Conductor commands without a coordinated migration.

---

## 8. Frontend filters client-side on traders batch

**Decision:** Fetch all summaries; filter node/broker in the browser.

**Why:** Quotas are small; TCP is the expensive part. Re-fetching on every filter change wastes work. See [Traders](../guides/traders.md).

---

## 9. IBKR via dockerized Gateway (planned)

**Decision:** Companion container per Nautilus’s Gateway pattern — not shared host TWS.

**Why:** Automation and multi-tenant isolation. Host TWS doesn’t scale to N users on one machine cleanly.

---

## 10. Nautilus boundary

**Decision:** No custom order engine; strategies are normal Nautilus classes.

**Why:** Product promise is “run my Nautilus strategies,” not “learn Conductor’s DSL.” See [Vision](../vision.md).
