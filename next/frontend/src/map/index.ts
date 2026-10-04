import maplibregl, { type Map } from 'maplibre-gl'

export const CARIBBEAN_CENTER: [number, number] = [-61.35, 15.15]
export const DEFAULT_ZOOM = 7.7

/**
 * Basemap (verified + truly keyless):
 *  standard: OpenFreeMap "dark" vector style (https://tiles.openfreemap.org/styles/dark)
 *            vector tiles + glyphs/sprites all public, no API key.
 *  imagery:  NASA EOSDIS GIBS BlueMarble ShadedRelief+Bathymetry raster (public WMTS, 8 levels).
 *
 * Removed sources (not usable): Esri World Imagery (403 blocked from our network),
 * CARTO basemaps.dark_all (now serves an "API KEY REQUIRED" watermark tile to anonymous clients).
 */
export const OFM_DARK_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark'

const GIBS_SATELLITE = [
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/BlueMarble_ShadedRelief_Bathymetry/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg',
]

interface RasterSpec {
  type: 'raster'
  tiles: string[]
  tileSize: number
  attribution: string
  maxzoom?: number
}

export const IMAGERY_LABEL: Record<'fr' | 'en', string> = {
  fr: 'Imagerie NASA',
  en: 'NASA imagery',
}

/**
 * Dark vector style is loaded from its public URL; we inject the GIBS raster
 * source at runtime AFTER the style loads so the geographic basemap is never
 * blank and the imagery overlays (or replaces) the background cleanly.
 */
export function standardStyle(): string {
  return OFM_DARK_STYLE_URL
}

let instance: Map | null = null

export function initMap(container: HTMLElement, _satellite = false): Map {
  if (instance) return instance
  instance = new maplibregl.Map({
    container,
    style: standardStyle(),
    center: CARIBBEAN_CENTER,
    zoom: DEFAULT_ZOOM,
    attributionControl: false,
    pitchWithRotate: false,
  })

  // Attach the imagery raster source once the style is on-screen.
  instance.once('load', () => {
    const m = instance as Map
    if (!m.getSource('imagery')) {
      m.addSource('imagery', satelliteSpec())
    }
  })

  instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')
  instance.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-right')
  const attrib = new maplibregl.AttributionControl({ compact: true })
  instance.addControl(attrib, 'bottom-left')
  return instance
}

function satelliteSpec(): RasterSpec {
  return {
    type: 'raster',
    tiles: GIBS_SATELLITE,
    tileSize: 256,
    attribution: 'NASA EOSDIS GIBS',
    maxzoom: 8,
  }
}

/** Toggle Earth imagery raster above the dark vector basemap. */
export function setImageryVisible(map: Map, visible: boolean): void {
  if (!visible) {
    if (map.getLayer('imagery-layer')) map.removeLayer('imagery-layer')
    return
  }
  if (!map.getSource('imagery')) map.addSource('imagery', satelliteSpec())
  if (!map.getLayer('imagery-layer')) {
    // Insert as the bottom-most layer above background so vector labels stack above it
    map.addLayer({ id: 'imagery-layer', type: 'raster', source: 'imagery', paint: { 'raster-opacity': 1 } })
  }
}

/**
 * Legacy helper kept for compatibility: 'satellite' now toggles the imagery
 * raster overlay instead of swapping the whole style (labels retained).
 */
export function setBasemapSatellite(map: Map, satellite: boolean): void {
  setImageryVisible(map, satellite)
}

export function getMap(): Map | null {
  return instance
}

export function destroyMap(): void {
  if (instance) {
    instance.remove()
    instance = null
  }
}
