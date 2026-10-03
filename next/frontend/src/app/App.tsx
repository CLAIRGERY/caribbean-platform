import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import MapStage from '../map/MapStage'
import Header from '../components/Header'
import Timeline from '../components/Timeline'
import Inspector from '../components/Inspector'
import LayerControl from '../components/LayerControl'
import OceanFlowGate from '../three/OceanFlowGate'
import Intro from '../components/Intro'
import { useLayers } from '../stores'

/**
 * App shell: full-viewport MapLibre stage; all UI floats over it.
 * Intro self-skips on repeat visits / reduced motion (Intro.tsx).
 */
export default function App() {
  const { t } = useTranslation()
  const oceanFlow = useLayers((s) => s.oceanFlow)

  useEffect(() => {
    document.title = document.documentElement.lang.startsWith('fr')
      ? 'SaKgaZé — Surveillance des sargasses · Caraïbe'
      : 'SaKgaZé — Sargassum surveillance · Caribbean'
  }, [t])


  return (
    <div className="sak-stage relative">
      <Intro />
      <MapStage />
      {oceanFlow && <OceanFlowGate enabled />}
      <Header />
      <LayerControl />
      <Timeline />
      <Inspector />
    </div>
  )
}

