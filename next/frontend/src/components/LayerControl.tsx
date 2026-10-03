import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useLayers } from '../stores'
import { OCEAN } from './premium'

function InstrumentToggle({
  on,
  glow,
  label,
  onClick,
  icon,
}: {
  on: boolean
  glow: string
  label: string
  onClick: () => void
  icon: string
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      aria-pressed={on}
      className={`sak-toggle ${on ? 'is-on' : ''}`}
      style={{ ['--glow' as string]: glow } as React.CSSProperties}
    >
      <span className="flex items-center gap-2.5">
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: glow, boxShadow: on ? `0 0 10px ${glow}` : 'none', opacity: on ? 1 : 0.3 }}
        />
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em]">{label}</span>
      </span>
      <span role="presentation" className="sak-toggle-track">
        <span className="sak-toggle-knob" />
      </span>
      <span aria-hidden className="text-[13px] opacity-70">
        {icon}
      </span>
    </motion.button>
  )
}

/** Floating layer instrument (scientific switch panel). `embedded` = used inside mobile menu. */
export default function LayerControl({ embedded = false }: { embedded?: boolean }) {
  const { t } = useTranslation()
  const layers = useLayers()

  const controls = (
    <div className={embedded ? 'grid grid-cols-1 gap-2' : 'flex flex-col gap-2'}>
      <div className="mb-0.5 px-1.5">
        <div className="sak-kicker">{t('layers.layersTitle')}</div>
      </div>
      <InstrumentToggle
        on={layers.sargassum}
        glow={OCEAN.ochre}
        label={t('layers.sargassum') as string}
        icon="🌿"
        onClick={() => layers.toggle('sargassum')}
      />
      <InstrumentToggle
        on={layers.drift}
        glow={OCEAN.amber}
        label={t('layers.drift') as string}
        icon="🌊"
        onClick={() => layers.toggle('drift')}
      />
      <InstrumentToggle
        on={layers.marine}
        glow={OCEAN.coral}
        label={t('layers.marine') as string}
        icon="⚠"
        onClick={() => layers.toggle('marine')}
      />
      <InstrumentToggle
        on={layers.satelliteBasemap}
        glow={OCEAN.seaglass}
        label={t('layers.satellite') as string}
        icon="🛰"
        onClick={() => layers.toggle('satelliteBasemap')}
      />
      <InstrumentToggle
        on={layers.oceanFlow}
        glow={OCEAN.biolume}
        label={t('layers.oceanFlow') as string}
        icon="〰"
        onClick={() => layers.toggle('oceanFlow')}
      />
    </div>
  )

  if (embedded) return controls

  return (
    <motion.aside
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.3 }}
      className="pointer-events-auto absolute right-3 z-30 sm:right-4"
      style={{ bottom: 'calc(6rem + env(safe-area-inset-bottom, 0px))' }}
      aria-label={t('layers.layersTitle') as string}
    >
      <div className="sak-glass p-2.5">{controls}</div>
    </motion.aside>
  )
}
