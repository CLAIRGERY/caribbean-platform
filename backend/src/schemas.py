"""
Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class FeatureGeometry(BaseModel):
    type: str
    coordinates: Any


class FeatureProperties(BaseModel):
    surface_km2: Optional[float] = None
    density_score: Optional[float] = None
    density_level: Optional[str] = None
    acquisition_date: Optional[datetime] = None
    prediction_horizon_days: Optional[int] = None
    eta_hours: Optional[float] = None
    landing_probability_pct: Optional[float] = None
    target_sector: Optional[str] = None
    alert_type: Optional[str] = None
    alert_level: Optional[str] = None
    sector: Optional[str] = None
    event_name: Optional[str] = None
    wind_speed_knots: Optional[float] = None
    gust_speed_knots: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    h2s_risk: Optional[str] = None


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: FeatureGeometry
    properties: Union[FeatureProperties, Dict[str, Any]] = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    inserted: int
    endpoint: str
    errors: List[str] = Field(default_factory=list)
