import { Html } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'

export type QualityTier = 'ultra' | 'high' | 'balanced' | 'safe'
export type QualityRequest = 'auto' | QualityTier

export type QualityProfile = {
  tier: QualityTier
  dprMax: number
  composerPixelRatio: number
  ssr: boolean
  volumetric: boolean
  bloom: boolean
  topologySize: number
  dataFieldCount: number
  cubeResolution: number
  reflectorResolution: number
  transmissionResolution: number
  transmissionSamples: number
  shadows: boolean
  sparkleScale: number
  targetFps: number
}

export const QUALITY_PROFILES: Record<QualityTier, QualityProfile> = {
  ultra: {
    tier: 'ultra', dprMax: 2, composerPixelRatio: 1.35, ssr: true, volumetric: true, bloom: true,
    topologySize: 48, dataFieldCount: 1800, cubeResolution: 256, reflectorResolution: 512,
    transmissionResolution: 160, transmissionSamples: 3, shadows: true, sparkleScale: 1, targetFps: 50,
  },
  high: {
    tier: 'high', dprMax: 1.65, composerPixelRatio: 1.08, ssr: true, volumetric: true, bloom: true,
    topologySize: 40, dataFieldCount: 1200, cubeResolution: 128, reflectorResolution: 384,
    transmissionResolution: 128, transmissionSamples: 2, shadows: true, sparkleScale: .78, targetFps: 48,
  },
  balanced: {
    tier: 'balanced', dprMax: 1.35, composerPixelRatio: 1, ssr: false, volumetric: false, bloom: true,
    topologySize: 32, dataFieldCount: 720, cubeResolution: 128, reflectorResolution: 256,
    transmissionResolution: 96, transmissionSamples: 2, shadows: true, sparkleScale: .5, targetFps: 42,
  },
  safe: {
    tier: 'safe', dprMax: 1, composerPixelRatio: 1, ssr: false, volumetric: false, bloom: false,
    topologySize: 24, dataFieldCount: 320, cubeResolution: 64, reflectorResolution: 128,
    transmissionResolution: 64, transmissionSamples: 1, shadows: false, sparkleScale: .22, targetFps: 34,
  },
}

const ORDER: QualityTier[] = ['safe', 'balanced', 'high', 'ultra']
const SESSION_KEY = 'stepin.spatial.quality.auto'
const CONTEXT_LOST_KEY = 'stepin.spatial.context_lost'

function isTier(value: string | null): value is QualityTier {
  return value === 'ultra' || value === 'high' || value === 'balanced' || value === 'safe'
}

function persistSafeContext() {
  try {
    window.sessionStorage.setItem(SESSION_KEY, 'safe')
    window.sessionStorage.setItem(CONTEXT_LOST_KEY, String(Date.now()))
  } catch {
    // Storage can be unavailable in hardened WebView environments.
  }
}

export function getQualityRequest(): QualityRequest {
  if (typeof window === 'undefined') return 'auto'
  const value = new URLSearchParams(window.location.search).get('quality')
  return isTier(value) ? value : 'auto'
}

export function detectInitialQuality(): QualityTier {
  if (typeof navigator === 'undefined' || typeof window === 'undefined') return 'high'
  const nav = navigator as Navigator & { deviceMemory?: number }
  const cores = nav.hardwareConcurrency || 4
  const memory = nav.deviceMemory || 4
  const userAgent = nav.userAgent || ''
  const isWebView = /WebView2|; wv\)|\bwv\b/i.test(userAgent)
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const pixelLoad = Math.max(1, window.innerWidth * window.innerHeight * Math.min(window.devicePixelRatio || 1, 2))

  if (reducedMotion || memory <= 2 || cores <= 2 || pixelLoad > 8_000_000) return 'safe'
  if (isWebView || memory <= 4 || cores <= 4 || pixelLoad > 5_200_000) return 'balanced'
  if (memory >= 8 && cores >= 8 && pixelLoad < 4_200_000) return 'ultra'
  return 'high'
}

