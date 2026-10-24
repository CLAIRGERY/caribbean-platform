# Backend migration — legacy v1 → SaKgaZé API v2

The v2 backend now exists (`workspace/backend-next/`, FastAPI + PostGIS + Alembic)
and serves **both** surfaces, so the frontend can be migrated with an environment
variable only.

## 1. Route surface

### Canonical (documented, OpenAPI at `/docs`)

| Route | Response |
|---|---|
| `GET /health` | `{"status":"ok","service":"sakgaze-api-v2","version":"2.0.0"}` — DB-free |
| `GET /api/v2/status` | freshness per source (`LIVE`/`RECENT`/`STALE`/`UNAVAILABLE`), `ingestion_runs` ledger, database state |
| `GET /api/v2/sargassum` | GeoJSON FeatureCollection (Polygon/MultiPolygon) |
| `GET /api/v2/drift` | GeoJSON FeatureCollection (LineString/MultiLineString) |
| `GET /api/v2/marine-alerts` | GeoJSON FeatureCollection (Point/Polygon) |
| `GET /api/v2/health/db` | `{"database":"ok"|"unavailable","configured":bool}` |

Query parameters on all three layers:

| param | range | default |
|---|---|---|
| `days` | 1 … `MAX_DAYS` (90) | 7 |
| `limit` | 1 … per-layer ceiling (sargassum 2000, drift 3000, alerts 1000) | 1000 / 1500 / 500 |
| `offset` | 0 … 1 000 000 | 0 |
| `bbox` | `minx,miny,maxx,maxy` (EPSG:4326, no antimeridian crossing) | — |
| `until` | ISO-8601 | now |

Out-of-range values → `400` with a structured envelope; unparsable types → `422`
in the same envelope; a dead database → `503` `DATABASE_UNAVAILABLE` (never `500`).

### Compatibility aliases (kept for the current frontend)

```
GET /api/v1/sakgaze/detections/latest
GET /api/v1/sakgaze/drift-predictions/latest
GET /api/v1/weathernext/marine-alerts/latest
GET /api/v1/ingestion/status
```

Identical handlers and payloads. Property names are a superset of the v1 fields
the frontend already reads (`acquisition_date`, `surface_km2`, `density_score`,
`density_level`, `source_satellite`, `prediction_horizon_days`, `eta_hours`,
`landing_probability_pct`, `target_sector`, `alert_level`, `sector`,
`wind_speed_knots`, `wave_height_m`, `issued_at`, `source`, `external_id`).

## 2. Switching the frontend

```bash
# frontend-next/.env
VITE_API_BASE_URL=https://<new-service>.onrender.com/api/v1
```

then `npm run build` and redeploy the `dist/` contents to Hostinger. No code change:
`src/lib/api.ts` composes every URL from that variable.

To move to the canonical surface later, change to `…/api/v2` and update the four
paths in `src/lib/api.ts` (`/sargassum`, `/drift`, `/marine-alerts`,
`/status`) plus the request mapper.

## 3. Response extras (safe to ignore)

GeoJSON foreign member `meta`:

```json
{"count": 812, "limit": 1000, "offset": 0, "days": 7, "bbox": null,
 "latest_data_timestamp": "2026-10-20T14:57:41Z", "simplified": true,
 "simplify_tolerance": 0.0005, "source": "sargassum_detections",
 "generated_at": "2026-10-24T13:58:02Z"}
```

Plus headers `X-Request-ID`, `X-Sakgaze-Simplified`,
`Cache-Control: public, max-age=60, stale-while-revalidate=300`.

## 4. Geospatial performance

* `ST_AsGeoJSON(ST_SimplifyPreserveTopology(geometry, :tol), 6)` — **delivery only**.
  Stored geometry is never modified, so scientific accuracy is preserved.
* `ST_Intersects(geometry, ST_MakeEnvelope(...))` for `bbox`, backed by GIST indexes.
* Temporal indexes on `acquisition_date`, `created_at`, `issued_at`.
* Responses gzip above `GZIP_MIN_SIZE`.
* Tested query shapes target 1 000 sargassum / 1 500 drift / 500 alert features.

## 5. Database

* `DATABASE_URL` consumed verbatim; no project ref, host or password in code.
* Migrations: `alembic upgrade head` (see `new-supabase-setup.md`).
* The initial revision is **additive and idempotent**: against the existing
  production database it only adds missing columns/indexes.
* Boot performs **no DDL** (`SAKGAZE_AUTO_MIGRATE=0`).

## 6. Rollback

1. Point `VITE_API_BASE_URL` back at the legacy service, rebuild, redeploy.
2. Nothing in the legacy service or database is modified by this migration.
