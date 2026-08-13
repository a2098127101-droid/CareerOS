import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialNode } from '../../api/types'

export type Alpha5ThemeName =
  | 'idle'
  | 'analytic'
  | 'revision'
  | 'verification'
  | 'awakening'
  | 'transfer'
  | 'completed'

export type Alpha5EventKind = 'evidence_verified' | 'capability_awakened' | 'work_sample_stage'

export type Alpha5Event = {
  id: string
  kind: Alpha5EventKind
  nodeId: string
  label: string
  state: string
}

export type Alpha5Theme = {
  name: Alpha5ThemeName
  background: string
  fog: string
  fogDensity: number
  key: string
  fill: string
  accent: string
  secondary: string
  warning: string
  exposure: number
  dataEnergy: number
  volumeDensity: number
  particleSpeed: number
  bloom: number
}

const THEMES: Record<Alpha5ThemeName, Alpha5Theme> = {
  idle: {
    name: 'idle', background: '#010408', fog: '#041018', fogDensity: .022,
    key: '#66eadf', fill: '#89a8bc', accent: '#67f0e3', secondary: '#f0b66a', warning: '#e88989',
    exposure: 1.16, dataEnergy: .55, volumeDensity: .46, particleSpeed: .65, bloom: 1.05,
  },
  analytic: {
    name: 'analytic', background: '#01070b', fog: '#04202a', fogDensity: .027,
    key: '#6ef6ed', fill: '#77b4cf', accent: '#62f7e8', secondary: '#86c7ff', warning: '#e88989',
    exposure: 1.22, dataEnergy: .82, volumeDensity: .62, particleSpeed: .9, bloom: 1.18,
  },
  revision: {
    name: 'revision', background: '#080603', fog: '#2a1608', fogDensity: .031,
    key: '#ffc271', fill: '#d7965b', accent: '#ffc069', secondary: '#64d9d4', warning: '#f28b86',
    exposure: 1.17, dataEnergy: .9, volumeDensity: .78, particleSpeed: 1.05, bloom: 1.28,
  },
  verification: {
    name: 'verification', background: '#030704', fog: '#0a281d', fogDensity: .032,
    key: '#80f2bc', fill: '#77b9a0', accent: '#7cf0b8', secondary: '#f1c17d', warning: '#e68988',
    exposure: 1.28, dataEnergy: 1.15, volumeDensity: .92, particleSpeed: 1.18, bloom: 1.42,
  },
  awakening: {
    name: 'awakening', background: '#010805', fog: '#073521', fogDensity: .038,
    key: '#76ffc0', fill: '#96eec7', accent: '#72ffc0', secondary: '#8cf7ed', warning: '#f2a2a2',
    exposure: 1.38, dataEnergy: 1.6, volumeDensity: 1.18, particleSpeed: 1.55, bloom: 1.72,
  },
  transfer: {
    name: 'transfer', background: '#040407', fog: '#16142b', fogDensity: .031,
    key: '#a8b6ff', fill: '#8f9bcf', accent: '#aeb9ff', secondary: '#69eee0', warning: '#e78c8c',
    exposure: 1.2, dataEnergy: 1.05, volumeDensity: .76, particleSpeed: 1.28, bloom: 1.3,
  },
  completed: {
    name: 'completed', background: '#010705', fog: '#0c2f22', fogDensity: .028,
    key: '#88f5c4', fill: '#9fd4bc', accent: '#82f1bb', secondary: '#f3d098', warning: '#db8c8c',
    exposure: 1.25, dataEnergy: 1.22, volumeDensity: .7, particleSpeed: 1.05, bloom: 1.38,
  },
}

