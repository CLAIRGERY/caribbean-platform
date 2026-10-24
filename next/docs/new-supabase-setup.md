# New Supabase / PostGIS project — setup & migration

## 1. Create the project

1. Supabase → New project → choose the region closest to the Caribbean audience
   (`eu-west-3` currently hosts the legacy project; `us-east-1` lowers latency for
   the Lesser Antilles but check egress costs).
2. Save the database password in a password manager. It is shown once.
3. Enable PostGIS: SQL editor → `create extension if not exists postgis;`
   (the Alembic revision also does this, but doing it first makes the extension
   owner explicit).
4. Copy **both** connection strings:
   * Session pooler (port `5432`) → for migrations and the API.
   * Transaction pooler (port `6543`) → valid for the API too; note that libpq
     `options` are ignored there, which is why the app issues explicit `SET`.

## 2. Environment

```bash
export DATABASE_URL='postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres'
```

Never commit this value. `backend-next/.env` is git-ignored; use GitHub Actions
secrets / Render env vars for deployed environments.

## 3. Apply the schema

```bash
cd workspace/backend-next
alembic upgrade head          # creates alembic_version + all tables/indexes
alembic current               # -> 0001_initial (head)
alembic upgrade head --sql    # dry-run: prints the exact SQL, touches nothing
```

Revision `0001_initial` is **additive and idempotent**:

* creates the extension, the four tables and every index **only if missing**;
* against an existing `sargassum_detections` / `drift_predictions` /
  `marine_alerts` it only adds the missing `external_id` / `source` columns;
* indexes use `CREATE INDEX IF NOT EXISTS`;
* `downgrade()` deliberately refuses to run — dropping scientific tables is a
  reviewed manual operation, never an automated one.

## 4. Tables

| table | geometry | time column | notes |
|---|---|---|---|
| `sargassum_detections` | `geometry(GEOMETRY,4326)` NOT NULL | `acquisition_date` | full-precision polygons |
| `drift_predictions` | `geometry(GEOMETRY,4326)` NOT NULL | `created_at` | corridors, 24/48/72 h |
| `marine_alerts` | `geometry(GEOMETRY,4326)` NULL | `issued_at` | sector polygons / points |
| `ingestion_runs` | — | `started_at`, `finished_at` | per-source ledger read by `/api/v2/status` |

Indexes: GIST on every geometry, B-tree on the three time columns, `external_id`
lookups, `(source, finished_at)` for the ledger.

## 5. Migrating existing data (optional, non-destructive)

1. Dump from the legacy project:
   ```bash
   pg_dump "$LEGACY_DATABASE_URL" --no-owner --no-privileges \
     -t sargassum_detections -t drift_predictions -t marine_alerts \
     -t ingestion_runs -f sakgaze_data.sql
   ```
2. Restore into the new project **after** `alembic upgrade head`:
   ```bash
   psql "$DATABASE_URL" -f sakgaze_data.sql
   ```
3. Verify:
   ```sql
   SELECT 'sargassum', count(*), max(acquisition_date) FROM sargassum_detections
   UNION ALL SELECT 'drift', count(*), max(created_at) FROM drift_predictions
   UNION ALL SELECT 'alerts', count(*), max(issued_at) FROM marine_alerts;
   ```
4. Only then point the ingestion workflow's `DATABASE_URL` secret at the new
   project. Do **not** delete the legacy project: it is the rollback path.

## 6. Verification checklist

- [ ] `alembic current` reports `0001_initial (head)`
- [ ] `SELECT postgis_version();` works
- [ ] all four tables exist with a GIST index on geometry
- [ ] `/api/v2/status` reports `database: "ok"` and three sources
- [ ] `/api/v2/sargassum?limit=1` returns a FeatureCollection
- [ ] row counts match the source database (if data was migrated)

## 7. Rollback

Point `DATABASE_URL` back at the legacy project. No destructive statement is ever
issued by this procedure.
