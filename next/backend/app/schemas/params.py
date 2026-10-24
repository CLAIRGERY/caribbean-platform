"""Query-parameter parsing and validation (pure functions, unit-testable).

Every parameter is bounded. Nothing is interpolated into SQL: values travel as
bound parameters, and this module is the only place that decides what a
parameter means.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from app.core.errors import InvalidParameter

BBox = Tuple[float, float, float, float]


def parse_bbox(raw: Optional[str]) -> Optional[BBox]:
    """Parse ``minx,miny,maxx,maxy`` (EPSG:4326) or return None.

    Rejects: wrong arity, non-numeric, out-of-range, inverted axes and
    antimeridian-crossing boxes (unsupported by ST_MakeEnvelope on one envelope).
    """
    if raw is None or raw.strip() == "":
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise InvalidParameter(
            "bbox must be 'minx,miny,maxx,maxy'",
            details={"received": raw, "expected_arity": 4},
        )
    try:
        minx, miny, maxx, maxy = (float(p) for p in parts)
    except ValueError:
        raise InvalidParameter("bbox values must be numbers", details={"received": raw})
    for value in (minx, miny, maxx, maxy):
        if value != value:  # NaN
            raise InvalidParameter("bbox values must be finite numbers")
    if not (-180.0 <= minx <= 180.0 and -180.0 <= maxx <= 180.0):
        raise InvalidParameter("bbox longitude must be within [-180, 180]", details={"received": raw})
    if not (-90.0 <= miny <= 90.0 and -90.0 <= maxy <= 90.0):
        raise InvalidParameter("bbox latitude must be within [-90, 90]", details={"received": raw})
    if minx >= maxx or miny >= maxy:
        raise InvalidParameter(
            "bbox must satisfy minx < maxx and miny < maxy (antimeridian-crossing boxes are not supported)",
            details={"received": raw},
        )
    return (minx, miny, maxx, maxy)


def parse_days(raw: Optional[int], *, maximum: int) -> int:
    days = 7 if raw is None else int(raw)
    if days < 1 or days > maximum:
        raise InvalidParameter(f"days must be between 1 and {maximum}", details={"received": days})
    return days


def parse_limit(raw: Optional[int], *, maximum: int, default: int) -> int:
    limit = default if raw is None else int(raw)
    if limit < 1:
        raise InvalidParameter("limit must be >= 1", details={"received": limit})
    if limit > maximum:
        raise InvalidParameter(f"limit must be <= {maximum}", details={"received": limit, "max": maximum})
    return limit


def parse_offset(raw: Optional[int]) -> int:
    offset = 0 if raw is None else int(raw)
    if offset < 0:
        raise InvalidParameter("offset must be >= 0", details={"received": offset})
    if offset > 1_000_000:
        raise InvalidParameter("offset is unreasonably large", details={"received": offset})
    return offset


def parse_until(raw: Optional[str]) -> Optional[datetime]:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidParameter("until must be an ISO-8601 timestamp", details={"received": raw})
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class LayerQuery:
    """Validated query for one map layer."""

    days: int
    limit: int
    offset: int
    bbox: Optional[BBox]
    until: Optional[datetime]

    @property
    def since(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=self.days)

    def meta(self) -> Dict[str, object]:
        return {
            "days": self.days,
            "limit": self.limit,
            "offset": self.offset,
            "bbox": list(self.bbox) if self.bbox else None,
            "until": self.until.isoformat() if self.until else None,
        }


def build_layer_query(
    *,
    days: Optional[int],
    limit: Optional[int],
    offset: Optional[int],
    bbox: Optional[str],
    until: Optional[str],
    max_limit: int,
    default_limit: int,
    max_days: int,
) -> LayerQuery:
    return LayerQuery(
        days=parse_days(days, maximum=max_days),
        limit=parse_limit(limit, maximum=max_limit, default=default_limit),
        offset=parse_offset(offset),
        bbox=parse_bbox(bbox),
        until=parse_until(until),
    )
