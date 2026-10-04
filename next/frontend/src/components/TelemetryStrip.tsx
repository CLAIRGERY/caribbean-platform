import { useTranslation } from 'react-i18next'
import { useDetections, useDrift, useMarineAlerts } from '../hooks/useLayers'

/**
 * Compact telemetry strip: real backend counts + timestamps.
 * Shows EN ATTENTE when the backend does not supply a value. Never fake.
 */
export default function TelemetryStrip({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()

  const dc = det.isSuccess ? det.data?.features.length ?? null : null
  const df = drf.isSuccess ? drf.data?.features.length ?? null : null
  const ma = mar.isSuccess ? mar.data?.features.length ?? null : null

  const latestTs = (q: typeof det): string | null => {
    if (!q.isSuccess || !q.data) return null
    let max: number | null = null
    for (const f of q.data.features) {
      const v =
        (f.properties.acquisition_date as string | undefined) ??
        (f.properties.forecast_time as string | undefined) ??
        (f.properties.issued_at as string | undefined)
      if (typeof v === 'string') {
        const ts = Date.parse(v)
        if (Number.isFinite(ts) && (max === null || ts > max)) max = ts
      }
    }
    if (max === null) return null
    const locale = navigator.language.startsWith('fr') ? 'fr-FR' : 'en-US'
    return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(
      new Date(max),
    ) + ' UTC'
  }

  const row = (label: string, value: string | null, okHint: string = '') => (
    <div className="sak-telemetry-row">
      <span>{label}</span>
      <strong className={value === null ? 'sak-pending' : undefined}>
        {value ?? t('telemetry.pending')}
      </strong>
      {okHint && <span className="sak-meta">{okHint}</span>}
    </div>
  )

  return (
    <div className={`sak-telemetry ${className}`}>
      <div className="sak-kicker mb-0.5">{t('telemetry.satellite')}</div>
      {row(t('telemetry.satellite'), dc !== null ? `${dc}` : null)}
      {row(t('telemetry.drift'), df !== null ? `${df}` : null)}
      {row(t('telemetry.marine'), ma !== null ? `${ma}` : null)}
      {row(t('status.lastIngestion'), latestTs(det))}
    </div>
  )
}
