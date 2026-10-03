import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE_URL } from '../lib/api'
import logo from '../assets/brand/logo-sakgaze.png'

export default function AboutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" aria-label="close" className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div role="dialog" aria-modal="true" className="sak-glass sak-glass--strong sak-luminous-border relative z-10 w-full max-w-md p-5">
        <div className="flex items-center gap-3">
          <img src={logo} alt="" className="h-10 w-10 rounded-full object-cover ring-1 ring-cyan-200/30" />
          <div>
            <h2 className="font-display text-base font-semibold text-white/95">SaKgaZé</h2>
            <p className="text-xs text-cyan-100/60">{t('brand.subtitle')}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-lg text-cyan-100/80 hover:bg-white/10"
            aria-label={t('a11y.close') ?? ''}
          >
            <span aria-hidden>✕</span>
          </button>
        </div>
        <p className="mt-4 text-sm leading-relaxed text-white/80">
          SaKgaZé combine l'imagerie satellite Sentinel-2 et la modélisation de dérive (vents et courants) pour
          anticiper l'arrivée des sargasses sur les côtes caraïbes.
        </p>
        <p className="mt-3 text-[11px] text-cyan-100/50">
          {t('footer.apiBase')}: <code className="break-all">{API_BASE_URL}</code>
        </p>
      </div>
    </div>
  )
}
