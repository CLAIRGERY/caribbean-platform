import { useEffect, useRef, useState } from 'react'
import type { FeatureCollection } from '../types/geo'
import { initMap, getMap, setBasemapSatellite, destroyMap } from './index'
import { addSargassumLayer, addDriftLayer, addMarineLayer, setLayerVisibility, setSourceData, SRC } from './layers'
import { useDetections, useDrift, useMarineAlerts, useIngestionStatus } from '../hooks/useLayers'
import { useLayers as useLayerStore, useTimeline } from '../stores'
import EmptyStateOverlay from '../components/EmptyStateOverlay'
import MapInspectorBridge from './MapInspectorBridge'
import { useTranslation } from 'react-i18next'

type Data = FeatureCollection<Record<string, unknown>>

const EMPTY: Data = { type: 'FeatureCollection', features: [] }

function tsOf(p: Record<string, unknown>): number | null {
  const v =
    (p.acquisition_date as string | undefined) ??
    (p.forecast_time as string | undefined) ??
    (p.issued_at as string | undefined) ??
    (p.generated_at as string | undefined)
  if (typeof v !== 'string') return null
  const t = Date.parse(v)
  return Number.isFinite(t) ? t : null
}

function filterByTime(data: Data | undefined, from: number | null, to: number | null): Data | undefined {
  if (!data) return undefined
  if (from === null && to === null) return data
  const feats = data.features.filter((f) => {
    const ts = tsOf(f.properties)
    if (ts === null) return from === null && to === null
    if (from !== null && ts < from) return false
    if (to !== null && ts > to) return false
    return true
  })
  return { type: 'FeatureCollection', features: feats }
}

export default function MapStage() {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const readyRef = useRef(false)
  const [ready, setReady] = useState(false)
  const layerStore = useLayerStore()
  const timeline = useTimeline()
  const detections = useDetections()
  const drift = useDrift()
  const marine = useMarineAlerts()
  const status = useIngestionStatus()

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const map = initMap(el, true)
    map.once('load', () => {
      readyRef.current = true
      setReady(true)
    })
    const onResize = () => map.resize()
    window.addEventListener('resize', onResize)
    window.addEventListener('orientationchange', onResize)
    requestAnimationFrame(() => map.resize())
    const t0 = window.setTimeout(() => map.resize(), 60)
    return () => {
      window.clearTimeout(t0)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('orientationchange', onResize)
      destroyMap()
      readyRef.current = false
      setReady(false)
    }
  }, [])

  // Sargassum
  useEffect(() => {
    const map = getMap()
    if (!map || !ready) return
    const data = detections.data ? (filterByTime(detections.data, timeline.range.from, timeline.range.to) ?? EMPTY) : null
    if (data) {
      addSargassumLayer(map, data)
      setSourceData(map, SRC.sargassum, data)
      setLayerVisibility(map, ['sargassum-fill', 'sargassum-outline'], layerStore.sargassum)
    }
  }, [detections.data, timeline.range.from, timeline.range.to, ready, layerStore.sargassum])

  // Drift
  useEffect(() => {
    const map = getMap()
    if (!map || !ready) return
    const data = drift.data ? (filterByTime(drift.data, timeline.range.from, timeline.range.to) ?? EMPTY) : null
    if (data) {
      addDriftLayer(map, data)
      setSourceData(map, SRC.drift, data)
      setLayerVisibility(map, ['drift-line'], layerStore.drift)
    }
  }, [drift.data, timeline.range.from, timeline.range.to, ready, layerStore.drift])

  // Marine
  useEffect(() => {
    const map = getMap()
    if (!map || !ready) return
    const data = marine.data ? (filterByTime(marine.data, timeline.range.from, timeline.range.to) ?? EMPTY) : null
    if (data) {
      addMarineLayer(map, data)
      setSourceData(map, SRC.marine, data)
      setLayerVisibility(map, ['marine-fill', 'marine-stroke'], layerStore.marine)
    }
  }, [marine.data, timeline.range.from, timeline.range.to, ready, layerStore.marine])

  // Visibility toggles
  useEffect(() => {
    const map = getMap()
    if (!map) return
    setLayerVisibility(map, ['sargassum-fill', 'sargassum-outline'], layerStore.sargassum)
    setLayerVisibility(map, ['drift-line'], layerStore.drift)
    setLayerVisibility(map, ['marine-fill', 'marine-stroke'], layerStore.marine)
  }, [layerStore.sargassum, layerStore.drift, layerStore.marine, ready])

  // Basemap
  useEffect(() => {
    const map = getMap()
    if (!map || !ready) return
    setBasemapSatellite(map, layerStore.satelliteBasemap)
  }, [layerStore.satelliteBasemap, ready])

  const anyFilterActive = timeline.range.from !== null || timeline.range.to !== null
  const hasAnyData =
    (detections.data?.features.length ?? 0) + (drift.data?.features.length ?? 0) + (marine.data?.features.length ?? 0) > 0

  const filterHidesAll =
    anyFilterActive &&
    hasAnyData &&
    (filterByTime(detections.data, timeline.range.from, timeline.range.to)?.features.length ?? 0) === 0 &&
    (filterByTime(drift.data, timeline.range.from, timeline.range.to)?.features.length ?? 0) === 0 &&
    (filterByTime(marine.data, timeline.range.from, timeline.range.to)?.features.length ?? 0) === 0

  return (
    <div ref={containerRef} className="sak-map-container" role="application" aria-label={t('layers.layersTitle') as string}>
      <MapInspectorBridge />
      {!ready && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="animate-pulse text-sm text-cyan-100/70">{t('loading.initializing')}</span>
        </div>
      )}
      {ready && status.isSuccess && detections.isSuccess && !hasAnyData && <EmptyStateOverlay status={status.data} />}
      {ready && filterHidesAll && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-4">
          <div className="sak-glass px-4 py-3 text-sm text-amber-100/90">{t('timeline.hiddenByFilter')}</div>
        </div>
      )}
    </div>
  )
}
