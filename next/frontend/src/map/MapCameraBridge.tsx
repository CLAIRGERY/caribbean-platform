import { useEffect } from 'react'
import { getMap } from './index'
import { useSelection } from '../stores'

/**
 * Gentle camera: when a feature is selected, easeTo its geometry center
 * (desktop: also zoom-in one notch). 600ms motion; skip when reduced-motion.
 */
export default function MapCameraBridge() {
  const selection = useSelection((s) => s.selection)

  useEffect(() => {
    const map = getMap()
    if (!map || !selection) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const id = selection.props?.external_id as string | number | undefined
    // Search source layers for the selected feature (lightweight source query)
    try {
      const layers =
        selection.kind === 'sargassum'
          ? ['sargassum-fill']
          : selection.kind === 'drift'
            ? ['drift-line']
            : ['marine-fill']
      const feats = map.queryRenderedFeatures({ layers: layers as never }) as Array<{
        geometry: { type: string; coordinates: unknown }
      }>
      let center: [number, number] | null = null
      for (const f of feats) {
        if (String((f as { properties?: { external_id?: unknown } }).properties?.external_id) !== String(id)) continue
        const g = f.geometry as { type: string; coordinates: unknown }
        if (g?.type === 'Point') center = g.coordinates as [number, number]
        else if (g?.type === 'LineString') {
          const c = g.coordinates as [number, number][]
          center = c[Math.floor(c.length / 2)]
        } else if (g?.type === 'Polygon') {
          const ring = (g.coordinates as [number, number][][])[0]
          let sx = 0, sy = 0
          for (const [x, y] of ring) { sx += x; sy += y }
          center = [sx / ring.length, sy / ring.length]
        }
        if (center) break
      }
      if (center) {
        map.easeTo({
          center,
          zoom: Math.min(map.getZoom() + 0.6, 10),
          duration: reduced ? 0 : 650,
          essential: false,
        })
      }
    } catch {
      /* camera bridge must NEVER break the map */
    }
  }, [selection])

  return null
}
