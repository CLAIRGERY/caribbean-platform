"""
Central configuration for the integrated Caribbean platform.
Handles environment variables and shared constants for:
- SaKgaZé (sargassum satellite detection)
- Weathernext (marine weather / cyclones)
- Coupled drift engine & risk scoring
"""
import os
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# AOI: Caribbean Basin & Lesser Antilles (WGS84)
# ---------------------------------------------------------------------------
AOI_BBOX = (-89.0, 7.0, -59.0, 27.0)  # minx, miny, maxx, maxy
CRS_WGS84 = "EPSG:4326"

# ---------------------------------------------------------------------------
# FastAPI backend
# ---------------------------------------------------------------------------
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_BASE_URL = os.getenv("API_BASE_URL", f"http://{API_HOST}:{API_PORT}")

# ---------------------------------------------------------------------------
# PostgreSQL / PostGIS
# ---------------------------------------------------------------------------
POSTGRES_USER = os.getenv("POSTGRES_USER", "ludovic.clairgery")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "caribbean_platform")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)
SYNC_DATABASE_URL = DATABASE_URL

# ---------------------------------------------------------------------------
# Copernicus Data Space Ecosystem (CDSE)
# ---------------------------------------------------------------------------
CDSE_AUTH_URL = os.getenv("CDSE_AUTH_URL", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token")
CDSE_CLIENT_ID = os.getenv("CDSE_CLIENT_ID", "cdse-public")
CDSE_STAC_URL = os.getenv("CDSE_STAC_URL", "https://catalogue.dataspace.copernicus.eu/stac")
CDSE_ODATA_URL = os.getenv("CDSE_ODATA_URL", "https://catalogue.dataspace.copernicus.eu/odata/v1")
CDSE_USERNAME = os.getenv("CDSE_USERNAME", "")
CDSE_PASSWORD = os.getenv("CDSE_PASSWORD", "")

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------
NHC_ATOM_URL = os.getenv("NHC_ATOM_URL", "https://www.nhc.noaa.gov/index-at.xml")
NHC_GIS_URL = os.getenv("NHC_GIS_URL", "https://www.nhc.noaa.gov/CurrentStorms.json")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://marine-api.open-meteo.com/v1/marine")
OPEN_METEO_WEATHER_URL = os.getenv("OPEN_METEO_WEATHER_URL", "https://api.open-meteo.com/v1/forecast")

# ---------------------------------------------------------------------------
# Processing knobs
# ---------------------------------------------------------------------------
S2_MAX_CLOUD_COVER = float(os.getenv("S2_MAX_CLOUD_COVER", "20"))
S2_COLLECTION = os.getenv("S2_COLLECTION", "SENTINEL-2")
S2_PRODUCT_TYPE = os.getenv("S2_PRODUCT_TYPE", "S2MSI2A")
FAI_THRESHOLD = float(os.getenv("FAI_THRESHOLD", "0.008"))
MIN_PATCH_AREA_KM2 = float(os.getenv("MIN_PATCH_AREA_KM2", "0.01"))

# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", "2"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))

# ---------------------------------------------------------------------------
# Coastal sectors (name, approximate centroid, buffer km)
# ---------------------------------------------------------------------------
COASTAL_SECTORS = {
    "Guadeloupe": {"lon": -61.55, "lat": 16.27, "buffer_km": 25.0},
    "Martinique": {"lon": -61.02, "lat": 14.64, "buffer_km": 25.0},
    "St. Martin": {"lon": -63.05, "lat": 18.07, "buffer_km": 20.0},
    "St. Barths": {"lon": -62.83, "lat": 17.90, "buffer_km": 15.0},
    "Dominica": {"lon": -61.37, "lat": 15.41, "buffer_km": 20.0},
    "St. Lucia": {"lon": -60.98, "lat": 13.91, "buffer_km": 20.0},
    "Barbados": {"lon": -59.54, "lat": 13.19, "buffer_km": 20.0},
    "Grenada": {"lon": -61.72, "lat": 12.12, "buffer_km": 20.0},
}


def ensure_output_dir() -> Path:
    out = ROOT / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out
