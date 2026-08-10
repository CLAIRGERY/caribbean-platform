# SaKgaZé / Weathernext — Agent Workflow Guidelines

## Environment execution rule
Always prefix terminal/Python execution with `PYTHONPATH=` and use `.venv/bin/python` to avoid NumPy/C-extension crashes caused by `PYTHONPATH` leaks between Python versions.

```bash
cd /Users/ludovic.clairgery/caribbean-platform
PYTHONPATH= .venv/bin/python -m uvicorn backend.src.main:app --host 127.0.0.1 --port 8000
```

## Temporary files
Write all verification, test, scratch, and cache scripts into the project-local directory:

```
caribbean-platform/tmp/
```

Do **not** write agent-generated scripts to system paths such as `/tmp/` or `/private/var/folders/.../T`; the sandbox may refuse writes to those locations.

## Running tests
```bash
PYTHONPATH= .venv/bin/pytest backend/tests/
```

## Running pipelines manually
```bash
PYTHONPATH= .venv/bin/python -m sakgaze.src.pipeline
PYTHONPATH= .venv/bin/python -m weathernext.src.pipeline
PYTHONPATH= .venv/bin/python -m drift.src.engine
```

## Scheduler
Run the 6-hour scheduler in the background:
```bash
PYTHONPATH= .venv/bin/python scheduler.py
```
