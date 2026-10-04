import maplibregl, { type Map, type StyleSpecification } from 'maplibre-gl'

export const CARIBBEAN_CENTER: [number, number] = [-61.35, 15.15]
export const DEFAULT_ZOOM = 7.7

/**
 * Basemap sources (all verified reachable from runtime; no private keys):
 *  - satellite: NASA GIBS BlueMarble ShadedRelief+Bathymetry (public WMTS, 8 levels)
 *  - standard:  CARTO dark_all raster (readable dark cartography)
 *  - fallback:  OSM raster
 */
const GIBS_SATELLITE = [
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/BlueMarble_ShadedRelief_Bathymetry/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg',
]
const CARTO_DARK = [
  'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
  'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
]


interface RasterSpec {
  type: 'raster'
  tiles: string[]
  tileSize: number
  attribution: string
  maxzoom?: number
}

function rasterSource(satellite: boolean): RasterSpec {
  return satellite
    ? { type: 'raster', tiles: GIBS_SATELLITE, tileSize: 256, attribution: 'NASA EOSDIS GIBS / BlueMarble', maxzoom: 8 }
    : { type: 'raster', tiles: CARTO_DARK, tileSize: 256, attribution: '&copy; CARTO &copy; OpenStreetMap contributors' }
}

export function buildStyle(satellite: boolean): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: rasterSource(satellite),
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#04122A' } },
      { id: 'basemap', type: 'raster', source: 'basemap', paint: { 'raster-opacity': 1 } },
    ],
  }
}

let instance: Map | null = null

export function initMap(container: HTMLElement, satellite: boolean): Map {
  if (instance) return instance
  instance = new maplibregl.Map({
    container,
    style: buildStyle(satellite),
    center: CARIBBEAN_CENTER,
    zoom: DEFAULT_ZOOM,
    attributionControl: false,
    pitchWithRotate: false,
  })
  instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')
  instance.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-right')
  const attrib = new maplibregl.AttributionControl({ compact: true })
  instance.addControl(attrib, 'bottom-left')
  return instance
}

export function getMap(): Map | null {
  return instance
}

/** Swap the basemap raster source without touching layers above. */
export function setBasemapSatellite(map: Map, satellite: boolean): void {
  if (!map.getLayer('basemap')) return
  map.removeLayer('basemap')
  map.removeSource('basemap')
  map.addSource('basemap', rasterSource(satellite))
  map.addLayer({ id: 'basemap', type: 'raster', source: 'basemap', paint: { 'raster-opacity': 1 } })
}

export function destroyMap(): void {
  if (instance) {
    instance.remove()
    instance = null
  }
}
