# New Supabase Setup (backend-next skeleton)

## Service
Render → New Web Service → connect repo → set:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Env: `DATABASE_URL` (verbatim from Supabase), `CORS_ORIGINS=https://sakgaze.com`
- Health check path: `/health`

## Supabase
- Create the project; copy the Transaction-pooler connection string exactly into `DATABASE_URL`.
- Enable PostGIS: `CREATE EXTENSION postgis;`
- Tables to model (see backend-migration-next.md):
  `sargassum_detections`, `drift_predictions`, `marine_alerts`, `ingestion_runs`
- Store full precision geometry (GEOMETRY(MultiPolygonZM,4326) etc.). Delivery endpoints simplify with
  `ST_SimplifyPreserveTopology(geom, 0.0005)` + `ST_AsGeoJSON(..., 5, ...)` + gzip + indexes on (acquisition_date).
