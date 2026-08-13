import {
  ContactShadows,
  CubeCamera,
  Edges,
  Float,
  Html,
  Line,
  MeshReflectorMaterial,
  MeshTransmissionMaterial,
  RoundedBox,
  Sparkles,
  useCursor,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'
import { ShaderScreen } from './alpha4/ShaderScreen'
import { ArtifactAssembler } from './alpha5/ArtifactAssembler'
import { DirectorSequencer } from './alpha5/DirectorSequencer'
import { EvidenceFlowField } from './alpha5/EvidenceFlowField'
import { GPGPUCapabilityNetwork } from './alpha5/GPGPUCapabilityNetwork'
import { InstancedDataField } from './alpha5/InstancedDataField'
import { RealtimePostPipeline } from './alpha5/RealtimePostPipeline'
import {
  ThemeLightingDirector,
  resolveAlpha5Theme,
  useAlpha5Event,
  type Alpha5Event,
  type Alpha5Theme,
} from './alpha5/ThemeSystem'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

const BASE = {
  steel: '#20313b',
  dark: '#03090e',
  panel: '#08131b',
  ivory: '#edf5f5',
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html transform center distanceFactor={7.6} pointerEvents="none"><div className={`scene-label ${className}`}>{children}</div></Html>
}

function makeSurface(kind: 'floor' | 'metal' | 'wood') {
  const canvas = document.createElement('canvas')
  canvas.width = kind === 'wood' ? 1024 : 768
  canvas.height = kind === 'wood' ? 256 : 768
  const context = canvas.getContext('2d')
  if (!context) return new THREE.Texture()
  context.fillStyle = kind === 'floor' ? '#050b10' : kind === 'metal' ? '#777f85' : '#584431'
  context.fillRect(0, 0, canvas.width, canvas.height)
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
  for (let i = 0; i < pixels.data.length; i += 4) {
    const seed = Math.sin(i * .00173 + (kind === 'wood' ? 4 : 1)) * .5 + .5
    const noise = seed * (kind === 'metal' ? 34 : kind === 'floor' ? 9 : 20)
    pixels.data[i] += noise
    pixels.data[i + 1] += noise * .92
    pixels.data[i + 2] += noise * .82
  }
  context.putImageData(pixels, 0, 0)
  if (kind === 'floor') {
    for (let p = 0; p < canvas.width; p += 64) {
      context.strokeStyle = p % 256 === 0 ? 'rgba(90,240,225,.085)' : 'rgba(180,205,220,.025)'
      context.lineWidth = p % 256 === 0 ? 1.2 : .55
      context.beginPath(); context.moveTo(p, 0); context.lineTo(p, canvas.height); context.stroke()
      context.beginPath(); context.moveTo(0, p); context.lineTo(canvas.width, p); context.stroke()
    }
  }
  if (kind === 'metal') {
    for (let y = 0; y < canvas.height; y += 2) {
      context.strokeStyle = `rgba(255,255,255,${.015 + (y % 17) * .0012})`
      context.beginPath(); context.moveTo(0, y); context.lineTo(canvas.width, y); context.stroke()
    }
  }
  if (kind === 'wood') {
    for (let y = 2; y < canvas.height; y += 3) {
      context.strokeStyle = `rgba(30,14,7,${.025 + (y % 19) / 700})`
      context.beginPath()
      for (let x = -20; x < canvas.width + 20; x += 9) {
        const py = y + Math.sin(x * .018 + y * .045) * 1.8
        if (x === -20) context.moveTo(x, py)
        else context.lineTo(x, py)
      }
      context.stroke()
    }
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(kind === 'floor' ? 5.8 : kind === 'metal' ? 2.5 : 2.4, kind === 'floor' ? 4.6 : kind === 'metal' ? 6 : 1)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 12
  return texture
}

function useSurfaces() {
  const surfaces = useMemo(() => ({ floor: makeSurface('floor'), metal: makeSurface('metal'), wood: makeSurface('wood') }), [])
  useEffect(() => () => Object.values(surfaces).forEach((texture) => texture.dispose()), [surfaces])
  return surfaces
}

function Glow({ position, scale, color, power = 1.5 }: { position: Vec3; scale: Vec3; color: string; power?: number }) {
  return <mesh position={position} scale={scale}><boxGeometry /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={power} toneMapped={false} /></mesh>
}

function Cable({ a, b }: { a: Vec3; b: Vec3 }) {
  const data = useMemo(() => {
    const start = new THREE.Vector3(...a)
    const end = new THREE.Vector3(...b)
    const direction = end.clone().sub(start)
    return {
      midpoint: start.clone().add(end).multiplyScalar(.5),
      length: direction.length(),
      quaternion: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize()),
    }
  }, [a, b])
  return <mesh position={data.midpoint} quaternion={data.quaternion}><cylinderGeometry args={[.014, .014, data.length, 10]} /><meshStandardMaterial color="#4d626c" metalness={.92} roughness={.18} /></mesh>
}

function RefractiveGate({ position, rotation, theme }: { position: Vec3; rotation: Vec3; theme: Alpha5Theme }) {
  return (
    <group position={position} rotation={rotation}>
      <RoundedBox args={[2.72, 3.72, .14]} radius={.08} smoothness={5}><meshPhysicalMaterial color="#101d25" metalness={.78} roughness={.2} /><Edges color="#314954" threshold={25} /></RoundedBox>
      <RoundedBox args={[2.52, 3.5, .045]} radius={.065} smoothness={5} position={[0, 0, .11]}>
        <MeshTransmissionMaterial transmission={1} thickness={.64} roughness={.075} chromaticAberration={.055} anisotropicBlur={.14} distortion={.085} distortionScale={.4} temporalDistortion={.12} samples={4} resolution={256} backside color={theme.accent} />
      </RoundedBox>
      <Glow position={[-1.04, 0, .16]} scale={[.012, 3.0, .012]} color={theme.accent} power={1.15} />
      <Glow position={[1.04, 0, .16]} scale={[.012, 3.0, .012]} color={theme.secondary} power={.95} />
    </group>
  )
}

function Architecture({ theme, floor, metal }: { theme: Alpha5Theme; floor: THREE.Texture; metal: THREE.Texture }) {
  const ringA = useRef<THREE.Group>(null)
  const ringB = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (ringA.current) ringA.current.rotation.z += delta * (.025 + theme.dataEnergy * .012)
    if (ringB.current) ringB.current.rotation.z = -state.clock.elapsedTime * (.035 + theme.dataEnergy * .008)
  })
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[30, 23]} />
        <MeshReflectorMaterial map={floor} color="#050b10" roughness={.62} metalness={.34} blur={[440, 170]} mixBlur={1} mixStrength={20} mirror={.27} resolution={512} depthScale={.32} minDepthThreshold={.34} maxDepthThreshold={1.7} />
      </mesh>

      <RoundedBox args={[20.4, 7.7, .52]} radius={.22} smoothness={6} position={[0, 3.65, -7.55]} receiveShadow><meshPhysicalMaterial color="#040b10" metalness={.67} roughness={.3} roughnessMap={metal} clearcoat={.48} /></RoundedBox>
      <RoundedBox args={[16.8, 6.05, .075]} radius={.14} smoothness={6} position={[0, 3.5, -7.23]}><meshPhysicalMaterial color="#07161d" metalness={.48} roughness={.14} clearcoat={.95} /></RoundedBox>
      {Array.from({ length: 13 }, (_, i) => {
        const x = -9.0 + i * 1.5
        return <group key={i} position={[x, 3.5, -7.16]}><RoundedBox args={[.105, 5.45, .09]} radius={.035} smoothness={3}><meshStandardMaterial color="#263943" metalness={.85} roughness={.18} roughnessMap={metal} /></RoundedBox><Glow position={[0, 0, .07]} scale={[.015, 4.45, .01]} color={i % 4 === 0 ? theme.secondary : theme.accent} power={i % 4 === 0 ? .8 : 1.1} /></group>
      })}

      {[-9.3, 9.3].map((x) => <RoundedBox key={x} args={[.32, 6.9, 16.4]} radius={.12} smoothness={5} position={[x, 3.35, .1]}><meshPhysicalMaterial color="#071017" metalness={.74} roughness={.31} roughnessMap={metal} /></RoundedBox>)}

      <group position={[0, 5.25, .55]} rotation={[Math.PI / 2, 0, 0]}>
        <group ref={ringA}><mesh><torusGeometry args={[4.55, .12, 20, 200]} /><meshPhysicalMaterial color="#14252e" metalness={.92} roughness={.14} clearcoat={.75} /></mesh><mesh><torusGeometry args={[4.55, .022, 10, 200]} /><meshBasicMaterial color={theme.accent} transparent opacity={.72} toneMapped={false} /></mesh></group>
        <group ref={ringB}><mesh><torusGeometry args={[3.34, .067, 18, 180]} /><meshPhysicalMaterial color="#594635" metalness={.62} roughness={.2} clearcoat={.7} /></mesh><mesh><torusGeometry args={[3.34, .013, 10, 180]} /><meshBasicMaterial color={theme.secondary} transparent opacity={.62} toneMapped={false} /></mesh></group>
      </group>
      <Cable a={[-4.8, 6.65, -1.5]} b={[-3.1, 5.25, .2]} />
      <Cable a={[4.8, 6.65, -1.5]} b={[3.1, 5.25, .2]} />
      <Cable a={[-3.7, 6.65, 2.6]} b={[-2.3, 5.25, 1.5]} />
      <Cable a={[3.7, 6.65, 2.6]} b={[2.3, 5.25, 1.5]} />

      <RefractiveGate position={[-7.35, 2.38, 2.8]} rotation={[0, .16, 0]} theme={theme} />
      <RefractiveGate position={[7.35, 2.38, 2.8]} rotation={[0, -.16, 0]} theme={theme} />
      <RefractiveGate position={[-5.95, 2.3, 5.7]} rotation={[0, .37, 0]} theme={theme} />
      <RefractiveGate position={[5.95, 2.3, 5.7]} rotation={[0, -.37, 0]} theme={theme} />

      {Array.from({ length: 8 }, (_, i) => <Glow key={i} position={[-8.1 + i * 2.32, .045, 4.7]} scale={[1.3, .014, .05]} color={i % 2 ? theme.accent : theme.secondary} power={1.08 + theme.dataEnergy * .08} />)}
      <ContactShadows position={[0, .014, .35]} opacity={.58} scale={23} blur={3.2} far={8} />
    </group>
  )
}

