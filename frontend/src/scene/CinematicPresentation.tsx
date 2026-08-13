import { Edges, Float, Html, Line, RoundedBox, Sparkles } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialNode } from '../api/types'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]
type PresentationKind = 'evidence_verified' | 'capability_verified' | 'work_sample_stage'

type PresentationEvent = {
  id: string
  kind: PresentationKind
  label: string
  state: string
}

type Props = {
  nodes: SpatialNode[]
  focus: Focus
}

const C = {
  cyan: '#75efe4',
  cyanSoft: '#58b9bd',
  amber: '#f2c27f',
  green: '#82f0be',
  rose: '#e28b87',
  ivory: '#f3ede3',
  graphite: '#0a1117',
}

function easeOutExpo(value: number) {
  if (value >= 1) return 1
  return 1 - Math.pow(2, -10 * Math.max(0, value))
}

function VolumetricCone({ position, radius, height, color, opacity = .045 }: { position: Vec3; radius: number; height: number; color: string; opacity?: number }) {
  const material = useRef<THREE.MeshBasicMaterial>(null)
  useFrame((state) => {
    if (material.current) material.current.opacity = opacity * (.82 + Math.sin(state.clock.elapsedTime * .8 + position[0]) * .18)
  })
  return (
    <group position={position}>
      <mesh>
        <coneGeometry args={[radius, height, 48, 1, true]} />
        <meshBasicMaterial
          ref={material}
          color={color}
          transparent
          opacity={opacity}
          side={THREE.DoubleSide}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          toneMapped={false}
        />
      </mesh>
      <pointLight position={[0, -height * .36, 0]} color={color} intensity={5.5} distance={4.5} decay={2.2} />
    </group>
  )
}

function VolumetricRig({ focus }: { focus: Focus }) {
  return (
    <group>
      <VolumetricCone position={[-2.85, 4.2, -.75]} radius={focus === 'foundation' ? 2.1 : 1.55} height={7.3} color={C.cyan} opacity={focus === 'foundation' ? .075 : .038} />
      <VolumetricCone position={[2.85, 4.15, -.75]} radius={focus === 'work-sample' ? 2.1 : 1.55} height={7.2} color={C.amber} opacity={focus === 'work-sample' ? .075 : .036} />
      <VolumetricCone position={[-5.95, 4.8, -2.05]} radius={1.25} height={5.8} color={C.green} opacity={.025} />
      <VolumetricCone position={[5.75, 4.6, -2.15]} radius={1.4} height={5.6} color={C.amber} opacity={.027} />
    </group>
  )
}

function ScanPlane({ origin, color, phase }: { origin: Vec3; color: string; phase: number }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (!ref.current) return
    const y = Math.sin(state.clock.elapsedTime * 1.7 + phase) * .41
    ref.current.position.y = origin[1] + y
  })
  return (
    <mesh ref={ref} position={origin}>
      <planeGeometry args={[1.62, .018]} />
      <meshBasicMaterial color={color} transparent opacity={.8} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
    </mesh>
  )
}

function ScreenScanners() {
  return (
    <group>
      <ScanPlane origin={[-2.85, 1.67, -1.01]} color={C.cyan} phase={0} />
      <ScanPlane origin={[2.85, 1.67, -1.01]} color={C.amber} phase={1.4} />
    </group>
  )
}

