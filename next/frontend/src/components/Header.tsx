import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import logo from '../assets/brand/logo-sakgaze.png'
import { useIngestionStatus } from '../hooks/useLayers'
import LiveStatus from './LiveStatus'
import LangSwitch from './LangSwitch'
import LayerControl from './LayerControl'
import AboutDialog from './AboutDialog'
import { useUI, useLayers } from '../stores'
import { useState } from 'react'

export default function Header() {
  const { t } = useTranslation()
  const status = useIngestionStatus()
  const menuOpen = useUI((s) => s.mobileMenuOpen)
  const setMenuOpen = useUI((s) => s.setMobileMenuOpen)
  const toggleOceanFlow = useLayers((s) => s.toggle)
  const oceanFlowOn = useLayers((s) => s.oceanFlow)
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

  return (
    <>
      <header className="pointer-events-none absolute inset-x-0 top-0 z-30 p-3 sm:p-4">
        <div className="pointer-events-auto sak-glass sak-luminous-border flex items-center gap-3 px-3 py-2 sm:px-4 sm:py-2.5">
          <img
            src={logo}
            alt="SaKgaZé"
            className="h-9 w-9 flex-none rounded-full object-cover ring-1 ring-cyan-200/30"
            width={36}
            height={36}
          />
          <div className="min-w-0">
            <h1 className="truncate font-display text-sm font-semibold tracking-tight text-white/95 sm:text-base">
              SaKgaZé
            </h1>
            <p className="truncate text-[10px] text-cyan-100/60 sm:text-[11px]">{t('brand.subtitle')}</p>
          </div>

          <div className="ml-1 hidden md:flex">
            <LiveStatus status={status} />
          </div>

          <div className="ml-auto flex items-center gap-2">
            <LangSwitch />
            <button
              type="button"
              onClick={() => toggleOceanFlow('oceanFlow')}
              aria-pressed={oceanFlowOn}
              title={t('layers.oceanFlow') as string}
              className={`hidden h-9 w-9 items-center justify-center rounded-lg sm:flex ${
                oceanFlowOn ? 'bg-violet-400/25 text-violet-200' : 'text-cyan-100/70 hover:bg-white/10'
              }`}
            >
              <span aria-hidden>〰</span>
            </button>
            <button
              type="button"
              onClick={() => setAboutOpen(true)}
              className="hidden h-9 w-9 items-center justify-center rounded-lg text-cyan-100/70 hover:bg-white/10 sm:flex"
              title={t('a11y.menu') as string}
              aria-label={t('a11y.menu') as string}
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
        </div>

        {menuOpen && (
          <div
            id="sak-mobile-menu"
            className="pointer-events-auto mt-2 sak-glass sak-glass--strong flex flex-col gap-2 p-3 md:hidden"
          >
            <LiveStatus status={status} />
            <LayerControl embedded />
            <button
              type="button"
              className="rounded-lg border border-white/10 px-3 py-2.5 text-left text-sm text-cyan-100/90"
              onClick={() => {
                setMenuOpen(false)
                setAboutOpen(true)
              }}
            >
              {t('a11y.menu')} · ⓘ
            </button>
          </div>
        )}
      </header>

      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </>
  )
}
