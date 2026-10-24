# New Render service — SaKgaZé API v2

Do **not** overwrite the existing `sakgaze-api` service. Create a second service
and cut the frontend over with `VITE_API_BASE_URL` (see
`backend-migration-next.md`).

## 1. Service settings

| field | value |
|---|---|
| Type | Web Service (Python) |
| Root directory | `backend-next` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Python version | 3.11 or 3.12 (`PYTHON_VERSION=3.12.7`) |
| Auto-deploy | off until the first manual deploy succeeds |

`main.py` at the repository root of `backend-next` is a shim, so
`uvicorn main:app` also works if the start command is already configured that way.

## 2. Environment variables

| key | required | notes |
|---|---|---|
| `DATABASE_URL` | yes | Supabase **session pooler** (5432) recommended for Render: it supports prepared statements and DDL. The transaction pooler (6543) works for reads but silently drops libpq `options` — the app sets its limits with explicit `SET`, so either works. |
| `CORS_ORIGINS` | yes | `https://sakgaze.com,https://www.sakgaze.com` |
| `API_ENV` | yes | `production` |
| `LOG_FORMAT` | no | `json` |
| `DB_STATEMENT_TIMEOUT_MS` | no | default `8000` |
| `DB_POOL_SIZE` / `DB_POOL_MAX_OVERFLOW` | no | default `5` / `5` |
| `MAP_SIMPLIFY_TOLERANCE` | no | default `0.0005` (~55 m at 15 °N) |
| `SAKGAZE_AUTO_MIGRATE` | no | **`0`** — boot DDL is forbidden |

Never place any of these in a `VITE_` variable: those are shipped to the browser.

## 3. First deploy sequence

```bash
# 1. schema (run once, from a machine with DATABASE_URL set)
cd workspace/backend-next
alembic upgrade head

# 2. deploy the service, then check
curl -s https://<service>.onrender.com/health
curl -s https://<service>.onrender.com/api/v2/status | jq '.database, .sources'
curl -s "https://<service>.onrender.com/api/v2/sargassum?days=7&limit=1" | jq '.meta'
```

Expected: `/health` → `200` in a few ms; `/api/v2/status` → `database: "ok"` and
three sources with a `freshness` value; a layer → a FeatureCollection with `meta`.

## 4. Cold starts

Render free instances sleep. The API therefore:

* answers `/health` without touching the database (instant), so the platform probe
  does not queue behind a sleeping pooler;
* returns `503 DATABASE_UNAVAILABLE` (structured) rather than hanging, because
  every connection sets `statement_timeout`;
* sets `Cache-Control: max-age=60` on layers, so a warm CDN/browser hit is cheap.

The frontend retries a cold start at 2 s / 5 s / 10 s and then stops with an
explicit **Réessayer** button (`src/hooks/useLayers.ts`).

## 5. Logs

`LOG_FORMAT=json` emits one line per request and per layer fetch:

```json
{"ts":"2026-10-24T14:02:11Z","level":"INFO","logger":"sakgaze.api",
 "message":"request","extra_fields":{"request_id":"ab12","path":"/api/v2/sargassum","status":200,"duration_ms":41.2}}
```

No DSN, credential or SQL text is ever logged (`app/core/logging.py` redacts by
key name).

## 6. Rollback

Delete/stop the new service, point `VITE_API_BASE_URL` back at the legacy host,
rebuild the frontend. The legacy service and database are untouched.
