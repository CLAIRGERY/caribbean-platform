# Backend Migration — Next (new Render + new Supabase)

## Goal
Move the product onto a NEW Render backend + NEW Supabase project. The frontend
must keep working with ONLY an environment change — no code rewrite.

## Frontend contract (already in place)

- `src/lib/api.ts` is the single network entrypoint; it composes every URL from
  `VITE_API_BASE_URL`.
- `.env.example` documents the variable; the default still points to the legacy
  `https://sakgaze-api.onrender.com/api/v1`.
- Migration, once the new backend implements the same routes, is:

  ```
  # frontend-next/.env
  VITE_API_BASE_URL=https://<new-render-service>.onrender.com/api/v1
  ```

  then `npm run build`, then redeploy to Hostinger. Nothing else changes.

## Contract the new backend must honor (v1-compatible)

| Route                                        | Response shape                        | Notes                                    |
|----------------------------------------------|---------------------------------------|------------------------------------------|
| `GET /health`                                | `{"status": "ok"}`                    | used only for quick pings                |
| `GET /api/v1/sakgaze/detections/latest`      | GeoJSON FeatureCollection (Polygon/MultiPolygon) | props: acquisition_date (UTC ISO), surface_km2, density, density_score, source, external_id; cap ~1000 features, gzip, ST_SimplifyPreserveTopology(tolerance≈0.0005°) |
| `GET /api/v1/sakgaze/drift-predictions/latest` | GeoJSON FeatureCollection (LineString) | props: seed_id, forecast_horizon_h, forecast_time, generated_at, velocity_kmh |
| `GET /api/v1/weathernext/marine-alerts/latest` | GeoJSON FeatureCollection (points/polygons)     | props: alert_level/severity, sector, wind_kmh, wave_height_m, eta, issued_at |
| `GET /api/v1/ingestion/status`               | JSON object with freshness info       | at minimum a parseable timestamped field |

Rules the new backend MUST keep:

- gzip compression on the three payload-heavy GET routes.
- CORS: allow the Hostinger origin (whitelist from `CORS_ORIGINS`).
- No breaking changes in the property names listed above — the frontend types in
  `src/types/geo.ts` are the source of truth.

## v2 sketch (optional — backend-next/)

A clean FastAPI skeleton can later expose `/api/v2/...` (see
`backend-migration-next.md` §"Future" and `new-render-setup.md` if written);
the frontend will then ship a small adapter in `lib/api.ts` keyed on the same
`VITE_API_BASE_URL`.

## Database (Supabase)

- Migrations must NOT hardcode: database password, project ref, pooler hostname.
- Consume `DATABASE_URL` verbatim (as the legacy backend already does).
- Keep full scientific geometry in PostGIS; simplify only the delivery geometry
  (ST_SimplifyPreserveTopology + ST_AsGeoJSON precision) and bound responses
  with `limit`/`days`/`bbox` query parameters.
