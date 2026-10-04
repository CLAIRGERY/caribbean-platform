import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useLayers } from '../stores'
import { OCEAN } from './premium'

/** Animated mini waveform (active-state indicator); CSS-driven cheap GPU. */
function Wave({ on, glow }: { on: boolean; glow: string }) {
  const heights = on ? [5, 10, 7, 12, 6] : [3, 3, 3, 3, 3]
  return (
    <span className="sak-wave" style={{ ['--glow' as string]: glow } as React.CSSProperties}>
      {heights.map((h, i) => (
        <motion.span
          key={i}
          animate={{ height: h, opacity: on ? 0.9 : 0.25 }}
          transition={{ duration: on ? 0.9 - i * 0.08 : 0.2, repeat: on ? Infinity : 0, repeatType: 'mirror' }}
        />
      ))}
    </span>
  )
}

function SourceDot({ on, glow }: { on: boolean; glow: string }) {
  return (
    <span
      className="rounded-full"
      style={{
        width: 6,
        height: 6,
        background: on ? glow : 'rgba(231,238,247,0.12)',
        boxShadow: on ? `0 0 7px ${glow}` : 'none',
      }}
    />
  )
}

function InstrumentRow({
  on,
  toggler,
  labelSource,
  labelTitle,
  labelSubtitle,
  glow,
  icon,
}: {
  on: boolean
  toggler: () => void
  labelSource: string
  labelTitle: string
  labelSubtitle: string
  glow: string
  icon: string
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.98 }}
      onClick={toggler}
      aria-pressed={on}
      className={`sak-controller ${on ? 'is-active' : ''}`}
      style={{ ['--glow' as string]: glow } as React.CSSProperties}
    >
      <span className="flex items-center">
        <SourceDot on={on} glow={glow} />
      </span>
      <span className="flex flex-col items-start justify-center min-w-0">
        <span
          className="truncate font-display text-[11px] font-semibold tracking-[0.2em] uppercase"
          style={{ color: on ? '#EAF6FF' : 'rgba(231,238,247,0.45)' }}
        >
          {icon} {labelTitle}
        </span>
        <span className="text-[8px] uppercase tracking-[0.1em] text-white/35">{labelSubtitle}</span>
      </span>
      <span className="flex flex-col items-end justify-center gap-[3px]">
        <Wave on={on} glow={glow} />
        <span className="text-[7px] uppercase tracking-widest" style={{ color: on ? glow : 'rgba(231,238,247,0.2)' }}>
          {labelSource}
        </span>
      </span>
    </motion.button>
  )
}

/** Oceanographic sensor console (replaces generic layer cards). */
export default function LayerControl({ embedded = false }: { embedded?: boolean }) {
  const { t } = useTranslation()
  const layers = useLayers()

  const cluster = (
    <div className="sak-instrument flex flex-col">
      <div className="px-3 py-2 flex items-center justify-between">
        <div className="sak-kicker">{t('layers.layersTitle')}</div>
        <div className="flex gap-1" aria-hidden>
          <SourceDot on={layers.sargassum} glow={OCEAN.ochre} />
          <SourceDot on={layers.drift} glow={OCEAN.amber} />
          <SourceDot on={layers.marine} glow={OCEAN.coral} />
        </div>
      </div>
      <InstrumentRow
        on={layers.sargassum}
        toggler={() => layers.toggle('sargassum')}
        labelSource="SATELLITE"
        labelTitle={t('layers.sargassum') as string}
        labelSubtitle="SATELLITE DETECTION"
        glow={OCEAN.ochre}
        icon="●"
      />
      <InstrumentRow
        on={layers.drift}
        toggler={() => layers.toggle('drift')}
        labelSource="OPEN-METEO"
        labelTitle={t('layers.drift') as string}
        labelSubtitle="FORECAST VECTOR FIELD"
        glow={OCEAN.amber}
        icon="●"
      />
      <InstrumentRow
        on={layers.marine}
        toggler={() => layers.toggle('marine')}
        labelSource="WEATHERNEXT"
        labelTitle={t('layers.marine') as string}
        labelSubtitle="COASTAL MONITORING"
        glow={OCEAN.coral}
        icon="●"
      />
      <InstrumentRow
        on={layers.satelliteBasemap}
        toggler={() => layers.toggle('satelliteBasemap')}
        labelSource="ESRI"
        labelTitle={t('layers.satellite') as string}
        labelSubtitle="IMAGERY"
        glow={OCEAN.seaglass}
        icon="●"
      />
      <InstrumentRow
        on={layers.oceanFlow}
        toggler={() => layers.toggle('oceanFlow')}
        labelSource="GPU"
        labelTitle={t('layers.oceanFlow') as string}
        labelSubtitle="CURRENT FIELD"
        glow={OCEAN.biolume}
        icon="●"
      />
      <InstrumentRow
        on={layers.coastalRisk}
        toggler={() => layers.toggle('coastalRisk')}
        labelSource="MODE"
        labelTitle="Risque côtier"
        labelSubtitle="COASTAL RISK"
        glow={OCEAN.rust}
        icon="●"
      />
    </div>
  )

  if (embedded) return cluster

  return (
    <motion.aside
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.35 }}
      className="pointer-events-auto absolute right-3 z-30 sm:right-4"
      style={{ bottom: 'calc(7rem + env(safe-area-inset-bottom, 0px))', width: 218 }}
      aria-label={t('layers.layersTitle') as string}
    >
      {cluster}
    </motion.aside>
  )
}
