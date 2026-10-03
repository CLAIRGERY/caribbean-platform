import { useTranslation } from 'react-i18next'
import { useDetections, useDrift, useMarineAlerts, API_BASE_URL } from '../hooks/useLayers'
import { OCEAN } from './premium'

/** Cold-start / degraded banner. Expanded=false reduces visual weight. */
export default function StatusBanner({ expanded = true }: { expanded?: boolean }) {
  const { t } = useTranslation()
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()

  const failing = [det, drf, mar].filter((q) => q.isError) as Array<typeof det>
  if (failing.length === 0) return null

  const allFailed = failing.length === 3

  return (
    <div className="pointer-events-auto absolute left-1/2 z-40 w-fit max-w-[92%]" style={{ top: allFailed ? 76 : 96 }}>
      <div
        className="sak-glass flex items-center gap-2.5 px-3.5 py-2.5"
        style={{
          borderColor: `${OCEAN.coral}44`,
          ...(allFailed ? { transform: 'translateX(-50%)' } : {}),
        }}
      >
        <span aria-hidden>⚠️</span>
        <div className="text-[11px] leading-tight">
          <div className="font-semibold" style={{ color: allFailed ? OCEAN.coral : OCEAN.gold }}>
            {allFailed ? (t('status.offline') as string) : (t('status.degraded') as string)}
          </div>
          {expanded && (
            <div className="text-white/45" title={API_BASE_URL}>
              {t('status.waking')}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={() => void failing.forEach((q) => q.refetch())}
          className="sak-glow-btn ml-1"
          style={{ minHeight: 36, fontSize: 10, paddingInline: 12 }}
        >
          {t('status.retry')}
        </button>
      </div>
    </div>
  )
}