function Reactor({ theme }: { theme: Alpha5Theme }) {
  const group = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!group.current) return
    group.current.rotation.y += delta * (.26 + theme.dataEnergy * .12)
    group.current.rotation.z = Math.sin(state.clock.elapsedTime * .42) * .11
  })
  const dynamic = theme.name === 'awakening' || theme.name === 'verification' || theme.name === 'completed'
  return (
    <group position={[0, 2.48, .7]}>
      <CubeCamera resolution={256} frames={dynamic ? Infinity : 6} near={.1} far={32}>
        {(texture) => <mesh><icosahedronGeometry args={[.47, 5]} /><meshPhysicalMaterial envMap={texture} envMapIntensity={3.2} color="#c9e6e2" metalness={1} roughness={.028} clearcoat={1} clearcoatRoughness={.02} iridescence={.45} /></mesh>}
      </CubeCamera>
      <group ref={group}>
        <mesh rotation={[Math.PI / 2.35, .2, 0]}><torusKnotGeometry args={[.92, .025, 260, 24, 2, 5]} /><meshPhysicalMaterial color="#627781" metalness={.95} roughness={.11} clearcoat={.8} /></mesh>
        <mesh rotation={[-Math.PI / 2.7, -.22, 0]}><torusGeometry args={[1.24, .018, 12, 170]} /><meshBasicMaterial color={theme.secondary} transparent opacity={.54} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2.8, .3, .2]}><torusGeometry args={[1.48, .012, 12, 170]} /><meshBasicMaterial color={theme.accent} transparent opacity={.42} toneMapped={false} /></mesh>
      </group>
      <pointLight color={theme.accent} intensity={8 + theme.dataEnergy * 6} distance={7} decay={2.1} />
    </group>
  )
}

