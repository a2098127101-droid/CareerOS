import {
  CameraControls,
  ContactShadows,
  Edges,
  Float,
  Html,
  Line,
  MeshReflectorMaterial,
  RoundedBox,
  Sparkles,
  useCursor,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, ChromaticAberration, DepthOfField, EffectComposer, Vignette } from '@react-three/postprocessing'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'
import { CinematicPresentation } from './CinematicPresentation'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

const C = {
  bg: '#03070b',
  panel: '#0b1218',
  steel: '#283743',
  cyan: '#75eee3',
  cyan2: '#3e9aa2',
  amber: '#f2bf78',
  green: '#7ce8b6',
  blue: '#74aee6',
  rose: '#df8b85',
  ivory: '#f0e8dc',
}

const capabilityColor: Record<string, string> = {
  unobserved: '#43505c',
  signal: '#a7b3bf',
  evidence: '#f0bd70',
  verified_evidence: '#7ef0bd',
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html transform center distanceFactor={8} pointerEvents="none"><div className={`scene-label ${className}`}>{children}</div></Html>
}

function makeTexture(kind: 'wood' | 'floor' | 'metal') {
  const canvas = document.createElement('canvas')
  canvas.width = kind === 'wood' ? 1024 : 768
  canvas.height = kind === 'wood' ? 256 : 768
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  if (kind === 'wood') {
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height)
    gradient.addColorStop(0, '#8d765c')
    gradient.addColorStop(.45, '#67513d')
    gradient.addColorStop(1, '#3f3024')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    for (let y = 2; y < canvas.height; y += 3) {
      ctx.strokeStyle = `rgba(25,14,7,${.02 + (y % 17) / 580})`
      ctx.beginPath()
      for (let x = -20; x < canvas.width + 20; x += 9) {
        const py = y + Math.sin(x * .019 + y * .052) * 2 + Math.sin(x * .006 + y * .12)
        if (x === -20) ctx.moveTo(x, py)
        else ctx.lineTo(x, py)
      }
      ctx.stroke()
    }
  } else {
    ctx.fillStyle = kind === 'floor' ? '#091017' : '#83878a'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < image.data.length; i += 4) {
      const noise = Math.random() * (kind === 'floor' ? 8 : 34)
      image.data[i] += noise
      image.data[i + 1] += noise
      image.data[i + 2] += noise
    }
    ctx.putImageData(image, 0, 0)
    if (kind === 'floor') {
      for (let p = 0; p <= canvas.width; p += 64) {
        ctx.strokeStyle = p % 256 === 0 ? 'rgba(112,235,226,.075)' : 'rgba(175,195,210,.032)'
        ctx.lineWidth = p % 256 === 0 ? 1.2 : .6
        ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, canvas.height); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(canvas.width, p); ctx.stroke()
      }
    } else {
      for (let y = 0; y < canvas.height; y += 2) {
        ctx.strokeStyle = `rgba(245,245,245,${.025 + Math.random() * .045})`
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke()
      }
    }
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(kind === 'wood' ? 2.4 : kind === 'floor' ? 4.6 : 2.2, kind === 'wood' ? 1 : kind === 'floor' ? 3.8 : 5.4)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 12
  return texture
}

function useTextures() {
  const value = useMemo(() => ({ wood: makeTexture('wood'), floor: makeTexture('floor'), metal: makeTexture('metal') }), [])
  useEffect(() => () => Object.values(value).forEach((texture) => texture.dispose()), [value])
  return value
}

function GlowBar({ position, scale, color, power = 1.6 }: { position: Vec3; scale: Vec3; color: string; power?: number }) {
  return <mesh position={position} scale={scale}><boxGeometry /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={power} toneMapped={false} /></mesh>
}

function Cable({ from, to }: { from: Vec3; to: Vec3 }) {
  const data = useMemo(() => {
    const start = new THREE.Vector3(...from)
    const end = new THREE.Vector3(...to)
    const direction = end.clone().sub(start)
    const length = direction.length()
    const midpoint = start.clone().add(end).multiplyScalar(.5)
    const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize())
    return { midpoint, length, quaternion }
  }, [from, to])
  return <mesh position={data.midpoint} quaternion={data.quaternion}><cylinderGeometry args={[.012, .012, data.length, 10]} /><meshStandardMaterial color="#53626d" metalness={.85} roughness={.24} /></mesh>
}

