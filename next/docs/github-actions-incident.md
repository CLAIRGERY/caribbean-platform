# GitHub Actions incident — SaKgaZé Ingestion

**Status:** root cause identified from production logs, correction implemented and
unit-verified. A real GitHub Actions run of the corrected workflow is **pending**
(see "Verification" at the end — it needs a token with the `workflow` scope to
push the workflow file).

Period: **2026-09-09 20:57 UTC → 2026-10-24 11:09 UTC** (6 weeks).
Runs affected: **343 consecutive failed/cancelled runs** after the last success
(run `34404115118`, 2026-09-09T20:57:19Z).

---

## 1. Evidence

Workflow `SaKgaZé Ingestion` (id `337539264`), job `ingest`.
Last analysed run: **`40088472994`** — created 2026-10-24T11:05:12Z, duration **3 min 56 s**.

Step timings for that run:

| step | result | window |
|---|---|---|
| Checkout / Set up Python / pip cache | success | 11:05:16 → 11:05:20 |
| Install dependencies | success | 11:05:20 → 11:05:56 |
| **Run ingestion** | **failure** | 11:05:56 → 11:09:07 |
| everything after | skipped | — |

Failure (verbatim, secrets masked by GitHub):

```
psycopg2.errors.QueryCanceled: canceling statement due to statement timeout
sqlalchemy.exc.OperationalError: (psycopg2.errors.QueryCanceled)
    canceling statement due to statement timeout
[SQL: ALTER TABLE sargassum_detections ADD COLUMN IF NOT EXISTS external_id VARCHAR(64);]
  File "backend/src/ingestion/runner.py", line 163, in run
    init_db()
  File "backend/src/database.py", line 41, in init_db
    _apply_migrations()
  File "backend/src/database.py", line 60, in _apply_migrations
    conn.execute(text(stmt))
```

Duration distribution of recent failures: 32 s, 39 s, 45 s, 47 s, 48 s, 51 s, 65 s,
66 s, 178 s, 194 s, **237 s**. The user-reported "4 minutes 21 seconds" matches the
long tail: the run dies while *waiting for a table lock*, not while working.

## 2. Root cause

Two defects compounded:

1. **DDL on the ingestion hot path.** `runner.run()` called `init_db()` on every
   execution, which issued `CREATE EXTENSION`, `create_all`, `CREATE INDEX … USING
   GIST` and `ALTER TABLE … ADD COLUMN IF NOT EXISTS` against the production
   tables, with **no `lock_timeout`**. `ALTER TABLE` needs an `ACCESS EXCLUSIVE`
   lock; when any other session holds a lock on `sargassum_detections`, the run
   queues behind it and is eventually cancelled by the server-side statement
   timeout — *before any satellite acquisition happens*.
2. **The timeout was never the intended one.** `create_engine(connect_args={
   "options": "-c statement_timeout=8000 …"})` is silently ignored by the Supabase
   **transaction pooler** (pgbouncer does not forward arbitrary libpq startup
   `options`). The real timeout came from the server/pooler, which is why the same
   bug took 30 s on one run and 4 min on another.

Consequence chain (this is why the product looked "empty", not "broken"):

```
ingestion dies at init_db → 0 new detections stored
        → drift engine has no input polygons → 0 drift forecasts
        → marine alerts still produced (independent source)
        → /latest endpoints keep serving data that ages out of the 7-day window
        → dashboard looks stale, GitHub sends red emails every few hours
```

A cancelled run (31 of them around 2026-09-10) is the most likely origin of the
persistent lock holder: the connection survived the cancellation while its
transaction — and therefore the `ACCESS EXCLUSIVE` lock — stayed open.

## 3. Why the notifications never stopped

* 12 scheduled runs/day, all failing at the same place.
* No `lock_timeout`, so every run burned 30 s – 4 min before failing.
* The runner swallowed per-source exceptions and exited `0`, so failures could
  not be distinguished from empty acquisitions. (This run did fail, because the
  exception escaped before that logic — the inverse defect: some runs would have
  reported green while ingesting nothing.)
* No distinction between "no new satellite observation" (normal) and "database
  locked" (incident).

## 4. Correction implemented

| defect | fix | file |
|---|---|---|
| DDL in the hot path | runner never touches the schema; `init_db()` is opt-in (`SAKGAZE_AUTO_MIGRATE=0`) and not called on boot | `backend/src/ingestion/runner.py`, `backend/src/database.py` |
| Unbounded DDL waits | dedicated maintenance CLI with `lock_timeout=5s`, `statement_timeout=60s`, catalogue-driven additive changes, `CONCURRENTLY` GIST indexes | `backend/src/db_admin.py` |
| Stale lock holder | `--terminate-blockers` targets only sessions that are `idle in transaction` or explicitly waiting on a lock, age > 60 s | `backend/src/db_admin.py` |
| Ignored statement timeout | explicit `SET statement_timeout / lock_timeout / idle_in_transaction_session_timeout` on every connection | `backend/src/database.py` |
| Silent failures | structured classification (`AUTHENTICATION_ERROR`, `DATABASE_UNAVAILABLE`, `NO_NEW_DATA`, …) with stable exit codes 0/10/11/12/13/20-23/29 | `backend/src/ingestion/errors.py` |
| Empty result treated as incident, or failure treated as success | `main()` returns a real exit code; `NO_NEW_DATA` exits 0 with a ⚪️ annotation; real failures exit non-zero with an actionable `::error` title | `runner.py`, workflow |
| Missing credentials hidden as "no data" | raising `MissingCredentials` → `CONFIGURATION_ERROR` (exit 11) | `sargassum.py` |
| Notification volume | 3 targeted crons instead of 12 full runs/day, one concurrency group, `cancel-in-progress: false`, no automatic retry | `.github/workflows/sakgaze-ingestion.yml` |
| Opaque runs | JSON report on stdout + Markdown step summary (per-source outcome table, run metadata, incident note) | `runner.py`, `db_admin.py` |

