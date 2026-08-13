import {
  CubeCamera,
  Edges,
  Float,
  Html,
  MeshReflectorMaterial,
  MeshTransmissionMaterial,
  RoundedBox,
  Sparkles,
  useCursor,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'
import { ShaderScreen } from './alpha4/ShaderScreen'
import { ArtifactAssembler } from './alpha5/ArtifactAssembler'
import { DirectorSequencer } from './alpha5/DirectorSequencer'
import { EvidenceFlowField } from './alpha5/EvidenceFlowField'
import { InstancedDataField } from './alpha5/InstancedDataField'
import { RealtimePostPipeline } from './alpha5/RealtimePostPipeline'
import { ThemeLightingDirector, resolveAlpha5Theme, useAlpha5Event, type Alpha5Theme } from './alpha5/ThemeSystem'
import { ArtifactChoreography } from './alpha6/ArtifactChoreography'
import { ControlRoomTransformation } from './alpha6/ControlRoomTransformation'
import { ShowcaseDirectorSequencer } from './alpha6/ShowcaseDirectorSequencer'
import { ShowcaseLightingTimeline } from './alpha6/ShowcaseLightingTimeline'
import { ShowcaseDemoBadge, useShowcaseRuntime } from './alpha6/ShowcaseRuntime'
import { TopologyReflowNetwork } from './alpha6/TopologyReflowNetwork'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html transform center distanceFactor={7.8} pointerEvents="none"><div className={`scene-label ${className}`}>{children}</div></Html>
}

function DataSpire({ position, height, theme, phase }: { position: Vec3; height: number; theme: Alpha5Theme; phase: number }) {
  const ref = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!ref.current) return
    ref.current.rotation.y += delta * (.08 + phase * .01)
    ref.current.position.y = Math.sin(state.clock.elapsedTime * .45 + phase) * .08
  })
  return (
    <group ref={ref} position={position}>
      <mesh><cylinderGeometry args={[.12, .18, height, 8]} /><meshPhysicalMaterial color="#14232c" metalness={.9} roughness={.14} clearcoat={.7} /></mesh>
      <mesh scale={[1.04, .92, 1.04]}><cylinderGeometry args={[.125, .125, height, 8, 1, true]} /><meshBasicMaterial color={phase % 2 ? theme.secondary : theme.accent} transparent opacity={.22} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>
      <mesh position={[0, height * .5 + .08, 0]}><sphereGeometry args={[.08, 16, 16]} /><meshBasicMaterial color={phase % 2 ? theme.secondary : theme.accent} toneMapped={false} /></mesh>
    </group>
  )
}

function ShowcaseArchitecture({ theme }: { theme: Alpha5Theme }) {
  const ring = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!ring.current) return
    ring.current.rotation.y += delta * (.05 + theme.dataEnergy * .035)
    ring.current.rotation.z = Math.sin(state.clock.elapsedTime * .18) * .05
  })
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[32, 24]} />
        <MeshReflectorMaterial color="#040b10" roughness={.54} metalness={.4} blur={[520, 180]} mixBlur={1} mixStrength={24} mirror={.36} resolution={512} depthScale={.4} minDepthThreshold={.3} maxDepthThreshold={1.8} />
      </mesh>
      <RoundedBox args={[21, 7.9, .54]} radius={.22} smoothness={6} position={[0, 3.7, -7.8]} receiveShadow><meshPhysicalMaterial color="#030a0f" metalness={.72} roughness={.27} clearcoat={.5} /></RoundedBox>
      <RoundedBox args={[17.6, 6.3, .08]} radius={.13} smoothness={6} position={[0, 3.55, -7.47]}><MeshTransmissionMaterial transmission={.55} thickness={.36} roughness={.16} chromaticAberration={.028} anisotropicBlur={.06} samples={2} resolution={128} color="#16303a" /></RoundedBox>
      {Array.from({ length: 15 }, (_, index) => {
        const x = -9.45 + index * 1.35
        const color = index % 4 === 0 ? theme.secondary : theme.accent
        return <group key={index} position={[x, 3.55, -7.34]}><mesh><boxGeometry args={[.065, 5.7, .075]} /><meshPhysicalMaterial color="#263b45" metalness={.88} roughness={.17} /></mesh><mesh position={[0, 0, .055]}><boxGeometry args={[.014, 4.7, .01]} /><meshBasicMaterial color={color} transparent opacity={.72} toneMapped={false} /></mesh></group>
      })}
      <group ref={ring} position={[0, 5.45, .55]} rotation={[Math.PI / 2, 0, 0]}>
        <mesh><torusGeometry args={[5.15, .075, 16, 220]} /><meshPhysicalMaterial color="#1c3039" metalness={.94} roughness={.12} clearcoat={.82} /></mesh>
        <mesh><torusGeometry args={[5.16, .018, 10, 220]} /><meshBasicMaterial color={theme.accent} transparent opacity={.58} toneMapped={false} /></mesh>
      </group>
      {Array.from({ length: 12 }, (_, index) => {
        const angle = index / 12 * Math.PI * 2
        return <DataSpire key={index} position={[Math.cos(angle) * 7.7, 1.0, Math.sin(angle) * 5.4 - .6]} height={1.6 + (index % 4) * .35} theme={theme} phase={index} />
      })}
    </group>
  )
}

