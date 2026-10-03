import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Ocean Flow Mode: OPTIONAL lazy Three.js particle atmosphere.
 * Loaded only when enabled; if dynamic import fails, app continues normally.
 * Mobile: fewer particles. prefers-reduced-motion: never auto-animates.
 */
export default function OceanFlowGate({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!enabled) return
    let disposed = false

    void (async () => {
      try {
        const THREE = (await import('three')) as typeof import('three')
        if (disposed || !containerRef.current) return
        const container = containerRef.current

        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
        renderer.setSize(container.clientWidth, container.clientHeight)
        container.appendChild(renderer.domElement)

        const scene = new THREE.Scene()
        const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100)
        camera.position.z = 3

        const isMobile = window.innerWidth < 768
        const COUNT = isMobile ? 400 : 1200
        const positions = new Float32Array(COUNT * 3)
        const speeds = new Float32Array(COUNT)
        for (let i = 0; i < COUNT; i++) {
          positions[i * 3] = (Math.random() - 0.5) * 6
          positions[i * 3 + 1] = (Math.random() - 0.5) * 4
          positions[i * 3 + 2] = (Math.random() - 0.5) * 2
          speeds[i] = 0.0004 + Math.random() * 0.0009
        }
        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        const material = new THREE.PointsMaterial({
          color: new THREE.Color('#67E8F9'),
          size: 0.02,
          transparent: true,
          opacity: 0.55,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
        const points = new THREE.Points(geometry, material)
        scene.add(points)

        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        let raf = 0
        const tick = () => {
          if (disposed) return
          raf = requestAnimationFrame(tick)
          if (!reduced) {
            const pos = geometry.attributes.position as import('three').BufferAttribute & { array: Float32Array }
            for (let i = 0; i < pos.array.length; i += 3) {
              pos.array[i] += speeds[i / 3]
              if (pos.array[i] > 3) pos.array[i] = -3
            }
            pos.needsUpdate = true
          }
          renderer.render(scene, camera)
        }
        raf = requestAnimationFrame(tick)

        const onResize = () => {
          if (!container) return
          renderer.setSize(container.clientWidth, container.clientHeight)
          camera.aspect = container.clientWidth / container.clientHeight
          camera.updateProjectionMatrix()
        }
        window.addEventListener('resize', onResize)

        cleanupRef.current = () => {
          cancelAnimationFrame(raf)
          window.removeEventListener('resize', onResize)
          renderer.dispose()
          geometry.dispose()
          material.dispose()
          renderer.domElement.remove()
        }
      } catch {
        if (!disposed) setFailed(true)
      }
    })()

    return () => {
      disposed = true
      cleanupRef.current?.()
      cleanupRef.current = null
    }
  }, [enabled])

  if (!enabled) return null

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute inset-0 z-10"
      aria-hidden="true"
      title={failed ? (t('oceanFlow.failed') as string) : undefined}
    />
  )
}