function StageCard({ label, sub, accent, position, statusKey, delay = 0 }: { label: string; sub: string; accent: string; position: Vec3; statusKey: string; delay?: number }) {
  const root = useRef<THREE.Group>(null)
  const elapsed = useRef(0)
  useEffect(() => {
    elapsed.current = 0
    if (root.current) {
      root.current.scale.setScalar(.001)
      root.current.position.set(position[0], position[1] - .34, position[2])
    }
  }, [statusKey, position])
  useFrame((state, delta) => {
    elapsed.current += delta
    if (!root.current) return
    const p = easeOutExpo(Math.min(1, Math.max(0, elapsed.current - delay) / .72))
    root.current.scale.setScalar(Math.max(.001, p))
    root.current.position.y = THREE.MathUtils.lerp(position[1] - .34, position[1] + Math.sin(state.clock.elapsedTime * .75 + delay * 5) * .025, p)
    root.current.rotation.z = Math.sin(state.clock.elapsedTime * .45 + delay) * .018 * p
  })
  return (
    <group ref={root} position={position}>
      <RoundedBox args={[1.12, .7, .055]} radius={.08} smoothness={5}>
        <meshPhysicalMaterial color="#101a21" metalness={.32} roughness={.16} clearcoat={1} clearcoatRoughness={.08} transmission={.12} />
        <Edges color={accent} threshold={20} />
      </RoundedBox>
      <mesh position={[0, -.245, .047]}><planeGeometry args={[.82, .02]} /><meshBasicMaterial color={accent} toneMapped={false} /></mesh>
      <Html transform center distanceFactor={7} position={[0, 0, .07]} pointerEvents="none">
        <div className="version-stage-label"><strong>{label}</strong><small>{sub}</small></div>
      </Html>
    </group>
  )
}

function RevisionTheatre({ status }: { status: string }) {
  const ring = useRef<THREE.Group>(null)
  useFrame((_, delta) => { if (ring.current) ring.current.rotation.y += delta * (status === 'completed' ? .42 : .16) })
  if (!['revision_required', 'transfer_ready', 'completed'].includes(status)) return null
  const showV2 = status === 'transfer_ready' || status === 'completed'
  const showTransfer = status === 'completed'
  const connectionPoints = showTransfer
    ? [[4.72, 3.05, -2.15], [5.2, 3.42, -2.15], [5.75, 3.05, -2.15], [6.3, 3.42, -2.15], [6.82, 3.05, -2.15]] as Vec3[]
    : showV2
      ? [[4.9, 3.18, -2.15], [5.75, 3.48, -2.15], [6.6, 3.18, -2.15]] as Vec3[]
      : [[5.08, 3.2, -2.15], [6.42, 3.2, -2.15]] as Vec3[]
  return (
    <group>
      {connectionPoints.length > 1 && <Line points={connectionPoints} color={status === 'completed' ? C.green : C.amber} lineWidth={1.1} transparent opacity={.45} />}
      <StageCard statusKey={status} label="V1" sub="FIRST DELIVERY" accent={C.cyanSoft} position={showTransfer ? [4.72, 3.05, -2.15] : showV2 ? [4.9, 3.18, -2.15] : [5.08, 3.2, -2.15]} />
      <StageCard statusKey={status} label="FEEDBACK" sub="SUPERVISOR" accent={C.amber} position={showTransfer ? [5.2, 3.42, -2.15] : showV2 ? [5.75, 3.48, -2.15] : [6.42, 3.2, -2.15]} delay={.14} />
      {showV2 && <StageCard statusKey={status} label="V2" sub="REVISION" accent={C.green} position={showTransfer ? [5.75, 3.05, -2.15] : [6.6, 3.18, -2.15]} delay={.3} />}
      {showTransfer && <StageCard statusKey={status} label="TRANSFER" sub="NEW MATERIAL" accent={C.ivory} position={[6.3, 3.42, -2.15]} delay={.46} />}
      {showTransfer && <StageCard statusKey={status} label="DONE" sub="SERVER COMPLETED" accent={C.green} position={[6.82, 3.05, -2.15]} delay={.62} />}
      <group ref={ring} position={[5.75, 3.18, -2.15]} rotation={[Math.PI / 2, 0, 0]}>
        <mesh><torusGeometry args={[1.78, .015, 10, 120]} /><meshBasicMaterial color={status === 'completed' ? C.green : C.amber} transparent opacity={.28} toneMapped={false} /></mesh>
        <mesh scale={[.76, .76, .76]}><torusGeometry args={[1.78, .008, 10, 120]} /><meshBasicMaterial color={C.cyan} transparent opacity={.18} toneMapped={false} /></mesh>
      </group>
    </group>
  )
}

