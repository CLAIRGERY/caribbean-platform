# Production readiness, deploy & rollback

Everything below is **prepared and locally verified**; nothing has been deployed to a
production account. Commands are copy-paste ready.

---

## 1. Frontend — Hostinger (static)

### Artefact
`~/Projects/SaKgaZe-Next/builds/frontend-next-dist/` (2.31 MB, built 2026-10-24 from
`feature/sakgaze-next` with the production API base URL baked in).

```
index.html
favicon-96.png
logo-sakgaze.png
assets/index-*.js  66.6 kB (20.7 gz)      assets/maplibre-*.js   787 kB (210 gz)
assets/i18n-*.js   55.5 kB (18.3 gz)      assets/three-lazy-*.js 737 kB (187 gz) ← lazy only
assets/query-*.js  25.1 kB  (8.2 gz)      assets/motion-*.js     127 kB  (41.7 gz)
assets/reactvendor-*.js 132.8 kB (43.1 gz) assets/zustand-*.js  2.6 kB
assets/rolldown-runtime-*.js 0.7 kB       assets/index-*.css      22.8 kB (6 gz)
assets/logo-sakgaze-512-*.png 314 kB
```

### Deploy
1. hPanel → File Manager → `public_html/`.
2. **Back up** the current contents first (see rollback).
3. Upload the **contents** of the folder above (not the folder itself).
4. Keep the existing `.htaccess` SPA rewrite; verify it still rewrites unknown paths to
   `index.html` (React Router is not used, but deep links must not 404).
5. Hard-refresh: the asset names are content-hashed, so old bundles are simply unused.
6. Verify: `https://sakgaze.com/` loads, map paints, `FR | EN` switches, DevTools Network
   shows `index-*.js` + `maplibre-*.js` from the new build and no 404.

### Environment baked at build time
`VITE_API_BASE_URL=https://sakgaze-api.onrender.com/api/v1` (current `.env`).
Changing the backend later = change this value, `npm run build`, re-upload. No code edit.

---

## 2. Backend — Render v2

### Service
| field | value |
|---|---|
| Root directory | `backend-next` |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` (DB-free, ~13 ms measured) |
| Python | 3.12 (`PYTHON_VERSION=3.12.7`) |

### Env
`DATABASE_URL`, `CORS_ORIGINS=https://sakgaze.com,https://www.sakgaze.com`, `API_ENV=production`,
`LOG_FORMAT=json`, `SAKGAZE_AUTO_MIGRATE=0` (boot DDL stays off).

### Cutover (non-destructive)
Create the **new** service; leave `sakgaze-api` untouched. When it is healthy, switch the
frontend variable to `https://<new-service>.onrender.com/api/v1` and redeploy the static
build. Verified locally that the API answers:
`/health` 200 · `/api/v2/status` 200 `degraded` with DB unreachable · `/api/v2/sargassum`
503 `DATABASE_UNAVAILABLE` (4 ms) · `/docs` 200 → cold start and outage are explicit, never a
hung request.

---

## 3. Database — Supabase / PostGIS

```bash
cd workspace/backend-next
export DATABASE_URL='postgresql+psycopg2://…'     # session pooler (5432) for migrations
alembic upgrade head        # 16 statements: extension, tables (IF absent), IF NOT EXISTS indexes
alembic current             # 0001_initial (head)
```

The revision is additive: on the existing production schema it only adds missing
`external_id` / `source` columns and indexes. `downgrade()` refuses to run — dropping
scientific tables is never automated.

---

## 4. Rollback

### Frontend (seconds)
Keep the previous `public_html/` archive (e.g. `public_html_backup_<date>.zip`). Restore it and
purge the Hostinger cache. The old bundle references only hashed assets that were not deleted.

### Backend
Point `VITE_API_BASE_URL` back to `https://sakgaze-api.onrender.com/api/v1`, rebuild, re-upload.
The legacy service and its database were never modified. New Render service: suspend it.

### Database
Point `DATABASE_URL` back to the legacy project. No destructive statement was ever issued:
no `DROP`, no `TRUNCATE`, no data rewrite; only additive columns/indexes.

### Ingestion
```bash
git revert <bad-commit>          # never force-push
```
or disable the schedule without touching code:
```bash
# stop the failing scheduled runs (reversible)
curl -X PUT -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/CLAIRGERY/caribbean-platform/actions/workflows/337539264/disable
# re-enable later
curl -X PUT …/enable
```

---

## 5. Verified locally (2026-10-24)

| check | result |
|---|---|
| `npm run typecheck` (tsc --noEmit, strict) | PASS |
| `npm run build` | PASS, 2.31 MB dist |
| dist audit | 11/11 referenced assets present, no sourcemaps, no `.env`, production URL baked |
| backend v2 tests | 61 passed, 2 skipped (PostGIS integration needs a DB) |
| ingestion tests | 53 passed |
| frontend ⇄ API contract | 5/5 frontend paths on `/api/v1` and `/api/v2`, `/docs`, `/status` |
| layer independence | sargassum 503 → banner « Service dégradé », drift + marine still active, map 1440×900 |
| full outage | all layers 503 → « Service indisponible », basemap + controls alive |
| empty DB | 0 features → « Aucune observation récente », no error banner |
| Three.js optional | chunk absent on first load, loads on toggle, blocked chunk → map unaffected |
| i18n | FR → EN → persisted after reload → FR |
| Alembic | head `0001_initial`, 16 DDL statements, valid offline SQL |
| Render cold/outage | health 13 ms, status 200 degraded, layers 503 structured |

## 6. Not deployed

Hostinger upload, Render service creation, Supabase provisioning and the merge to `main`
all require account access; none was performed.