export function initialQualityForRequest(request: QualityRequest): QualityTier {
  if (request !== 'auto') return request
  if (typeof window !== 'undefined') {
    const stored = window.sessionStorage.getItem(SESSION_KEY)
    if (isTier(stored)) return stored
  }
  return detectInitialQuality()
}

export function lowerQuality(tier: QualityTier): QualityTier {
  const index = ORDER.indexOf(tier)
  return ORDER[Math.max(0, index - 1)]
}

export function useQualityState() {
  const request = useMemo(() => getQualityRequest(), [])
  const [tier, setTier] = useState<QualityTier>(() => initialQualityForRequest(request))
  const [fps, setFps] = useState(0)
  const locked = request !== 'auto'

  useEffect(() => {
    if (!locked && typeof window !== 'undefined') window.sessionStorage.setItem(SESSION_KEY, tier)
  }, [tier, locked])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const forceSafe = (event: Event) => {
      if (event.type === 'webglcontextlost' && 'preventDefault' in event) event.preventDefault()
      persistSafeContext()
      setTier('safe')
    }
    document.addEventListener('webglcontextlost', forceSafe, true)
    document.addEventListener('webglcontextrestored', forceSafe, true)
    return () => {
      document.removeEventListener('webglcontextlost', forceSafe, true)
      document.removeEventListener('webglcontextrestored', forceSafe, true)
    }
  }, [])

  return { request, tier, setTier, fps, setFps, locked, profile: QUALITY_PROFILES[tier] }
}

export function AdaptiveFrameBudget({ tier, locked, onTier, onFps }: {
  tier: QualityTier
  locked: boolean
  onTier: (tier: QualityTier) => void
  onFps: (fps: number) => void
}) {
  const { gl } = useThree()
  const sample = useRef({ frames: 0, seconds: 0, lowWindows: 0, lastReport: 0 })
  const downgraded = useRef(new Set<QualityTier>())

  useEffect(() => {
    if (locked) return
    const caps = gl.capabilities
    const renderer = gl.getContext().getParameter(gl.getContext().RENDERER) as string | null
    const rendererText = String(renderer || '').toLowerCase()
    const constrained = caps.maxTextureSize < 8192 || caps.maxTextures < 16 || /swiftshader|llvmpipe|software/.test(rendererText)
    if (constrained && tier !== 'safe') onTier(tier === 'ultra' ? 'balanced' : lowerQuality(tier))
  }, [gl, locked, onTier, tier])

  useFrame((_, delta) => {
    const dt = Math.min(.1, Math.max(.0001, delta))
    sample.current.frames += 1
    sample.current.seconds += dt
    sample.current.lastReport += dt
    if (sample.current.seconds < 4) return

    const fps = sample.current.frames / sample.current.seconds
    if (sample.current.lastReport >= 4) {
      onFps(Math.round(fps))
      sample.current.lastReport = 0
    }

    if (!locked) {
      const target = QUALITY_PROFILES[tier].targetFps
      sample.current.lowWindows = fps < target * .78 ? sample.current.lowWindows + 1 : Math.max(0, sample.current.lowWindows - 1)
      if (sample.current.lowWindows >= 2 && tier !== 'safe' && !downgraded.current.has(tier)) {
        downgraded.current.add(tier)
        onTier(lowerQuality(tier))
        sample.current.lowWindows = 0
      }
    }

    sample.current.frames = 0
    sample.current.seconds = 0
  })

  return null
}

export function QualityTelemetryBadge({ tier, fps, locked }: { tier: QualityTier; fps: number; locked: boolean }) {
  if (typeof window === 'undefined') return null
  const debug = new URLSearchParams(window.location.search).get('qualitydebug') === '1'
  if (!debug && tier !== 'safe') return null
  return (
    <Html transform center distanceFactor={8.5} position={[-7.2, 5.9, 2.8]} pointerEvents="none">
      <div className="presentation-event-label">
        <span>RENDER BUDGET {locked ? 'LOCKED' : 'AUTO'}</span>
        <strong>{tier.toUpperCase()}</strong>
        <small>{fps ? `${fps} FPS sampled` : 'measuring frame budget'}</small>
      </div>
    </Html>
  )
}
