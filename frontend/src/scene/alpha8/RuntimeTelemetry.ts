export type MotionMode = 'full' | 'reduced' | 'off'
export type RuntimeTelemetryEvent = 'boot' | 'frame_sample' | 'quality_change' | 'context_lost' | 'context_restored'

const RUN_KEY = 'stepin.spatial.runtime.run_id'

export function getMotionMode(): MotionMode {
  if (typeof window === 'undefined') return 'full'
  const value = new URLSearchParams(window.location.search).get('motion')
  if (value === 'full' || value === 'reduced' || value === 'off') return value
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  return prefersReduced ? 'reduced' : 'full'
}

export function isShowcaseDemo(): boolean {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return params.get('demo') === '1' || params.get('showcase') === '1'
}

export function runtimeRunId(): string {
  if (typeof window === 'undefined') return 'server-render'
  try {
    const stored = window.sessionStorage.getItem(RUN_KEY)
    if (stored) return stored
    const value = globalThis.crypto?.randomUUID?.() || `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    window.sessionStorage.setItem(RUN_KEY, value)
    return value
  } catch {
    return `run-${Date.now().toString(36)}`
  }
}

export function classifyRenderer(renderer: string | null | undefined): string {
  const value = String(renderer || '').toLowerCase()
  if (/swiftshader|llvmpipe|software/.test(value)) return 'software'
  if (/nvidia|geforce|quadro|rtx|gtx/.test(value)) return 'nvidia'
  if (/amd|radeon|ati/.test(value)) return 'amd'
  if (/intel/.test(value)) return 'intel'
  if (/apple/.test(value)) return 'apple'
  if (/qualcomm|adreno/.test(value)) return 'qualcomm'
  if (/arm|mali/.test(value)) return 'arm'
  return value ? 'other' : 'unknown'
}

function bucketDimension(value: number): number {
  return Math.max(160, Math.round(value / 160) * 160)
}

function bucketCores(value: number): number {
  if (value <= 2) return 2
  if (value <= 4) return 4
  if (value <= 8) return 8
  if (value <= 16) return 16
  return 32
}

function bucketMemory(value: number): number {
  if (value <= 2) return 2
  if (value <= 4) return 4
  if (value <= 8) return 8
  if (value <= 16) return 16
  return 32
}

export function runtimeDeviceSnapshot() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return { viewport: { width: 160, height: 160, dpr: 1 }, device: { cores: 0, memoryGb: 0, webview: false } }
  }
  const nav = navigator as Navigator & { deviceMemory?: number }
  return {
    viewport: {
      width: bucketDimension(window.innerWidth),
      height: bucketDimension(window.innerHeight),
      dpr: Math.round(Math.min(4, Math.max(.5, window.devicePixelRatio || 1)) * 10) / 10,
    },
    device: {
      cores: bucketCores(nav.hardwareConcurrency || 0),
      memoryGb: bucketMemory(nav.deviceMemory || 0),
      webview: /WebView2|; wv\)|\bwv\b/i.test(nav.userAgent || ''),
    },
  }
}

export function postSpatialRuntimeTelemetry(payload: Record<string, unknown>): void {
  if (typeof window === 'undefined') return
  const body = {
    ...payload,
    runId: runtimeRunId(),
    motionMode: getMotionMode(),
    demoMode: isShowcaseDemo(),
  }
  void fetch('/api/spatial-runtime/v1/telemetry', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => {
    // Runtime telemetry is certification evidence only; it must never block practice.
  })
}
