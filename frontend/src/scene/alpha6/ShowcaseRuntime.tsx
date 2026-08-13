import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { SpatialNode } from '../../api/types'
import type { Alpha5Event } from '../alpha5/ThemeSystem'
import { AUTO_DEMO_ORDER, SHOWCASE_CLIPS, type ShowcaseClipName } from './ShowcaseSequenceConfig'

export type ShowcaseRuntimeState = {
  active: boolean
  demoMode: boolean
  clip: ShowcaseClipName | null
  startedAt: number
  duration: number
  serial: number
  source: 'none' | 'server' | 'demo'
}

function eventClip(event: Alpha5Event | null, workStatus: string): ShowcaseClipName | null {
  if (event?.kind === 'capability_awakened') return 'server_awakening'
  if (event?.kind === 'evidence_verified') return 'server_verification'
  if (event?.kind === 'work_sample_stage') {
    if (event.state === 'revision_required') return 'server_revision'
    if (event.state === 'transfer_ready') return 'server_transfer'
    if (event.state === 'completed') return 'server_completed'
  }
  if (workStatus === 'completed') return null
  return null
}

function readDemoMode() {
  if (typeof window === 'undefined') return false
  const query = new URLSearchParams(window.location.search)
  return query.get('demo') === '1' || query.get('showcase') === '1'
}

export function useShowcaseRuntime(event: Alpha5Event | null, workStatus: string): ShowcaseRuntimeState {
  const demoMode = useMemo(readDemoMode, [])
  const [runtime, setRuntime] = useState<ShowcaseRuntimeState>({ active: false, demoMode, clip: null, startedAt: 0, duration: 0, serial: 0, source: 'none' })
  const lastServerEvent = useRef<string | null>(null)
  const demoIndex = useRef(-1)
  const demoStart = useRef<number | null>(null)

  useEffect(() => {
    const clip = eventClip(event, workStatus)
    if (!clip || !event || event.id === lastServerEvent.current) return
    lastServerEvent.current = event.id
    setRuntime((current) => ({
      active: true,
      demoMode,
      clip,
      startedAt: 0,
      duration: SHOWCASE_CLIPS[clip].duration,
      serial: current.serial + 1,
      source: 'server',
    }))
  }, [event, workStatus, demoMode])

  useFrame((state) => {
    const now = state.clock.elapsedTime

    if (runtime.source === 'server' && runtime.active) {
      if (runtime.startedAt === 0) {
        setRuntime((current) => current.source === 'server' ? { ...current, startedAt: now } : current)
        return
      }
      if (now - runtime.startedAt >= runtime.duration) {
        setRuntime((current) => current.source === 'server' ? { ...current, active: false, clip: null, source: 'none', startedAt: now } : current)
      }
      return
    }

    if (!demoMode || runtime.source === 'server') return
    if (demoStart.current === null) demoStart.current = now
    const elapsed = now - demoStart.current
    let cursor = 0
    let selected = AUTO_DEMO_ORDER[0]
    let selectedIndex = 0
    const total = AUTO_DEMO_ORDER.reduce((sum, name) => sum + SHOWCASE_CLIPS[name].duration, 0)
    const local = total > 0 ? elapsed % total : 0
    for (let index = 0; index < AUTO_DEMO_ORDER.length; index += 1) {
      const name = AUTO_DEMO_ORDER[index]
      const duration = SHOWCASE_CLIPS[name].duration
      if (local >= cursor && local < cursor + duration) {
        selected = name
        selectedIndex = index
        break
      }
      cursor += duration
    }
    if (demoIndex.current !== selectedIndex || runtime.source !== 'demo') {
      demoIndex.current = selectedIndex
      setRuntime((current) => ({
        active: true,
        demoMode: true,
        clip: selected,
        startedAt: now - (local - cursor),
        duration: SHOWCASE_CLIPS[selected].duration,
        serial: current.serial + 1,
        source: 'demo',
      }))
    }
  })

  return runtime
}

export function showcaseProgress(runtime: ShowcaseRuntimeState, elapsedTime: number) {
  if (!runtime.active || !runtime.clip || runtime.duration <= 0 || runtime.startedAt <= 0) return 0
  return Math.max(0, Math.min(1, (elapsedTime - runtime.startedAt) / runtime.duration))
}

export function ShowcaseDemoBadge({ runtime, nodes }: { runtime: ShowcaseRuntimeState; nodes: SpatialNode[] }) {
  if (!runtime.demoMode) return null
  const verified = nodes.filter((node) => node.kind === 'capability' && String(node.data?.verificationLevel || node.state) === 'verified_evidence').length
  return (
    <Html fullscreen pointerEvents="none" style={{ pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', left: 24, bottom: 24, padding: '10px 14px', border: '1px solid rgba(126,244,226,.35)', background: 'rgba(2,8,13,.72)', backdropFilter: 'blur(14px)', borderRadius: 12, color: '#dff8f4', fontFamily: 'system-ui, sans-serif', letterSpacing: '.08em', textTransform: 'uppercase', fontSize: 10 }}>
        <strong style={{ display: 'block', color: '#74f4df', fontSize: 11 }}>Showcase Auto Demo</strong>
        <span>visual rehearsal · server state unchanged · verified={verified}</span>
      </div>
    </Html>
  )
}