function Workstation({ node, position, theme, side, wood, metal, onActivate }: { node?: SpatialNode; position: Vec3; theme: Alpha5Theme; side: 'left' | 'right'; wood: THREE.Texture; metal: THREE.Texture; onActivate: () => void }) {
  const root = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const locked = node?.state === 'locked'
  const active = locked ? '#52616a' : side === 'left' ? theme.accent : theme.secondary
  useFrame((state, delta) => {
    if (root.current) {
      const s = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.06 : 1, 7, delta)
      root.current.scale.setScalar(s)
      root.current.position.y = THREE.MathUtils.damp(root.current.position.y, hovered ? .06 : 0, 7, delta)
    }
    if (halo.current) halo.current.rotation.z = state.clock.elapsedTime * (hovered ? .37 : .09)
  })
  return (
    <group ref={root} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onActivate() }}>
      <spotLight position={[0, 5.3, 1.6]} color={active} intensity={hovered ? 44 : locked ? 6 : 27} distance={10.5} angle={.46} penumbra={.92} castShadow />
      <RoundedBox args={[3.78, .34, 2.68]} radius={.2} smoothness={6} position={[0, .17, 0]} castShadow receiveShadow><meshPhysicalMaterial color="#071119" metalness={.86} roughness={.17} roughnessMap={metal} clearcoat={.7} /><Edges color={hovered ? active : '#2e4652'} threshold={20} /></RoundedBox>
      <group ref={halo} position={[0, .36, 0]} rotation={[-Math.PI / 2, 0, 0]}><mesh><ringGeometry args={[1.12, 1.47, 120]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .58 : locked ? .05 : .23} toneMapped={false} /></mesh><mesh><ringGeometry args={[1.7, 1.74, 120]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .88 : locked ? .04 : .4} toneMapped={false} /></mesh></group>
      <RoundedBox args={[3.1, .18, 1.63]} radius={.1} smoothness={6} position={[0, .94, 0]} castShadow><meshPhysicalMaterial map={wood} color={locked ? '#46494b' : '#715a43'} roughness={.25} metalness={.05} clearcoat={.68} /></RoundedBox>
      {[-1.33, 1.33].map((x) => <RoundedBox key={x} args={[.19, 1.32, 1.2]} radius={.06} smoothness={4} position={[x, .59, 0]} castShadow><meshStandardMaterial color="#1b2932" metalness={.84} roughness={.21} roughnessMap={metal} /></RoundedBox>)}
      <RoundedBox args={[2.22, 1.45, .15]} radius={.09} smoothness={6} position={[0, 1.78, -.42]} castShadow><meshPhysicalMaterial color="#03090d" metalness={.9} roughness={.1} clearcoat={1} /><Edges color={hovered ? active : '#36505d'} threshold={24} /></RoundedBox>
      <mesh position={[0, 1.78, -.33]}><planeGeometry args={[1.98, 1.2]} /><ShaderScreen color={active} seed={side === 'left' ? 17 : 29} glitch={locked ? .08 : hovered ? .95 : .5 + theme.dataEnergy * .12} scanSpeed={.9 + theme.particleSpeed * .22} intensity={locked ? .3 : 1.08 + theme.dataEnergy * .18} /></mesh>
      <RoundedBox args={[1.25, .065, .45]} radius={.04} smoothness={4} position={[-.38, 1.05, .37]} rotation={[-.08, 0, 0]}><meshPhysicalMaterial color="#111b22" metalness={.7} roughness={.22} clearcoat={.55} /></RoundedBox>
      {Array.from({ length: 9 }, (_, i) => <Glow key={i} position={[-.88 + i * .145, 1.09, .26]} scale={[.05, .006, .13]} color={i < 6 ? active : '#30404a'} power={i < 6 ? 1.4 : .1} />)}
      <Float speed={1.1} rotationIntensity={.018} floatIntensity={.07}><group position={[0, 2.82, -.14]}><RoundedBox args={[2.12, .46, .055]} radius={.085} smoothness={5}><MeshTransmissionMaterial transmission={1} thickness={.34} roughness={.055} chromaticAberration={.035} anisotropicBlur={.09} distortionScale={.22} temporalDistortion={.05} samples={3} resolution={128} color={active} /></RoundedBox><Edges color={active} threshold={18} /><group position={[0, 0, .07]}><Label className={locked ? 'muted workstation-label' : 'workstation-label'}>{node?.label || 'Workstation'}</Label></group></group></Float>
    </group>
  )
}