function Architecture({ floor, metal }: { floor: THREE.Texture; metal: THREE.Texture }) {
  const ringA = useRef<THREE.Group>(null)
  const ringB = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (ringA.current) ringA.current.rotation.z += delta * .035
    if (ringB.current) ringB.current.rotation.z = -state.clock.elapsedTime * .05
  })
  const cableStarts: Vec3[] = [[-4.4, 6.25, -1.4], [4.4, 6.25, -1.4], [-3.4, 6.25, 2.2], [3.4, 6.25, 2.2]]
  const cableEnds: Vec3[] = [[-2.85, 4.55, .1], [2.85, 4.55, .1], [-2.1, 4.55, 1.25], [2.1, 4.55, 1.25]]
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[25, 20]} />
        <MeshReflectorMaterial map={floor} color="#081017" roughness={.66} metalness={.3} blur={[360, 130]} mixBlur={1} mixStrength={20} mirror={.34} resolution={512} depthScale={.3} minDepthThreshold={.36} maxDepthThreshold={1.6} />
      </mesh>
      <RoundedBox args={[18, 7, .42]} radius={.2} smoothness={6} position={[0, 3.4, -7.18]} receiveShadow>
        <meshPhysicalMaterial color="#071017" metalness={.55} roughness={.38} roughnessMap={metal} clearcoat={.38} />
      </RoundedBox>
      <RoundedBox args={[14.8, 5.55, .08]} radius={.12} smoothness={6} position={[0, 3.25, -6.91]}>
        <meshPhysicalMaterial color="#0d1b23" metalness={.43} roughness={.18} clearcoat={.82} clearcoatRoughness={.1} />
      </RoundedBox>
      {Array.from({ length: 9 }, (_, i) => (
        <group key={i} position={[0, 6.3, -5.85 + i * 1.45]}>
          <RoundedBox args={[17.2, .13, .18]} radius={.045} smoothness={3}><meshStandardMaterial color="#27343d" metalness={.8} roughness={.23} roughnessMap={metal} /></RoundedBox>
          <GlowBar position={[0, -.085, .11]} scale={[12.7, .014, .022]} color={i % 3 === 0 ? C.amber : C.cyan} power={1.45} />
        </group>
      ))}
      {[-7.6, 7.6].map((x) => <RoundedBox key={x} args={[.2, 6.3, 15.4]} radius={.08} smoothness={4} position={[x, 3.15, 0]}><meshStandardMaterial color="#0b141b" metalness={.56} roughness={.48} /></RoundedBox>)}
      {cableStarts.map((from, index) => <Cable key={index} from={from} to={cableEnds[index]} />)}
      <group position={[0, 4.55, .6]} rotation={[Math.PI / 2, 0, 0]}>
        <group ref={ringA}><mesh><torusGeometry args={[3.75, .085, 18, 160]} /><meshPhysicalMaterial color="#1c2933" metalness={.84} roughness={.18} clearcoat={.62} /></mesh><mesh><torusGeometry args={[3.75, .018, 10, 160]} /><meshBasicMaterial color={C.cyan} transparent opacity={.58} toneMapped={false} /></mesh></group>
        <group ref={ringB}><mesh><torusGeometry args={[2.78, .05, 16, 144]} /><meshPhysicalMaterial color="#66503d" metalness={.48} roughness={.25} clearcoat={.52} /></mesh><mesh><torusGeometry args={[2.78, .012, 10, 144]} /><meshBasicMaterial color={C.amber} transparent opacity={.48} toneMapped={false} /></mesh></group>
      </group>
      {[-6.2, 6.2].map((x) => (
        <group key={x} position={[x, 2.1, 3.55]} rotation={[0, x < 0 ? .16 : -.16, 0]}>
          <RoundedBox args={[2.55, 3.18, .08]} radius={.065} smoothness={5}><meshPhysicalMaterial color="#172b34" metalness={.42} roughness={.08} transmission={.55} thickness={.38} transparent opacity={.22} clearcoat={1} /><Edges color="#4c7380" threshold={25} /></RoundedBox>
          <GlowBar position={[0, 0, .07]} scale={[.012, 2.52, .012]} color={x < 0 ? C.cyan : C.amber} power={1.05} />
        </group>
      ))}
      <ContactShadows position={[0, .012, .2]} opacity={.58} scale={20} blur={2.9} far={7} />
    </group>
  )
}

