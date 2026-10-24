"""Parameter parsing and SQL-shape unit tests (no database required)."""
from __future__ import annotations

import pytest

from app.core.errors import InvalidParameter
from app.repositories.geospatial import LAYERS, build_sql
from app.schemas.params import (
    build_layer_query,
    parse_bbox,
    parse_days,
    parse_limit,
    parse_offset,
    parse_until,
)


def test_parse_bbox_valid():
    assert parse_bbox("-62.5,14.0,-59.5,17.5") == (-62.5, 14.0, -59.5, 17.5)


def test_parse_bbox_empty_is_none():
    assert parse_bbox(None) is None
    assert parse_bbox("") is None


@pytest.mark.parametrize("raw", ["1,2,3", "1,2,3,4,5", "a,b,c,d", "5,14,1,17", "1,20,3,10"])
def test_parse_bbox_invalid(raw):
    with pytest.raises(InvalidParameter):
        parse_bbox(raw)


def test_parse_days_bounds():
    assert parse_days(None, maximum=90) == 7
    assert parse_days(1, maximum=90) == 1
    with pytest.raises(InvalidParameter):
        parse_days(0, maximum=90)
    with pytest.raises(InvalidParameter):
        parse_days(91, maximum=90)


def test_parse_limit_bounds():
    assert parse_limit(None, maximum=2000, default=1000) == 1000
    with pytest.raises(InvalidParameter):
        parse_limit(0, maximum=2000, default=1000)
    with pytest.raises(InvalidParameter):
        parse_limit(2001, maximum=2000, default=1000)


def test_parse_offset_bounds():
    assert parse_offset(None) == 0
    assert parse_offset(50) == 50
    with pytest.raises(InvalidParameter):
        parse_offset(-3)


def test_parse_until_accepts_zulu_and_naive():
    assert parse_until("2026-10-20T10:00:00Z").year == 2026
    assert parse_until("2026-10-20T10:00:00").tzinfo is not None
    assert parse_until(None) is None
    with pytest.raises(InvalidParameter):
        parse_until("20/10/2026")


def test_build_layer_query_since_is_tz_aware():
    q = build_layer_query(days=3, limit=10, offset=0, bbox=None, until=None,
                          max_limit=100, default_limit=10, max_days=90)
    assert q.since.tzinfo is not None
    assert q.meta()["days"] == 3


def test_sql_is_bounded_and_simplified():
    q = build_layer_query(days=7, limit=500, offset=0, bbox=None, until=None,
                          max_limit=2000, default_limit=1000, max_days=90)
    sql, params = build_sql(LAYERS["sargassum"], q)
    assert "ST_AsGeoJSON" in sql
    assert "ST_SimplifyPreserveTopology" in sql
    assert "LIMIT :limit" in sql and "OFFSET :offset" in sql
    assert "WHERE acquisition_date >= :since" in sql
    assert params["limit"] == 500 and params["offset"] == 0


def test_sql_bbox_adds_envelope_and_params():
    q = build_layer_query(days=7, limit=10, offset=0, bbox="-62,14,-60,17", until=None,
                          max_limit=100, default_limit=10, max_days=90)
    sql, params = build_sql(LAYERS["drift"], q)
    assert "ST_Intersects" in sql and "ST_MakeEnvelope" in sql
    assert params["minx"] == -62 and params["maxy"] == 17


def test_sql_never_interpolates_user_values():
    q = build_layer_query(days=7, limit=10, offset=0, bbox="-62,14,-60,17", until="2026-10-20T00:00:00Z",
                          max_limit=100, default_limit=10, max_days=90)
    sql, _ = build_sql(LAYERS["alerts"], q)
    assert "-62" not in sql and "2026-10-20" not in sql
    assert ":until" in sql


def test_every_layer_has_its_own_timestamp_column():
    assert LAYERS["sargassum"].time_column == "acquisition_date"
    assert LAYERS["drift"].time_column == "created_at"
    assert LAYERS["alerts"].time_column == "issued_at"
    # drift must never be presented as an observation timestamp
    assert "created_at" in LAYERS["drift"].properties
