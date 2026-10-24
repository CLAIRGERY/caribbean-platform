# GitHub Actions — corrected ingestion workflow

`infrastructure/github-actions/sakgaze-ingestion.yml` is the **declared** version of the
ingestion workflow. `.github/workflows/sakgaze-ingestion.yml` is the file GitHub actually
executes.

## Why they differ

GitHub refuses any push that creates or updates a file under `.github/workflows/` unless the
credential carries the **`workflow`** OAuth scope:

```
refusing to allow an OAuth App to create or update workflow
`.github/workflows/sakgaze-ingestion.yml` without `workflow` scope
```

The current token has `gist, repo`. The corrected workflow therefore ships as a template plus
a prepared commit on the local branch `fix/ci-workflow`.

## Installing it (once the scope is granted)

```bash
cd <repo>
# option A — push the prepared commit
git push origin fix/ci-workflow:refs/heads/fix/ci-workflow
gh pr create --base feature/sakgaze-next --head fix/ci-workflow   # or merge directly

# option B — copy the template over the live file
cp infrastructure/github-actions/sakgaze-ingestion.yml .github/workflows/sakgaze-ingestion.yml
git add .github/workflows/sakgaze-ingestion.yml && git commit -m "fix(ci): install bounded ingestion workflow"
git push
```

Then re-authorise GitHub with the extra scope:

```bash
# device flow, no gh CLI required
POST https://github.com/login/device/code     client_id=178c6fc778ccc68e1d6a  scope=repo,workflow
# enter the user_code at https://github.com/login/device, then poll
POST https://github.com/login/oauth/access_token
```

## What the corrected workflow changes

| before | after |
|---|---|
| `python -m backend.src.ingestion.runner` called `init_db()` → `ALTER TABLE` → lock wait → statement timeout | database maintenance is a separate 5-minute step running `db_admin --migrate` with `lock_timeout=5s` / `statement_timeout=60s` |
| 12 identical "all sources" runs per day | 3 targeted crons: sargassum 02:00/14:00 UTC, drift every 6 h @ :30, marine every 6 h @ :45 |
| `concurrency` group present, but failures accumulated | unchanged group, `cancel-in-progress: false` (never kill a run mid-write), single source per run |
| any failure → generic red run | exit codes 10/11/12/13/2x mapped to actionable `::error` annotations |
| no summary | Markdown step summary (per-source outcome table, rows, duration) + incident metadata on failure |

Until it is installed, **the runner-side fix is already active** on `feature/sakgaze-next`
(runs `40101891775` and `40102327877` were green), but the scheduled crons still execute
`main`'s old code and will keep failing — hence the notification volume.
