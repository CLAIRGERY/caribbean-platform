import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useTimeline } from '../stores'
import { useDetections, useDrift, useMarineAlerts } from '../hooks/useLayers'
import { OCEAN } from './premium'

/**
 * Floating timeline ribbon — REAL timestamps only, with observation/forecast
 * separation. When no range exists shows "Dernière observation" (never fake ticks).
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
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto absolute bottom-4 left-1/2 z-30 w-[min(560px,calc(100%-1.5rem))] -translate-x-1/2"
    >
      {active && (
        <div className="mb-1.5 flex items-center justify-center">
          <button
            type="button"
            onClick={() => reset()}
            className="sak-glow-btn"
            style={{ minHeight: 36, fontSize: 10 }}
          >
            ↔ {t('timeline.reset')}
          </button>
        </div>
      )}
      <div className="sak-glass sak-luminous-border px-4 py-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="sak-kicker">{t('timeline.observation')}</span>
          <span
            className="text-[10px] font-semibold uppercase tracking-widest"
            style={{ color: range.to !== null ? OCEAN.cyanGlow : 'rgba(255,255,255,0.35)' }}
          >
            {range.to !== null ? fmt(range.to) : t('timeline.now')}
          </span>
          <span className="sak-kicker">{t('timeline.forecast')}</span>
        </div>
        <div className="relative">
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
          {/* glowing current-time notch */}
          <span
            aria-hidden
            className="pointer-events-none absolute"
            style={{
              left: `calc(${Math.min(100, Math.max(0, sliderPos))}% - 1px)`,
              top: -6,
              width: 2,
              height: 18,
              borderRadius: 1,
              background: '#EAF6FF',
              boxShadow: '0 0 10px #67E8F9, 0 0 22px rgba(103,232,249,.5)',
            }}
          />
        </div>
      </div>
    </motion.div>
  )
}
