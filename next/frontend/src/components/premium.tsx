/**
 * ThreeUI-inspired premium component system (primitives).
 *
 * Coherent marine-instrument design language: luminous glass, flow borders,
 * bioluminescent accents, real-time telemetry indicators. Every effect serves
 * the ocean/satellite/data narrative. Used across Header, LayerControl,
 * Timeline, Inspector, StatusBanner.
 */
import { motion, AnimatePresence } from 'framer-motion'
import type { ReactNode, CSSProperties } from 'react'

/* ── tokens ─────────────────────────────────────────────────────────── */

export const OCEAN = {
  abyss: '#04122A',
  midnight: '#0A1E3F',
  cyan: '#22D3EE',
  cyanGlow: '#67E8F9',
  seaglass: '#7DE2C3',
  lagoon: '#2DD4A7',
  biolume: '#8B7CF6',
  gold: '#D4A94E',
  ochre: '#C98B32',
  rust: '#B45309',
  amber: '#F59E0B',
  coral: '#FF6D4D',
} as const

/* ── ThreeGlassPanel ────────────────────────────────────────────────── */

export function ThreeGlassPanel({
  children,
  strong = false,
  className = '',
  style,
}: {
  children: ReactNode
  strong?: boolean
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      className={`sak-glass ${strong ? 'sak-glass--strong' : ''} ${className}`}
      style={style}
    >
      {children}
      <FlowBorder active={strong} />
    </div>
  )
}

/* ── FlowBorder: animated luminous edge ─────────────────────────────── */

export function FlowBorder({ active = true }: { active?: boolean }) {
  if (!active) return null
  return (
    <motion.span
      aria-hidden
      className="sak-panel-flow-border"
      initial={{ opacity: 0 }}
      animate={{ opacity: [0.35, 0.85, 0.35], backgroundPosition: ['0% 0%', '100% 100%', '0% 0%'] }}
      transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      style={{
        position: 'absolute',
        inset: 0,
        borderRadius: 'inherit',
        pointerEvents: 'none',
        background:
          'linear-gradient(115deg, transparent 0%, rgba(103,232,249,0.25) 30%, rgba(125,226,195,0.2) 50%, rgba(139,124,246,0.25) 70%, transparent 100%)',
        backgroundSize: '220% 220%',
        mask:
          'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
        WebkitMask:
          'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
        WebkitMaskComposite: 'xor',
        maskComposite: 'exclude',
        padding: 1,
      }}
    />
  )
}

/* ── MarineStatusOrb: premium live/degraded/offline orb ─────────────── */

export type OrbState = 'connecting' | 'waking' | 'live' | 'degraded' | 'offline'

const ORB_COLORS: Record<OrbState, string> = {
  connecting: OCEAN.cyan,
  waking: OCEAN.amber,
  live: OCEAN.lagoon,
  degraded: OCEAN.gold,
  offline: OCEAN.coral,
}

export function MarineStatusOrb({ state, size = 10 }: { state: OrbState; size?: number }) {
  const color = ORB_COLORS[state]
  const busy = state === 'connecting' || state === 'waking'
  return (
    <span className="sak-orb" style={{ width: size, height: size, position: 'relative', display: 'inline-flex' }}>
      <AnimatePresence>
        {busy && (
          <motion.span
            initial={{ scale: 1, opacity: 0.6 }}
            animate={{ scale: [1, 2.4], opacity: [0.5, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
            style={{ position: 'absolute', inset: 0, borderRadius: '999px', background: color }}
          />
        )}
      </AnimatePresence>
      <span
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          borderRadius: '999px',
          background: color,
          boxShadow: `0 0 ${size}px ${color}88, 0 0 ${size * 2}px ${color}33`,
        }}
      />
    </span>
  )
}

/* ── OceanGlowButton: magnetic premium button ───────────────────────── */

export function OceanGlowButton({
  children,
  onClick,
  active = false,
  glow = OCEAN.cyan,
  ariaPressed,
  ariaLabel,
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  active?: boolean
  glow?: string
  ariaPressed?: boolean
  ariaLabel?: string
  className?: string
}) {
  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-pressed={ariaPressed}
      aria-label={ariaLabel}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.96 }}
      className={`sak-glow-btn ${active ? 'is-active' : ''} ${className}`}
      style={
        {
          '--glow': glow,
        } as CSSProperties & Record<string, string>
      }
    >
      {children}
    </motion.button>
  )
}

/* ── DataPulse: tiny animated telemetry dot row ─────────────────────── */

export function DataPulse({ color = OCEAN.cyan, count = 3 }: { color?: string; count?: number }) {
  return (
    <span className="sak-data-pulse" style={{ display: 'inline-flex', gap: 3 }}>
      {Array.from({ length: count }).map((_, i) => (
        <motion.span
          key={i}
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.18, ease: 'easeInOut' }}
          style={{ width: 3, height: 8, borderRadius: 2, background: color }}
        />
      ))}
    </span>
  )
}

/* ── WaveSeparator: animated hairline ───────────────────────────────── */

export function WaveSeparator({ color = OCEAN.cyanGlow }: { color?: string }) {
  return (
    <motion.div
      aria-hidden
      style={{ height: 1, borderRadius: 1, marginBlock: 10, background: color, opacity: 0.3 } as CSSProperties}
      animate={{ opacity: [0.2, 0.4, 0.2] }}
      transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
    />
  )
}

/* ── BiolumeBadge: restrained violet highlight ──────────────────────── */

export function BiolumeBadge({ children }: { children: ReactNode }) {
  return (
    <span
      className="sak-biolume-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 10px',
        borderRadius: 999,
        background: 'rgba(139,124,246,0.14)',
        border: '1px solid rgba(139,124,246,0.35)',
        color: '#C4B5FD',
        fontSize: 10,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      }}
    >
      {children}
    </span>
  )
}
