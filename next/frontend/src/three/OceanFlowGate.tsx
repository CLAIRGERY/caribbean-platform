import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Ocean Flow Mode — premium three.js particle field with depth parallax.
 * OPTIONAL + LAZY: only loads when enabled. If the dynamic import or WebGL
 * fails, the app continues normally (map untouched). Mobile gets fewer
 * particles; prefers-reduced-motion never animates.
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

        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: 'low-power' })
        renderer.setClearColor(0x000000, 0)
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
        renderer.setSize(container.clientWidth, container.clientHeight)
        container.appendChild(renderer.domElement)

        const scene = new THREE.Scene()
        const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100)
        camera.position.z = 3

        const isMobile = window.innerWidth < 768
        const COUNT = isMobile ? 260 : 900
        const positions = new Float32Array(COUNT * 3)
        const speeds = new Float32Array(COUNT)
        // particle drift generally to the WEST (typical Caribbean current direction)
        for (let i = 0; i < COUNT; i++) {
          positions[i * 3] = (Math.random() - 0.5) * 7
          positions[i * 3 + 1] = (Math.random() - 0.5) * 4.5
          positions[i * 3 + 2] = (Math.random() - 0.5) * 2.4
          speeds[i] = 0.0006 + Math.random() * 0.0012
        }
        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        const material = new THREE.PointsMaterial({
          color: new THREE.Color('#8FE9FF'),
          size: 0.022,
          transparent: true,
          opacity: 0.5,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          sizeAttenuation: true,
        })
        const points = new THREE.Points(geometry, material)
        scene.add(points)

        // soft bioluminescent accent field (fewer, violet)
        const ACCENT = isMobile ? 60 : 150
        const aPositions = new Float32Array(ACCENT * 3)
        for (let i = 0; i < ACCENT; i++) {
          aPositions[i * 3] = (Math.random() - 0.5) * 7
          aPositions[i * 3 + 1] = (Math.random() - 0.5) * 4.5
          aPositions[i * 3 + 2] = (Math.random() - 0.5) * 2.4
        }
        const aGeom = new THREE.BufferGeometry()
        aGeom.setAttribute('position', new THREE.BufferAttribute(aPositions, 3))
        const aMat = new THREE.PointsMaterial({
          color: new THREE.Color('#8B7CF6'),
          size: 0.03,
          transparent: true,
          opacity: 0.35,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
        const accents = new THREE.Points(aGeom, aMat)
        scene.add(accents)

        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        let raf = 0
        const tick = () => {
          if (disposed) return
          raf = requestAnimationFrame(tick)
          if (!reduced) {
            // westward flow
            const pos = geometry.attributes.position as import('three').BufferAttribute & { array: Float32Array }
            for (let i = 0; i < pos.array.length; i += 3) {
              pos.array[i] -= speeds[i / 3]
              if (pos.array[i] < -3.5) pos.array[i] = 3.5
            }
            pos.needsUpdate = true
            accents.rotation.z += 0.0004
          }
          renderer.render(scene, camera)
        }
        raf = requestAnimationFrame(tick)

        // cursor depth response (desktop only)
        const onMove = (e: MouseEvent) => {
          const nx = (e.clientX / window.innerWidth - 0.5) * 0.2
          const ny = (e.clientY / window.innerHeight - 0.5) * 0.2
          camera.position.x += (nx - camera.position.x) * 0.04
          camera.position.y += (-ny - camera.position.y) * 0.04
          camera.lookAt(0, 0, 0)
        }
        if (!isMobile) window.addEventListener('mousemove', onMove)

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
          if (!isMobile) window.removeEventListener('mousemove', onMove)
          renderer.dispose()
          geometry.dispose()
          material.dispose()
          aGeom.dispose()
          aMat.dispose()
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
