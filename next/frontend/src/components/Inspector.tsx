import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import { useSelection, useUI } from '../stores'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-white/5 py-1.5 last:border-0">
      <span className="text-[10px] uppercase tracking-wide text-white/45">{label}</span>
      <span className="text-sm font-medium text-white/90">{value}</span>
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

/** Floating inspector panel (desktop) / bottom sheet (mobile). Shows only real values. */
export default function Inspector() {
  const { t } = useTranslation()
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
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 40 }}
          className="pointer-events-auto absolute bottom-24 right-3 z-40 w-[min(320px,calc(100%-1.5rem))] sm:bottom-28 sm:right-4"
          role="complementary"
          aria-label={t('inspector.title') as string}
        >
          <div className="sak-glass sak-glass--strong sak-luminous-border p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-display text-sm font-semibold text-white/90">{t('inspector.title')}</h2>
              <button
                type="button"
                onClick={clear}
                aria-label={t('inspector.close') as string}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-white/60 hover:bg-white/10"
              >
                <span aria-hidden>✕</span>
              </button>
            </div>
            <div className="space-y-0.5">
              {selection.kind === 'sargassum' && (
                <>
                  {fmt1(selection.props.surface_km2, ' km²') && (
                    <Row label={t('inspector.surface') as string} value={fmt1(selection.props.surface_km2, ' km²') as string} />
                  )}
                  {fmt1(selection.props.density_score) && (
                    <Row label={t('inspector.density') as string} value={fmt1(selection.props.density_score) as string} />
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
                </>
              )}
              {selection.kind === 'drift' && (
                <>
                  {typeof selection.props.forecast_horizon_h === 'number' && (
                    <Row label={t('inspector.horizon') as string} value={`+${selection.props.forecast_horizon_h} h`} />
                  )}
                  {fmt1(selection.props.velocity_kmh, ' km/h') && (
                    <Row label="Vitesse" value={fmt1(selection.props.velocity_kmh, ' km/h') as string} />
                  )}
                  {fmtDate(selection.props.forecast_time) && (
                    <Row label={t('inspector.eta') as string} value={fmtDate(selection.props.forecast_time) as string} />
                  )}
                  {typeof selection.props.source === 'string' && (
                    <Row label={t('inspector.source') as string} value={selection.props.source} />
                  )}
                </>
              )}
              {selection.kind === 'marine' && (
                <>
                  {typeof selection.props.alert_level === 'string' && (
                    <Row label={t('inspector.alertLevel') as string} value={selection.props.alert_level} />
                  )}
                  {typeof selection.props.sector === 'string' && (
                    <Row label={t('inspector.sector') as string} value={selection.props.sector} />
                  )}
                  {fmt1(selection.props.wind_kmh, ' km/h') && (
                    <Row label={t('inspector.wind') as string} value={fmt1(selection.props.wind_kmh, ' km/h') as string} />
                  )}
                  {fmt1(selection.props.wave_height_m, ' m') && (
                    <Row label={t('inspector.swell') as string} value={fmt1(selection.props.wave_height_m, ' m') as string} />
                  )}
                  {fmtDate(selection.props.issued_at) && (
                    <Row label={t('status.lastIngestion') as string} value={fmtDate(selection.props.issued_at) as string} />
                  )}
                </>
              )}
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
