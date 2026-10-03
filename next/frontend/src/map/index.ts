import maplibregl, { type Map, type StyleSpecification } from 'maplibre-gl'

export const CARIBBEAN_CENTER: [number, number] = [-61.5, 15.5]
export const DEFAULT_ZOOM = 6.2

const ESRI_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
]
const OSM_TILES = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']

function rasterSource(satellite: boolean) {
  return satellite
    ? { type: 'raster' as const, tiles: ESRI_TILES, tileSize: 256, attribution: 'Esri, Maxar, Earthstar Geographics' }
    : { type: 'raster' as const, tiles: OSM_TILES, tileSize: 256, attribution: '&copy; OpenStreetMap contributors' }
}

export function buildStyle(satellite: boolean): StyleSpecification {
  return {
    version: 8,
    sources: {
      basemap: rasterSource(satellite),
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#04122A' } },
      { id: 'basemap', type: 'raster', source: 'basemap', paint: { 'raster-opacity': 0.92 } },
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
  map.addLayer({ id: 'basemap', type: 'raster', source: 'basemap', paint: { 'raster-opacity': 0.92 } })
}

export function destroyMap(): void {
  if (instance) {
    instance.remove()
    instance = null
  }
}