export function useAlpha5Event(nodes: SpatialNode[]) {
  const previous = useRef<Map<string, string> | null>(null)
  const [event, setEvent] = useState<Alpha5Event | null>(null)
  const version = nodes.map((node) => `${node.id}:${node.state}:${String(node.data?.verificationStatus || '')}`).join('|')

  useEffect(() => {
    const current = new Map(nodes.map((node) => [node.id, String(node.state || '')]))
    if (!previous.current) {
      previous.current = current
      return
    }

    let next: Alpha5Event | null = null
    for (const node of nodes) {
      const before = previous.current.get(node.id)
      const after = String(node.state || '')
      if (!before || before === after) continue
      if (node.kind === 'capability' && after === 'verified_evidence') {
        next = { id: `${node.id}:${after}:${Date.now()}`, kind: 'capability_awakened', nodeId: node.id, label: node.label, state: after }
        break
      }
      if (node.kind === 'evidence' && (after === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED')) {
        next = { id: `${node.id}:${after}:${Date.now()}`, kind: 'evidence_verified', nodeId: node.id, label: node.label, state: after }
      }
      if (node.id === 'station:work-sample' && ['revision_required', 'transfer_ready', 'completed'].includes(after)) {
        next = { id: `${node.id}:${after}:${Date.now()}`, kind: 'work_sample_stage', nodeId: node.id, label: node.label, state: after }
      }
    }
    previous.current = current
    if (!next) return
    setEvent(next)
    const timer = window.setTimeout(() => setEvent((value) => value?.id === next?.id ? null : value), 6500)
    return () => window.clearTimeout(timer)
  // the compact version string intentionally gates this diff detector.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version])

  return event
}

export function resolveAlpha5Theme(nodes: SpatialNode[], focus: 'hub' | 'foundation' | 'work-sample', event: Alpha5Event | null): Alpha5Theme {
  if (event?.kind === 'capability_awakened') return THEMES.awakening
  if (event?.kind === 'evidence_verified') return THEMES.verification
  const station = nodes.find((node) => node.id === 'station:work-sample')
  const status = String(station?.state || '')
  if (status === 'completed') return THEMES.completed
  if (status === 'transfer_ready') return THEMES.transfer
  if (status === 'revision_required') return THEMES.revision
  if (focus === 'foundation') return THEMES.analytic
  return THEMES.idle
}

export function ThemeLightingDirector({ theme }: { theme: Alpha5Theme }) {
  const { gl, scene } = useThree()
  const ambient = useRef<THREE.AmbientLight>(null)
  const key = useRef<THREE.DirectionalLight>(null)
  const left = useRef<THREE.SpotLight>(null)
  const right = useRef<THREE.SpotLight>(null)
  const bgTarget = useMemo(() => new THREE.Color(theme.background), [theme.background])
  const fogTarget = useMemo(() => new THREE.Color(theme.fog), [theme.fog])
  const keyTarget = useMemo(() => new THREE.Color(theme.key), [theme.key])
  const fillTarget = useMemo(() => new THREE.Color(theme.fill), [theme.fill])
  const accentTarget = useMemo(() => new THREE.Color(theme.accent), [theme.accent])
  const secondaryTarget = useMemo(() => new THREE.Color(theme.secondary), [theme.secondary])

  useEffect(() => {
    if (!(scene.background instanceof THREE.Color)) scene.background = new THREE.Color(theme.background)
    if (!(scene.fog instanceof THREE.FogExp2)) scene.fog = new THREE.FogExp2(theme.fog, theme.fogDensity)
  }, [scene, theme.background, theme.fog, theme.fogDensity])

  useFrame((_, delta) => {
    const k = 1 - Math.exp(-delta * 2.7)
    if (scene.background instanceof THREE.Color) scene.background.lerp(bgTarget, k)
    if (scene.fog instanceof THREE.FogExp2) {
      scene.fog.color.lerp(fogTarget, k)
      scene.fog.density = THREE.MathUtils.damp(scene.fog.density, theme.fogDensity, 2.6, delta)
    }
    gl.toneMappingExposure = THREE.MathUtils.damp(gl.toneMappingExposure, theme.exposure, 2.8, delta)
    if (ambient.current) {
      ambient.current.color.lerp(fillTarget, k)
      ambient.current.intensity = THREE.MathUtils.damp(ambient.current.intensity, .34 + theme.dataEnergy * .12, 3, delta)
    }
    if (key.current) {
      key.current.color.lerp(keyTarget, k)
      key.current.intensity = THREE.MathUtils.damp(key.current.intensity, 2.4 + theme.dataEnergy * .9, 3, delta)
    }
    if (left.current) {
      left.current.color.lerp(accentTarget, k)
      left.current.intensity = THREE.MathUtils.damp(left.current.intensity, 13 + theme.dataEnergy * 8, 3, delta)
    }
    if (right.current) {
      right.current.color.lerp(secondaryTarget, k)
      right.current.intensity = THREE.MathUtils.damp(right.current.intensity, 11 + theme.dataEnergy * 6, 3, delta)
    }
  })

  return (
    <>
      <ambientLight ref={ambient} intensity={.4} color={theme.fill} />
      <hemisphereLight args={[theme.fill, '#090605', .72]} />
      <directionalLight ref={key} position={[5.8, 10, 6.5]} intensity={3} color={theme.key} castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-.00022} />
      <spotLight ref={left} position={[-7.5, 8, 4]} intensity={18} color={theme.accent} distance={19} angle={.44} penumbra={.92} />
      <spotLight ref={right} position={[7.3, 7.5, 3.5]} intensity={16} color={theme.secondary} distance={18} angle={.43} penumbra={.9} />
    </>
  )
}
