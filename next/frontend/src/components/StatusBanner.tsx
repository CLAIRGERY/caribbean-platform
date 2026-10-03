import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import { useDetections, useDrift, useMarineAlerts, API_BASE_URL } from '../hooks/useLayers'
import { useQueryClient } from '@tanstack/react-query'

/**
 * Cold-start banner: shows "connecting / waking / retrying / unavailable".
 * Auto retry (2s/5s/10s) happens inside the query layer; after final failure we
 * expose an explicit manual Retry button. No infinite auto-retry loop.
 */
export default function StatusBanner() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()

  const failing = [det, drf, mar].filter((q) => q.isError) as Array<typeof det>
  const pending = [det, drf, mar].filter((q) => q.isPending)
  const allFailed = failing.length === 3

  if (allFailed) {
    return (
      <div className="pointer-events-auto absolute inset-x-0 top-16 z-40 mx-auto w-fit max-w-[92%]">
        <div className="sak-glass sak-glass--strong sak-luminous-border flex items-center gap-3 px-4 py-3">
          <span className="text-lg" aria-hidden>
            ⚠️
          </span>
          <div className="text-xs sm:text-sm">
            <p className="font-medium text-amber-200">{t('status.unavailable')}</p>
            <p className="text-white/50" title={API_BASE_URL}>
              {t('status.waking')}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void qc.refetchQueries()}
            className="ml-2 min-h-[44px] rounded-lg bg-cyan-400/20 px-4 text-sm text-cyan-100 hover:bg-cyan-400/30"
          >
            {t('status.retry')}
          </button>
        </div>
      </div>
    )
  }

  if (pending.length > 0 && failing.length === 0) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="pointer-events-none absolute inset-x-0 top-16 z-30 mx-auto w-fit"
        >
          <div className="sak-glass px-3 py-1.5 text-[11px] text-cyan-100/70">{t('status.connecting')}</div>
        </motion.div>
      </AnimatePresence>
    )
  }

  if (failing.length > 0) {
    return (
      <div className="pointer-events-auto absolute inset-x-0 top-16 z-30 mx-auto w-fit max-w-[92%]">
        <div className="sak-glass flex items-center gap-2 px-3 py-2 text-[11px] text-amber-200/90">
          <span aria-hidden>⚠️</span>
          <span>{t('status.unavailable')}</span>
          <button
            type="button"
            onClick={() => void qc.refetchQueries()}
            className="ml-1 rounded-md px-2 py-1 text-cyan-200 underline-offset-2 hover:underline"
          >
            {t('status.retry')}
          </button>
        </div>
      </div>
    )
  }

  return null
}
