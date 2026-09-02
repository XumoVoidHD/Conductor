# Extending Conductor

Patterns for adding features without fighting the architecture.

---

## Where to put what

| Change | Primary place |
|--------|----------------|
| HTTP route | `backend/app/api/v1/` |
| Business rules / DB / Conductor enqueue | `backend/app/services/` |
| Orchestration (Docker, Redis jobs) | `conductor_node/` |
| Node runtime / TCP surface | `trading_node/` |
| UI | `frontend/` |
| Docs | `docs/` |

Keep **control** (lifecycle) on Conductor and **observe** (read state) on direct TCP unless you have a strong reason otherwise — see [Control vs observe](../concepts/control-vs-observe.md).

---

## Adding an API endpoint

1. Schema in `backend/app/schemas/` if needed  
2. Service function (quota, ownership, Conductor client)  
3. Router under `/api/v1/...` with JWT dependency  
4. Bruno request under `backend/bruno/`  
5. Docs under `docs/api/` or `docs/guides/`

---

## Adding a dashboard panel

1. Prefer existing poll + client-side filter for small lists  
2. Call backend APIs only — never talk to Redis/Docker from the browser  
3. Match toast / status conventions in `frontend/src/pages/DashboardPage.tsx`

---

## Adding a Conductor command

1. Define Redis job shape consumed by `conductor_node`  
2. Implement handler (idempotent where possible)  
3. Persist outcomes the API needs (`trading_nodes`, status fields)  
4. Document failure modes (gone node, port conflict, timeout)

---

## Adding observe data

1. Prefer a **small TCP command** (`summary`) over always shipping full snapshots  
2. Version replies (`OK SUMMARY …`) so old nodes can fall back  
3. Backend should tolerate offline nodes with stubs, not 500s

---

## Secrets

Never log credentials. Broker vault (planned) must encrypt at rest; today Bybit uses env injection — do not copy that pattern into the browser or git.
