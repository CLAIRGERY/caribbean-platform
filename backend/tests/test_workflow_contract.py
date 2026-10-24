"""Workflow contract tests.

The ingestion workflow is the production entry point; a silent YAML edit could
reintroduce the incident (DDL in the hot path, unbounded retries, misleading
green statuses). These assertions are the guard rail.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "sakgaze-ingestion.yml")


def _text():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return fh.read()


def test_workflow_exists():
    assert os.path.isfile(WORKFLOW)


def test_single_concurrency_group_without_cancel():
    text = _text()
    assert "concurrency:" in text
    assert "group: sakgaze-ingestion" in text
    # Cancelling a run mid-DDL is how the schema got locked in the first place.
    assert "cancel-in-progress: false" in text


def test_collectors_are_resolved_per_schedule():
    text = _text()
    assert "0 2,14 * * *" in text
    assert "30 */6 * * *" in text
    assert "45 */6 * * *" in text
    assert 'src="sargassum"' in text
    assert 'src="drift"' in text
    assert 'src="marine-alerts"' in text


def test_database_maintenance_is_a_separate_bounded_step():
    text = _text()
    assert "python -m backend.src.db_admin --inspect --terminate-blockers --migrate" in text
    assert "timeout-minutes: 5" in text
    # The ingestion runner itself must never be asked to migrate.
    assert "runner --source" in text or "--source \"${{ steps.plan.outputs.source }}\"" in text


def test_no_init_db_in_workflow():
    assert "init_db" not in _text()


def test_exit_codes_are_mapped_to_annotations():
    text = _text()
    for code in ("10", "11", "12", "13", "2*"):
        assert re.search(rf"\b{re.escape(code)}\)", text), f"exit code {code} not handled"
    assert "AUTHENTICATION_ERROR" in text
    assert "DATABASE_UNAVAILABLE" in text


def test_no_automatic_retry_loop():
    text = _text()
    assert "retry" not in text.lower() or "never retried automatically" in text
    assert "--retry" not in text


def test_secrets_are_referenced_not_literal():
    text = _text()
    assert "secrets.DATABASE_URL" in text
    # no DSN, token or key material committed in the workflow
    assert "postgresql://" not in text and "postgresql+psycopg2://" not in text
    assert not re.search(r"(password|secret_key|access_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+]{12,}", text, re.I)


def test_runner_documents_no_ddl_contract():
    runner = os.path.join(ROOT, "backend", "src", "ingestion", "runner.py")
    text = open(runner, encoding="utf-8").read()
    assert "No DDL" in text or "no DDL" in text.lower()
