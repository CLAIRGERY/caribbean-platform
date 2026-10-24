"""HTTP contract tests — the API surface the frontend depends on."""
from __future__ import annotations

import pytest

from app.core.errors import DatabaseUnavailable
from tests.conftest import FakeRepository, build_client


def test_health_is_database_free(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "sakgaze-api-v2"
    assert body["version"] == "2.0.0"


@pytest.mark.parametrize(
    "path,layer",
    [
        ("/api/v2/sargassum", "sargassum"),
        ("/api/v2/drift", "drift"),
        ("/api/v2/marine-alerts", "alerts"),
    ],
)
def test_layer_endpoints_return_geojson(client, path, layer):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/geo+json")
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"], "expected fake features"
    feature = body["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] in ("Point", "LineString", "Polygon", "MultiPolygon")
    assert body["meta"]["source"].startswith(("sargassum", "drift", "marine"))
    assert body["meta"]["simplified"] is True


@pytest.mark.parametrize(
    "v2,v1",
    [
        ("/api/v2/sargassum", "/api/v1/sakgaze/detections/latest"),
        ("/api/v2/drift", "/api/v1/sakgaze/drift-predictions/latest"),
        ("/api/v2/marine-alerts", "/api/v1/weathernext/marine-alerts/latest"),
    ],
)
def test_v1_aliases_match_v2_payloads(client, v2, v1):
    a = client.get(v2)
    b = client.get(v1)
    assert a.status_code == b.status_code == 200
    assert a.json()["type"] == b.json()["type"] == "FeatureCollection"
    assert len(a.json()["features"]) == len(b.json()["features"])


def test_v1_ingestion_status_alias(client):
    response = client.get("/api/v1/ingestion/status")
    assert response.status_code == 200
    assert response.json()["api_version"] == "2.0.0"


def test_empty_dataset_is_a_valid_collection():
    client = build_client(repository=FakeRepository(count=0))
    response = client.get("/api/v2/sargassum")
    assert response.status_code == 200
    body = response.json()
    assert body["features"] == []
    assert body["meta"]["count"] == 0


def test_limit_is_forwarded_and_bounded(client):
    response = client.get("/api/v2/sargassum", params={"limit": 500, "days": 14})
    assert response.status_code == 200
    assert response.json()["meta"]["limit"] == 500
    assert response.json()["meta"]["days"] == 14


def test_limit_above_ceiling_is_rejected(client):
    response = client.get("/api/v2/sargassum", params={"limit": 999999})
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_PARAMETER"
    assert "limit" in error["message"].lower()


def test_days_out_of_range_is_rejected(client):
    for days in (0, 91, -5):
        response = client.get("/api/v2/drift", params={"days": days})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_non_numeric_days_returns_structured_422(client):
    response = client.get("/api/v2/drift", params={"days": "not-a-number"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_bbox_is_forwarded(client, repository):
    response = client.get("/api/v2/marine-alerts", params={"bbox": "-62,14,-60,17"})
    assert response.status_code == 200
    assert response.json()["meta"]["bbox"] == [-62.0, 14.0, -60.0, 17.0]
    assert repository.calls[-1][1].bbox == (-62.0, 14.0, -60.0, 17.0)


@pytest.mark.parametrize(
    "bbox",
    ["-62,14,-60", "-62,14,-60,17,1", "a,b,c,d", "-62,14,-62,17", "-200,14,-60,17",
     "10,20,-30,40"],
)
def test_invalid_bbox_is_rejected(client, bbox):
    response = client.get("/api/v2/sargassum", params={"bbox": bbox})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PARAMETER"


def test_until_filter_is_parsed(client):
    response = client.get("/api/v2/sargassum", params={"until": "2026-10-20T00:00:00Z"})
    assert response.status_code == 200
    assert response.json()["meta"]["until"] == "2026-10-20T00:00:00+00:00"


def test_invalid_until_is_rejected(client):
    response = client.get("/api/v2/sargassum", params={"until": "yesterday"})
    assert response.status_code == 400


def test_database_failure_is_503_without_leaking_details():
    repo = FakeRepository(fail_with=DatabaseUnavailable("database query timed out",
                                                        details={"reason": "statement_timeout"}))
    client = build_client(repository=repo)
    response = client.get("/api/v2/sargassum")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "psycopg" not in response.text.lower()


def test_large_payload_is_gzip_encoded():
    client = build_client(repository=FakeRepository(count=200))
    response = client.get("/api/v2/sargassum", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_cache_headers_present(client):
    response = client.get("/api/v2/sargassum")
    assert "max-age=60" in response.headers["cache-control"]
    assert response.headers["x-sakgaze-simplified"] == "true"


def test_request_id_header_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"


def test_cors_allows_configured_origin(client):
    response = client.get("/api/v2/sargassum", headers={"Origin": "https://sakgaze.com"})
    assert response.headers.get("access-control-allow-origin") == "https://sakgaze.com"


def test_status_endpoint_shape(client):
    response = client.get("/api/v2/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["api_version"] == "2.0.0"
    assert isinstance(body["sources"], list)
    assert body["sources"][0]["freshness"] in ("LIVE", "RECENT", "STALE", "UNAVAILABLE", "UNKNOWN")


def test_negative_offset_is_rejected(client):
    response = client.get("/api/v2/sargassum", params={"offset": -1})
    assert response.status_code == 400


def test_unknown_route_is_structured(client):
    response = client.get("/api/v2/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"
