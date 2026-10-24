import { useEffect } from 'react'
import { getMap } from './index'
import { SRC } from './layers'
import { useSelection, type Selection } from '../stores'

/** Binds map click events to the inspector selection store; never breaks the map. */
export default function MapInspectorBridge() {
  const select = useSelection((s) => s.select)
  const clear = useSelection((s) => s.clear)

  useEffect(() => {
    const map = getMap()
    if (!map) return
    const onClick = (e: { point?: { x: number; y: number }; features?: unknown[] }) => {
      const feats = e.features
      if (!feats || feats.length === 0) {
        clear()
        return
      }
      for (const f of feats as Array<{ source?: string; properties?: Record<string, unknown>; id?: string | number }>) {
        if (!f.properties) continue
        let kind: Selection['kind'] | null = null
        if (f.source === SRC.sargassum) kind = 'sargassum'
        else if (f.source === SRC.drift) kind = 'drift'
        else if (f.source === SRC.marine) kind = 'marine'
        if (kind) {
          select({
            kind,
            id: String(f.id ?? f.properties.external_id ?? Math.random()),
            props: f.properties,
          })
          return
        }
      }
    }
    map.on('click', onClick as never)
    return () => {
      map.off('click', onClick as never)
    }
  }, [select, clear])

  return null
}
