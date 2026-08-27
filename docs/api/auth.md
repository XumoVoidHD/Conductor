# Auth API

Prefix: `/api/v1`

---

## Register

`POST /api/v1/auth/register`

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "Password@123"
}
```

Creates a user (Argon2 hash). Default role USER; `trading_nodes` quota defaults in DB (typically 2).

---

## Login

`POST /api/v1/auth/login`

```json
{
  "username": "alice",
  "password": "Password@123"
}
```

Returns:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": { "id": "...", "username": "alice", "trading_nodes": 2, "...": "..." }
}
```

JWT `sub` = user UUID. Dashboard Conductor commands use **username** as `user_id`.

---

## Me

`GET /api/v1/auth/me`  
Header: `Authorization: Bearer <token>`

---

## Health

`GET /api/v1/health` — no auth.
