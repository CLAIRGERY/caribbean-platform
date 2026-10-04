import { useTranslation } from 'react-i18next'
import { useDetections, useDrift, useMarineAlerts, useIngestionStatus } from '../hooks/useLayers'

/**
 * Compact telemetry strip: only REAL backend values.
 * Each row semantics:
 *  - SATELLITE: count of detection features + last acquisition time (UTC)
 *  - DÉRIVE: count of drift trajectories + max forecast horizon from their own `forecast_horizon_h`
 *  - ALERTES: active alert count + severity levels present
 *  - INGESTION: relative freshness («Actualisé il y a N min») from ingestion/status `last_run`
 * A field that does not exist in the API payload displays "—" or EN ATTENTE;
 * nothing is ever invented.
 */
export default function TelemetryStrip({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()
  const st = useIngestionStatus()

  const dc = det.isSuccess ? det.data?.features.length ?? null : null
  const df = drf.isSuccess ? drf.data?.features.length ?? null : null
  const ma = mar.isSuccess ? mar.data?.features.length ?? null : null

  // max forecast horizon actually present in the drift data
  const maxHorizon = drf.isSuccess
    ? drf.data?.features.reduce<number | null>((max, f) => {
        const h = f.properties.forecast_horizon_h
        return typeof h === 'number' && Number.isFinite(h) && (max === null || h > max) ? h : max
      }, null) ?? null
    : null

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
    return `${new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(new Date(max))} UTC`
  }

  // last ingestion: from status payload; display relative ("Actualisé il y a N min")
  const ingestRelative = (): string | null => {
    if (!st.isSuccess || !st.data) return null
    const raw = (st.data.last_run as string | number | undefined) ?? (st.data.last_ingestion as string | number | undefined)
    if (typeof raw !== 'string' && typeof raw !== 'number') return null
    const ts = typeof raw === 'number' ? raw : Date.parse(raw)
    if (!Number.isFinite(ts)) return null
    const minutes = Math.round((Date.now() - ts) / 60000)
    if (minutes < 0) return null
    return minutes <= 2 ? "Actualisé à l'instant" : `Actualisé il y a ${minutes} min`
  }

  // marine severity summary (real values only)
  const severitySummary = (): string | null => {
    if (!mar.isSuccess || !mar.data || mar.data.features.length === 0) return null
    const levels = new Set<string>()
    for (const f of mar.data.features) {
      const lvl = f.properties.alert_level
      if (typeof lvl === 'string') levels.add(lvl.toLowerCase())
    }
    return [...levels].slice(0, 3).join(' · ') || null
  }

  const row = (label: string, value: string | null) => (
    <div className="sak-telemetry-row">
      <span>{label}</span>
      <strong className={value === null ? 'sak-pending' : undefined}>{value ?? '—'}</strong>
    </div>
  )

  return (
    <div className={`sak-telemetry ${className}`}>
      <div className="sak-kicker mb-0.5">{t('telemetry.satellite')}</div>
      {row(`${t('telemetry.satellite')} · ${t('status.lastIngestion')}`, dc === null ? null : latestTs(det) ? `${dc} · ${latestTs(det)}` : `${dc}`)}
      {row(t('telemetry.drift'), df === null ? null : maxHorizon !== null ? `${df} · +${maxHorizon} h` : `${df}`)}
      {row(t('telemetry.marine'), ma === null ? null : severitySummary() ? `${ma} · ${severitySummary()}` : `${ma}`)}
      {row('INGESTION', ingestRelative())}
    </div>
  )
}
