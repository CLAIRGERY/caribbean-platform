import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useMarineAlerts } from '../hooks/useLayers'

/**
 * Coastal Risk Mode — combines REAL marine alerts only (no fake scores).
 * Renders count + sector labels in a compact instrument chip.
 */
export default function CoastalRiskPanel() {
  const { t } = useTranslation()
  const mar = useMarineAlerts()

  if (!mar.isSuccess || !mar.data) return null
  const feats = mar.data.features
  if (feats.length === 0) return null

  const byLevel: Record<string, number> = {}
  for (const f of feats) {
    const lvl = String(f.properties.alert_level ?? 'normal').toLowerCase()
    byLevel[lvl] = (byLevel[lvl] ?? 0) + 1
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="pointer-events-auto absolute bottom-32 left-3 z-30 sm:left-4 sm:bottom-36"
    >
      <div className="sak-glass px-3 py-2" style={{ borderColor: '#EF5B5844' }}>
        <div className="sak-kicker mb-0.5" style={{ color: '#EF7B45' }}>
          {t('layers.marine')}
        </div>
        <div className="font-display text-[13px] font-semibold" style={{ color: '#F5C9A0' }}>
          {feats.length} {new Intl.PluralRules(navigator.language).select(feats.length) === 'one' ? t('inspector.sector') : t('inspector.sectorPlural')}
        </div>
        <div className="mt-0.5 flex gap-2">
          {Object.entries(byLevel).map(([lvl, n]) => (
            <span key={lvl} className="text-[9px] uppercase tracking-wide text-white/55">
              {lvl}: {n}
            </span>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
