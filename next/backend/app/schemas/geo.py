"""GeoJSON + status response models (Pydantic v2).

GeoJSON allows foreign members, so ``meta`` travels inside the FeatureCollection.
The frontend therefore keeps receiving a plain GeoJSON document it can hand
straight to MapLibre.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

GeometryType = Literal["Point", "LineString", "Polygon", "MultiLineString", "MultiPolygon"]


class Geometry(BaseModel):
    type: GeometryType
    coordinates: Any

    @field_validator("coordinates")
    @classmethod
    def _not_empty(cls, value: Any) -> Any:
        if value is None or value == []:
            raise ValueError("geometry coordinates must not be empty")
        return value


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: Optional[Any] = None
    geometry: Optional[Geometry] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class FeatureMeta(BaseModel):
    count: int
    limit: int
    offset: int
    days: Optional[int] = None
    bbox: Optional[List[float]] = None
    until: Optional[str] = None
    latest_data_timestamp: Optional[str] = None
    simplified: bool = True
    source: str
    generated_at: str


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[Feature] = Field(default_factory=list)
    meta: Optional[FeatureMeta] = None


class SourceStatus(BaseModel):
    """Freshness of one scientific source, as observed — never as assumed."""

    key: str
    label: str
    last_success: Optional[datetime] = None
    latest_data_timestamp: Optional[datetime] = None
    record_count: int = 0
    freshness: Literal["LIVE", "RECENT", "STALE", "UNAVAILABLE", "UNKNOWN"] = "UNKNOWN"
    age_hours: Optional[float] = None
    thresholds_hours: Dict[str, float] = Field(default_factory=dict)
    note: Optional[str] = None


class IngestionRunSummary(BaseModel):
    source: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    records_downloaded: int = 0
    records_inserted: int = 0
    records_skipped: int = 0
    records_rejected: int = 0
    latest_data_timestamp: Optional[datetime] = None
    error: Optional[str] = None


class StatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    api_version: str
    environment: str
    database: Literal["ok", "unavailable", "not_configured"]
    generated_at: datetime
    sources: List[SourceStatus] = Field(default_factory=list)
    latest_runs: List[IngestionRunSummary] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "sakgaze-api-v2"
    version: str
