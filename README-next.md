# SaKgaZé Next — platform reconstruction

Caribbean sargassum intelligence: satellite detections, drift forecast corridors,
marine/coastal alerts and scientific freshness, on a full-viewport MapLibre map.
French-first (`fr-FR`) with an English toggle.

```
workspace/
├── frontend-next/      Vite + React + TS strict + MapLibre GL + Tailwind + Zustand
│                       + TanStack Query + i18next (+ lazy Three.js "Mode Flux Océanique")
├── backend-next/       FastAPI + Pydantic v2 + SQLAlchemy 2 + PostGIS + Alembic
├── caribbean-platform/ the real repository (legacy v1 backend, ingestion, workflows)
├── docs/               deployment, brand, incident and ingestion documentation
└── builds/             last production build of the frontend (dist/)
state/PROJECT_STATE.md  authoritative checkpoint for resuming work
```

## What is verified

| check | command | result |
|---|---|---|
| frontend types | `npm run typecheck` (tsc --noEmit, strict) | see `PROJECT_STATE.md` |
| frontend build | `npm run build` | see `PROJECT_STATE.md` |
| backend v2 tests | `python -m pytest tests -q` in `backend-next/` | 53 passed, 2 skipped (PostGIS integration needs a DB) |
| ingestion tests | `python -m pytest backend/tests/test_*.py -q` in `caribbean-platform/` | 50 passed |
| ingestion dry-run | `python -m backend.src.ingestion.runner --source all --dry-run` | CDSE STAC 200, 8 marine alerts, exit 0/11 as appropriate |
| migration SQL | `alembic upgrade head --sql` | valid Postgres/PostGIS DDL generated |

## Backend (v2)

```bash
cd backend-next
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
export DATABASE_URL='postgresql+psycopg2://…'
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Endpoints: `/health`, `/api/v2/status`, `/api/v2/sargassum`, `/api/v2/drift`,
`/api/v2/marine-alerts`, plus `/api/v1/...` compatibility aliases so the current
frontend switches over with `VITE_API_BASE_URL` alone. Docs at `/docs`.

## Frontend

```bash
cd frontend-next
npm install
npm run dev        # http://localhost:5173
npm run typecheck
npm run build      # -> dist/ (upload CONTENTS to public_html/)
```

See `docs/hostinger-web-deploy.md`, `docs/new-render-setup.md`,
`docs/new-supabase-setup.md`, `docs/backend-migration-next.md`,
`docs/ingestion-architecture.md` and `docs/github-actions-incident.md`.

## Product rules that are not negotiable

* The map is the product: it always fills the viewport; no permanent sidebar.
* The three layers load, fail and retry independently — one broken source never
  blanks the map.
* Only timestamps that exist in the data are shown; an empty result is an explicit
  empty state, never invented forecast buckets.
* Freshness is stated per source (`LIVE` / `RECENT` / `STALE` / `UNAVAILABLE`);
  historical data is never labelled live.
* No fabricated scientific values, in the UI or in the ingestion pipeline.
