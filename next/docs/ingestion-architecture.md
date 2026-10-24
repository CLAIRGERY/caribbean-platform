# Ingestion architecture & runbook (SaKgaZé)

## 1. Data flow

```
CDSE STAC (anonymous search)
   └─ Sentinel-2 L2A scene selection (cloud filter, AOI Caribbean basin)
        └─ OAuth2 + S3 band streaming → FAI index → ML false-positive filter
              └─ sargassum_detections  (polygons, surface_km2, density)
                     └─ drift engine (Open-Meteo currents + 10 m wind, 24/48/72 h)
                            └─ drift_predictions (corridors, landing probability)

Open-Meteo marine + forecast (8 coastal sectors)
   └─ marine_alerts (wind, gust, wave height/period, h2s risk, severity)
```

**Dependency worth knowing:** drift consumes *stored* sargassum detections. If
sargassum ingestion is blocked, drift goes to zero a few days later even though
Open-Meteo is perfectly healthy. The two sources are monitored separately.

## 2. Modules

| module | responsibility |
|---|---|
| `backend/src/ingestion/common.py` | HTTP client (timeout, retries with backoff), stable `external_id` hashing, GeoJSON validation |
| `backend/src/ingestion/errors.py` | failure taxonomy, exit codes, `MissingCredentials` |
| `backend/src/ingestion/sargassum.py` | CDSE STAC search + FAI vectorisation |
| `backend/src/ingestion/drift.py` | advection of detection centroids (0.03·wind + 1.0·current) |
| `backend/src/ingestion/marine_alerts.py` | sector-level marine/wind alerting |
| `backend/src/ingestion/runner.py` | orchestration: per-source isolation, classification, exit code, step summary |
| `backend/src/db_admin.py` | inspect / unblock / additive migration (the only place DDL may run) |
| `backend/src/crud.py` | idempotent writes keyed on `external_id` + run ledger |

## 3. Failure taxonomy & exit codes

| class | exit | fatal | retried automatically |
|---|---|---|---|
| `SUCCESS` | 0 | no | — |
| `NO_NEW_DATA` | 0 | no | next scheduled run |
| `PARTIAL_SUCCESS` | 0 | no | next scheduled run |
| `AUTHENTICATION_ERROR` | 10 | yes | **never** |
| `CONFIGURATION_ERROR` | 11 | yes | **never** |
| `DATABASE_UNAVAILABLE` | 12 | yes | **never** |
| `INVALID_SCIENTIFIC_DATA` | 13 | yes | no |
| `UPSTREAM_UNAVAILABLE` | 20 | yes | next scheduled run |
| `NETWORK_TIMEOUT` | 21 | yes | next scheduled run |
| `RATE_LIMITED` | 22 | yes | next scheduled run |
| `PROCESSING_ERROR` | 23 | yes | next scheduled run |
| `UNKNOWN_ERROR` | 29 | yes | no |

An empty acquisition window is `NO_NEW_DATA`: exit 0, ⚪️ annotation, no email.
A missing credential is `CONFIGURATION_ERROR`: exit 11, red run, explicit
variable name in the step summary — and no retry, because retrying a wrong
password only generates noise.

## 4. Idempotency

* Every feature carries `external_id = sha256(source|field…|field…)`.
* `ingest_*_idempotent()` loads the existing ids for the batch and skips them.
* Re-running a collector is therefore a no-op (`inserted=0, skipped=n`) and is
  classified `NO_NEW_DATA`, not a failure.
* `ingestion_runs` records one row per source per run (status, counts, latest
  data timestamp, error class) — this is what `/api/v2/status` reads.

## 5. Runbook

### Daily checks
```bash
gh run list --workflow "SaKgaZé Ingestion" --limit 5      # if gh is installed
# or: GitHub → Actions → SaKgaZé Ingestion → latest run → Job summary table
```

### The job failed with exit 12 (`DATABASE_UNAVAILABLE`)
```bash
DATABASE_URL=... python -m backend.src.db_admin --inspect
DATABASE_URL=... python -m backend.src.db_admin --inspect --terminate-blockers --migrate
```
`--inspect` prints server/PostGIS version, per-table row counts, index list and
every lock blocker (pid, state, age, blocking pids). `--terminate-blockers`
only kills sessions that are idle-in-transaction or waiting on a lock.

### The job failed with exit 10 (`AUTHENTICATION_ERROR`)
1. Check the CDSE account (Copernicus Data Space Ecosystem → Sentinel Hub /
   OAuth client, and the S3 credentials page).
2. Rotate `CDSE_USERNAME`, `CDSE_PASSWORD`, `CDSE_S3_ACCESS_KEY`,
   `CDSE_S3_SECRET_KEY` in GitHub → Settings → Secrets.
3. Re-dispatch the workflow (`workflow_dispatch`, `source=sargassum`).
No automatic retry will happen until then — by design.

### The job failed with exit 11 (`CONFIGURATION_ERROR`)
The step summary names the missing variable. Add it, re-dispatch.

### Manual dispatch
GitHub → Actions → SaKgaZé Ingestion → *Run workflow* → choose `all`,
`sargassum`, `drift` or `marine-alerts`. One concurrency group
(`sakgaze-ingestion`, `cancel-in-progress: false`) guarantees no overlap.

### Local dry-run (no writes, no credentials needed for STAC/marine)
```bash
cd workspace/caribbean-platform
python -m backend.src.ingestion.runner --source all --dry-run --json
```

## 6. Scientific limits (do not overstate in the UI)

* **Sentinel-2**: FAI thresholding on L2A surface reflectance; cloud cover ≤ 20 %;
  polygons are *detections*, not biomass. Revisit ≈ 5 days, and persistent cloud
  in the Caribbean can push effective coverage to weeks.
* **Drift**: a first-order surface advection (3 % of wind + 100 % of surface
  current) with landing cones. It is a **scenario**, not a validated Lagrangian
  trajectory model. Never label it "validated prediction".
* **Marine alerts**: sector-level thresholds derived from Open-Meteo wind/wave
  and H₂S risk heuristics. NOAA NHC is used for cyclone context only. These are
  advisories, not official marine warnings — official warnings come from the
  national meteorological services.
