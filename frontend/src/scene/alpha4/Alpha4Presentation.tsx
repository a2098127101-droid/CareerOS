import { CameraControls, Edges, Float, Html, Line, RoundedBox, Sparkles } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../../api/types'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

export type Alpha4Event = {
  id: string
  kind: 'capability_awakened' | 'evidence_verified' | 'work_sample_stage'
  nodeId: string
  label: string
  state: string
}

const C = {
  cyan: '#69f3e5',
  amber: '#ffc77b',
  green: '#75ffc0',
  blue: '#78b8ff',
  rose: '#f28d91',
  ivory: '#f4efe7',
  dark: '#071018',
}

export function evidencePosition(index: number): Vec3 {
  const col = index % 3
  const row = Math.floor(index / 3)
  return [-6.05 + (col - 1) * .72, 1.04 + row * .58, -2.04]
}

export function capabilityPosition(index: number): Vec3 {
  const ring = index < 5 ? 0 : 1
  const local = index % 5
  const a = local / 5 * Math.PI * 2 - Math.PI / 2 + ring * .24
  const rx = ring ? 3.05 : 2.05
  const ry = ring ? 1.48 : .98
  return [Math.cos(a) * rx, 3.42 + Math.sin(a) * ry, -6.22]
}

function nodePositionMap(nodes: SpatialNode[]) {
  const map = new Map<string, Vec3>()
  nodes.filter((node) => node.kind === 'evidence').slice(0, 15).forEach((node, index) => map.set(node.id, evidencePosition(index)))
  nodes.filter((node) => node.kind === 'capability').slice(0, 10).forEach((node, index) => map.set(node.id, capabilityPosition(index)))
  return map
}

export function useAlpha4Event(nodes: SpatialNode[]) {
  const previous = useRef<Map<string, string> | null>(null)
  const [event, setEvent] = useState<Alpha4Event | null>(null)

  useEffect(() => {
    const current = new Map(nodes.map((node) => [node.id, node.state]))
    if (!previous.current) {
      previous.current = current
      return
    }

    let next: Alpha4Event | null = null
    for (const node of nodes) {
      const before = previous.current.get(node.id)
      if (!before || before === node.state) continue
      if (node.kind === 'capability' && node.state === 'verified_evidence') {
        next = { id: `${node.id}:${Date.now()}`, kind: 'capability_awakened', nodeId: node.id, label: node.label, state: node.state }
        break
      }
      if (node.kind === 'evidence' && node.state === 'verified') {
        next = { id: `${node.id}:${Date.now()}`, kind: 'evidence_verified', nodeId: node.id, label: node.label, state: node.state }
      }
      if (node.id === 'station:work-sample' && ['revision_required', 'transfer_ready', 'completed'].includes(node.state)) {
        next = { id: `${node.id}:${Date.now()}`, kind: 'work_sample_stage', nodeId: node.id, label: node.label, state: node.state }
      }
    }

    previous.current = current
    if (!next) return
    setEvent(next)
    const timer = window.setTimeout(() => setEvent((value) => value?.id === next?.id ? null : value), 5200)
    return () => window.clearTimeout(timer)
  }, [nodes])

  return event
}

function focusShot(focus: Focus): { eye: Vec3; target: Vec3 } {
  if (focus === 'foundation') return { eye: [-3.85, 3.0, 5.3], target: [-2.95, 1.45, -.55] }
  if (focus === 'work-sample') return { eye: [3.85, 3.0, 5.3], target: [2.95, 1.45, -.55] }
  return { eye: [0, 5.25, 12.6], target: [0, 2.05, -2.15] }
}

