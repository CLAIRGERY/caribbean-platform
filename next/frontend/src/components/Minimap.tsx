import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import { getMap } from '../map'

/**
 * Compact navigation minimap: mirrored Caribbean overview with a viewport
 * frame. Uses its own tiny MapLibre instance (cheap raster) — remains in sync
 * on every move of the main map.
 */
export default function Minimap() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const minimapObjRef = useRef<maplibregl.Map | null>(null)
  const frameRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const mini = new maplibregl.Map({
      container: el,
      style: {
        version: 8,
        sources: {
          base: {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '&copy; CARTO OSM',
          },
        },
        layers: [{ id: 'base', type: 'raster', source: 'base' }],
      },
      center: [-61.5, 15.5],
      zoom: 2.4,
      attributionControl: false,
      interactive: true,
    })
    minimapObjRef.current = mini
    setTimeout(() => mini.resize(), 100)

    const sync = () => {
      const main = getMap()
      const miniMap = minimapObjRef.current
      const frame = frameRef.current
      if (!main || !miniMap || !frame) return
      if (frame.dataset.syncing === '1' ) return

      // Project main viewport bounds into minimap coordinates
      frame.dataset.syncing = '1'
      try {
        const bounds = main.getBounds()
        const nw = mini.project([bounds.getWest(), bounds.getNorth()])
        const se = mini.project([bounds.getEast(), bounds.getSouth()])
        const rect = miniMap.getCanvas().getBoundingClientRect()
        const rect0 = el.getBoundingClientRect()
        const x1 = (nw.x / rect.width) * rect0.width
        const y1 = (nw.y / rect.height) * rect0.height
        const x2 = (se.x / rect.width) * rect0.width
        const y2 = (se.y / rect.height) * rect0.height
        frame.style.left = `${Math.min(x1, x2)}px`
        frame.style.top = `${Math.min(y1, y2)}px`
        frame.style.width = `${Math.abs(x2 - x1)}px`
        frame.style.height = `${Math.abs(y2 - y1)}px`
      } catch {
        /* ignore sync failures */
      }
      setTimeout(() => {
        if (frame) frame.dataset.syncing = ''
      }, 20)
    }

    const main = getMap()
    if (main) main.on('move', sync)
    mini.on('move', () => sync())
    setTimeout(() => sync(), 200)

    return () => {
      const main = getMap()
      if (main) main.off('move', sync)
      mini.remove()
      minimapObjRef.current = null
    }
  }, [])

  return (
    <div className="sak-minimap hidden sm:block" role="complementary" aria-label="Minimap overview">
      <div ref={containerRef} className="absolute inset-0" style={{ width: '100%', height: '100%' }} />
      <div ref={frameRef} className="sak-mvp-frame" style={{ border: '2px solid rgba(103,232,249,0.5)', boxShadow: '0 0 12px rgba(103,232,249,0.35)' }} />
    </div>
  )
}