function ShowcaseReactor({ theme }: { theme: Alpha5Theme }) {
  const cage = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!cage.current) return
    cage.current.rotation.y += delta * (.28 + theme.dataEnergy * .18)
    cage.current.rotation.x = Math.sin(state.clock.elapsedTime * .31) * .12
  })
  const dynamic = ['verification', 'awakening', 'completed'].includes(theme.name)
  return (
    <group position={[0, 2.5, .65]}>
      <CubeCamera resolution={256} frames={dynamic ? Infinity : 8} near={.1} far={34}>
        {(texture) => <mesh><icosahedronGeometry args={[.5, 5]} /><meshPhysicalMaterial envMap={texture} envMapIntensity={3.5} color="#c5e7e2" metalness={1} roughness={.022} clearcoat={1} clearcoatRoughness={.015} iridescence={.62} /></mesh>}
      </CubeCamera>
      <group ref={cage}>
        <mesh rotation={[Math.PI / 2.35, .2, 0]}><torusKnotGeometry args={[1.0, .024, 280, 24, 3, 5]} /><meshPhysicalMaterial color="#657983" metalness={.96} roughness={.1} clearcoat={.85} /></mesh>
        <mesh rotation={[-Math.PI / 2.7, -.2, 0]}><torusGeometry args={[1.36, .016, 12, 180]} /><meshBasicMaterial color={theme.secondary} transparent opacity={.55} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2.9, .3, .2]}><torusGeometry args={[1.65, .011, 12, 180]} /><meshBasicMaterial color={theme.accent} transparent opacity={.45} toneMapped={false} /></mesh>
      </group>
      <Sparkles count={46} scale={[3.4, 3.4, 3.4]} size={2.7} speed={.22 + theme.dataEnergy * .22} opacity={.48} color={theme.accent} />
      <pointLight color={theme.accent} intensity={8 + theme.dataEnergy * 7} distance={8} decay={2} />
    </group>
  )
}

