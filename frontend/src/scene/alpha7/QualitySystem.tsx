import { Html } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  classifyRenderer,
  getMotionMode,
  postSpatialRuntimeTelemetry,
  runtimeDeviceSnapshot,
} from '../alpha8/RuntimeTelemetry'

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

function percentile(values: number[], p: number): number {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const index = Math.max(0, Math.min(sorted.length - 1, Math.ceil(sorted.length * p) - 1))
  return Math.round(sorted[index] * 100) / 100
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
  const pixelLoad = Math.max(1, window.innerWidth * window.innerHeight * Math.min(window.devicePixelRatio || 1, 2))

  // Motion accessibility and render quality are intentionally independent. A user may
  // keep Ultra materials while asking the runtime to stop continuous animation.
  if (memory <= 2 || cores <= 2 || pixelLoad > 8_000_000) return 'safe'
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
      const kind = event.type === 'webglcontextlost' ? 'context_lost' : 'context_restored'
      if (event.type === 'webglcontextlost' && 'preventDefault' in event) event.preventDefault()
      persistSafeContext()
      setTier('safe')
      postSpatialRuntimeTelemetry({
        event: kind,
        qualityTier: 'safe',
        qualityRequest: request,
        reason: kind,
        ...runtimeDeviceSnapshot(),
      })
    }
    document.addEventListener('webglcontextlost', forceSafe, true)
    document.addEventListener('webglcontextrestored', forceSafe, true)
    return () => {
      document.removeEventListener('webglcontextlost', forceSafe, true)
      document.removeEventListener('webglcontextrestored', forceSafe, true)
    }
  }, [request])

  return { request, tier, setTier, fps, setFps, locked, profile: QUALITY_PROFILES[tier] }
}

export function AdaptiveFrameBudget({ tier, locked, onTier, onFps }: {
  tier: QualityTier
  locked: boolean
  onTier: (tier: QualityTier) => void
  onFps: (fps: number) => void
}) {
  const { gl, setFrameloop, invalidate } = useThree()
  const request = useMemo(() => getQualityRequest(), [])
  const motionMode = useMemo(() => getMotionMode(), [])
  const sample = useRef({ frames: 0, seconds: 0, lowWindows: 0, frameTimes: [] as number[] })
  const downgraded = useRef(new Set<QualityTier>())
  const bootSent = useRef(false)

  useEffect(() => {
    // In reduced/off motion the scene keeps its material/quality profile but renders on
    // demand instead of running a perpetual animation loop. Pointer/state invalidations
    // still render fresh frames without continuous camera/particle movement.
    setFrameloop(motionMode === 'full' ? 'always' : 'demand')
    invalidate()
    return () => setFrameloop('always')
  }, [invalidate, motionMode, setFrameloop])

  useEffect(() => {
    if (bootSent.current) return
    bootSent.current = true
    const context = gl.getContext()
    const rawRenderer = String(context.getParameter(context.RENDERER) || '')
    const webgl2 = typeof WebGL2RenderingContext !== 'undefined' && context instanceof WebGL2RenderingContext
    const caps = gl.capabilities
    postSpatialRuntimeTelemetry({
      event: 'boot',
      qualityTier: tier,
      qualityRequest: request,
      reason: 'boot',
      ...runtimeDeviceSnapshot(),
      gpu: {
        rendererClass: classifyRenderer(rawRenderer),
        webglVersion: webgl2 ? 'webgl2' : 'webgl1',
        maxTextureSize: caps.maxTextureSize,
        maxTextures: caps.maxTextures,
        maxSamples: caps.maxSamples,
        precision: caps.precision || 'unknown',
      },
    })
  }, [gl, request, tier])

  useEffect(() => {
    if (locked) return
    const caps = gl.capabilities
    const renderer = gl.getContext().getParameter(gl.getContext().RENDERER) as string | null
    const rendererText = String(renderer || '').toLowerCase()
    const constrained = caps.maxTextureSize < 8192 || caps.maxTextures < 16 || /swiftshader|llvmpipe|software/.test(rendererText)
    if (constrained && tier !== 'safe') {
      const next = tier === 'ultra' ? 'balanced' : lowerQuality(tier)
      onTier(next)
      postSpatialRuntimeTelemetry({
        event: 'quality_change', qualityTier: next, qualityRequest: request,
        reason: 'webgl_capability', ...runtimeDeviceSnapshot(),
      })
    }
  }, [gl, locked, onTier, request, tier])

  useFrame((_, delta) => {
    const dt = Math.min(.1, Math.max(.0001, delta))
    sample.current.frames += 1
    sample.current.seconds += dt
    sample.current.frameTimes.push(dt * 1000)
    if (sample.current.frameTimes.length > 360) sample.current.frameTimes.shift()
    if (sample.current.seconds < 4) return

    const fps = sample.current.frames / sample.current.seconds
    const roundedFps = Math.round(fps)
    onFps(roundedFps)
    postSpatialRuntimeTelemetry({
      event: 'frame_sample',
      qualityTier: tier,
      qualityRequest: request,
      reason: 'sample',
      fps: Math.round(fps * 100) / 100,
      frameTime: {
        p50: percentile(sample.current.frameTimes, .50),
        p95: percentile(sample.current.frameTimes, .95),
        p99: percentile(sample.current.frameTimes, .99),
      },
      ...runtimeDeviceSnapshot(),
    })

    if (!locked) {
      const target = QUALITY_PROFILES[tier].targetFps
      sample.current.lowWindows = fps < target * .78 ? sample.current.lowWindows + 1 : Math.max(0, sample.current.lowWindows - 1)
      if (sample.current.lowWindows >= 2 && tier !== 'safe' && !downgraded.current.has(tier)) {
        downgraded.current.add(tier)
        const next = lowerQuality(tier)
        onTier(next)
        postSpatialRuntimeTelemetry({
          event: 'quality_change', qualityTier: next, qualityRequest: request,
          reason: 'sustained_low_fps', fps: Math.round(fps * 100) / 100,
          ...runtimeDeviceSnapshot(),
        })
        sample.current.lowWindows = 0
      }
    }

    sample.current.frames = 0
    sample.current.seconds = 0
    sample.current.frameTimes = []
  })

  return null
}

export function QualityTelemetryBadge({ tier, fps, locked }: { tier: QualityTier; fps: number; locked: boolean }) {
  if (typeof window === 'undefined') return null
  const debug = new URLSearchParams(window.location.search).get('qualitydebug') === '1'
  const motionMode = getMotionMode()
  if (!debug && tier !== 'safe' && motionMode === 'full') return null
  return (
    <Html transform center distanceFactor={8.5} position={[-7.2, 5.9, 2.8]} pointerEvents="none">
      <div className="presentation-event-label">
        <span>RENDER BUDGET {locked ? 'LOCKED' : 'AUTO'}</span>
        <strong>{tier.toUpperCase()}</strong>
        <small>{fps ? `${fps} FPS sampled` : 'measuring frame budget'} · MOTION {motionMode.toUpperCase()}</small>
      </div>
    </Html>
  )
}
