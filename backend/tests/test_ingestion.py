"""Unit tests for the automatic ingestion layer.

All external HTTP calls are mocked — the suite must NOT depend on live APIs.
"""
import hashlib
import os
import sys
from datetime import datetime, timezone
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import common
from backend.src.ingestion import marine_alerts as marine_mod
from backend.src.ingestion import drift as drift_mod
from backend.src.ingestion import sargassum as sak_mod


# ---------------------------------------------------------------------------
# common.py
# ---------------------------------------------------------------------------
def test_external_id_is_deterministic():
    a = common.external_id("sargassum", "2026-08-18", 1.5, 0.9)
    b = common.external_id("sargassum", "2026-08-18", 1.5, 0.9)
    assert a == b
    assert len(a) == 64


def test_external_id_differs_by_field():
    a = common.external_id("sargassum", "2026-08-18", 1.5, 0.9)
    b = common.external_id("sargassum", "2026-08-19", 1.5, 0.9)
    assert a != b


def test_is_valid_feature():
    ok = {"geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}
    bad_geom = {"geometry": {"type": "Polygon"}}
    bad_type = {"geometry": {"type": "Bogus", "coordinates": []}}
    assert common.is_valid_feature(ok)
    assert not common.is_valid_feature(bad_geom)
    assert not common.is_valid_feature(bad_type)
    assert not common.is_valid_feature({})


def test_build_feature_collection_filters_invalid():
    valid = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {}}
    invalid = {"type": "Feature", "geometry": {"type": "Polygon"}, "properties": {}}
    fc = common.build_feature_collection([valid, invalid], source="test")
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert fc["properties"]["source"] == "test"


# ---------------------------------------------------------------------------
# HTTP robustness
# ---------------------------------------------------------------------------
def test_fetch_json_retries_then_raises():
    with mock.patch("backend.src.ingestion.common.httpx.Client") as MockClient:
        client = MockClient.return_value
        client.get.return_value.raise_for_status.side_effect = Exception("boom")
        client.get.return_value.json.side_effect = Exception("boom")
        with pytest.raises(Exception):
            common.fetch_json("https://example.invalid/x")


def test_fetch_json_success():
    payload = {"features": []}
    with mock.patch("backend.src.ingestion.common.httpx.Client") as MockClient:
        client = MockClient.return_value
        resp = mock.MagicMock()
        resp.json.return_value = payload
        client.get.return_value = resp
        result = common.fetch_json("https://example.invalid/x")
        assert result == payload


def test_fetch_json_malformed_response():
    with mock.patch("backend.src.ingestion.common.httpx.Client") as MockClient:
        client = MockClient.return_value
        resp = mock.MagicMock()
        resp.json.side_effect = ValueError("not json")
        client.get.return_value = resp
        with pytest.raises(Exception):
            common.fetch_json("https://example.invalid/x")


# ---------------------------------------------------------------------------
# marine_alerts normalization
# ---------------------------------------------------------------------------
def _sector_feature(name="Guadeloupe"):
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-61.6, 16.2], [-61.5, 16.2], [-61.5, 16.3], [-61.6, 16.2]]]},
        "properties": {
            "alert_type": "marine_conditions",
            "alert_level": "Yellow",
            "sector": name,
            "issued_at": "2026-08-19T00:00:00+00:00",
        },
    }


def test_normalize_marine_alerts_adds_external_id():
    feats = marine_mod.normalize_marine_alerts([_sector_feature()])
    assert feats[0]["properties"]["external_id"]


def test_marine_level_thresholds():
    assert marine_mod._marine_level(10, 1.0) == "Green"
    assert marine_mod._marine_level(22, 1.0) == "Yellow"
    assert marine_mod._marine_level(40, 1.0) == "Orange"
    assert marine_mod._marine_level(50, 1.0) == "Red"
    assert marine_mod._marine_level(70, 1.0) == "Purple"
    assert marine_mod._marine_level(5, 9.0) == "Purple"  # wave-driven


def test_cyclone_level_thresholds():
    assert marine_mod._cyclone_level(20) == "Green"
    assert marine_mod._cyclone_level(40) == "Yellow"
    assert marine_mod._cyclone_level(70) == "Orange"
    assert marine_mod._cyclone_level(110) == "Red"
    assert marine_mod._cyclone_level(140) == "Purple"


