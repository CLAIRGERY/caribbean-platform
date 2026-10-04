import type { Map as MLMap, GeoJSONSource } from 'maplibre-gl'
import type { FeatureCollection } from '../types/geo'

export const SRC = {
  sargassum: 'sak-sargassum',
  drift: 'sak-drift',
  marine: 'sak-marine',
} as const

/** Sargassum: thematic density palette — sea-green → sargassum gold → burnt rust. */
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
        // density_score 0..1 organic tropical palette (no purple); unknown falls back to mid
        'fill-color': [
          'interpolate',
          ['linear'],
          ['to-number', ['coalesce', ['get', 'density_score'], 0.4]],
          0.2, '#8EA85B',
          0.5, '#C3A84B',
          0.75, '#E09A38',
          0.92, '#C76832',
        ],
        'fill-opacity': 0.38,
        'fill-outline-color': '#E09A38',
      },
    })
    map.addLayer({
      id: 'sargassum-outline',
      type: 'line',
      source: SRC.sargassum,
      paint: { 'line-color': '#E09A38', 'line-width': 1.2, 'line-opacity': 0.6 },
    })
  }
}

/** Drift hero: halo corridor + crisp trajectory + fading forecast tail + endpoint glow. */
export function addDriftLayer(map: MLMap, data: FeatureCollection<Record<string, unknown>>): void {
  if (!map.getSource(SRC.drift)) {
    map.addSource(SRC.drift, { type: 'geojson', data })
  }
  if (!map.getLayer('drift-halo')) {
    map.addLayer({
      id: 'drift-halo',
      type: 'line',
      source: SRC.drift,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#F59E0B',
        'line-width': 9,
        'line-opacity': 0.13,
        'line-blur': 4,
      },
    })
  }
  if (!map.getLayer('drift-line')) {
    map.addLayer({
      id: 'drift-line',
      type: 'line',
      source: SRC.drift,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#F59E0B',
        'line-width': 2.2,
        // view: opacity keyed on forecast_time so far forecasts fade (no fabricated uncertainty)
        'line-opacity': ['case', ['has', 'forecast_time'], 0.72, 0.55],
      },
    })
  }
}

/** Marine alert severity hierarchy (normal cyan → watch amber → warning orange → critical coral). */
export function addMarineLayer(map: MLMap, data: FeatureCollection<Record<string, unknown>>): void {
  if (!map.getSource(SRC.marine)) {
    map.addSource(SRC.marine, { type: 'geojson', data })
  }
  if (!map.getLayer('marine-fill')) {
    map.addLayer({
      id: 'marine-fill',
      type: 'fill',
      source: SRC.marine,
      paint: {
        'fill-color': [
          'match',
          ['to-string', ['coalesce', ['get', 'alert_level'], 'normal']],
          'watch', '#F59E0B',
          'warning', '#F97316',
          'critical', '#FF6D4D',
          'normal', '#7DE2C3',
          '#7DE2C3',
        ],
        'fill-opacity': 0.18,
        'fill-outline-color': [
          'match',
          ['to-string', ['coalesce', ['get', 'alert_level'], 'normal']],
          'watch', '#F59E0B',
          'warning', '#F97316',
          'critical', '#FF6D4D',
          'normal', '#22D3EE',
          '#22D3EE',
        ],
      },
    })
    map.addLayer({
      id: 'marine-stroke',
      type: 'line',
      source: SRC.marine,
      paint: {
        'line-color': [
          'match',
          ['to-string', ['coalesce', ['get', 'alert_level'], 'normal']],
          'watch', '#F59E0B',
          'warning', '#F97316',
          'critical', '#FF6D4D',
          'normal', '#22D3EE',
          '#22D3EE',
        ],
        'line-width': 1.6,
        'line-opacity': 0.8,
      },
    })
  }
}

export function safeSetData(map: MLMap, srcId: string, data: FeatureCollection<Record<string, unknown>>): void {
  const src = map.getSource(srcId) as GeoJSONSource | undefined
  if (src) src.setData(data)
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