function usePresentationEvent(nodes: SpatialNode[]) {
  const previous = useRef<Map<string, string> | null>(null)
  const [event, setEvent] = useState<PresentationEvent | null>(null)
  useEffect(() => {
    const current = new Map(nodes.map((node) => [node.id, node.state]))
    if (!previous.current) {
      previous.current = current
      return
    }
    let next: PresentationEvent | null = null
    for (const node of nodes) {
      const before = previous.current.get(node.id)
      if (!before || before === node.state) continue
      if (node.kind === 'capability' && node.state === 'verified_evidence') {
        next = { id: `${node.id}:${Date.now()}`, kind: 'capability_verified', label: node.label, state: node.state }
        break
      }
      if (node.kind === 'evidence' && node.state === 'verified') {
        next = { id: `${node.id}:${Date.now()}`, kind: 'evidence_verified', label: node.label, state: node.state }
      }
      if (node.id === 'station:work-sample' && ['revision_required', 'transfer_ready', 'completed'].includes(node.state)) {
        next = { id: `${node.id}:${Date.now()}`, kind: 'work_sample_stage', label: node.label, state: node.state }
      }
    }
    previous.current = current
    if (!next) return
    setEvent(next)
    const timer = window.setTimeout(() => setEvent((value) => value?.id === next?.id ? null : value), 3300)
    return () => window.clearTimeout(timer)
  }, [nodes])
  return event
}

function EventBurst({ event }: { event: PresentationEvent }) {
  const root = useRef<THREE.Group>(null)
  const ringA = useRef<THREE.Mesh>(null)
  const ringB = useRef<THREE.Mesh>(null)
  const light = useRef<THREE.PointLight>(null)
  const started = useRef(0)
  const world: Vec3 = event.kind === 'evidence_verified' ? [-5.95, 2.3, -1.3] : event.kind === 'capability_verified' ? [0, 3.3, -6.05] : [5.75, 3.25, -1.6]
  const color = event.kind === 'capability_verified' ? C.green : event.kind === 'evidence_verified' ? C.amber : C.cyan
  useFrame((state) => {
    if (!started.current) started.current = state.clock.elapsedTime
    const t = state.clock.elapsedTime - started.current
    const p = Math.min(1, t / 2.4)
    if (ringA.current) ringA.current.scale.setScalar(.35 + p * 3.8)
    if (ringB.current) ringB.current.scale.setScalar(.2 + Math.min(1, p * 1.3) * 2.7)
    if (root.current) root.current.rotation.y = t * .22
    if (light.current) light.current.intensity = Math.max(0, 34 * (1 - p))
  })
  const statusText = event.kind === 'capability_verified' ? 'VERIFIED EVIDENCE' : event.kind === 'evidence_verified' ? 'EVIDENCE VERIFIED' : event.state.replaceAll('_', ' ').toUpperCase()
  return (
    <group ref={root} position={world}>
      <pointLight ref={light} color={color} intensity={34} distance={8} decay={2} />
      <mesh ref={ringA} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[.42, .018, 12, 96]} /><meshBasicMaterial color={color} transparent opacity={.72} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>
      <mesh ref={ringB} rotation={[Math.PI / 2.35, .3, 0]}><torusGeometry args={[.38, .009, 10, 96]} /><meshBasicMaterial color={C.ivory} transparent opacity={.42} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>
      <Float speed={1.2} rotationIntensity={.12} floatIntensity={.18}>
        <mesh><icosahedronGeometry args={[.22, 2]} /><meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={5} metalness={.25} roughness={.08} clearcoat={1} iridescence={1} toneMapped={false} /></mesh>
      </Float>
      <Sparkles count={34} scale={[2.4, 2.1, 2.4]} size={4.2} speed={.65} opacity={.9} color={color} noise={[1, 1, 1]} />
      <Html transform center distanceFactor={7} position={[0, .72, .35]} pointerEvents="none">
        <div className="presentation-event-label"><span>{statusText}</span><strong>{event.label}</strong><small>triggered by server SceneState</small></div>
      </Html>
    </group>
  )
}

export function CinematicPresentation({ nodes, focus }: Props) {
  const event = usePresentationEvent(nodes)
  const workSample = useMemo(() => nodes.find((node) => node.id === 'station:work-sample'), [nodes])
  return (
    <group>
      <VolumetricRig focus={focus} />
      <ScreenScanners />
      <RevisionTheatre status={String(workSample?.state || 'locked')} />
      {event && <EventBurst key={event.id} event={event} />}
    </group>
  )
}