function Workstation({ node, position, accent, wood, metal, onActivate }: { node?: SpatialNode; position: Vec3; accent: string; wood: THREE.Texture; metal: THREE.Texture; onActivate: () => void }) {
  const root = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const locked = node?.state === 'locked'
  const active = locked ? '#53616b' : accent
  useFrame((state, delta) => {
    if (root.current) {
      const scale = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.045 : 1, 6.5, delta)
      root.current.scale.setScalar(scale)
      root.current.position.y = THREE.MathUtils.damp(root.current.position.y, hovered ? .045 : 0, 6, delta)
    }
    if (halo.current) halo.current.rotation.z = state.clock.elapsedTime * (hovered ? .22 : .07)
  })
  return (
    <group ref={root} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onActivate() }}>
      <spotLight position={[0, 4.8, 1.5]} color={active} intensity={hovered ? 38 : locked ? 6 : 24} distance={9.5} angle={.48} penumbra={.9} castShadow />
      <RoundedBox args={[3.62, .31, 2.52]} radius={.17} smoothness={6} position={[0, .15, 0]} castShadow receiveShadow><meshPhysicalMaterial color="#0d151b" metalness={.8} roughness={.2} roughnessMap={metal} clearcoat={.58} /><Edges color={hovered ? active : '#31414d'} threshold={20} /></RoundedBox>
      <group ref={halo} position={[0, .32, 0]} rotation={[-Math.PI / 2, 0, 0]}><mesh><ringGeometry args={[1.08, 1.38, 96]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .42 : locked ? .05 : .2} toneMapped={false} /></mesh><mesh><ringGeometry args={[1.58, 1.61, 96]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .75 : locked ? .04 : .34} toneMapped={false} /></mesh></group>
      <RoundedBox args={[3, .17, 1.55]} radius={.095} smoothness={6} position={[0, .9, 0]} castShadow><meshPhysicalMaterial map={wood} color={locked ? '#474a4b' : '#7c654f'} roughness={.3} metalness={.05} clearcoat={.58} /></RoundedBox>
      {[-1.29, 1.29].map((x) => <RoundedBox key={x} args={[.18, 1.28, 1.14]} radius={.055} smoothness={4} position={[x, .57, 0]} castShadow><meshStandardMaterial color="#202c35" metalness={.78} roughness={.24} roughnessMap={metal} /></RoundedBox>)}
      <RoundedBox args={[2.05, 1.31, .14]} radius={.085} smoothness={6} position={[0, 1.68, -.4]} castShadow><meshPhysicalMaterial color="#060c11" metalness={.84} roughness={.14} clearcoat={.9} /><Edges color={hovered ? active : '#3b4c58'} threshold={24} /></RoundedBox>
      <RoundedBox args={[1.82, 1.08, .035]} radius={.055} smoothness={5} position={[0, 1.68, -.326]}><meshPhysicalMaterial color="#061115" emissive={active} emissiveIntensity={locked ? .06 : hovered ? 1.15 : .62} roughness={.1} metalness={.36} clearcoat={1} /></RoundedBox>
      <Html transform center distanceFactor={6.4} position={[0, 1.68, -.285]} pointerEvents="none"><div className={`monitor-ui ${locked ? 'locked' : ''}`}><div className="monitor-ui-top"><span>STEPIN / CINEMATIC RUNTIME</span><b>{locked ? 'SERVER LOCKED' : 'LIVE SCENESTATE'}</b></div><div className="monitor-ui-scan"><i /><i /><i /><i /></div><strong>{node?.label || 'Workstation'}</strong><small>visuals consume state · authority remains server-side</small></div></Html>
      <RoundedBox args={[.14, .54, .14]} radius={.035} smoothness={4} position={[0, 1.02, -.4]}><meshStandardMaterial color="#2b3741" metalness={.84} roughness={.2} /></RoundedBox>
      <RoundedBox args={[1.22, .058, .43]} radius={.04} smoothness={4} position={[-.38, 1.025, .35]} rotation={[-.08, 0, 0]}><meshPhysicalMaterial color="#141d23" metalness={.62} roughness={.24} clearcoat={.46} /></RoundedBox>
      {Array.from({ length: 8 }, (_, i) => <GlowBar key={i} position={[-.82 + i * .14, 1.06, .235]} scale={[.048, .006, .13]} color={i < 5 ? active : '#35434e'} power={i < 5 ? 1.35 : .12} />)}
      <RoundedBox args={[.46, .046, .33]} radius={.045} smoothness={5} position={[.79, 1.015, .34]}><meshPhysicalMaterial color="#151e24" metalness={.46} roughness={.2} clearcoat={.78} /></RoundedBox>
      <Float speed={1} rotationIntensity={.02} floatIntensity={.06}><group position={[0, 2.6, -.18]}><RoundedBox args={[2, .45, .05]} radius={.08} smoothness={5}><meshPhysicalMaterial color="#12222b" transmission={.32} transparent opacity={.75} roughness={.05} metalness={.16} clearcoat={1} /><Edges color={active} threshold={18} /></RoundedBox><group position={[0, 0, .06]}><Label className={locked ? 'muted workstation-label' : 'workstation-label'}>{node?.label || 'Workstation'}</Label></group></group></Float>
    </group>
  )
}

