import i18next, { type i18n as I18nType } from 'i18next'
import { initReactI18next } from 'react-i18next'
import fr from './fr.json'
import en from './en.json'

export const LANG_KEY = 'sakgaze.lang'
export type Lang = 'fr' | 'en'

function detectInitialLang(): Lang {
  try {
    const stored = window.localStorage.getItem(LANG_KEY)
    if (stored === 'fr' || stored === 'en') return stored
  } catch {
    /* localStorage may be unavailable */
  }
  return 'fr'
}

let initialized: I18nType | null = null

export function getI18n(): I18nType {
  if (initialized) return initialized
  i18next.use(initReactI18next).init({
    lng: detectInitialLang(),
    fallbackLng: 'fr',
    defaultNS: 'app',
    resources: {
      fr: { app: (fr as { app: Record<string, unknown> }).app },
      en: { app: (en as { app: Record<string, unknown> }).app },
    },
    interpolation: { escapeValue: false },
    returnEmptyString: false,
  })
  initialized = i18next
  document.documentElement.lang = initialized.language === 'en' ? 'en-US' : 'fr-FR'
  return initialized
}

export function initI18n(): I18nType {
  return getI18n()
}

export function setLang(lang: Lang): void {
  void i18next.changeLanguage(lang)
  try {
    window.localStorage.setItem(LANG_KEY, lang)
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang === 'fr' ? 'fr-FR' : 'en-US'
}

export { i18next }