def test_fetch_cyclones_empty_when_no_storms():
    with mock.patch.object(marine_mod.common, "fetch_json", return_value={"activeStorms": []}):
        assert marine_mod._fetch_cyclones() == []


def test_fetch_cyclones_nhc_unreachable():
    with mock.patch.object(marine_mod.common, "fetch_json", side_effect=Exception("timeout")):
        assert marine_mod._fetch_cyclones() == []


def test_wind_knots_conversion():
    # 36 km/h ≈ 19.4 knots
    with mock.patch.object(marine_mod.common, "fetch_json", return_value={
        "hourly": {"wind_speed_10m": [36.0], "wind_gusts_10m": [50.0], "wind_direction_10m": [90.0]}
    }):
        summary = marine_mod._fetch_wind_summary(16.0, -61.0)
        assert round(summary["wind_speed_knots"], 1) == 19.4
        assert summary["wind_direction_deg"] == 90.0


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------
def test_drift_empty_when_no_detections():
    assert drift_mod.fetch_drift_predictions(detections=[]) == []


def test_drift_velocity_uses_wind_and_current():
    wind = {"wind_speed_knots": 20.0, "wind_direction_deg": 0.0}
    marine = {"current_speed_kmh": 3.6, "current_direction_deg": 0.0}  # 1 m/s
    u, v = drift_mod._drift_velocity(wind, marine)
    # wind: 20 kt * 0.5144 = 10.29 m/s * 0.03 = 0.309 m/s (north, v component)
    # current: 1 m/s (north)
    assert abs(v - (0.309 + 1.0)) < 0.01
    assert abs(u) < 1e-6


def test_advect_moves_northward():
    line = drift_mod._advect(-61.0, 15.0, 0.0, 1.0, 24)
    coords = list(line.coords)
    assert coords[0] == (-61.0, 15.0)
    assert coords[-1][1] > 15.0  # latitude increased


def test_landing_probability_zero_when_no_overlap():
    from shapely.geometry import Polygon
    cone = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    sector = Polygon([(10, 10), (11, 10), (11, 11), (10, 10)])
    assert drift_mod._landing_probability(cone, sector, 24) == 0.0


def test_h2s_flag_logic():
    assert drift_mod._h2s_flag("high", 0.9, 3.0) == "alerte_gaz"
    assert drift_mod._h2s_flag("high", 0.9, 10.0) is None
    assert drift_mod._h2s_flag("medium", 0.5, 2.0) == "attention_gaz"


# ---------------------------------------------------------------------------
# sargassum
# ---------------------------------------------------------------------------
def test_filter_cloud_drops_high_cloud():
    items = [
        {"properties": {"eo:cloud_cover": 95.0, "datetime": "2026-08-19"}},
        {"properties": {"eo:cloud_cover": 5.0, "datetime": "2026-08-18"}},
        {"properties": {"cloud_cover": 30.0, "datetime": "2026-08-17"}},
    ]
    valid = sak_mod._filter_cloud(items)
    assert len(valid) == 1
    assert valid[0]["properties"]["eo:cloud_cover"] == 5.0


def test_sargassum_no_credentials_returns_empty():
    with mock.patch.object(sak_mod, "_search_scenes", return_value=[
        {"properties": {"eo:cloud_cover": 5.0, "datetime": "2026-08-18"}}
    ]):
        with mock.patch.object(sak_mod, "CDSE_USERNAME", ""):
            with mock.patch.object(sak_mod, "CDSE_PASSWORD", ""):
                result = sak_mod.fetch_sargassum_detections()
                assert result == []


def test_sargassum_no_scenes_returns_empty():
    with mock.patch.object(sak_mod, "_search_scenes", return_value=[]):
        assert sak_mod.fetch_sargassum_detections() == []


def test_normalize_sargassum_adds_external_id():
    feat = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[-61.5, 16.2], [-61.4, 16.2], [-61.4, 16.3], [-61.5, 16.2]]]},
        "properties": {
            "surface_km2": 5.0, "density_score": 0.8, "density_level": "high",
            "acquisition_date": "2026-08-18T14:57:41+00:00",
        },
    }
    out = sak_mod.normalize_sargassum_detections([feat])
    assert out[0]["properties"]["external_id"]
    assert out[0]["properties"]["source"] == "cdse_sentinel2"
