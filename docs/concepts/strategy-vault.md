# Strategy vault

Where strategies live, who can see them, and how deploy resolves them.

---

## What is stored

Each vault row is metadata for a runnable Nautilus strategy:

- Slug / name / description
- `module`, `class_name`, `config_class`, `default_config`
- Optional `source_url` + `source_path` → artifact URI (`local://`, `s3://`, `gs://`)
- Ownership: SYSTEM (global) vs user-owned

Access:

| Kind | Visibility |
|------|------------|
| SYSTEM / global | Everyone |
| Owned | Owner |
| Shared | Rows in `strategy_access` |

Seeds include `running_ping`, `hello_bars`, `ema_cross`.

---

## Why a vault (not hardcoded catalog)

Early dashboards often hardcode strategy IDs in the API. A vault lets you:

- Register new strategies without shipping a backend release for every file
- Share strategies between users
- Point at remote artifacts later (S3/GCS) without changing Conductor’s deploy envelope

Conductor still receives a **complete** strategy block on deploy. The vault is resolved **in the API**, not inside Conductor. That keeps the orchestrator free of DB access and auth policy.

---

## Register & deploy

1. `POST /dashboard/strategies/register` — filename under `strategies/` or explicit source fields. ADMIN → SYSTEM; USER → owned.
2. `GET /dashboard/strategies` — accessible set for the current user.
3. `POST /dashboard/deploy { strategy_id }` — API loads vault row, merges config overrides, injects broker config, enqueues Conductor `deploy`.

Artifact materialization for non-local sources happens on the Conductor/node side into `data/nodes/{node_id}/artifacts` when needed (`shared/artifacts/`).

---

## Not in scope (yet)

- Zip/folder upload UI
- Immutable version tags per revision
- Marketplace / discovery beyond share grants

See [Vision](../vision.md) and [Status & roadmap](../status-and-roadmap.md).
