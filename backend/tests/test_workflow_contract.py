"""Workflow contract tests.

The ingestion workflow is the production entry point; a silent YAML edit could
reintroduce the incident (DDL in the hot path, unbounded retries, misleading
green statuses).

Two files are involved during the migration window:

* ``.github/workflows/sakgaze-ingestion.yml``  – the file GitHub actually runs;
* ``infrastructure/github-actions/sakgaze-ingestion.yml`` – the corrected version,
  kept as a template because pushing workflow files requires the ``workflow``
  OAuth scope (see docs/github-actions-incident.md §6).

The tests assert on whichever files exist: the template must always encode the
full contract, and the live file must never contain ``init_db`` (guards the
regression even on the legacy copy).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIVE = os.path.join(ROOT, ".github", "workflows", "sakgaze-ingestion.yml")
TEMPLATE = os.path.join(ROOT, "infrastructure", "github-actions", "sakgaze-ingestion.yml")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def contract_text() -> str:
    """The declared policy: the corrected template when present, else the live file."""
    return _read(TEMPLATE if os.path.isfile(TEMPLATE) else LIVE)


def test_a_workflow_file_exists():
    assert os.path.isfile(LIVE)
    assert os.path.isfile(TEMPLATE), (
        "the corrected workflow template must ship in infrastructure/github-actions/"
    )


def test_single_concurrency_group_without_cancel():
    text = contract_text()
    assert "concurrency:" in text
    assert "group: sakgaze-ingestion" in text
    # Cancelling a run mid-DDL is how the schema got locked in the first place.
    assert "cancel-in-progress: false" in text


def test_collectors_are_resolved_per_schedule():
    text = contract_text()
    assert "0 2,14 * * *" in text
    assert "30 */6 * * *" in text
    assert "45 */6 * * *" in text
    assert 'src="sargassum"' in text
    assert 'src="drift"' in text
    assert 'src="marine-alerts"' in text


def test_database_maintenance_is_a_separate_bounded_step():
    text = contract_text()
    assert "python -m backend.src.db_admin --inspect --terminate-blockers --migrate" in text
    assert "timeout-minutes: 5" in text
    assert "--source \"${{ steps.plan.outputs.source }}\"" in text


def test_live_workflow_never_calls_init_db():
    """The deployed file must not run schema DDL from the ingestion path."""
    assert "init_db" not in _read(LIVE)


def test_exit_codes_are_mapped_to_annotations():
    text = contract_text()
    for code in ("10", "11", "12", "13", "2*"):
        assert re.search(rf"\b{re.escape(code)}\)", text), f"exit code {code} not handled"
    assert "AUTHENTICATION_ERROR" in text
    assert "DATABASE_UNAVAILABLE" in text


def test_no_automatic_retry_loop():
    text = contract_text()
    assert "retry" not in text.lower() or "never retried automatically" in text
    assert "--retry" not in text


def test_secrets_are_referenced_not_literal():
    for path in (LIVE, TEMPLATE):
        text = _read(path)
        assert "secrets.DATABASE_URL" in text
        assert "postgresql://" not in text and "postgresql+psycopg2://" not in text
        assert not re.search(
            r"(password|secret_key|access_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+]{12,}", text, re.I
        )


def test_runner_documents_no_ddl_contract():
    runner = os.path.join(ROOT, "backend", "src", "ingestion", "runner.py")
    text = _read(runner)
    assert "no ddl" in text.lower()
