/**
 * Geo types mirroring the SaKgaZé API (/api/v1, /api/v2-ready).
 * Only fields actually emitted by the backend are typed. Never invent data.
 */

export interface CommonProps {
  source?: string
  external_id?: string
  [key: string]: unknown
}

export interface SargassumProps extends CommonProps {
  acquisition_date?: string
  surface_km2?: number
  density?: number
  density_score?: number
}

export interface DriftProps extends CommonProps {
  seed_id?: string
  forecast_horizon_h?: number
  forecast_time?: string
  generated_at?: string
  velocity_kmh?: number
  seed_surface_km2?: number
}

export interface MarineProps extends CommonProps {
  alert_level?: string
  severity?: string
  sector?: string
  wind_kmh?: number
  wave_height_m?: number
  eta?: string
  issued_at?: string
  text_fr?: string
  text_en?: string
}

export type CommonGeom =
  | { type: 'Point'; coordinates: [number, number] }
  | { type: 'MultiPoint'; coordinates: [number, number][] }
  | { type: 'LineString'; coordinates: [number, number][] }
  | { type: 'MultiLineString'; coordinates: [number, number][][] }
  | { type: 'Polygon'; coordinates: [number, number][][] }
  | { type: 'MultiPolygon'; coordinates: [number, number][][][] }

export interface GeoFeature<P extends CommonProps> {
  type: 'Feature'
  id?: string | number
  geometry: CommonGeom
  properties: P
}

export interface FeatureCollection<P extends CommonProps> {
  type: 'FeatureCollection'
  features: GeoFeature<P>[]
}

export interface IngestionStatus {
  [key: string]: unknown
}
