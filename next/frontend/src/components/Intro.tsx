import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { AnimatePresence, motion } from 'framer-motion'
import logo from '../assets/brand/logo-sakgaze.png'

const INTRO_KEY = 'sakgaze.intro-seen'
const EXIT_EVENT = 'sakgaze:intro-exit'

/**
 * Premium intro (≤1.2s): dark ocean → luminous scanline → logo → fade into map.
 * Auto-dismiss; skipped on repeat visits and reduced motion (App handles both).
 */
export default function Intro() {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let seen = false
    try {
      seen = window.localStorage.getItem(INTRO_KEY) === '1'
      window.localStorage.setItem(INTRO_KEY, '1')
    } catch {
      seen = false
    }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (seen || reduced) return

    setVisible(true)
    const a = setTimeout(() => setVisible(false), 1200)
    return () => clearTimeout(a)
  }, [])

  useEffect(() => {
    const onExit = () => setVisible(false)
    window.addEventListener(EXIT_EVENT, onExit)
    return () => window.removeEventListener(EXIT_EVENT, onExit)
  }, [])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="pointer-events-none absolute inset-0 z-[60] flex items-center justify-center"
          style={{ background: 'rgba(2,10,24,0.92)' }}
          aria-hidden="true"
        >
          {/* bathymetric particle field suggestion */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 0.5, scale: 1 }}
            transition={{ duration: 0.9 }}
            className="absolute inset-0"
            style={{
              background:
                'radial-gradient(70% 60% at 50% 55%, rgba(34,211,238,0.10) 0%, transparent 70%), radial-gradient(50% 40% at 30% 70%, rgba(45,212,167,0.06) 0%, transparent 70%)',
            }}
          />
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="relative flex flex-col items-center gap-3"
          >
            <img src={logo} alt="" className="h-16 w-16 rounded-full shadow-2xl ring-1 ring-cyan-200/25" />
            <div className="sak-kicker">SaKgaZé</div>
          </motion.div>
          {/* scan line travels down then fades */}
          <motion.div
            className="sak-scanline"
            initial={{ top: '35%', opacity: 0 }}
            animate={{ top: ['45%', '62%'], opacity: [0, 1, 0] }}
            transition={{ duration: 1.1, ease: 'easeInOut' }}
          />
          <motion.button
            type="button"
            className="pointer-events-auto absolute bottom-6 px-3 text-[10px] uppercase tracking-widest text-white/40 hover:text-white/70"
            onClick={() => setVisible(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.6 }}
            transition={{ delay: 0.5 }}
          >
            {t('intro.skip')}
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
