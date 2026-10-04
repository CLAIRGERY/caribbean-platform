import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * ShaderLayers — the two required shader effects, RENDERED LAZILY together:
 *  1. OceanAtmosphereShader: subtle animated depth-gradient noise (background)
 *  2. CurrentFlowShader: directional cyan streaks suggesting a current field
 *
 * Both compile only after Ocean Flow is enabled so THREE stays off the initial
 * bundle. Uses additive blending over the map so it never blocks the geographic
 * canvas (pointer-events: none). Fails silently if WebGL is unavailable.
 */

const VERT = /* glsl */ `
  void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }
`

const FRAG_ATMOSPHERE = /* glsl */ `
  precision mediump float;
  uniform float uTime;
  uniform vec2 uRes;
  // classic value-noise / fbm (cheap, no textures)
  float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p){
    vec2 i = floor(p); vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  float fbm(vec2 p){ float v = 0.0; float a = 0.5;
    for (int i = 0; i < 4; i++){ v += a * noise(p); p *= 2.03; a *= 0.5; }
    return v; }
  void main(){
    vec2 uv = gl_FragCoord.xy / uRes.xy;
    float t = uTime * 0.03;
    // dark-to-cyan depth gradient + slow moving noise
    vec3 deep = vec3(0.02, 0.08, 0.16);
    vec3 shallow = vec3(0.04, 0.45, 0.55);
    float g = pow(1.0 - uv.y, 2.2);
    vec3 col = mix(deep, shallow, g * 0.16);
    float n = fbm(uv * 3.4 + vec2(t * 0.5, t * 0.3));
    col += vec3(0.02, 0.20, 0.26) * (n - 0.5) * 0.24;
    col *= 0.55 + 0.45 * fbm(uv * 5.0 - vec2(t * 0.4, 0.0));
    gl_FragColor = vec4(col, 0.20);
  }
`

const FRAG_CURRENTFLOW = /* glsl */ `
  precision mediump float;
  uniform float uTime;
  uniform vec2 uRes;
  // directional streaks: cyan filaments flowing WEST
  float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p){
    vec2 i = floor(p); vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
  }
  void main(){
    vec2 uv = gl_FragCoord.xy / uRes.xy;
    float y = uv.y;
    float drift = uTime * 0.045;
    // filament: high-frequency streak band convolved with slow-moving noise
    vec2 p = vec2(uv.x * 4.0 + drift * 4.0, y * 22.0);
    float streaks = sin(p.y + sin(p.x * 0.35 + drift * 0.6) * 0.6) * 0.5 + 0.5;
    float motive = noise(vec2(uv.x * 3.0 - drift * 1.2, uv.y * 7.0 + drift * 0.4));
    float intensity = smoothstep(0.55, 1.0, streaks * (0.35 + 0.65 * motive));
    // vertical attenuation: stronger mid-water
    float band = smoothstep(0.0, 0.45, y) * (1.0 - smoothstep(0.55, 1.0, y)) + 0.15;
    vec3 col = vec3(0.02, 0.55, 0.62) * intensity * band;
    gl_FragColor = vec4(col, 0.16);
  }
`

export default function ShaderLayers({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!enabled) return
    let disposed = false

    void (async () => {
      try {
        const THREE = await import('three')
        if (disposed || !containerRef.current) return
        const container = containerRef.current

        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: 'low-power' })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25))
        renderer.setSize(container.clientWidth, container.clientHeight)
        container.appendChild(renderer.domElement)

        const scene = new THREE.Scene()
        const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)

        const mkMat = (frag: string): import('three').ShaderMaterial =>
          new THREE.ShaderMaterial({
            vertexShader: VERT,
            fragmentShader: frag,
            uniforms: { uTime: { value: 0 }, uRes: { value: [container.clientWidth, container.clientHeight] } },
            transparent: true,
            depthWrite: false,
          })

        const atmo = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mkMat(FRAG_ATMOSPHERE))
        const current = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mkMat(FRAG_CURRENTFLOW))

        // Render atmo first, currents additively on top
        // ( amphibious layered as a single additive-on-top pass; keep one render per frame )
        const group = new THREE.Group()
        group.add(atmo)
        group.add(current)
        scene.add(group)

        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        const clock = new THREE.Clock()
        let raf = 0
        const tick = () => {
          if (disposed) return
          raf = requestAnimationFrame(tick)
          if (!reduced) {
            for (const m of [atmo, current] as import('three').Mesh[]) {
              const mat = m.material as import('three').ShaderMaterial
              mat.uniforms.uTime.value = clock.getElapsedTime()
            }
          }
          renderer.render(scene, camera)
        }
        raf = requestAnimationFrame(tick)

        const onResize = () => {
          renderer.setSize(container.clientWidth, container.clientHeight)
          camera.updateProjectionMatrix()
        }
        window.addEventListener('resize', onResize)

        cleanupRef.current = () => {
          cancelAnimationFrame(raf)
          window.removeEventListener('resize', onResize)
          renderer.dispose()
          atmo.geometry.dispose()
          ;(atmo.material as import('three').ShaderMaterial).dispose()
          current.geometry.dispose()
          ;(current.material as import('three').ShaderMaterial).dispose()
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
      className="pointer-events-none absolute inset-0 z-20"
      aria-hidden="true"
      title={failed ? (t('oceanFlow.failed') as string) : undefined}
    />
  )
}
