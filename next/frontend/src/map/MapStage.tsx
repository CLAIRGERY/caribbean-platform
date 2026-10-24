import { useEffect, useRef, useState } from 'react'
import type { FeatureCollection } from '../types/geo'
import { initMap, getMap, setImageryVisible, destroyMap } from './index'
import { addSargassumLayer, addDriftLayer, addMarineLayer, setLayerVisibility, setSourceData, SRC, syncScientificLayerOrder, assertLayerOrderDev, setImageryContrastMode } from './layers'
import { useDetections, useDrift, useMarineAlerts, useIngestionStatus } from '../hooks/useLayers'
import { useLayers as useLayerStore, useTimeline } from '../stores'
import EmptyStateOverlay from '../components/EmptyStateOverlay'
import MapInspectorBridge from './MapInspectorBridge'
import MapCameraBridge from './MapCameraBridge'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'

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
  const [scanActive, setScanActive] = useState(false)
  const scanFired = useRef(false)

  // Satellite scan sweep: single pulse when the first detections dataset arrives.
  useEffect(() => {
    if (!detections.isSuccess || scanFired.current) return
    scanFired.current = true
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) return
    setScanActive(true)
    const t0 = window.setTimeout(() => setScanActive(false), 1500)
    return () => window.clearTimeout(t0)
  }, [detections.isSuccess])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const satelliteOn = useLayerStore.getState().satelliteBasemap
    const map = initMap(el, satelliteOn)
    const markReady = () => {
      if (readyRef.current) return
      readyRef.current = true
      setReady(true)
      map.resize()
    }
    // 'load' is the clean signal; fall back to 'idle' or first tick in case of blocked style events
    map.once('load', () => {
      markReady()
      setImageryVisible(map, satelliteOn)
    })
    map.once('idle', markReady)
    window.setTimeout(markReady, 2500)
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
      syncScientificLayerOrder(map)
      assertLayerOrderDev(map)
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
      setLayerVisibility(map, ['drift-line', 'drift-halo'], layerStore.drift)
      syncScientificLayerOrder(map)
      assertLayerOrderDev(map)
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
      syncScientificLayerOrder(map)
      assertLayerOrderDev(map)
    }
  }, [marine.data, timeline.range.from, timeline.range.to, ready, layerStore.marine])

  // Visibility toggles
  useEffect(() => {
    const map = getMap()
    if (!map) return
    setLayerVisibility(map, ['sargassum-fill', 'sargassum-outline'], layerStore.sargassum)
    setLayerVisibility(map, ['drift-line', 'drift-halo'], layerStore.drift)
    setLayerVisibility(map, ['marine-fill', 'marine-stroke'], layerStore.marine)
  }, [layerStore.sargassum, layerStore.drift, layerStore.marine, ready])

  // Imagery (Satellite toggle) — always re-syncs scientific order above it
  useEffect(() => {
    const map = getMap()
    if (!map || !ready) return
    setImageryVisible(map, layerStore.satelliteBasemap)
    syncScientificLayerOrder(map)
    setImageryContrastMode(map, layerStore.satelliteBasemap)
    assertLayerOrderDev(map)
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
      <MapCameraBridge />
      {/* V3 ocean atmosphere: bathymetric depth field, caustics, currents, coast glow, vignette */}
      <div className="sak-atmo-bathy" aria-hidden="true" />
      <div className="sak-atmo-caustics" aria-hidden="true" />
      <div className="sak-atmo-currents" aria-hidden="true" />
      <div className="sak-atmo-coast" aria-hidden="true" />
      <div className="sak-vignette" aria-hidden="true" />
      {scanActive && (
        <motion.div
          className="sak-scan-sweep"
          initial={{ top: '12%', opacity: 0 }}
          animate={{ top: ['38%', '78%'], opacity: [0, 0.9, 0] }}
          transition={{ duration: 1.4, ease: 'easeInOut' }}
          aria-hidden="true"
        />
      )}
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
