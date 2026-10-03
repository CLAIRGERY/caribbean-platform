import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useTimeline } from '../stores'
import { useDetections, useDrift, useMarineAlerts } from '../hooks/useLayers'

/**
 * Timeline built ONLY from real timestamps present in the data.
 * When a filter is active a Reset control appears; if the filter hides
 * everything, MapStage shows an explanatory banner (never a silent empty map).
 */
export default function Timeline() {
  const { t } = useTranslation()
  const range = useTimeline((s) => s.range)
  const setRange = useTimeline((s) => s.setRange)
  const reset = useTimeline((s) => s.reset)
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()

  const stamps = useMemo(() => {
    const all: number[] = []
    for (const q of [det, drf, mar]) {
      if (!q.data) continue
      for (const f of q.data.features) {
        const p = f.properties
        const v =
          (p.acquisition_date as string | undefined) ??
          (p.forecast_time as string | undefined) ??
          (p.issued_at as string | undefined) ??
          (p.generated_at as string | undefined)
        if (typeof v === 'string') {
          const ts = Date.parse(v)
          if (Number.isFinite(ts)) all.push(ts)
        }
      }
    }
    all.sort((a, b) => a - b)
    return all
  }, [det.data, drf.data, mar.data])

  if (stamps.length < 2) return null

  const min = stamps[0]
  const max = stamps[stamps.length - 1]
  const active = range.from !== null || range.to !== null
  const sliderPos =
    range.to !== null && max > min ? Math.round(((range.to - min) / (max - min)) * 100) : 100

  const onChange = (v: number) => {
    const ms = min + ((max - min) * v) / 100
    setRange({ from: null, to: ms })
  }

  const locale = navigator.language.startsWith('fr') ? 'fr-FR' : 'en-US'
  const fmt = (ms: number) =>
    new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(
      new Date(ms),
    )

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="pointer-events-auto absolute bottom-4 left-1/2 z-30 w-[min(560px,calc(100%-1.5rem))] -translate-x-1/2"
    >
      {active && (
        <div className="mb-1.5 flex items-center justify-center">
          <button
            type="button"
            onClick={() => reset()}
            className="sak-glass min-h-[44px] px-3 py-2 text-[11px] text-cyan-200 hover:text-cyan-100"
          >
            ↔ {t('timeline.reset')}
          </button>
        </div>
      )}
      <div className="sak-glass sak-luminous-border px-4 py-3">
        <div className="mb-1 flex items-center justify-between text-[10px] text-white/50">
          <span>{fmt(min)}</span>
          <span className="text-cyan-200/80">{range.to !== null ? fmt(range.to) : t('timeline.now')}</span>
          <span>{fmt(max)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={sliderPos}
          onChange={(e) => onChange(Number(e.target.value))}
          className="sak-timeline-slider w-full"
          aria-label={t('timeline.title') as string}
        />
      </div>
    </motion.div>
  )
}
