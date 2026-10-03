import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import type { IngestionStatus } from '../types/geo'

/** Shown when the API is reachable but returns zero features (empty database mode). */
export default function EmptyStateOverlay({ status }: { status: IngestionStatus | undefined }) {
  const { t } = useTranslation()
  const serving = status && Object.keys(status).length > 0

  return (
    <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="pointer-events-auto sak-glass sak-glass--strong sak-luminous-border max-w-sm p-5 text-center"
      >
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-cyan-400/10 text-xl">
          <span aria-hidden>🧪</span>
        </div>
        <h2 className="font-display text-base font-semibold text-white/95">{t('empty.noObservations')}</h2>
        <p className="mt-1 text-sm text-cyan-100/70">{t('empty.waitingIngestion')}</p>
        <p className="mt-2 text-xs text-white/45">{t('empty.willAppear')}</p>
        {serving && (
          <p className="mt-3 truncate text-[10px] text-cyan-100/40" title={JSON.stringify(status)}>
            {Object.entries(status)
              .slice(0, 2)
              .map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`)
              .join(' · ')}
          </p>
        )}
      </motion.div>
    </div>
  )
}
