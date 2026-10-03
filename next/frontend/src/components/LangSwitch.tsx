import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { setLang, type Lang } from '../i18n'

export default function LangSwitch() {
  const { i18n } = useTranslation()
  const [current, setCurrent] = useState<Lang>((i18n.language?.slice(0, 2) as Lang) || 'fr')

  useEffect(() => {
    setCurrent((i18n.language?.slice(0, 2) as Lang) || 'fr')
  }, [i18n.language])

  return (
    <div
      role="group"
      aria-label="language"
      className="flex overflow-hidden rounded-lg border border-white/10 text-[11px] font-medium"
    >
      {(['fr', 'en'] as Lang[]).map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => {
            setLang(lang)
            setCurrent(lang)
          }}
          aria-pressed={current === lang}
          className={`min-h-[36px] px-2.5 py-1.5 transition-colors ${
            current === lang ? 'bg-cyan-400/20 text-cyan-100' : 'text-white/60 hover:bg-white/5'
          }`}
        >
          {lang.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