function EvidenceVault({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-5.95, 0, -2.05]}>
      <RoundedBox args={[3.2, 4.55, .54]} radius={.18} smoothness={6} position={[0, 2.28, 0]} castShadow><meshPhysicalMaterial color="#091218" metalness={.62} roughness={.2} clearcoat={.6} /><Edges color="#2f414d" threshold={22} /></RoundedBox>
      <RoundedBox args={[2.8, 3.92, .07]} radius={.08} smoothness={5} position={[0, 2.3, .31]}><meshPhysicalMaterial color="#17313b" transmission={.48} transparent opacity={.23} roughness={.08} thickness={.25} clearcoat={1} /></RoundedBox>
      {Array.from({ length: 5 }, (_, i) => <group key={i} position={[0, .76 + i * .72, .44]}><RoundedBox args={[2.58, .07, .35]} radius={.025} smoothness={3}><meshStandardMaterial color="#35434d" metalness={.82} roughness={.2} /></RoundedBox><GlowBar position={[0, .04, .18]} scale={[2.2, .012, .016]} color={i === 4 ? C.green : C.amber} power={1} /></group>)}
      {nodes.slice(0, 15).map((node, index) => <EvidenceCapsule key={node.id} node={node} position={[-.84 + (index % 3) * .84, .95 + Math.floor(index / 3) * .72, .63]} onInspect={onInspect} />)}
      <group position={[0, 4.92, .31]}><Label className="zone-label">EVIDENCE VAULT · VERIFIED BY SERVER</Label></group>
    </group>
  )
}