function evidencePosition(index: number): Vec3 {
  const col = index % 3
  const row = Math.floor(index / 3)
  return [-6.0 + (col - 1) * .78, 1.1 + row * .56, -1.45]
}

function EvidenceVault({ nodes, theme, onInspect }: { nodes: SpatialNode[]; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  return (
    <group>
      <RoundedBox args={[3.35, 4.9, .62]} radius={.2} smoothness={6} position={[-6.0, 2.47, -2.06]} castShadow><meshPhysicalMaterial color="#051018" metalness={.72} roughness={.15} clearcoat={.78} /><Edges color="#294651" threshold={22} /></RoundedBox>
      <RoundedBox args={[2.95, 4.18, .065]} radius={.085} smoothness={5} position={[-6.0, 2.47, -1.71]}><MeshTransmissionMaterial transmission={1} thickness={.4} roughness={.075} chromaticAberration={.045} anisotropicBlur={.14} distortionScale={.25} temporalDistortion={.05} samples={4} resolution={192} color={theme.accent} /></RoundedBox>
      {nodes.slice(0, 15).map((node, index) => <EvidenceUnit key={node.id} node={node} index={index} theme={theme} onInspect={onInspect} />)}
      <group position={[-6, 5.18, -1.68]}><Label className="zone-label">EVIDENCE VAULT / DEPTH-LINKED RECORDS</Label></group>
    </group>
  )
}

function EvidenceUnit({ node, index, theme, onInspect }: { node: SpatialNode; index: number; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  const root = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
  const color = verified ? theme.accent : theme.secondary
  const position = evidencePosition(index)
  useFrame((state, delta) => {
    if (!root.current) return
    const scale = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.2 : 1, 8, delta)
    root.current.scale.setScalar(scale)
    root.current.rotation.y = THREE.MathUtils.damp(root.current.rotation.y, hovered ? -.15 : Math.sin(state.clock.elapsedTime * .25 + index) * .025, 6, delta)
  })
  return (
    <group ref={root} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
      <RoundedBox args={[.63, .33, .18]} radius={.06} smoothness={5}><meshPhysicalMaterial color="#10222a" metalness={.45} roughness={.13} clearcoat={1} /><Edges color={color} threshold={20} /></RoundedBox>
      <mesh position={[0, 0, .106]}><planeGeometry args={[.47, .205]} /><ShaderScreen color={color} seed={index + 41} glitch={verified ? .14 : .48} scanSpeed={1.05 + theme.particleSpeed * .12} intensity={verified ? 1.55 : .82} /></mesh>
      <mesh position={[.24, .115, .137]}><sphereGeometry args={[.028, 20, 20]} /><meshBasicMaterial color={color} toneMapped={false} /></mesh>
    </group>
  )
}

function capabilityPosition(index: number, total: number): Vec3 {
  const ring = index % 2 === 0 ? 2.45 : 1.58
  const angle = (index / Math.max(1, total)) * Math.PI * 2 + (index % 2) * .28
  return [Math.cos(angle) * ring, 3.45 + Math.sin(index * 1.7) * .42, -5.95 + Math.sin(angle) * .78]
}

function CapabilityCore({ node, index, total, theme, onInspect }: { node: SpatialNode; index: number; total: number; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  const root = useRef<THREE.Group>(null)
  const ring = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  const color = level === 'verified_evidence' ? theme.accent : level === 'evidence' ? theme.secondary : level === 'signal' ? '#a7bbc8' : '#45535d'
  const radius = level === 'verified_evidence' ? .27 : level === 'evidence' ? .215 : level === 'signal' ? .18 : .14
  useFrame((state, delta) => {
    if (root.current) {
      const pulse = level === 'verified_evidence' ? 1 + Math.sin(state.clock.elapsedTime * 2.6 + index) * .045 : 1
      root.current.scale.setScalar(THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.28 : pulse, hovered ? 8 : 4, delta))
    }
    if (ring.current) ring.current.rotation.z += delta * (hovered ? 1.6 : level === 'verified_evidence' ? .6 : .25)
  })
  return (
    <Float speed={.8} rotationIntensity={.04} floatIntensity={.11}>
      <group ref={root} position={capabilityPosition(index, total)} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
        <mesh><sphereGeometry args={[radius, 56, 56]} /><meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={level === 'verified_evidence' ? 2.8 : level === 'evidence' ? .9 : .12} roughness={.07} metalness={.78} clearcoat={1} clearcoatRoughness={.03} iridescence={level === 'verified_evidence' ? 1 : .2} toneMapped={level !== 'verified_evidence'} /></mesh>
        <group ref={ring}><mesh rotation={[0, 0, Math.PI / 4]}><torusGeometry args={[radius * 1.8, .014, 10, 96]} /><meshBasicMaterial color={color} transparent opacity={hovered ? .9 : level === 'unobserved' ? .11 : .5} toneMapped={false} /></mesh><mesh rotation={[Math.PI / 2.7, 0, -Math.PI / 5]}><torusGeometry args={[radius * 2.18, .008, 10, 96]} /><meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? .52 : .12} toneMapped={false} /></mesh></group>
        <group position={[0, -radius * 2.6, 0]}><Label className="capability-label">{node.label}</Label></group>
      </group>
    </Float>
  )
}