export function DirectorCamera({ controls, focus, event, nodes }: { controls: RefObject<CameraControls | null>; focus: Focus; event: Alpha4Event | null; nodes: SpatialNode[] }) {
  useEffect(() => {
    const camera = controls.current
    if (!camera) return
    const timers: number[] = []
    const set = (eye: Vec3, target: Vec3, smooth = true) => camera.setLookAt(...eye, ...target, smooth)
    const base = focusShot(focus)

    if (!event) {
      void set(base.eye, base.target)
      return
    }

    if (event.kind === 'capability_awakened') {
      const capabilities = nodes.filter((node) => node.kind === 'capability').slice(0, 10)
      const index = Math.max(0, capabilities.findIndex((node) => node.id === event.nodeId))
      const target = capabilityPosition(index)
      void set([target[0] * .6, target[1] + 1.1, 1.2], target)
      timers.push(window.setTimeout(() => void set([target[0] * .34, target[1] + .35, -1.35], target), 1100))
      timers.push(window.setTimeout(() => void set(base.eye, base.target), 4050))
    } else if (event.kind === 'evidence_verified') {
      void set([-7.8, 3.2, 2.65], [-6.05, 2.2, -2.0])
      timers.push(window.setTimeout(() => void set([-6.9, 2.65, .4], [-6.05, 2.15, -2.0]), 850))
      timers.push(window.setTimeout(() => void set(base.eye, base.target), 3600))
    } else {
      void set([7.65, 4.0, 2.65], [5.8, 2.65, -2.0])
      timers.push(window.setTimeout(() => void set([6.85, 3.3, .45], [5.8, 2.65, -2.0]), 850))
      timers.push(window.setTimeout(() => void set(base.eye, base.target), 3900))
    }

    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [controls, event, focus, nodes])
  return null
}

function FlowParticles({ curve, color, phase }: { curve: THREE.QuadraticBezierCurve3; color: string; phase: number }) {
  const geometry = useMemo(() => {
    const positions = new Float32Array(24 * 3)
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return g
  }, [])

  useEffect(() => () => geometry.dispose(), [geometry])
  useFrame((state) => {
    const attr = geometry.getAttribute('position') as THREE.BufferAttribute
    for (let i = 0; i < 24; i++) {
      const t = (state.clock.elapsedTime * .17 + phase + i / 24) % 1
      const p = curve.getPoint(t)
      const shimmer = Math.sin(state.clock.elapsedTime * 5 + i * 1.7) * .018
      attr.setXYZ(i, p.x, p.y + shimmer, p.z)
    }
    attr.needsUpdate = true
  })

  return <points geometry={geometry}><pointsMaterial color={color} size={.055} sizeAttenuation transparent opacity={.88} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></points>
}

function EvidenceFlow({ from, to, phase }: { from: Vec3; to: Vec3; phase: number }) {
  const curve = useMemo(() => {
    const a = new THREE.Vector3(...from)
    const b = new THREE.Vector3(...to)
    const m = a.clone().lerp(b, .5)
    m.y = Math.max(a.y, b.y) + 1.05
    m.z += .55
    return new THREE.QuadraticBezierCurve3(a, m, b)
  }, [from, to])
  const points = useMemo(() => curve.getPoints(48), [curve])
  return (
    <group>
      <Line points={points} color={C.cyan} lineWidth={1.7} transparent opacity={.08} />
      <Line points={points} color={C.green} lineWidth={.42} transparent opacity={.28} />
      <FlowParticles curve={curve} color={C.green} phase={phase} />
    </group>
  )
}

export function EvidenceCapabilityFlows({ nodes, connections }: { nodes: SpatialNode[]; connections: SpatialConnection[] }) {
  const positions = useMemo(() => nodePositionMap(nodes), [nodes])
  const links = useMemo(() => connections.filter((link) => link.relation === 'contributes_to' && positions.has(link.from) && positions.has(link.to)).slice(0, 18), [connections, positions])
  return <group>{links.map((link, index) => <EvidenceFlow key={link.id} from={positions.get(link.from)!} to={positions.get(link.to)!} phase={(index * .173) % 1} />)}</group>
}

function ShockRing({ color, delay, tilt = 0 }: { color: string; delay: number; tilt?: number }) {
  const ref = useRef<THREE.Mesh>(null)
  const material = useRef<THREE.MeshBasicMaterial>(null)
  useFrame((state) => {
    const t = Math.max(0, state.clock.elapsedTime % 5.2 - delay)
    const p = Math.min(1, t / 1.8)
    if (ref.current) ref.current.scale.setScalar(.15 + p * 5.8)
    if (material.current) material.current.opacity = Math.max(0, .72 * (1 - p))
  })
  return <mesh ref={ref} rotation={[Math.PI / 2 + tilt, 0, tilt * .5]}><torusGeometry args={[.38, .018, 12, 120]} /><meshBasicMaterial ref={material} color={color} transparent opacity={.7} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>
}

function CapabilityAwakening({ event, nodes }: { event: Alpha4Event; nodes: SpatialNode[] }) {
  const capabilities = nodes.filter((node) => node.kind === 'capability').slice(0, 10)
  const index = Math.max(0, capabilities.findIndex((node) => node.id === event.nodeId))
  const position = capabilityPosition(index)
  const core = useRef<THREE.Group>(null)
  const columns = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (core.current) {
      core.current.rotation.x += delta * .55
      core.current.rotation.y += delta * .9
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 4.4) * .08
      core.current.scale.setScalar(pulse)
    }
    if (columns.current) columns.current.rotation.y -= delta * .22
  })
  return (
    <group position={position}>
      <pointLight color={C.green} intensity={36} distance={9} decay={2} />
      <ShockRing color={C.green} delay={0} />
      <ShockRing color={C.cyan} delay={.28} tilt={.32} />
      <ShockRing color={C.ivory} delay={.55} tilt={-.28} />
      <group ref={core}>
        <mesh><icosahedronGeometry args={[.42, 4]} /><meshPhysicalMaterial color={C.green} emissive={C.green} emissiveIntensity={6} metalness={.32} roughness={.06} clearcoat={1} iridescence={1} iridescenceIOR={1.45} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2.3, .3, 0]}><torusKnotGeometry args={[.62, .018, 180, 16, 2, 3]} /><meshBasicMaterial color={C.cyan} transparent opacity={.76} toneMapped={false} /></mesh>
      </group>
      <group ref={columns}>
        {Array.from({ length: 12 }, (_, i) => {
          const a = i / 12 * Math.PI * 2
          return <mesh key={i} position={[Math.cos(a) * 1.12, (i % 3 - 1) * .16, Math.sin(a) * 1.12]} rotation={[0, -a, 0]}><boxGeometry args={[.035, .72 + (i % 4) * .16, .035]} /><meshBasicMaterial color={i % 2 ? C.cyan : C.green} transparent opacity={.55} toneMapped={false} /></mesh>
        })}
      </group>
      <Sparkles count={95} scale={[4.6, 3.8, 4.6]} size={5.5} speed={1.2} opacity={.95} color={C.green} noise={[1, 1, 1]} />
      <Html transform center distanceFactor={7} position={[0, 1.22, .3]} pointerEvents="none"><div className="presentation-event-label"><span>CAPABILITY AWAKENED</span><strong>{event.label}</strong><small>verified by server evidence · visual layer is read-only</small></div></Html>
    </group>
  )
}

