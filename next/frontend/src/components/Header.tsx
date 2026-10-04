import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import logo from '../assets/brand/logo-sakgaze.png'
import { useHealth } from '../hooks/useLayers'
import { useDetections, useDrift, useMarineAlerts } from '../hooks/useLayers'
import { deriveConnState } from '../lib/connState'
import { MarineStatusOrb, type OrbState } from './premium'
import LangSwitch from './LangSwitch'
import StatusBanner from './StatusBanner'
import { USE_TEST_FIXTURES } from '../lib/api'
import TelemetryStrip from './TelemetryStrip'
import { useUI, useLayers, useSelection } from '../stores'

function connToOrb(c: string): OrbState {
  return (['connecting', 'waking', 'live', 'degraded', 'offline'] as const).includes(c as OrbState)
    ? (c as OrbState)
    : 'connecting'
}

/** Iconic floating instrumentation bar (premium V2 header). */
export default function Header() {
  const { t } = useTranslation()
  
  const det = useDetections()
  const drf = useDrift()
  const mar = useMarineAlerts()
  const menuOpen = useUI((s) => s.mobileMenuOpen)
  const setMenuOpen = useUI((s) => s.setMobileMenuOpen)
  const toggleLayer = useLayers((s) => s.toggle)
  const oceanFlowOn = useLayers((s) => s.oceanFlow)
  const clearSel = useSelection((s) => s.clear)
  const healthQ = useHealth()
  const [aboutOpen, setAboutOpen] = useState(false)

  useEffect(() => {
    if (menuOpen) {
      const onKey = (e: KeyboardEvent) => {
        if (e.key === 'Escape') setMenuOpen(false)
      }
      window.addEventListener('keydown', onKey)
      return () => window.removeEventListener('keydown', onKey)
    }
    return undefined
  }, [menuOpen, setMenuOpen])

  const succ = [det, drf, mar].filter((q) => q.isSuccess).length
  const errs = [det, drf, mar].filter((q) => q.isError).length
  const healthOk: boolean | null = healthQ.isSuccess ? true : healthQ.isError ? false : null
  const conn = deriveConnState(succ, errs, 3, healthOk)
  const orb = connToOrb(conn)
  const orbLabel =
    conn === 'live'
      ? (t('status.liveShort') as string)
      : conn === 'degraded'
        ? (t('status.degradedShort') as string)
        : conn === 'offline'
          ? (t('status.offlineShort') as string)
          : (t('status.syncShort') as string)
  const orbFull =
    conn === 'live'
      ? (t('status.live') as string)
      : conn === 'connecting'
        ? (t('status.connecting') as string)
        : conn === 'waking'
          ? (t('status.waking') as string)
          : conn === 'degraded'
            ? (t('status.degraded') as string)
            : (t('status.offline') as string)

  return (
    <>
      {/* Single consolidated outage / degraded banner lives in StatusBanner. */}
      <StatusBanner expanded={false} />

      <header className="pointer-events-none absolute inset-x-0 top-0 z-40 p-3 sm:p-4">
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          className="pointer-events-auto sak-glass sak-luminous-border flex items-center gap-3 px-3 py-2 sm:px-5 sm:py-2.5"
        >
          <img
            src={logo}
            alt="SaKgaZé"
            className="h-9 w-9 flex-none rounded-full object-cover ring-1 ring-cyan-200/25"
            width={36}
            height={36}
          />
          <div className="min-w-0">
            <h1 className="truncate font-display text-sm font-semibold tracking-tight text-white/95 sm:text-base">
              SaKgaZé
            </h1>
            <p className="sak-kicker hidden truncate sm:block">{t('brand.tagline')}</p>
          </div>

          {USE_TEST_FIXTURES && (
            <span
              className="hidden sm:flex items-center px-2 py-0.5 rounded-md"
              style={{ background: 'rgba(240,180,77,0.15)', border: '1px solid rgba(240,180,77,0.4)', color: '#F0C573', fontSize: 9, letterSpacing: '0.18em' }}
              title="DEV TEST FIXTURES ACTIVE"
            >
              TEST DATA
            </span>
          )}

          <div className="ml-1 flex items-center gap-2 px-2" title={orbFull}>
            <MarineStatusOrb state={orb} size={10} />
            <span className="hidden text-[10px] font-semibold uppercase tracking-[0.18em] text-white/55 md:inline">
              {orbLabel}
            </span>
            {/* per-source telemetry (desktop only) */}
            <span className="ml-2 hidden items-center gap-1 lg:flex">
              {[
                { ok: det.isSuccess, tip: 'SENTINEL-2', c: '#67E8F9' },
                { ok: drf.isSuccess, tip: 'OPEN-METEO', c: '#F59E0B' },
                { ok: mar.isSuccess, tip: 'WEATHERNEXT', c: '#FF6D4D' },
              ].map((m, i) => (
                <span
                  key={i}
                  title={m.tip}
                  className="h-1.5 w-6 rounded-full"
                  style={{ background: m.ok ? m.c : 'rgba(255,255,255,0.12)', boxShadow: m.ok ? `0 0 6px ${m.c}88` : 'none' }}
                />
              ))}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <LangSwitch />
            <button
              type="button"
              onClick={() => toggleLayer('oceanFlow')}
              aria-pressed={oceanFlowOn}
              aria-label={t('layers.oceanFlow') as string}
              title={t('layers.oceanFlow') as string}
              className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                oceanFlowOn ? 'bg-violet-400/25 text-violet-200' : 'text-cyan-100/70 hover:bg-white/10'
              }`}
            >
              <span aria-hidden>〰</span>
            </button>
            <button
              type="button"
              onClick={() => setAboutOpen(true)}
              className="hidden h-10 w-10 items-center justify-center rounded-lg text-cyan-100/70 hover:bg-white/10 sm:flex"
              aria-label={t('a11y.info') as string}
              title={t('a11y.info') as string}
            >
              <span aria-hidden>ⓘ</span>
            </button>
            <button
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex h-10 w-10 items-center justify-center rounded-lg text-cyan-100/90 hover:bg-white/10 md:hidden"
              aria-expanded={menuOpen}
              aria-controls="sak-mobile-menu"
              aria-label={t('a11y.menu') as string}
            >
              <span aria-hidden>{menuOpen ? '✕' : '☰'}</span>
            </button>
          </div>
        </motion.div>

        {menuOpen && (
          <div
            id="sak-mobile-menu"
            className="pointer-events-auto mt-2 sak-glass sak-glass--strong flex flex-col gap-2 p-3 md:hidden"
          >
            <div className="flex items-center justify-between px-2 py-1">
              <MarineStatusOrb state={orb} size={9} />
              <span className="text-[10px] uppercase tracking-widest text-white/50">{orbLabel}</span>
            </div>
            <TelemetryStrip />
            <button
              type="button"
              className="rounded-lg border border-white/10 px-3 py-2.5 text-left text-sm text-cyan-100/90"
              onClick={() => {
                setMenuOpen(false)
                setAboutOpen(true)
              }}
            >
              {t('a11y.info')} · ⓘ
            </button>
          </div>
        )}
      </header>

      {aboutOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            aria-label={t('a11y.close') as string}
            className="absolute inset-0 bg-black/55"
            onClick={() => setAboutOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            className="sak-glass sak-glass--strong sak-luminous-border relative z-10 w-full max-w-md p-6"
          >
            <div className="flex items-center gap-3">
              <img src={logo} alt="" className="h-11 w-11 rounded-full object-cover ring-1 ring-cyan-200/25" />
              <div>
                <h2 className="font-display text-lg font-semibold text-white/95">{t('about.title')}</h2>
                <p className="sak-kicker">{t('about.tagline')}</p>
              </div>
              <button
                type="button"
                onClick={() => setAboutOpen(false)}
                className="ml-auto flex h-9 w-9 items-center justify-center rounded-lg text-cyan-100/70 hover:bg-white/10"
                aria-label={t('a11y.close') as string}
              >
                <span aria-hidden>✕</span>
              </button>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-white/80">{t('about.body')}</p>
            <div className="sak-meta mt-4">{t('about.sourceLabel')}</div>
            <div className="truncate text-[10px] text-cyan-100/50">
              Sentinel-2 · Copernicus · Open-Meteo · WeatherNext
            </div>
          </div>
        </div>
      )}

      {/* keeps selection store wired; ESC clear handled by Inspector */}
      <button type="button" className="sr-only" onClick={clearSel} aria-hidden tabIndex={-1} />
    </>
  )
}
