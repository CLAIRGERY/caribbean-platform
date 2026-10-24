"""Frontend ⇄ API path contract.

Reads the path literals out of the actual frontend source and asserts the API
serves every one of them (v1 compatibility + canonical v2 equivalent). A rename
on either side fails here instead of in production.
"""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tests.conftest import FakeRepository, build_client  # noqa: E402

sys.path.insert(0, os.path.join(BACKEND_DIR, "scripts"))
from contract_check import GEOJSON_PATHS, V2_EQUIVALENT, frontend_paths  # noqa: E402


def test_frontend_paths_are_extracted():
    paths = frontend_paths()
    assert "/health" in paths
    assert "/sakgaze/detections/latest" in paths
    assert "/sakgaze/drift-predictions/latest" in paths
    assert "/weathernext/marine-alerts/latest" in paths
    assert "/ingestion/status" in paths


def test_every_frontend_path_is_served_by_v1():
    client = build_client(repository=FakeRepository(count=1))
    for path in frontend_paths():
        response = client.get("/api/v1" + path)
        assert response.status_code == 200, f"/api/v1{path} -> {response.status_code}"


def test_every_frontend_path_has_a_v2_equivalent():
    client = build_client(repository=FakeRepository(count=1))
    for path in frontend_paths():
        assert path in V2_EQUIVALENT, f"no v2 equivalent declared for {path}"
        response = client.get("/api/v2" + V2_EQUIVALENT[path])
        assert response.status_code == 200, f"/api/v2{V2_EQUIVALENT[path]} -> {response.status_code}"


def test_versioned_health_exists_for_every_prefix():
    """The frontend composes /health onto its base URL, so it must exist per version."""
    client = build_client(repository=FakeRepository(count=1))
    for prefix in ("/api/v1", "/api/v2"):
        response = client.get(prefix + "/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_geojson_layers_declare_the_documented_content_type():
    client = build_client(repository=FakeRepository(count=1))
    for path in GEOJSON_PATHS:
        response = client.get("/api/v1" + path)
        assert response.headers["content-type"].startswith("application/geo+json")
        assert response.json()["meta"]["count"] == 1
