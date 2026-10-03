import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { useLayers } from '../stores'

function Pill({
  active,
  color,
  label,
  onClick,
}: {
  active: boolean
  color: string
  label: string
  onClick: () => void
}) {
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      aria-pressed={active}
      className={`sak-glass flex min-h-[44px] items-center gap-2 px-3 py-2 text-xs transition-all ${
        active ? 'text-white/95' : 'text-white/45'
      }`}
    >
      <span
        className="h-2.5 w-2.5 rounded-full transition-opacity"
        style={{ background: color, boxShadow: `0 0 8px ${color}`, opacity: active ? 1 : 0.3 }}
      />
      <span>{label}</span>
    </motion.button>
  )
}

/** Floating layer control (top-right on desktop, inside mobile menu on mobile). */
export default function LayerControl({ embedded = false }: { embedded?: boolean }) {
  const { t } = useTranslation()
  const layers = useLayers()

  const items = [
    {
      key: 'sargassum' as const,
      label: t('layers.sargassum') as string,
      color: '#AB47BC',
      on: layers.sargassum,
    },
    { key: 'drift' as const, label: t('layers.drift') as string, color: '#FF6D00', on: layers.drift },
    { key: 'marine' as const, label: t('layers.marine') as string, color: '#F59E0B', on: layers.marine },
  ]

  const controls = (
    <div className={embedded ? 'grid grid-cols-1 gap-2' : 'flex flex-col gap-2'}>
      {items.map((it) => (
        <Pill
          key={it.key}
          active={it.on}
          color={it.color}
          label={it.label}
          onClick={() => layers.toggle(it.key)}
        />
      ))}
      <Pill
        active={layers.satelliteBasemap}
        color="#67E8F9"
        label={t('layers.satellite') as string}
        onClick={() => layers.toggle('satelliteBasemap')}
      />
      <Pill
        active={layers.oceanFlow}
        color="#8B7CF6"
        label={t('layers.oceanFlow') as string}
        onClick={() => layers.toggle('oceanFlow')}
      />
    </div>
  )

  if (embedded) return controls

  return (
    <aside
      className="pointer-events-auto absolute right-3 top-20 z-30 sm:right-4 sm:top-24"
      aria-label={t('layers.layersTitle') as string}
    >
      {controls}
    </aside>
  )
}