function Workstation({ node, position, theme, side, onActivate }: { node?: SpatialNode; position: Vec3; theme: Alpha5Theme; side: 'left' | 'right'; onActivate: () => void }) {
  const root = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const locked = node?.state === 'locked'
  const accent = locked ? '#52616a' : side === 'left' ? theme.accent : theme.secondary
  useFrame((_, delta) => {
    if (!root.current) return
    const scale = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.055 : 1, 7, delta)
    root.current.scale.setScalar(scale)
    root.current.position.y = THREE.MathUtils.damp(root.current.position.y, hovered ? .06 : 0, 7, delta)
  })
  return (
    <group ref={root} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onActivate() }}>
      <RoundedBox args={[3.85, .34, 2.7]} radius={.2} smoothness={6} position={[0, .17, 0]} castShadow><meshPhysicalMaterial color="#071119" metalness={.86} roughness={.17} clearcoat={.72} /><Edges color={hovered ? accent : '#2a424e'} threshold={22} /></RoundedBox>
      <RoundedBox args={[3.05, .16, 1.55]} radius={.09} smoothness={5} position={[0, .93, 0]}><meshPhysicalMaterial color="#26343b" metalness={.52} roughness={.24} clearcoat={.68} /></RoundedBox>
      <RoundedBox args={[2.24, 1.46, .16]} radius={.09} smoothness={6} position={[0, 1.78, -.42]}><meshPhysicalMaterial color="#03080c" metalness={.9} roughness={.1} clearcoat={.95} /><Edges color={hovered ? accent : '#38515c'} threshold={24} /></RoundedBox>
      <mesh position={[0, 1.78, -.325]}><planeGeometry args={[2.0, 1.2]} /><ShaderScreen color={accent} seed={side === 'left' ? 21 : 34} glitch={locked ? .08 : hovered ? .9 : .48} scanSpeed={hovered ? 1.55 : 1} intensity={locked ? .3 : hovered ? 1.5 : 1.12} /></mesh>
      <Float speed={1.1} rotationIntensity={.02} floatIntensity={.07}><group position={[0, 2.82, -.18]}><RoundedBox args={[2.18, .48, .055]} radius={.08} smoothness={5}><MeshTransmissionMaterial transmission={1} thickness={.3} roughness={.06} chromaticAberration={.032} anisotropicBlur={.08} samples={3} resolution={128} color={accent} /></RoundedBox><Edges color={accent} threshold={20} /><group position={[0, 0, .07]}><Label className={locked ? 'muted workstation-label' : 'workstation-label'}>{node?.label || 'Workstation'}</Label></group></group></Float>
      <spotLight position={[0, 5.1, 1.3]} color={accent} intensity={hovered ? 34 : locked ? 5 : 20} distance={10} angle={.46} penumbra={.92} />
    </group>
  )
}

function EvidenceRack({ nodes, theme, onInspect }: { nodes: SpatialNode[]; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-6.25, 0, -1.35]}>
      <RoundedBox args={[3.1, 4.9, .62]} radius={.18} smoothness={6} position={[0, 2.45, 0]}><meshPhysicalMaterial color="#061018" metalness={.72} roughness={.16} clearcoat={.78} /><Edges color="#2a4652" threshold={22} /></RoundedBox>
      <RoundedBox args={[2.75, 4.2, .055]} radius={.08} smoothness={5} position={[0, 2.45, .35]}><MeshTransmissionMaterial transmission={1} thickness={.38} roughness={.08} chromaticAberration={.04} anisotropicBlur={.1} samples={3} resolution={160} color={theme.accent} /></RoundedBox>
      {nodes.slice(0, 16).map((node, index) => {
        const x = -1.0 + (index % 4) * .66
        const y = .85 + Math.floor(index / 4) * .82
        const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
        const color = verified ? theme.accent : theme.secondary
        return <group key={node.id} position={[x, y, .48]} onClick={(event) => { event.stopPropagation(); onInspect(node) }}><RoundedBox args={[.5, .3, .16]} radius={.05} smoothness={4}><meshPhysicalMaterial color="#10212a" metalness={.42} roughness={.14} clearcoat={1} /><Edges color={color} threshold={20} /></RoundedBox><mesh position={[0, 0, .09]}><planeGeometry args={[.36, .18]} /><ShaderScreen color={color} seed={index + 41} glitch={verified ? .12 : .42} scanSpeed={1.1} intensity={verified ? 1.5 : .82} /></mesh></group>
      })}
      <group position={[0, 5.12, .3]}><Label className="zone-label">EVIDENCE VAULT / SERVER RECORDS</Label></group>
    </group>
  )
}