function EvidenceVerifiedBurst({ event, nodes }: { event: Alpha4Event; nodes: SpatialNode[] }) {
  const evidence = nodes.filter((node) => node.kind === 'evidence').slice(0, 15)
  const index = Math.max(0, evidence.findIndex((node) => node.id === event.nodeId))
  const position = evidencePosition(index)
  return (
    <group position={position}>
      <pointLight color={C.amber} intensity={24} distance={6} decay={2} />
      <ShockRing color={C.amber} delay={0} />
      <ShockRing color={C.ivory} delay={.38} tilt={.35} />
      <Float speed={1.4} rotationIntensity={.3} floatIntensity={.25}><mesh><octahedronGeometry args={[.27, 2]} /><meshPhysicalMaterial color={C.amber} emissive={C.amber} emissiveIntensity={5} roughness={.08} metalness={.35} clearcoat={1} iridescence={.7} toneMapped={false} /></mesh></Float>
      <Sparkles count={45} scale={[2.7, 2.5, 2.7]} size={4.2} speed={.8} opacity={.85} color={C.amber} noise={[1, 1, 1]} />
    </group>
  )
}

function Fragment({ position, size, color, phase }: { position: Vec3; size: Vec3; color: string; phase: number }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (!ref.current) return
    ref.current.rotation.x = Math.sin(state.clock.elapsedTime * .55 + phase) * .12
    ref.current.rotation.y = Math.sin(state.clock.elapsedTime * .42 + phase * 1.7) * .16
    ref.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * .8 + phase) * .035
  })
  return <mesh ref={ref} position={position}><boxGeometry args={size} /><meshPhysicalMaterial color={color} metalness={.3} roughness={.18} clearcoat={1} transmission={.08} /><Edges color={color} threshold={20} /></mesh>
}