function EvidenceCapsule({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
  const accent = verified ? C.green : C.amber
  useFrame((state, delta) => {
    if (!ref.current) return
    const scale = THREE.MathUtils.damp(ref.current.scale.x, hovered ? 1.16 : 1, 8, delta)
    ref.current.scale.setScalar(scale)
    ref.current.rotation.y = THREE.MathUtils.damp(ref.current.rotation.y, hovered ? -.12 : Math.sin(state.clock.elapsedTime * .22 + position[0]) * .015, 6, delta)
  })
  return (
    <Float speed={.85} rotationIntensity={.025} floatIntensity={.08}>
      <group ref={ref} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
        <RoundedBox args={[.66, .39, .18]} radius={.06} smoothness={5}><meshPhysicalMaterial color="#17242c" metalness={.44} roughness={.15} clearcoat={1} /><Edges color={accent} threshold={20} /></RoundedBox>
        <RoundedBox args={[.52, .27, .025]} radius={.028} smoothness={4} position={[0, 0, .108]}><meshStandardMaterial color={verified ? '#16372b' : '#3c2b1c'} emissive={accent} emissiveIntensity={hovered ? 1.35 : verified ? .8 : .25} toneMapped={false} /></RoundedBox>
        <mesh position={[.235, .125, .14]}><sphereGeometry args={[.028, 18, 18]} /><meshBasicMaterial color={accent} toneMapped={false} /></mesh>
      </group>
    </Float>
  )
}

function ProjectForge({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const ring = useRef<THREE.Group>(null)
  useFrame((_, delta) => { if (ring.current) ring.current.rotation.y += delta * .12 })
  const visible = nodes.slice(0, 10)
  return (
    <group position={[5.75, 0, -2.15]}>
      <mesh position={[0, .48, 0]} castShadow><cylinderGeometry args={[1.84, 2.04, .6, 72]} /><meshPhysicalMaterial color="#0d151b" metalness={.76} roughness={.18} clearcoat={.62} /></mesh>
      <mesh position={[0, .82, 0]}><cylinderGeometry args={[1.69, 1.69, .11, 72]} /><meshPhysicalMaterial color="#68513d" metalness={.18} roughness={.3} clearcoat={.58} /></mesh>
      <group ref={ring} position={[0, 1.04, 0]}><mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.27, .018, 12, 96]} /><meshBasicMaterial color={C.cyan} transparent opacity={.58} toneMapped={false} /></mesh><mesh rotation={[Math.PI / 2, 0, 0]} scale={[.74, .74, .74]}><torusGeometry args={[1.27, .012, 10, 96]} /><meshBasicMaterial color={C.amber} transparent opacity={.52} toneMapped={false} /></mesh></group>
      {visible.map((node, index) => <ArtifactPlate key={node.id} node={node} index={index} count={visible.length} onInspect={onInspect} />)}
      <group position={[0, 2.15, 0]}><Label className="zone-label">PROJECT FORGE · IMMUTABLE VERSIONS</Label></group>
    </group>
  )
}