function CapabilityNodes({ nodes, theme, onInspect }: { nodes: SpatialNode[]; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  return (
    <group>
      {nodes.slice(0, 10).map((node, index) => {
        const angle = index / Math.max(1, Math.min(nodes.length, 10)) * Math.PI * 2
        const radius = index % 2 ? 2.05 : 3.0
        const position: Vec3 = [Math.cos(angle) * radius, 3.5 + Math.sin(index * 1.5) * .35, -5.95 + Math.sin(angle) * .65]
        const level = String(node.data?.verificationLevel || node.state || 'unobserved')
        const color = level === 'verified_evidence' ? theme.accent : level === 'evidence' ? theme.secondary : level === 'signal' ? '#a7bcc7' : '#40515b'
        const size = level === 'verified_evidence' ? .26 : level === 'evidence' ? .21 : .16
        return <Float key={node.id} speed={.75} rotationIntensity={.03} floatIntensity={.1}><group position={position} onClick={(event) => { event.stopPropagation(); onInspect(node) }}><mesh><sphereGeometry args={[size, 48, 48]} /><meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={level === 'verified_evidence' ? 2.6 : level === 'evidence' ? .8 : .1} metalness={.76} roughness={.07} clearcoat={1} iridescence={level === 'verified_evidence' ? 1 : .15} toneMapped={level !== 'verified_evidence'} /></mesh><mesh rotation={[Math.PI / 2.6, 0, index * .3]}><torusGeometry args={[size * 1.9, .009, 8, 80]} /><meshBasicMaterial color={color} transparent opacity={.42} toneMapped={false} /></mesh></group></Float>
      })}
      <group position={[0, 5.78, -6.0]}><Label className="zone-label">TOPOLOGY REFLOW / SERVER GRAPH</Label></group>
    </group>
  )
}

function Scene(props: Props) {
  const { nodes, connections, focus, onFocus, onInspect } = props
  const event = useAlpha5Event(nodes)
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workStatus = String(workSample?.state || 'locked')
  const runtime = useShowcaseRuntime(event, workStatus)
  const theme = resolveAlpha5Theme(nodes, focus, event)
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const transitionKey = `${focus}:${theme.name}:${runtime.serial}:${event?.id || workStatus}`
  const artifactRuntime = runtime.active && Boolean(runtime.clip && ['artifact_destruction', 'artifact_assembly', 'server_revision', 'server_transfer', 'server_completed', 'grand_finale'].includes(runtime.clip))

  return (
    <>
      <ThemeLightingDirector theme={theme} />
      <ShowcaseLightingTimeline theme={theme} runtime={runtime} />
      <ShowcaseArchitecture theme={theme} />
      <ControlRoomTransformation runtime={runtime} theme={theme} workStatus={workStatus} />
      <ShowcaseReactor theme={theme} />

      <InstancedDataField nodes={nodes} theme={theme} />
      <TopologyReflowNetwork capabilities={capabilities} connections={connections} theme={theme} runtime={runtime} />
      <EvidenceFlowField nodes={nodes} connections={connections} theme={theme} />

      <Workstation node={foundation} position={[-3.1, 0, -.72]} theme={theme} side="left" onActivate={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[3.1, 0, -.72]} theme={theme} side="right" onActivate={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />
      <EvidenceRack nodes={evidence} theme={theme} onInspect={onInspect} />
      <CapabilityNodes nodes={capabilities} theme={theme} onInspect={onInspect} />

      {artifactRuntime ? <ArtifactChoreography runtime={runtime} theme={theme} /> : <ArtifactAssembler status={workStatus} theme={theme} />}

      {runtime.active ? <ShowcaseDirectorSequencer runtime={runtime} /> : <DirectorSequencer focus={focus} event={event} nodes={nodes} />}
      <ShowcaseDemoBadge runtime={runtime} nodes={nodes} />
      <RealtimePostPipeline theme={theme} transitionKey={transitionKey} />
    </>
  )
}

export function ShowcaseCGWorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 7.2, 18.4], fov: 40, near: .1, far: 110 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.16
        gl.outputColorSpace = THREE.SRGBColorSpace
        gl.shadowMap.type = THREE.PCFSoftShadowMap
        scene.background = new THREE.Color('#010408')
      }}
      frameloop="always"
    >
      <Scene {...props} />
    </Canvas>
  )
}
