import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import type { UseQueryResult } from '@tanstack/react-query'
import type { IngestionStatus } from '../types/geo'

export type StatusQ = UseQueryResult<IngestionStatus>

function fmtTs(v: unknown): string | null {
  if (typeof v !== 'string' && typeof v !== 'number') return null
  const t = typeof v === 'number' ? v : Date.parse(v)
  if (!Number.isFinite(t)) return null
  const locale = navigator.language.startsWith('fr') ? 'fr-FR' : 'en-US'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(t))
}

export default function LiveStatus({ status }: { status: StatusQ }) {
  const { t } = useTranslation()
  const d = status.data ?? null
  const lastRun =
    (d?.last_run as string | number | undefined) ??
    (d?.last_ingestion as string | number | undefined) ??
    (d?.latest_run as string | number | undefined) ??
    null
  const fmt = lastRun !== null ? fmtTs(lastRun) : null
  const isOk = status.isSuccess && Boolean(d && Object.keys(d).length > 0)

  return (
    <div className="flex items-center gap-2 px-1 py-1 text-[11px]" title={t('status.freshness') ?? ''}>
      <AnimatePresence mode="wait">
        {status.isError && (
          <motion.span
            key="err"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="rounded-md bg-amber-500/10 px-2 py-0.5 text-amber-300"
          >
            {t('status.unavailable')}
          </motion.span>
        )}
        {status.isPending && (
          <motion.span key="load" className="text-cyan-100/60 animate-pulse">
            {t('status.connecting')}
          </motion.span>
        )}
        {isOk && (
          <motion.span key="ok" className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="sak-anim-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-emerald-300">{t('status.live')}</span>
            {fmt && <span className="hidden text-white/45 md:inline">· {t('status.lastIngestion')} {fmt}</span>}
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  )
}