function CapabilityDeck({ nodes, theme, onInspect }: { nodes: SpatialNode[]; theme: Alpha5Theme; onInspect: (node: SpatialNode) => void }) {
  return (
    <group>
      <mesh position={[0, 3.45, -6.0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[3.35, .022, 12, 170]} /><meshBasicMaterial color={theme.accent} transparent opacity={.14 + theme.dataEnergy * .04} toneMapped={false} /></mesh>
      <mesh position={[0, 3.45, -6.0]} rotation={[Math.PI / 2, 0, 0]} scale={[.67, .67, .67]}><torusGeometry args={[3.35, .014, 12, 170]} /><meshBasicMaterial color={theme.secondary} transparent opacity={.13 + theme.dataEnergy * .03} toneMapped={false} /></mesh>
      {nodes.slice(0, 10).map((node, index) => <CapabilityCore key={node.id} node={node} index={index} total={Math.min(10, nodes.length)} theme={theme} onInspect={onInspect} />)}
      <group position={[0, 5.68, -6.0]}><Label className="zone-label">GPGPU CAPABILITY FIELD / SERVER-ANCHORED</Label></group>
    </group>
  )
}

function TrajectoryRail({ nodes, theme }: { nodes: SpatialNode[]; theme: Alpha5Theme }) {
  const recent = nodes.slice(-30)
  const points = recent.map((_, index) => [-4.1 + index * .285, .44 + Math.sin(index * .61) * .075, 3.35 + Math.cos(index * .37) * .14] as Vec3)
  return (
    <group>
      <RoundedBox args={[8.7, .24, .84]} radius={.13} smoothness={5} position={[0, .18, 3.35]}><meshPhysicalMaterial color="#061018" metalness={.68} roughness={.19} clearcoat={.64} /><Edges color="#263f49" threshold={28} /></RoundedBox>
      {points.length > 1 && <Line points={points} color={theme.accent} lineWidth={1.1} transparent opacity={.28 + theme.dataEnergy * .05} />}
      {recent.map((node, index) => {
        const color = node.state === 'failure' ? theme.warning : node.state === 'success' ? theme.accent : '#6d8794'
        return <mesh key={node.id} position={points[index]}><sphereGeometry args={[node.state === 'failure' ? .09 : .057, 20, 20]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={node.state === 'success' ? 1.35 : .3} toneMapped={false} /></mesh>
      })}
      <group position={[0, .78, 3.35]}><Label className="trajectory-label">TRAJECTORY / IMMUTABLE SERVER EVENTS</Label></group>
    </group>
  )
}

function AwakeningSequence({ event, nodes, theme }: { event: Alpha5Event | null; nodes: SpatialNode[]; theme: Alpha5Theme }) {
  const root = useRef<THREE.Group>(null)
  if (event?.kind !== 'capability_awakened') return null
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const index = Math.max(0, capabilities.findIndex((node) => node.id === event.nodeId))
  const position = capabilityPosition(index, Math.max(1, capabilities.length))
  useFrame((state, delta) => {
    if (!root.current) return
    root.current.rotation.y += delta * .65
    root.current.rotation.z = Math.sin(state.clock.elapsedTime * .8) * .18
  })
  return (
    <group ref={root} position={position}>
      {[.62, 1.0, 1.45].map((radius, i) => <mesh key={radius} rotation={[Math.PI / (2.2 + i * .2), i * .3, 0]}><torusGeometry args={[radius, .018 - i * .003, 12, 120]} /><meshBasicMaterial color={i === 1 ? theme.secondary : theme.accent} transparent opacity={.64 - i * .12} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} /></mesh>)}
      <mesh><torusKnotGeometry args={[.39, .055, 180, 18, 3, 5]} /><meshPhysicalMaterial color={theme.accent} emissive={theme.accent} emissiveIntensity={5} metalness={.52} roughness={.045} iridescence={1} clearcoat={1} toneMapped={false} /></mesh>
      {Array.from({ length: 12 }, (_, i) => {
        const angle = i / 12 * Math.PI * 2
        return <mesh key={i} position={[Math.cos(angle) * 1.05, Math.sin(i * .9) * .25, Math.sin(angle) * 1.05]} rotation={[0, -angle, 0]}><boxGeometry args={[.035, .7 + (i % 3) * .2, .035]} /><meshBasicMaterial color={i % 2 ? theme.accent : theme.secondary} transparent opacity={.72} toneMapped={false} /></mesh>
      })}
      <pointLight color={theme.accent} intensity={34} distance={8} decay={2} />
      <Sparkles count={90} scale={[3.2, 3.2, 3.2]} size={4.2} speed={1.1} opacity={.95} color={theme.accent} noise={[1, 1, 1]} />
      <Html transform center distanceFactor={7} position={[0, 1.45, .2]} pointerEvents="none"><div className="presentation-event-label"><span>CAPABILITY AWAKENING</span><strong>{event.label}</strong><small>triggered by server verified_evidence</small></div></Html>
    </group>
  )
}

function VerificationBurst({ event, theme }: { event: Alpha5Event | null; theme: Alpha5Theme }) {
  const root = useRef<THREE.Group>(null)
  if (event?.kind !== 'evidence_verified') return null
  useFrame((state, delta) => {
    if (!root.current) return
    root.current.rotation.y += delta * .5
    root.current.scale.setScalar(.9 + Math.sin(state.clock.elapsedTime * 2.2) * .07)
  })
  return (
    <group ref={root} position={[-6.0, 2.5, -1.25]}>
      <mesh><icosahedronGeometry args={[.3, 2]} /><meshPhysicalMaterial color={theme.accent} emissive={theme.accent} emissiveIntensity={4.5} metalness={.5} roughness={.05} clearcoat={1} toneMapped={false} /></mesh>
      {[.52, .84, 1.18].map((radius, i) => <mesh key={radius} rotation={[Math.PI / 2, i * .25, i * .15]}><torusGeometry args={[radius, .015, 10, 100]} /><meshBasicMaterial color={i === 1 ? theme.secondary : theme.accent} transparent opacity={.6 - i * .1} toneMapped={false} /></mesh>)}
      <Sparkles count={48} scale={[2.5, 2.5, 2.5]} size={3.6} speed={.8} opacity={.9} color={theme.accent} />
      <pointLight color={theme.accent} intensity={24} distance={6} decay={2} />
    </group>
  )
}

function Scene(props: Props) {
  const { nodes, connections, focus, onFocus, onInspect } = props
  const surfaces = useSurfaces()
  const event = useAlpha5Event(nodes)
  const theme = resolveAlpha5Theme(nodes, focus, event)
  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const trajectory = nodes.filter((node) => node.kind === 'trajectory_event')
  const workStatus = String(workSample?.state || 'locked')
  const transitionKey = `${focus}:${theme.name}:${event?.id || workStatus}`

  return (
    <>
      <ThemeLightingDirector theme={theme} />
      <Architecture theme={theme} floor={surfaces.floor} metal={surfaces.metal} />
      <Reactor theme={theme} />

      <InstancedDataField nodes={nodes} theme={theme} />
      <GPGPUCapabilityNetwork capabilities={capabilities} theme={theme} />
      <EvidenceFlowField nodes={nodes} connections={connections} theme={theme} />

      <Workstation node={foundation} position={[-3.0, 0, -.68]} theme={theme} side="left" wood={surfaces.wood} metal={surfaces.metal} onActivate={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[3.0, 0, -.68]} theme={theme} side="right" wood={surfaces.wood} metal={surfaces.metal} onActivate={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />

      <EvidenceVault nodes={evidence} theme={theme} onInspect={onInspect} />
      <CapabilityDeck nodes={capabilities} theme={theme} onInspect={onInspect} />
      <TrajectoryRail nodes={trajectory} theme={theme} />
      <ArtifactAssembler status={workStatus} theme={theme} />

      <AwakeningSequence event={event} nodes={nodes} theme={theme} />
      <VerificationBurst event={event} theme={theme} />
      <DirectorSequencer focus={focus} event={event} nodes={nodes} />
      <RealtimePostPipeline theme={theme} transitionKey={transitionKey} />
    </>
  )
}

export function RealtimeCGWorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 7.2, 18.4], fov: 40, near: .1, far: 100 }}
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
