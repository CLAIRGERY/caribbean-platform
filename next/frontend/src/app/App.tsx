import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import MapStage from '../map/MapStage'
import Header from '../components/Header'
import Timeline from '../components/Timeline'
import Inspector from '../components/Inspector'
import StatusBanner from '../components/StatusBanner'
import LayerControl from '../components/LayerControl'
import OceanFlowGate from '../three/OceanFlowGate'
import { useLayers } from '../stores'

/**
 * App shell: full-viewport MapLibre stage; all UI floats over it.
 * The stage holds min-height:100dvh and the map is absolutely positioned,
 * so no child can collapse its height (zero-height-bug prevention).
 */
export default function App() {
  const { t } = useTranslation()
  const oceanFlow = useLayers((s) => s.oceanFlow)

  useEffect(() => {
    // keep document title in sync with language
    document.title = document.documentElement.lang.startsWith('fr')
      ? 'SaKgaZé — Prévision des échouages de sargasses Caraïbes'
      : 'SaKgaZé — Sargassum intelligence, Caribbean'
  }, [t])

  return (
    <div className="sak-stage relative">
      <MapStage />
      {oceanFlow && <OceanFlowGate enabled />}
      <StatusBanner />
      <Header />
      <LayerControl />
      <Timeline />
      <Inspector />
    </div>
  )
}
