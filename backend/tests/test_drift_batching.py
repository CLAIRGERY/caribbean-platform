"""Unit tests for the drift Open-Meteo batching fix.

All external HTTP is mocked — these tests must not touch live APIs.
"""
import os
import sys
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.src.ingestion import drift as drift_mod


# ---------------------------------------------------------------------------
# Coordinate formatting
# ---------------------------------------------------------------------------
def test_fmt_coord_4_decimals():
    assert drift_mod._fmt_coord(-89.54555603033204) == "-89.5456"
    assert drift_mod._fmt_coord(27.974944766647493) == "27.9749"
    assert drift_mod._fmt_coord(0.0) == "0.0000"
    assert drift_mod._fmt_coord(16.2) == "16.2000"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def test_iter_chunks_100_seeds():
    coords = [(float(i), float(i)) for i in range(100)]
    sizes = [len(c) for c in drift_mod._iter_chunks(coords, drift_mod.OPEN_METEO_BATCH_SIZE)]
    assert sizes == [40, 40, 20]


def test_iter_chunks_edge_cases():
    assert [len(c) for c in drift_mod._iter_chunks([], 40)] == []
    assert [len(c) for c in drift_mod._iter_chunks(list(range(40)), 40)] == [40]
    assert [len(c) for c in drift_mod._iter_chunks(list(range(41)), 40)] == [40, 1]


# ---------------------------------------------------------------------------
# Batch fetch: ordering + formatting + partial failure
# ---------------------------------------------------------------------------
def test_fetch_marine_batch_preserves_order_and_formats():
    coords = [
        (16.27123456, -61.55123456),
        (14.64123456, -61.02123456),
        (18.07123456, -63.05123456),
    ]
    seen_urls = []

    def fake_fetch_json(url, params):
        seen_urls.append((url, params))
        n = len(params["latitude"].split(","))
        return [
            {"hourly": {
                "wave_height": [float(i)],
                "wave_period": [float(i)],
                "ocean_current_velocity": [float(i)],
                "ocean_current_direction": [float(i)],
            }}
            for i in range(n)
        ]

    with mock.patch.object(drift_mod.common, "fetch_json", side_effect=fake_fetch_json):
        out = drift_mod._fetch_marine_batch(coords)

    assert len(out) == 3
    assert all(x is not None for x in out)
    # Order is preserved: out[i] corresponds to coords[i].
    assert out[0]["wave_height_m"] == 0.0
    assert out[1]["wave_height_m"] == 1.0
    assert out[2]["wave_height_m"] == 2.0
    # Coordinates were 4-decimal formatted (no 15-17 digit floats).
    lat_param = seen_urls[0][1]["latitude"]
    lon_param = seen_urls[0][1]["longitude"]
    assert lat_param == "16.2712,14.6412,18.0712"
    assert lon_param == "-61.5512,-61.0212,-63.0512"


def test_fetch_marine_batch_partial_failure_keeps_successes():
    coords = [(float(i), float(i)) for i in range(45)]  # 2 chunks: 40 + 5
    calls = {"n": 0}

    def fake_fetch_json(url, params):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated chunk failure")
        n = len(params["latitude"].split(","))
        return [{"hourly": {"wave_height": [1.0]}} for _ in range(n)]

    with mock.patch.object(drift_mod.common, "fetch_json", side_effect=fake_fetch_json):
        out = drift_mod._fetch_marine_batch(coords)

    assert len(out) == 45
    # First chunk (40 coords) failed → None entries; second chunk (5) succeeded.
    assert all(x is None for x in out[:40])
    assert all(x is not None for x in out[40:])


def test_fetch_wind_batch_partial_failure_keeps_successes():
    coords = [(float(i), float(i)) for i in range(50)]  # 2 chunks: 40 + 10
    calls = {"n": 0}

    def fake_fetch_json(url, params):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated chunk failure")
        n = len(params["latitude"].split(","))
        return [{"hourly": {"wind_speed_10m": [10.0]}} for _ in range(n)]

    with mock.patch.object(drift_mod.common, "fetch_json", side_effect=fake_fetch_json):
        out = drift_mod._fetch_wind_batch(coords)

    assert len(out) == 50
    assert all(x is not None for x in out[:40])  # first chunk ok
    assert all(x is None for x in out[40:])      # second chunk failed


# ---------------------------------------------------------------------------
# No duplicate trajectories (deterministic external_ids within a run)
# ---------------------------------------------------------------------------
def test_fetch_drift_predictions_no_duplicate_external_ids():
    detections = []
    for i in range(5):
        lon = -61.0 + i * 0.05
        lat = 16.0 + i * 0.02
        detections.append({
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[lon, lat], [lon + 0.01, lat],
                                 [lon, lat + 0.01], [lon, lat]]],
            },
            "properties": {
                "surface_km2": 5.0 - i,
                "density_level": "medium",
                "density_score": 0.5,
            },
        })

    def fake_marine(coords):
        return [{"wave_height_m": 1.0, "wave_period_s": 5.0,
                 "current_speed_kmh": 1.0, "current_direction_deg": 90.0}
                for _ in coords]

    def fake_wind(coords):
        return [{"wind_speed_knots": 10.0, "gust_speed_knots": 12.0,
                 "wind_direction_deg": 90.0} for _ in coords]

    with mock.patch.object(drift_mod, "_fetch_marine_batch", side_effect=fake_marine), \
         mock.patch.object(drift_mod, "_fetch_wind_batch", side_effect=fake_wind):
        features = drift_mod.fetch_drift_predictions(detections)

    assert len(features) > 0
    ids = [f["properties"]["external_id"] for f in features]
    assert len(ids) == len(set(ids))  # no duplicate external_ids


def test_fetch_drift_predictions_skips_failed_chunk_seeds():
    detections = []
    for i in range(5):
        lon = -61.0 + i * 0.05
        lat = 16.0 + i * 0.02
        detections.append({
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[lon, lat], [lon + 0.01, lat],
                                 [lon, lat + 0.01], [lon, lat]]],
            },
            "properties": {"surface_km2": 5.0 - i, "density_level": "medium",
                           "density_score": 0.5},
        })

    def fake_marine(coords):
        # First seed fails, rest succeed.
        return [None] + [{"wave_height_m": 1.0, "wave_period_s": 5.0,
                          "current_speed_kmh": 1.0, "current_direction_deg": 90.0}
                         for _ in coords[1:]]

    def fake_wind(coords):
        return [{"wind_speed_knots": 10.0, "gust_speed_knots": 12.0,
                 "wind_direction_deg": 90.0} for _ in coords]

    with mock.patch.object(drift_mod, "_fetch_marine_batch", side_effect=fake_marine), \
         mock.patch.object(drift_mod, "_fetch_wind_batch", side_effect=fake_wind):
        features = drift_mod.fetch_drift_predictions(detections)

    # Seed 0 was skipped; no feature should originate from it.
    origins = {round(f["properties"]["origin_lon"], 5) for f in features}
    assert round(-61.0, 5) not in origins
    assert len(features) > 0  # remaining seeds still produced trajectories