function ArtifactPlate({ node, index, count, onInspect }: { node: SpatialNode; index: number; count: number; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const angle = (index / Math.max(1, count)) * Math.PI * 2
  const radius = .73 + (index % 2) * .3
  const accent = node.kind === 'artifact' ? C.amber : C.blue
  useFrame((state, delta) => {
    if (!ref.current) return
    const scale = THREE.MathUtils.damp(ref.current.scale.x, hovered ? 1.16 : 1, 7, delta)
    ref.current.scale.setScalar(scale)
    ref.current.position.y = 1.18 + (index % 3) * .12 + Math.sin(state.clock.elapsedTime * .9 + index) * .022 + (hovered ? .08 : 0)
  })
  return (
    <group ref={ref} position={[Math.cos(angle) * radius, 1.18 + (index % 3) * .12, Math.sin(angle) * radius]} rotation={[0, -angle + Math.PI / 2, 0]} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
      <RoundedBox args={[.61, .065, .9]} radius={.04} smoothness={4}><meshPhysicalMaterial color={node.kind === 'artifact' ? '#92795a' : '#526f8b'} metalness={.34} roughness={.22} clearcoat={.82} /><Edges color={accent} threshold={22} /></RoundedBox>
      <GlowBar position={[0, .045, -.3]} scale={[.38, .009, .018]} color={accent} power={hovered ? 2.3 : 1.15} />
    </group>
  )
}

function capabilityLocal(index: number): Vec3 {
  const ring = index < 5 ? 0 : 1
  const local = index % 5
  const angle = (local / 5) * Math.PI * 2 - Math.PI / 2 + ring * .22
  return [Math.cos(angle) * (ring ? 3.25 : 2.1), Math.sin(angle) * (ring ? 1.55 : 1.05), 0]
}

function CapabilityField({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const frame = useRef<THREE.Group>(null)
  useFrame((state) => { if (frame.current) frame.current.rotation.z = Math.sin(state.clock.elapsedTime * .14) * .012 })
  return (
    <group ref={frame} position={[0, 3.28, -6.38]}>
      <mesh><torusGeometry args={[3.85, .025, 12, 160]} /><meshBasicMaterial color={C.cyan} transparent opacity={.16} toneMapped={false} /></mesh>
      <mesh><torusGeometry args={[2.48, .014, 12, 160]} /><meshBasicMaterial color={C.amber} transparent opacity={.18} toneMapped={false} /></mesh>
      {nodes.slice(0, 10).map((node, index) => <CapabilityOrb key={node.id} node={node} position={capabilityLocal(index)} onInspect={onInspect} />)}
      <Sparkles count={56} scale={[8, 3.9, 1.2]} size={2.2} speed={.12} opacity={.35} color={C.cyan} noise={[1, 1, .25]} />
      <group position={[0, 2.25, 0]}><Label className="zone-label">CAPABILITY CONSTELLATION · SERVER AUTHORITY</Label></group>
    </group>
  )
}

function CapabilityOrb({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const root = useRef<THREE.Group>(null)
  const ring = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  const color = capabilityColor[level] || capabilityColor.unobserved
  const radius = level === 'verified_evidence' ? .25 : level === 'evidence' ? .215 : level === 'signal' ? .18 : .145
  useFrame((state, delta) => {
    if (root.current) {
      const pulse = level === 'verified_evidence' ? 1 + Math.sin(state.clock.elapsedTime * 2.15 + position[0]) * .03 : 1
      const scale = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.24 : pulse, hovered ? 8 : 4, delta)
      root.current.scale.setScalar(scale)
    }
    if (ring.current) ring.current.rotation.z += delta * (hovered ? 1.25 : .24)
  })
  return (
    <Float speed={.72} rotationIntensity={.035} floatIntensity={.11}>
      <group ref={root} position={position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
        <mesh><sphereGeometry args={[radius, 56, 56]} /><meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={level === 'verified_evidence' ? hovered ? 4 : 2.6 : level === 'evidence' ? 1.35 : .22} roughness={.1} metalness={.42} clearcoat={1} clearcoatRoughness={.05} iridescence={level === 'verified_evidence' ? 1 : .18} iridescenceIOR={1.3} toneMapped={level !== 'unobserved'} /></mesh>
        <mesh ref={ring} rotation={[0, 0, Math.PI / 4]}><torusGeometry args={[radius * 1.65, .015, 10, 80]} /><meshBasicMaterial color={color} transparent opacity={hovered ? .82 : level === 'unobserved' ? .1 : .5} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2.7, 0, -Math.PI / 5]}><torusGeometry args={[radius * 2, .008, 10, 80]} /><meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? .46 : .12} toneMapped={false} /></mesh>
        <group position={[0, -radius * 2.4, 0]}><Label className="capability-label">{node.label}</Label></group>
      </group>
    </Float>
  )
}

