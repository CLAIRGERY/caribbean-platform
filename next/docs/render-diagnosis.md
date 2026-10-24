# Render — Backend Diagnosis (SaKgaZé API)

## Actual deployment configuration (from repo `render.yaml`)

```yaml
services:
  - type: web
    name: sakgaze-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.src.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        value: "postgresql+psycopg2://postgres.<project-ref>:<redacted>@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"
      - key: CORS_ORIGINS
        value: "https://sakgaze.com,http://localhost:3000,http://127.0.0.1:3000"
```

Verdict on the command shape: **correct** — binds `0.0.0.0:$PORT`, imports
`backend.src.main:app`, which matches `backend/src/main.py` in this repo.

## Defects found in code (all fixed in this milestone)

### 1. Blocking startup (`lifespan`)
`backend/src/main.py` declared `lifespan` → `init_db()` →
`CREATE EXTENSION postgis` + `Base.metadata.create_all()` + migrations + `CREATE INDEX`
on a Supabase connection pool with **no connect/statement timeout**.
When the Supabase pooler is asleep / unreachable, `uvicorn` never finishes booting —
Render probes `/health` → never answers → dyno looks permanently broken.

**Fix applied** (`backend/src/database.py`):
- engine got bounded timeouts:
  `connect_args={connect_timeout: 8, statement_timeout: 8000, idle_in_transaction_session_timeout: 30000}`
- `init_db()` became **fail-soft**: logs `init_db skipped: database not reachable` and
  lets the process boot; doesn't crash startup.

### 2. `/health` called the DB synchronously
Original `/health` ran `SELECT 1` via a Depends-cached session → this alone could
hang a free-tier probe for 60s.

**Fix applied** (`backend/src/main.py`):
- `GET /health` — instant process-health response, **no DB dependency**.
- new `GET /health/db` — bounded DB check for diagnostics.

### 3. Requirements pin mismatch
`annotated-types==0.8.0`, `anyio==4.14.2`, `click==8.4.2` etc. do not resolve on
current PyPI index → **pip install fails entirely** at build step. This alone makes
the deployed dyno permanently crash-loop.

**Fix applied** (`requirements.txt`): all exact `==` pins converted to `>=`
lower bounds that resolve cleanly (the backend stays functional; Render resolves
fresh versions at deploy time).

## Remaining external action (dashboard only)

Nothing in code still blocks boot. If the published Render service is already built
with the broken requirements file, the service owner must:

1. Trigger **Manual Deploy → Clear build cache & deploy** in the Render dashboard so the
   fixed `requirements.txt` is re-resolved.
2. Confirm in the Render **Logs** tab that the boot line ends with
   `Uvicorn running on http://0.0.0.0:<port>`.
3. Set the Health Check Path in the Render service settings to **`/health`**.

## Verification checklist (post-redeploy)

```bash
curl -sS https://sakgaze-api.onrender.com/health         # expect {"status":"ok","service":"sakgaze-api"}
curl -sS https://sakgaze-api.onrender.com/health/db      # expect {"database":"ok"} (or "error" if Supabase asleep)
curl -sS https://sakgaze-api.onrender.com/api/v1/ingestion/status
```

Local equivalent:

```bash
python3 -m venv /tmp/sakvenv
source /tmp/sakvenv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg2://user:pass@host:5432/db'  # REAL value from your Supabase project
uvicorn backend.src.main:app --host 0.0.0.0 --port $PORT &
curl -sS http://127.0.0.1:8000/health
```

`/health` returns in <2s locally, even when `DATABASE_URL` is malformed — verified in
this milestone's local boot test.