Scheduling after the fix:

| cron | collector | runs/day |
|---|---|---|
| `0 2,14 * * *` | sargassum (Sentinel-2 revisit ≈ 5 days) | 2 |
| `30 */6 * * *` | drift forecast refresh | 4 |
| `45 */6 * * *` | marine alerts | 4 |

Total 10 targeted runs/day instead of 12 redundant "all sources" runs.

## 5. Verification performed (local, real execution)

```
pytest backend/tests/test_error_classification.py \
       backend/tests/test_runner_outcome.py \
       backend/tests/test_db_admin.py \
       backend/tests/test_workflow_contract.py \
       backend/tests/test_collector_config.py -q
→ 50 passed
```

Live collector dry-run (`python -m backend.src.ingestion.runner --source all --dry-run`,
no database writes):

* CDSE STAC search: HTTP 200, **20 candidate Sentinel-2 scenes** in the 30-day AOI window
  → the upstream catalogue is healthy; only credentials are needed for band streaming.
* Open-Meteo marine + wind: HTTP 200 at 8 coastal sectors → **8 valid marine alert features**.
* Drift: 0 features, because it consumes stored detections (see dependency chain above).
* Exit code 11 (`CONFIGURATION_ERROR`) locally — correct: no CDSE credentials on this
  workstation. In CI the secrets are injected, so this path is not expected.

## 5bis. Real workflow runs (evidence trail)

| run | sha | outcome | what it proved |
|---|---|---|---|
| `40101224907` | `f333341` | failure, exit 11, 90 s | **DDL deadlock gone** — run reached CDSE, obtained an OAuth token (HTTP 200), streamed bands, vectorised **153 sargassum polygons in 44 s**; then `CONFIGURATION_ERROR — No module named 'psycopg'` |
| `40101438202` | `540547b` | failure, exit 12, 4 min 45 s | Driver fixed (SQLAlchemy 2.1 + bare URL resolves to psycopg 3). Database reached, then: sargassum `psycopg2.OperationalError: server didn't return client encoding`; drift `SELECT` and marine `INSERT` `canceling statement due to statement timeout` → classified `DATABASE_UNAVAILABLE` |
| `40101891775` | `02d1a52` | see `state/PROJECT_STATE.md` | adds a read-only DB preflight (server version + lock blockers) and a bounded 60 s batch statement timeout |

Interpretation of run `40101438202`: acquisition and processing are healthy end-to-end
with the real secrets (CDSE OAuth, S3 band streaming, FAI vectorisation, NOAA NHC storm
feed, Open-Meteo marine/wind). The remaining failure is on the **database side only**
(connection-level error for one source, lock/statement timeouts for the other two), which
is exactly the class the product must report rather than mask. The preflight added in
`02d1a52` names the cause (paused project vs. stale lock holder) in the CI log.

## 6. Verification NOT yet performed

**A real GitHub Actions run of the corrected workflow has not been executed.**
`git push` of `.github/workflows/sakgaze-ingestion.yml` is rejected with:

```
refusing to allow an OAuth App to create or update workflow
`.github/workflows/sakgaze-ingestion.yml` without `workflow` scope
```

The stored OAuth token has scopes `gist, repo` only. The corrected workflow is therefore
committed as `infrastructure/github-actions/sakgaze-ingestion.yml` (template) and on the
local branch `fix/ci-workflow`; installation is documented in
`infrastructure/github-actions/README.md`.

**Note on the notification storm**: scheduled crons execute the workflow file from `main`,
which still contains the old runner call. The runner-side fix is already active on
`feature/sakgaze-next` (green runs `40101891775`, `40102327877`), so the notifications only
stop once this branch reaches `main` (authorisation required) or the corrected workflow /
schedule is installed.

Required external action:
re-authorise GitHub with the **`workflow`** scope (device flow, same client id as
before), then push the workflow commit and dispatch it:

```
POST /repos/CLAIRGERY/caribbean-platform/actions/workflows/337539264/dispatches
{"ref": "feature/sakgaze-next", "inputs": {"source": "all"}}
```

Until that run is green and the database rows are confirmed, the ingestion
workflow must be reported as **UNVERIFIED**, not "fixed".

## 7. Residual risk register

| risk | mitigation |
|---|---|
| CDSE credentials revoked/expired | `AUTHENTICATION_ERROR` (exit 10) with an explicit rotate instruction; **no retry** — a wrong password must never loop |
| A future edit reintroduces DDL in the runner | `test_runner_never_runs_ddl` (AST scan) + `test_workflow_contract` fail the build |
| Lock reappears (new long transaction) | maintenance step fails in ≤ 5 s with `DATABASE_UNAVAILABLE` and names the blocking PID; `--terminate-blockers` clears it |
| Sentinel-2 window genuinely empty (cloud) | `NO_NEW_DATA`, exit 0, ⚪️ annotation, no email, freshness shown as STALE by the API |
| Drift starvation after a sargassum outage | documented dependency; `/api/v2/status` reports drift freshness separately |
