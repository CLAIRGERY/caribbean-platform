import type { Map as MLMap, GeoJSONSource } from 'maplibre-gl'
import type { FeatureCollection } from '../types/geo'

export const SRC = {
  sargassum: 'sak-sargassum',
  drift: 'sak-drift',
  marine: 'sak-marine',
} as const

/** bottomsIndices: sargassum under drift under marine. */
export function addSargassumLayer(map: MLMap, data: FeatureCollection<Record<string, unknown>>): void {
  if (!map.getSource(SRC.sargassum)) {
    map.addSource(SRC.sargassum, { type: 'geojson', data })
  }
  if (!map.getLayer('sargassum-fill')) {
    map.addLayer({
      id: 'sargassum-fill',
      type: 'fill',
      source: SRC.sargassum,
      paint: {
        'fill-color': '#AB47BC',
        'fill-opacity': 0.2,
        'fill-outline-color': '#E040FB',
      },
    })
    map.addLayer({
      id: 'sargassum-outline',
      type: 'line',
      source: SRC.sargassum,
      paint: { 'line-color': '#E040FB', 'line-width': 1.1, 'line-opacity': 0.5 },
    })
  }
}

export function addDriftLayer(map: MLMap, data: FeatureCollection<Record<string, unknown>>): void {
  if (!map.getSource(SRC.drift)) {
    map.addSource(SRC.drift, { type: 'geojson', data })
  }
  if (!map.getLayer('drift-line')) {
    map.addLayer({
      id: 'drift-line',
      type: 'line',
      source: SRC.drift,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#FF6D00', 'line-width': 1.9, 'line-opacity': 0.85 },
    })
  }
}

export function addMarineLayer(map: MLMap, data: FeatureCollection<Record<string, unknown>>): void {
  if (!map.getSource(SRC.marine)) {
    map.addSource(SRC.marine, { type: 'geojson', data })
  }
  if (!map.getLayer('marine-fill')) {
    map.addLayer({
      id: 'marine-fill',
      type: 'fill',
      source: SRC.marine,
      paint: { 'fill-color': '#F59E0B', 'fill-opacity': 0.14, 'fill-outline-color': '#FFB74D' },
    })
    map.addLayer({
      id: 'marine-stroke',
      type: 'line',
      source: SRC.marine,
      paint: { 'line-color': '#F59E0B', 'line-width': 1.6, 'line-opacity': 0.8 },
    })
  }
}

export function safeSetData(map: MLMap, srcId: string, data: FeatureCollection<Record<string, unknown>>): void {
  const src = map.getSource(srcId) as GeoJSONSource | undefined
  if (src) src.setData(data as maplibregl.GeoJSONSourceSpecification['data'])
}

export function setLayerVisibility(map: MLMap, layerIds: string[], visible: boolean): void {
  for (const id of layerIds) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
  }
}

export function setSourceData(
  map: MLMap,
  srcId: string,
  data: FeatureCollection<Record<string, unknown>>,
): void {
  if (map.getSource(srcId)) {
    safeSetData(map, srcId, data)
  } else {
    map.addSource(srcId, { type: 'geojson', data })
  }
}
