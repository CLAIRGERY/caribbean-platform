import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import { useSelection, useUI } from '../stores'
import { OCEAN, WaveSeparator } from './premium'

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-white/5 py-1.5 last:border-0">
      <span className="text-[10px] uppercase tracking-wide text-white/45">{label}</span>
      <span className="text-sm font-medium text-white/90" style={color ? { color } : undefined}>
        {value}
      </span>
    </div>
  )
}

const fmt1 = (v: unknown, unit = ''): string | null => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return null
  return `${v.toFixed(1)}${unit}`
}

const fmtDate = (v: unknown): string | null => {
  if (typeof v !== 'string') return null
  const ts = Date.parse(v)
  if (!Number.isFinite(ts)) return null
  const locale = navigator.language.startsWith('fr') ? 'fr-FR' : 'en-US'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(ts))
}

function densityLabel(score: unknown): string | null {
  if (typeof score !== 'number' || !Number.isFinite(score)) return null
  // bucket with i18n-friendly approximations (never invented numbers)
  return score >= 0.75 ? 'HIGH' : score >= 0.45 ? 'MOD' : 'LOW'
}

const KIND_META: Record<'sargassum' | 'drift' | 'marine', { label: string; glow: string }> = {
  sargassum: { label: 'SARGASSES', glow: OCEAN.ochre },
  drift: { label: 'DÉRIVE', glow: OCEAN.amber },
  marine: { label: 'ALERTES', glow: OCEAN.coral },
}

/** Premium data panel — large metric + tiny metadata + luminous separation. */
export default function Inspector() {
  const { t, i18n } = useTranslation()
  const selection = useSelection((s) => s.selection)
  const clear = useSelection((s) => s.clear)
  const menuOpen = useUI((s) => s.mobileMenuOpen)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') clear()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [clear])

  const isOpen = Boolean(selection) && !menuOpen

  return (
    <AnimatePresence>
      {isOpen && selection && (
        <motion.aside
          key="inspector"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ ease: [0.22, 1, 0.36, 1], duration: 0.24 }}
          className="pointer-events-auto absolute bottom-24 right-3 z-40 w-[min(330px,calc(100%-1.5rem))] sm:bottom-28 sm:right-4"
          role="complementary"
          aria-label={t('inspector.title') as string}
        >
          <div className="sak-glass sak-glass--strong sak-luminous-border p-4">
            {/* kicker */}
            <div className="mb-2 flex items-center justify-between">
              <span
                className="sak-kicker"
                style={{ color: KIND_META[selection.kind].glow, opacity: 0.9 }}
              >
                {KIND_META[selection.kind].label}
              </span>
              <button
                type="button"
                onClick={clear}
                aria-label={t('inspector.close') as string}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-white/60 hover:bg-white/10"
              >
                <span aria-hidden>✕</span>
              </button>
            </div>

            {/* primary metric */}
            {selection.kind === 'sargassum' && (
              <>
                <div className="sak-metric">
                  {fmt1(selection.props.surface_km2, '') ?? '—'}
                  {fmt1(selection.props.surface_km2, '') && (
                    <span className="ml-1 text-sm font-normal text-white/60">km²</span>
                  )}
                </div>
                <WaveSeparator color={OCEAN.ochre} />
                <div className="space-y-0.5">
                  {densityLabel(selection.props.density_score) && (
                    <Row
                      label={t('inspector.density') as string}
                      value={densityLabel(selection.props.density_score) as string}
                    />
                  )}
                  {fmtDate(selection.props.acquisition_date) && (
                    <Row
                      label={t('inspector.acquisitionDate') as string}
                      value={fmtDate(selection.props.acquisition_date) as string}
                    />
                  )}
                  {typeof selection.props.source === 'string' && (
                    <Row label={t('inspector.source') as string} value={selection.props.source} />
                  )}
                </div>
              </>
            )}

            {selection.kind === 'drift' && (
              <>
                <div className="sak-metric" style={{ color: OCEAN.gold }}>
                  {typeof selection.props.forecast_horizon_h === 'number'
                    ? `+${selection.props.forecast_horizon_h}h`
                    : '—'}
                </div>
                <WaveSeparator color={OCEAN.amber} />
                <div className="space-y-0.5">
                  {fmt1(selection.props.velocity_kmh, ' km/h') && (
                    <Row
                      label={t('inspector.velocity') as string}
                      value={fmt1(selection.props.velocity_kmh, ' km/h') as string}
                    />
                  )}
                  {fmtDate(selection.props.forecast_time) && (
                    <Row label={t('inspector.eta') as string} value={fmtDate(selection.props.forecast_time) as string} />
                  )}
                  {typeof selection.props.source === 'string' && (
                    <Row label={t('inspector.source') as string} value={selection.props.source} />
                  )}
                </div>
              </>
            )}

            {selection.kind === 'marine' && (
              <>
                <div className="sak-metric" style={{ color: OCEAN.coral }}>
                  {typeof selection.props.alert_level === 'string'
                    ? selection.props.alert_level.toUpperCase()
                    : '—'}
                </div>
                <WaveSeparator color={OCEAN.coral} />
                <div className="space-y-0.5">
                  {typeof selection.props.sector === 'string' && (
                    <Row label={t('inspector.sector') as string} value={selection.props.sector} />
                  )}
                  {fmt1(selection.props.wind_kmh, ' km/h') && (
                    <Row
                      label={t('inspector.wind') as string}
                      value={fmt1(selection.props.wind_kmh, ' km/h') as string}
                    />
                  )}
                  {fmt1(selection.props.wave_height_m, ' m') && (
                    <Row
                      label={t('inspector.swell') as string}
                      value={fmt1(selection.props.wave_height_m, ' m') as string}
                    />
                  )}
                  {fmtDate(selection.props.issued_at) && (
                    <Row label={t('inspector.issued') as string} value={fmtDate(selection.props.issued_at) as string} />
                  )}
                </div>
              </>
            )}
            {/* i18n language is guaranteed wired by initI18n; keep i18n ref alive */}
            <span className="hidden">{String(i18n.language)}</span>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