function TrajectoryRibbon({ nodes }: { nodes: SpatialNode[] }) {
  const recent = nodes.slice(-24)
  const points = recent.map((_, index) => [index * .34, Math.sin(index * .72) * .07, Math.cos(index * .42) * .14] as Vec3)
  return (
    <group position={[-3.95, .34, 3.08]}>
      <RoundedBox args={[8.08, .22, .76]} radius={.12} smoothness={5} position={[3.95, -.16, 0]}><meshPhysicalMaterial color="#0b141b" metalness={.56} roughness={.22} clearcoat={.52} /><Edges color="#273843" threshold={28} /></RoundedBox>
      {points.length > 1 && <Line points={points} color={C.cyan} lineWidth={1.15} transparent opacity={.36} />}
      {recent.map((node, index) => { const color = node.state === 'failure' ? C.rose : node.state === 'success' ? C.green : '#7b8d9c'; return <Float key={node.id} speed={.68} rotationIntensity={0} floatIntensity={.04}><mesh position={points[index]}><sphereGeometry args={[node.state === 'failure' ? .092 : .06, 24, 24]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={node.state === 'success' ? 1.5 : .48} toneMapped={false} /></mesh></Float> })}
      <group position={[4, .3, 0]}><Label className="trajectory-label">TRAJECTORY · IMMUTABLE EVENT LEDGER</Label></group>
    </group>
  )
}

function semanticPositions(nodes: SpatialNode[]) {
  const map = new Map<string, Vec3>()
  nodes.filter((node) => node.kind === 'evidence').slice(0, 15).forEach((node, index) => map.set(node.id, [-5.95 - .84 + (index % 3) * .84, .95 + Math.floor(index / 3) * .72, -1.42]))
  const forge = nodes.filter((node) => node.kind === 'project' || node.kind === 'artifact').slice(0, 10)
  forge.forEach((node, index) => { const angle = (index / Math.max(1, forge.length)) * Math.PI * 2; const radius = .73 + (index % 2) * .3; map.set(node.id, [5.75 + Math.cos(angle) * radius, 1.18 + (index % 3) * .12, -2.15 + Math.sin(angle) * radius]) })
  nodes.filter((node) => node.kind === 'capability').slice(0, 10).forEach((node, index) => { const p = capabilityLocal(index); map.set(node.id, [p[0], 3.28 + p[1], -6.38]) })
  return map
}

function SemanticBeam({ from, to, relation, phase }: { from: Vec3; to: Vec3; relation: string; phase: number }) {
  const pulse = useRef<THREE.Mesh>(null)
  const color = relation === 'supports' ? C.amber : C.cyan
  const curve = useMemo(() => {
    const start = new THREE.Vector3(...from)
    const end = new THREE.Vector3(...to)
    const middle = start.clone().lerp(end, .5)
    middle.y = Math.max(start.y, end.y) + .78 + Math.abs(end.x - start.x) * .038
    return new THREE.QuadraticBezierCurve3(start, middle, end)
  }, [from, to])
  const points = useMemo(() => curve.getPoints(36), [curve])
  useFrame((state) => { if (pulse.current) pulse.current.position.copy(curve.getPoint((state.clock.elapsedTime * .13 + phase) % 1)) })
  return <group><Line points={points} color={color} lineWidth={2.8} transparent opacity={.05} /><Line points={points} color={color} lineWidth={.7} transparent opacity={.3} /><mesh ref={pulse}><sphereGeometry args={[.035, 18, 18]} /><meshBasicMaterial color={color} toneMapped={false} /></mesh></group>
}

function SemanticLinks({ nodes, connections }: { nodes: SpatialNode[]; connections: SpatialConnection[] }) {
  const positions = useMemo(() => semanticPositions(nodes), [nodes])
  const links = useMemo(() => connections.filter((link) => positions.has(link.from) && positions.has(link.to)).slice(0, 24), [connections, positions])
  return <group>{links.map((link, index) => <SemanticBeam key={link.id} from={positions.get(link.from)!} to={positions.get(link.to)!} relation={link.relation} phase={(index * .137) % 1} />)}</group>
}

function CoreMonolith() {
  const a = useRef<THREE.Group>(null)
  const b = useRef<THREE.Group>(null)
  useFrame((_, delta) => { if (a.current) a.current.rotation.y += delta * .1; if (b.current) b.current.rotation.y -= delta * .16 })
  return (
    <group position={[0, 2.3, .72]}>
      <group ref={a}><mesh rotation={[Math.PI / 2.6, 0, 0]}><torusGeometry args={[.69, .02, 12, 112]} /><meshBasicMaterial color={C.cyan} transparent opacity={.58} toneMapped={false} /></mesh><mesh rotation={[-Math.PI / 2.9, .35, 0]}><torusGeometry args={[.96, .012, 12, 112]} /><meshBasicMaterial color={C.amber} transparent opacity={.44} toneMapped={false} /></mesh></group>
      <group ref={b}><mesh><icosahedronGeometry args={[.31, 3]} /><meshPhysicalMaterial color="#cce8e4" emissive={C.cyan} emissiveIntensity={2.2} metalness={.46} roughness={.09} clearcoat={1} iridescence={1} toneMapped={false} /></mesh></group>
      <pointLight color={C.cyan} intensity={10} distance={5.2} decay={2.2} />
    </group>
  )
}

function Atmosphere() {
  return <group><Sparkles count={130} scale={[18, 6.8, 14]} size={1.6} speed={.12} opacity={.28} color="#9bd6cf" noise={[1, .35, 1]} /><Sparkles count={52} scale={[13, 5, 11]} size={2.4} speed={.08} opacity={.19} color="#ddb47c" noise={[1, .45, 1]} /><fogExp2 attach="fog" args={[C.bg, .029]} /></group>
}

function Scene({ nodes, connections, focus, onFocus, onInspect }: Props) {
  const controls = useRef<CameraControls>(null)
  const textures = useTextures()
  useEffect(() => {
    if (!controls.current) return
    if (focus === 'foundation') controls.current.setLookAt(-3.8, 2.95, 5.25, -2.85, 1.45, -.5, true)
    else if (focus === 'work-sample') controls.current.setLookAt(3.8, 2.95, 5.25, 2.85, 1.45, -.5, true)
    else controls.current.setLookAt(0, 5.15, 12.35, 0, 1.95, -1.98, true)
  }, [focus])
  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const projects = nodes.filter((node) => node.kind === 'project' || node.kind === 'artifact')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const trajectory = nodes.filter((node) => node.kind === 'trajectory_event')
  return (
    <>
      <color attach="background" args={[C.bg]} />
      <Atmosphere />
      <ambientLight intensity={.38} color="#91a8ba" />
      <hemisphereLight args={['#91a9bc', '#1a110c', .72]} />
      <directionalLight position={[5, 9, 5.8]} intensity={2.45} color="#e5f0f4" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-.00025} />
      <spotLight position={[-6.2, 7.2, 3.5]} intensity={15} color="#8ae4dc" distance={16} angle={.44} penumbra={.9} />
      <spotLight position={[6.2, 6.8, 2.7]} intensity={13} color="#e5af70" distance={15} angle={.42} penumbra={.88} />
      <Architecture floor={textures.floor} metal={textures.metal} />
      <CoreMonolith />
      <Workstation node={foundation} position={[-2.85, 0, -.68]} accent={C.cyan} wood={textures.wood} metal={textures.metal} onActivate={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[2.85, 0, -.68]} accent={C.amber} wood={textures.wood} metal={textures.metal} onActivate={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />
      <EvidenceVault nodes={evidence} onInspect={onInspect} />
      <ProjectForge nodes={projects} onInspect={onInspect} />
      <CapabilityField nodes={capabilities} onInspect={onInspect} />
      <TrajectoryRibbon nodes={trajectory} />
      <SemanticLinks nodes={nodes} connections={connections} />
      <CinematicPresentation nodes={nodes} focus={focus} />
      <CameraControls ref={controls} enabled={false} smoothTime={.82} />
    </>
  )
}

function PostFX({ focus }: { focus: Focus }) {
  return (
    <EffectComposer multisampling={4}>
      <DepthOfField focusDistance={focus === 'hub' ? .028 : .018} focalLength={focus === 'hub' ? .028 : .045} bokehScale={focus === 'hub' ? 1.15 : 2.15} height={480} />
      <Bloom intensity={1.14} luminanceThreshold={.9} luminanceSmoothing={.22} mipmapBlur />
      <ChromaticAberration offset={[.00034, .00052]} />
      <Vignette eskil={false} offset={.12} darkness={.8} />
    </EffectComposer>
  )
}

export function CinematicWorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 7.8, 18.5], fov: 41, near: .1, far: 95 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.18
        gl.outputColorSpace = THREE.SRGBColorSpace
        gl.shadowMap.type = THREE.PCFSoftShadowMap
        scene.background = new THREE.Color(C.bg)
      }}
      frameloop="always"
    >
      <Scene {...props} />
      <PostFX focus={props.focus} />
    </Canvas>
  )
}
