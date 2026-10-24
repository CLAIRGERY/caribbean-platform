import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import MapStage from '../map/MapStage'
import Header from '../components/Header'
import Timeline from '../components/Timeline'
import Inspector from '../components/Inspector'
import LayerControl from '../components/LayerControl'
import OceanFlowGate from '../three/OceanFlowGate'
import ShaderLayers from '../three/ShaderLayers'
import Intro from '../components/Intro'
import Minimap from '../components/Minimap'
import CoastalRiskPanel from '../components/CoastalRiskPanel'
import { useLayers } from '../stores'

/**
 * App shell: full-viewport MapLibre stage; all UI floats over it.
 * Intro self-skips on repeat visits / reduced motion (Intro.tsx).
 */
export default function App() {
  const { t } = useTranslation()
  const oceanFlow = useLayers((s) => s.oceanFlow)
  const coastalRisk = useLayers((s) => s.coastalRisk)

  useEffect(() => {
    document.title = document.documentElement.lang.startsWith('fr')
      ? 'SaKgaZé — Surveillance des sargasses · Caraïbe'
      : 'SaKgaZé — Sargassum surveillance · Caribbean'
  }, [t])


  return (
    <div className="sak-stage relative">
      <Intro />
      <MapStage />
      {coastalRisk && <CoastalRiskPanel />}
      {oceanFlow && (
        <>
          <OceanFlowGate enabled />
          <ShaderLayers enabled />
        </>
      )}
      <Header />
      <LayerControl />
      <Timeline />
      <Inspector />
      <Minimap />
    </div>
  )
}