function ExplodedVersion({ side, label, accent, position, revision }: { side: 'left' | 'right'; label: string; accent: string; position: Vec3; revision: boolean }) {
  const dir = side === 'left' ? -1 : 1
  const fragments: Array<{ p: Vec3; s: Vec3 }> = [
    { p: [position[0] + dir * .58, position[1] + .28, position[2]], s: [.76, .28, .08] },
    { p: [position[0] + dir * .27, position[1] -.18, position[2] + .08], s: [.52, .24, .07] },
    { p: [position[0] + dir * .04, position[1] + .42, position[2] -.04], s: [.42, .2, .06] },
    { p: [position[0] + dir * .74, position[1] -.35, position[2] -.08], s: [.33, .2, .06] },
  ]
  return (
    <group>
      {fragments.map((item, i) => <Fragment key={i} position={item.p} size={item.s} color={accent} phase={i + (revision ? 3 : 0)} />)}
      {fragments.map((item, i) => <Line key={`l-${i}`} points={[position, item.p]} color={accent} lineWidth={.55} transparent opacity={.2} />)}
      <group position={[position[0], position[1] + .92, position[2]]}><Html transform center distanceFactor={7} pointerEvents="none"><div className="version-stage-label"><strong>{label}</strong><small>{revision ? 'REVISED STRUCTURE' : 'FIRST STRUCTURE'}</small></div></Html></group>
    </group>
  )
}

export function VersionExplodeCompare({ status }: { status: string }) {
  if (!['revision_required', 'transfer_ready', 'completed'].includes(status)) return null
  const showV2 = status === 'transfer_ready' || status === 'completed'
  return (
    <group position={[5.8, 2.45, -2.05]}>
      <RoundedBox args={[4.1, 2.7, .08]} radius={.12} smoothness={5} position={[0, .2, -.4]}><meshPhysicalMaterial color="#08131b" metalness={.35} roughness={.14} transparent opacity={.42} transmission={.2} clearcoat={1} /><Edges color={showV2 ? C.green : C.amber} threshold={20} /></RoundedBox>
      <ExplodedVersion side="left" label="V1" accent={C.cyan} position={[-.95, .08, 0]} revision={false} />
      <group position={[0, .15, .08]}>
        <mesh><octahedronGeometry args={[.22, 1]} /><meshPhysicalMaterial color={C.amber} emissive={C.amber} emissiveIntensity={2.6} roughness={.12} metalness={.4} toneMapped={false} /></mesh>
        <Html transform center distanceFactor={7} position={[0, .52, 0]} pointerEvents="none"><div className="version-stage-label"><strong>FEEDBACK</strong><small>SUPERVISOR DELTA</small></div></Html>
      </group>
      {showV2 && <ExplodedVersion side="right" label={status === 'completed' ? 'V2 + TRANSFER' : 'V2'} accent={C.green} position={[.95, .08, 0]} revision />}
      {showV2 && <Line points={[[-.28, .15, .05], [.28, .15, .05]]} color={C.amber} lineWidth={1.2} transparent opacity={.55} />}
    </group>
  )
}

export function Alpha4Presentation({ nodes, connections, focus, event }: { nodes: SpatialNode[]; connections: SpatialConnection[]; focus: Focus; event: Alpha4Event | null }) {
  const workSample = useMemo(() => nodes.find((node) => node.id === 'station:work-sample'), [nodes])
  return (
    <group>
      <EvidenceCapabilityFlows nodes={nodes} connections={connections} />
      <VersionExplodeCompare status={String(workSample?.state || 'locked')} />
      {event?.kind === 'capability_awakened' && <CapabilityAwakening key={event.id} event={event} nodes={nodes} />}
      {event?.kind === 'evidence_verified' && <EvidenceVerifiedBurst key={event.id} event={event} nodes={nodes} />}
      {focus === 'hub' && <Sparkles count={38} scale={[17, 5.5, 13]} size={1.5} speed={.08} opacity={.18} color={C.blue} noise={[1, .4, 1]} />}
    </group>
  )
}
