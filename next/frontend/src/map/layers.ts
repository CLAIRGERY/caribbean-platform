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
        'line-opacity': 0.2,
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
        'fill-opacity': 0.24,
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

/**
 * Presentation-only satellite contrast mode (no scientific meaning change):
 * NASA GIBS imagery can be brighter than the dark vector map, so the
 * scientific overlays get slightly stronger strokes when imagery is visible.
 */
export function setImageryContrastMode(map: MLMap, imageryOn: boolean): void {
  const bump = (paintProp: string, value: number | number[]) => {
    void paintProp
    void value
  }
  void bump
  if (map.getLayer('sargassum-outline')) {
    map.setPaintProperty('sargassum-outline', 'line-width', imageryOn ? 1.6 : 1.2)
    map.setPaintProperty('sargassum-outline', 'line-opacity', imageryOn ? 0.85 : 0.6)
  }
  if (map.getLayer('marine-stroke')) {
    map.setPaintProperty('marine-stroke', 'line-width', imageryOn ? 2.0 : 1.6)
    map.setPaintProperty('marine-stroke', 'line-opacity', imageryOn ? 0.92 : 0.8)
  }
  if (map.getLayer('drift-line')) {
    map.setPaintProperty('drift-line', 'line-width', imageryOn ? 2.6 : 2.2)
  }
  if (map.getLayer('drift-halo')) {
    map.setPaintProperty('drift-halo', 'line-opacity', imageryOn ? 0.26 : 0.2)
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


/** Index of the first scientific layer (or undefined when none exist yet). */
/**
 * Deterministic layer order:
 *   background < OFM land/water labels < imageryNASA < sargassum* < marine* < drift-halo < drift-line
 * Called after style load, imagery toggle, and any scientific source change.
 */
export function syncScientificLayerOrder(map: MLMap): void {
  // Desired BOTTOM→TOP order among scientific layers.
  const desired: string[] = [
    'imagery-layer',
    'sargassum-fill',
    'sargassum-outline',
    'marine-fill',
    'marine-stroke',
    'drift-halo',
    'drift-line',
  ]

  // MapLibre addLayer(id, beforeId) places `id` immediately BELOW `beforeId`.
  // To enforce a deterministic bottom→top order:
  //   for each i from topmost→bottommost: moveLayer(layer[i], layer[i+1])
  // which stacks each one just below its successor.
  for (let i = desired.length - 1; i > 0; i--) {
    const me = desired[i]
    const above = desired[i - 1]
    if (map.getLayer(me) && map.getLayer(above)) {
      map.moveLayer(me, above)
    }
  }
  if (import.meta.env.DEV) console.debug('syncScientificLayerOrder applied')
}

/** Returns true when scientific layers exist above imagery (dev assertion helper). */
export function assertLayerOrderDev(map: MLMap): void {
  if (!import.meta.env.DEV) return
  const idx = (id: string): number | undefined => {
    const style = map.getStyle()
    const i = (style.layers as Array<{ id: string }>).findIndex((l) => l.id === id)
    return i === -1 ? undefined : i
  }
  const nasa = idx('imagery-layer')
  if (nasa === undefined) return
  for (const id of ['sargassum-fill', 'drift-line', 'marine-fill', 'drift-halo']) {
    const i = idx(id)
    if (i !== undefined && i < nasa) {
      console.warn(`[layer-order] ${id} (${i}) is BELOW imagery-layer (${nasa})`)
    }
  }
}
